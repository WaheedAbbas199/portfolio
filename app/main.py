
"""FastAPI application: JSON API + public site + admin SPA, all on ONE origin (so admin cookies are SameSite=Strict and need no CORS).

Vercel finds the app through the top-level `app = FastAPI(...)` below (entrypoint `app.main:app`, also pinned in pyproject.toml).
On Vercel the files in `public/` are served by the CDN, so they are NOT mounted here; locally they are mounted so `uvicorn app.main:app` works.
"""

import html
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dependencies import Container, get_container, get_db
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger, request_id_var
from app.core.security import DbLimiter, SlidingLimiter
from app.db.base import Base
from app.db.session import make_engine, make_session_factory
from app.services import chat_service, content_service, email_service, media_service
from app.services.seed import seed_defaults

log = get_logger(__name__)
ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR, ADMIN_DIR, TEMPLATE_DIR = ROOT / "public", ROOT / "admin", ROOT / "app" / "templates"

CSP_PUBLIC = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; font-src 'self'; "
    "media-src 'self'; frame-src 'self'; object-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'; worker-src 'self' blob:"
)
CSP_ADMIN = CSP_PUBLIC.replace("frame-src 'self'; ", "").replace("frame-ancestors 'self'", "frame-ancestors 'none'").replace("object-src 'self'", "object-src 'none'")
DEFAULT_SEO = {"title": "Portfolio", "description": "", "keywords": "", "og_image_id": None}


def build_container(settings: Settings, *, llm=None, email="auto", create_tables: bool = False) -> Container:
    engine = make_engine(settings)

    if create_tables:
        import app.models  # noqa: F401

        Base.metadata.create_all(engine)

    factory = make_session_factory(engine)

    if settings.effective_rate_limit_backend == "db":

        def make(n, w, m):
            return DbLimiter(factory, n, w, m)

    else:

        def make(n, w, m):
            return SlidingLimiter(n, w, m)

    return Container(
        settings=settings,
        engine=engine,
        session_factory=factory,
        llm=llm or chat_service.build_llm(settings),
        email=email_service.build_provider(settings) if email == "auto" else email,
        login_limiter=make(settings.login_max_attempts, settings.login_window_seconds, "Too many failed login attempts. Try again later."),
        chat_limiter=make(settings.chat_rate_per_minute, 60, "You're sending messages too quickly. Please wait a moment."),
        contact_limiter=make(settings.contact_rate_per_hour, 3600, "Too many messages from this connection. Please try again later."),
    )


def _render_index(session: Session | None, settings: Settings) -> str:
    try:
        seo = content_service.get_group(session, "seo") if session is not None else dict(DEFAULT_SEO)
        img = content_service.media_url(session, seo.get("og_image_id")) if session is not None else None
    except Exception:
        log.warning("index rendered without database SEO settings")
        seo, img = dict(DEFAULT_SEO), None

    base, e = settings.effective_site_url, html.escape
    google_verification = settings.google_site_verification.strip()

    meta = [
        f"<title>{e(seo['title'])}</title>",
        f'<meta name="description" content="{e(seo["description"])}">',
        f'<meta name="keywords" content="{e(seo["keywords"])}">',
        f'<link rel="canonical" href="{e(base)}/">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:title" content="{e(seo["title"])}">',
        f'<meta property="og:description" content="{e(seo["description"])}">',
        f'<meta property="og:url" content="{e(base)}/">',
        '<meta name="twitter:card" content="summary_large_image">',
    ]
    if google_verification:
        meta.append(
        f'<meta name="google-site-verification" content="{e(google_verification)}">'
    )

    if img:
        meta.append(f'<meta property="og:image" content="{e(base + img)}">')

    template = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    return re.sub(r"<!--SEO_META-->", "\n  ".join(meta), template)


def _make_lifespan(container: Container, settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            with container.session_factory() as s:
                seed_defaults(s)
        except Exception as exc:
            log.error("startup initialisation skipped: %s (run `alembic upgrade head`?)", type(exc).__name__)

        log.info(
            "startup complete (env=%s, vercel=%s, ai=%s, email=%s, rate_limit=%s)",
            settings.app_env,
            settings.on_vercel,
            container.llm.name,
            settings.email_provider if container.email else "off",
            settings.effective_rate_limit_backend,
        )
        yield

    return lifespan


def _fastapi_kwargs(settings: Settings, lifespan) -> dict:
    dev = not settings.is_production
    return dict(
        title="Waheed Abbas Portfolio API",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/api/v1/docs" if dev else None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json" if dev else None,
    )


def install(app: FastAPI, settings: Settings, container: Container) -> FastAPI:
    """Attach middleware, error handlers, routes and static serving to a FastAPI instance."""
    app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "If-None-Match"],
    )

    @app.middleware("http")
    async def context_and_headers(request: Request, call_next):
        rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex[:16]
        tok = request_id_var.set(rid)

        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(tok)

        path = request.url.path
        admin_path = path.startswith(("/admin", "/api/v1/admin"))

        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=(self)"

        if not path.startswith("/api/v1/docs") and "content-security-policy" not in response.headers:
            response.headers["Content-Security-Policy"] = CSP_ADMIN if admin_path else CSP_PUBLIC

        response.headers["X-Frame-Options"] = "DENY" if admin_path else "SAMEORIGIN"

        if admin_path:
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"

        if settings.cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

    def envelope(status: int, code: str, message: str, details=None) -> JSONResponse:
        body = {
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id_var.get(),
            }
        }
        return JSONResponse(status_code=status, content=body)

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return envelope(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [
            {
                "field": ".".join(str(p) for p in e["loc"] if p != "body"),
                "message": e["msg"],
            }
            for e in exc.errors()
        ]
        return envelope(422, "validation_failed", "Please check the highlighted fields.", details)

    @app.exception_handler(ValidationError)
    async def _model_validation(_: Request, exc: ValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return envelope(422, "validation_failed", "Please check the highlighted fields.", details)

    @app.exception_handler(DBAPIError)
    async def _db_error(_: Request, exc: DBAPIError):
        log.error("database error: %s", type(exc).__name__)
        return envelope(
            503,
            "database_unavailable",
            "The database is temporarily unavailable. Please retry in a moment.",
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return envelope(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error: %s", type(exc).__name__)
        return envelope(500, "internal_error", "Something went wrong on the server.")

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/media/{stored_name}", include_in_schema=False)
    def media(stored_name: str, db: Session = Depends(get_db)):
        asset = media_service.get_by_stored_name(db, stored_name)
        disposition = "inline" if asset.mime.startswith("image/") or asset.mime == "application/pdf" else "attachment"

        return Response(
            asset.data,
            media_type=asset.mime,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "Content-Disposition": f'{disposition}; filename="{asset.original_name}"',
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox",
            },
        )

    @app.get("/robots.txt", include_in_schema=False)
    def robots(c: Container = Depends(get_container)):
        return PlainTextResponse(
            f"User-agent: *\nDisallow: /admin\nDisallow: /api/v1/admin\nSitemap: {c.settings.effective_site_url}/sitemap.xml\n"
        )

    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap(c: Container = Depends(get_container)):
        loc = html.escape(c.settings.effective_site_url)
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<url><loc>{loc}/</loc></url></urlset>"
        )
        return Response(xml, media_type="application/xml")

    @app.get("/", include_in_schema=False)
    def index(request: Request, c: Container = Depends(get_container)):
        
        
        try:
            with c.session_factory() as s:
                body = _render_index(s, c.settings)
        except Exception:
            body = _render_index(None, c.settings)

        return HTMLResponse(body, headers={"Cache-Control": "public, max-age=0, must-revalidate"})

    @app.get("/admin", include_in_schema=False)
    def admin_index():
        return FileResponse(ADMIN_DIR / "index.html")

    app.mount("/admin/", StaticFiles(directory=ADMIN_DIR, html=True), name="admin")

    if not settings.on_vercel:
        app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")

    return app


def create_app(settings: Settings | None = None, *, container: Container | None = None) -> FastAPI:
    """Application factory (tests and tooling). Production uses the module-level `app` below."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)
    container = container or build_container(settings)

    return install(
        FastAPI(**_fastapi_kwargs(settings, _make_lifespan(container, settings))),
        settings,
        container,
    )


# ----------------------------------------------------------------------------------------------------------------------------
# Module-level application: the entrypoint Vercel (and `uvicorn app.main:app`) loads.
# If configuration is invalid, the app still boots and answers requests with a clear 503.
# ----------------------------------------------------------------------------------------------------------------------------

_boot_error: str | None = None
_settings: Settings | None = None
_container: Container | None = None

try:
    # On Vercel, use environment variables only. Do not load the local .env file.
    _settings = Settings(_env_file=None) if os.getenv("VERCEL") == "1" else get_settings()

    configure_logging(_settings.log_level, _settings.log_json)
    _container = build_container(_settings)

except Exception as exc:
    if isinstance(exc, ValidationError):
        _boot_error = "; ".join(
            f"{'.'.join(map(str, e['loc'])) or 'settings'}: {e['msg']}"
            for e in exc.errors()
        )
    else:
        _boot_error = f"{type(exc).__name__}: {exc}"


_lifespan = _make_lifespan(_container, _settings) if _container is not None else None

app = FastAPI(
    **_fastapi_kwargs(
        _settings or Settings.model_construct(app_env="production", vercel_env="production"),
        _lifespan,
    )
)

if _boot_error is None:
    install(app, _settings, _container)

else:
    _message = f"Server configuration error: {_boot_error}"
    log.error(_message)

    @app.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def _misconfigured(path: str):
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "server_misconfigured",
                    "message": _message,
                    "details": None,
                    "request_id": None,
                }
            },
        )

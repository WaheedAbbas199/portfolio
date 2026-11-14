from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import Settings


def make_engine(settings: Settings) -> Engine:
    url = make_url(settings.database_url)
    if url.get_backend_name() == "sqlite":
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in settings.database_url or settings.database_url in ("sqlite://", "sqlite:///"):
            kwargs["poolclass"] = StaticPool
        engine = create_engine(settings.database_url, **kwargs)

        @event.listens_for(engine, "connect")
        def _fk_pragma(dbapi_conn, _):  # enforce referential integrity on SQLite
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return engine

    # Managed PostgreSQL (Neon etc.): TLS is mandatory off-localhost.
    local = (url.host or "") in ("", "localhost", "127.0.0.1", "::1")
    if not local and "sslmode" not in url.query:
        url = url.update_query_dict({"sslmode": "require"})
    kwargs = {"pool_pre_ping": True, "connect_args": {"connect_timeout": 10}}
    if settings.on_vercel:
        # Serverless: every invocation may be a fresh process, so do not keep a client-side pool.
        # Use the provider's *pooled* connection string (e.g. Neon "-pooler" host) so connections are reused server-side.
        kwargs["poolclass"] = NullPool
    else:
        kwargs.update(pool_size=5, max_overflow=5, pool_recycle=300)
    return create_engine(url, **kwargs)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()

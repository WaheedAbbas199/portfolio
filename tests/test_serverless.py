"""Behaviour that only matters on a serverless host: settings detection, shared rate limits, proxy IPs, ETag freshness, inline email."""

import os
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.exceptions import RateLimited
from app.core.security import DbLimiter
from app.db.session import make_engine
from app.main import build_container, create_app
from tests.conftest import PASSWORD, FakeEmail, PNG, make_settings

A, P = "/api/v1/admin", "/api/v1/public"
NEON = "postgres://user:pw@ep-cool-123-pooler.eu-central-1.aws.neon.tech/neondb"


# ------------------------------- settings / engine -------------------------------
def test_vercel_environment_is_detected_and_hardened():
    s = Settings(_env_file=None, vercel="1", vercel_env="production", database_url=NEON, secret_key="k" * 40, vercel_project_production_url="me.vercel.app")
    assert s.on_vercel and s.is_production and s.cookie_secure and s.email_inline and s.trust_proxy
    assert s.effective_rate_limit_backend == "db" and s.effective_site_url == "https://me.vercel.app"
    assert s.database_url.startswith("postgresql+psycopg2://")


def test_local_defaults_stay_simple():
    s = Settings(_env_file=None)
    assert not s.on_vercel and not s.cookie_secure and not s.email_inline and not s.trust_proxy
    assert s.effective_rate_limit_backend == "memory" and s.effective_site_url == "http://localhost:8000"


def test_sqlite_and_weak_secret_are_rejected_on_vercel():
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(_env_file=None, vercel="1", database_url="sqlite:///./x.db", secret_key="k" * 40)
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(_env_file=None, vercel="1", vercel_env="production", database_url=NEON)


def test_postgres_engine_is_serverless_friendly_and_forces_tls():
    from sqlalchemy.pool import NullPool

    e = make_engine(Settings(_env_file=None, vercel="1", database_url=NEON, secret_key="k" * 40))
    assert isinstance(e.pool, NullPool) and "sslmode=require" in str(e.url.render_as_string(hide_password=False))
    local = make_engine(Settings(_env_file=None, database_url="postgresql://u:p@localhost/db"))
    assert "sslmode" not in str(local.url) and not isinstance(local.pool, NullPool)


def test_provider_urls_are_normalised():
    assert Settings(_env_file=None, database_url="postgresql://a:b@h/db").database_url == "postgresql+psycopg2://a:b@h/db"


# ------------------------------- shared (DB) rate limiter -------------------------------
def test_db_limiter_blocks_resets_and_stores_only_hashes(container):
    lim = DbLimiter(container.session_factory, 2, 60)
    lim.check_and_hit("1.2.3.4|a@b.co")
    lim.check_and_hit("1.2.3.4|a@b.co")
    with pytest.raises(RateLimited):
        lim.check_and_hit("1.2.3.4|a@b.co")
    lim.check_and_hit("other-key")  # separate bucket
    from app.models import RateLimitEvent

    with container.session_factory() as s:
        keys = {r.key for r in s.query(RateLimitEvent)}
    assert all(len(k) == 64 and "1.2.3.4" not in k and "@" not in k for k in keys)
    lim.reset("1.2.3.4|a@b.co")
    lim.check_and_hit("1.2.3.4|a@b.co")


def test_db_limiter_window_expires(container):
    lim = DbLimiter(container.session_factory, 1, 1)
    lim.check_and_hit("k")
    with pytest.raises(RateLimited):
        lim.check("k")
    time.sleep(1.2)
    lim.check("k")


def test_two_app_instances_share_login_limits_through_the_database(llm, email):
    """Simulates two serverless instances: a lockout earned on one is enforced on the other."""
    from app.db.base import Base

    s = make_settings(rate_limit_backend="db", login_max_attempts=3)
    c1 = build_container(s, llm=llm, email=email)
    Base.metadata.drop_all(c1.engine)
    Base.metadata.create_all(c1.engine)
    from app.core.security import hash_password
    from app.models import AdminUser

    with c1.session_factory() as db:
        db.add(AdminUser(email="owner@example.com", password_hash=hash_password(PASSWORD)))
        db.commit()
    c2 = build_container(s, llm=llm, email=email)
    c2.engine, c2.session_factory = c1.engine, c1.session_factory
    c2.login_limiter = DbLimiter(c1.session_factory, 3, s.login_window_seconds)
    a1, a2 = create_app(s, container=c1), create_app(s, container=c2)
    bad = {"email": "owner@example.com", "password": "wrong-password-1"}
    with TestClient(a1) as t1, TestClient(a2) as t2:
        for _ in range(3):
            assert t1.post(f"{A}/auth/login", json=bad).status_code == 401
        assert t2.post(f"{A}/auth/login", json={"email": "owner@example.com", "password": PASSWORD}).status_code == 429
    if "TEST_DATABASE_URL" in os.environ:
        Base.metadata.drop_all(c1.engine)


# ------------------------------- client IP behind a proxy -------------------------------
def _chat_client(app, container, trust):
    from app.core.security import SlidingLimiter

    container.settings.trust_proxy_headers = trust
    container.chat_limiter = SlidingLimiter(1, 60)
    return TestClient(app)


def test_forwarded_ip_is_used_only_when_a_trusted_proxy_sets_it(app, container):
    q = {"message": "What skills does he have?"}
    with _chat_client(app, container, "true") as tc:
        assert tc.post(f"{P}/chat", json=q, headers={"x-forwarded-for": "203.0.113.5"}).status_code == 200
        assert tc.post(f"{P}/chat", json=q, headers={"x-forwarded-for": "203.0.113.6"}).status_code == 200  # different visitor, own bucket
        assert tc.post(f"{P}/chat", json=q, headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1"}).status_code == 429
        assert tc.post(f"{P}/chat", json=q, headers={"x-forwarded-for": "not-an-ip"}).status_code in (200, 429)  # garbage falls back safely
    with _chat_client(app, container, "false") as tc:  # untrusted: a spoofed header must NOT create a fresh bucket
        assert tc.post(f"{P}/chat", json=q, headers={"x-forwarded-for": "198.51.100.1"}).status_code == 200
        assert tc.post(f"{P}/chat", json=q, headers={"x-forwarded-for": "198.51.100.2"}).status_code == 429


# ------------------------------- live CMS -> public sync (ETag) -------------------------------
def test_etag_revalidation_and_instant_freshness_after_admin_changes(admin, client):
    r1 = client.get(f"{P}/site")
    etag = r1.headers["etag"]
    assert r1.status_code == 200 and "max-age=0" in r1.headers["cache-control"] and "must-revalidate" in r1.headers["cache-control"]
    r2 = client.get(f"{P}/site", headers={"If-None-Match": etag})
    assert r2.status_code == 304 and r2.content == b""

    def changed(action) -> str:
        action()
        r = client.get(f"{P}/site", headers={"If-None-Match": changes[-1]})
        assert r.status_code == 200, "old ETag must no longer match after an admin change"
        changes.append(r.headers["etag"])
        return r.text

    changes = [etag]
    body = changed(lambda: admin.post(f"{A}/projects", json={"slug": "live-one", "title": "Live One", "published": True}, headers=admin.h))
    assert "Live One" in body
    pid = next(p["id"] for p in admin.get(f"{A}/projects").json() if p["slug"] == "live-one")
    assert "Live One" not in changed(lambda: admin.post(f"{A}/projects/{pid}/publish?published=false", headers=admin.h))
    hero = admin.get(f"{A}/settings").json()["hero"]
    assert "Brand New Headline" in changed(lambda: admin.put(f"{A}/settings/hero", json={**hero, "headline": "Brand New Headline"}, headers=admin.h))
    sid = admin.post(f"{A}/skills", json={"category": "Tools", "name": "Zig"}, headers=admin.h).json()["id"]
    changes[-1] = client.get(f"{P}/site").headers["etag"]
    assert "Zig" not in changed(lambda: admin.delete(f"{A}/skills/{sid}", headers=admin.h))
    changed(lambda: admin.post(f"{A}/media", files={"file": ("a.png", PNG, "image/png")}, headers=admin.h))


def test_project_detail_also_revalidates(admin, client):
    admin.post(f"{A}/projects", json={"slug": "detail-x", "title": "Detail X", "published": True, "problem": "P1"}, headers=admin.h)
    r = client.get(f"{P}/projects/detail-x")
    assert r.status_code == 200 and client.get(f"{P}/projects/detail-x", headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    pid = next(p["id"] for p in admin.get(f"{A}/projects").json() if p["slug"] == "detail-x")
    admin.put(f"{A}/projects/{pid}", json={"slug": "detail-x", "title": "Detail X", "published": True, "problem": "P2"}, headers=admin.h)
    assert client.get(f"{P}/projects/detail-x", headers={"If-None-Match": r.headers["etag"]}).json()["problem"] == "P2"


def test_media_urls_are_immutable_cacheable(admin, client):
    url = admin.post(f"{A}/media", files={"file": ("a.png", PNG, "image/png")}, headers=admin.h).json()["url"]
    assert "immutable" in client.get(url).headers["cache-control"]


# ------------------------------- inline email (serverless) -------------------------------
MSG = {"name": "Ada", "email": "ada@example.com", "category": "Job opportunity", "subject": "Role", "message": "We would like to talk about a role.", "elapsed_ms": 9000}


@pytest.mark.parametrize("fail,expected", [(False, "sent"), (True, "failed")])
def test_inline_mode_sends_before_replying_and_reports_the_truth(llm, fail, expected):
    from app.db.base import Base
    from app.core.security import hash_password  # noqa: F401

    s = make_settings(email_send_mode="inline")
    em = FakeEmail(fail=fail)
    c = build_container(s, llm=llm, email=em)
    Base.metadata.drop_all(c.engine)
    Base.metadata.create_all(c.engine)
    with TestClient(create_app(s, container=c)) as tc:
        r = tc.post(f"{P}/contact", json=MSG)
    assert r.status_code == 201 and r.json()["notification"] == expected
    assert len(em.sent) == (0 if fail else 1)
    from app.models import ContactMessage

    with c.session_factory() as db:
        assert db.query(ContactMessage).one().email_status.value == expected  # message kept either way
    if "TEST_DATABASE_URL" in os.environ:
        Base.metadata.drop_all(c.engine)


# ------------------------------- seeding & resilience -------------------------------
def test_starter_content_is_created_once_and_deleted_content_never_returns(app, admin):
    skills = admin.get(f"{A}/skills").json()
    assert skills  # seeded on first start
    for sk in skills:
        assert admin.delete(f"{A}/skills/{sk['id']}", headers=admin.h).status_code == 204
    with TestClient(app) as fresh:  # a new "cold start" runs the lifespan (seeding) again
        fresh.get("/api/v1/health")
    assert admin.get(f"{A}/skills").json() == []


def test_internal_marker_row_is_never_exposed(admin, client):
    assert "_meta" not in admin.get(f"{A}/settings").json() and "_meta" not in client.get(f"{P}/site").text


def test_database_outage_gives_a_clear_503_and_the_page_shell_still_loads(client, monkeypatch):
    from app.services import content_service

    def boom(*a, **k):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(content_service, "content_version", boom)
    r = client.get(f"{P}/site")
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable" and "connection refused" not in r.text
    monkeypatch.setattr(content_service, "get_group", boom)
    home = client.get("/")
    assert home.status_code == 200 and "<title>Portfolio</title>" in home.text


def test_vercel_mode_does_not_mount_public_dir_but_keeps_admin(llm, email):
    s = Settings(_env_file=None, vercel="1", vercel_env="preview", database_url="postgresql://u:p@localhost:5432/x", secret_key="k" * 40)
    names = {getattr(r, "name", None) for r in create_app(s, container=build_container(s, llm=llm, email=email)).routes}
    assert "admin" in names and "public" not in names


def _import_main(env: dict) -> str:
    code = "import json,app.main as m; from fastapi.testclient import TestClient; r=TestClient(m.app).get('/'); print(json.dumps([m._boot_error, r.status_code, r.text]))"
    clean = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "SECRET_KEY", "VERCEL", "VERCEL_ENV", "APP_ENV", "TEST_DATABASE_URL")}
    out = subprocess.run([sys.executable, "-c", code], env={**clean, **env}, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-500:]
    return out.stdout.strip().splitlines()[-1]


def test_misconfigured_production_boots_and_explains_itself_instead_of_crashing():
    import json

    err, status, body = json.loads(_import_main({"VERCEL": "1", "VERCEL_ENV": "production", "DATABASE_URL": "postgresql://u:p@localhost/db"}))
    assert "SECRET_KEY" in err and status == 503 and "server_misconfigured" in body and "SECRET_KEY" in body
    err2, status2, _ = json.loads(_import_main({"VERCEL": "1", "DATABASE_URL": "sqlite:///./x.db", "SECRET_KEY": "k" * 40}))
    assert "PostgreSQL" in err2 and status2 == 503


def test_valid_production_config_imports_cleanly():
    import json

    err, status, _ = json.loads(_import_main({"APP_ENV": "production", "SECRET_KEY": "s" * 48, "DATABASE_URL": "sqlite:///./data/_probe.db"}))
    assert err is None and status in (200, 500)

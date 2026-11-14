"""Static checks that guard the Vercel deployment contract (entrypoint, routing, dependencies, no stray static index)."""

import ast
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_app_main_exposes_a_top_level_fastapi_instance_for_vercel():
    tree = ast.parse((ROOT / "app" / "main.py").read_text())
    assigns = [n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "app" for t in n.targets)]
    assert assigns, "app/main.py must assign a module-level variable named `app`"
    call = assigns[-1].value
    assert isinstance(call, ast.Call) and getattr(call.func, "id", "") == "FastAPI", "`app` must be created with FastAPI(...) so Vercel can detect it"


def test_imported_app_is_a_fastapi_instance_with_all_routes():
    from fastapi import FastAPI

    from app.main import app

    assert isinstance(app, FastAPI)
    paths = {getattr(r, "path", "") for r in app.routes} | set(app.openapi()["paths"])
    assert {"/", "/admin", "/media/{stored_name}", "/robots.txt", "/sitemap.xml"} <= paths
    assert {"/api/v1/public/site", "/api/v1/public/contact", "/api/v1/public/chat", "/api/v1/admin/auth/login", "/api/v1/admin/projects"} <= paths


def test_entrypoint_is_pinned_and_not_a_test_module():
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert cfg["tool"]["vercel"]["entrypoint"] == "app.main:app"
    assert "conftest" not in json.dumps(cfg["tool"]) and "conftest" not in (ROOT / "vercel.json").read_text()


def test_vercel_json_is_valid_and_keeps_what_the_function_needs():
    cfg = json.loads((ROOT / "vercel.json").read_text())
    assert "app/main.py" in cfg["functions"] and (ROOT / "app/main.py").exists()
    exclude = cfg["functions"]["app/main.py"]["excludeFiles"]
    for needed in ("app/", "admin/", "public/"):
        assert needed not in exclude, f"{needed} must stay in the function bundle"
    assert "rewrites" not in cfg and "routes" not in cfg, "no custom routing: FastAPI handles /admin, /api, /media, /robots.txt, /sitemap.xml"
    assert "outputDirectory" not in cfg and "buildCommand" not in cfg


def test_no_static_index_shadows_the_function_route():
    # A file public/index.html would be served by the CDN at "/" and bypass SEO injection + security headers.
    assert not (ROOT / "public" / "index.html").exists() and (ROOT / "app" / "templates" / "index.html").exists()


def test_old_static_deploy_artifacts_are_gone():
    assert not (ROOT / "vercel-site").exists() and not (ROOT / "scripts" / "export_static.py").exists() and not (ROOT / "public" / "data").exists()


def test_requirements_txt_matches_pyproject_dependencies():
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    lines = [ln.strip() for ln in (ROOT / "requirements.txt").read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    assert sorted(lines) == sorted(deps)


def test_env_example_lists_every_variable_the_code_reads_and_no_secrets():
    from app.core.config import Settings

    text = (ROOT / ".env.example").read_text()
    documented = {ln.split("=")[0].strip().lstrip("# ").upper() for ln in text.splitlines() if "=" in ln}
    must = {n.upper() for n in Settings.model_fields if n not in {"vercel", "vercel_env", "vercel_project_production_url"}}
    assert not (must - documented), f"missing from .env.example: {sorted(must - documented)}"
    for line in text.splitlines():
        if line.startswith(("GEMINI_API_KEY=", "RESEND_API_KEY=", "SMTP_PASSWORD=")):
            assert line.split("=", 1)[1].strip() == ""
    assert "vercel.app" not in text.lower()

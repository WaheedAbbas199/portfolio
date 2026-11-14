# Waheed Abbas — AI Portfolio (3D, dark/light, admin CMS, chatbot, contact email)

Public portfolio with a **3D animated background (three.js)**, 3D tilt cards, page transitions, hover effects and a **dark/light toggle in the header**,
plus a private **admin dashboard**, a **Gemini chatbot grounded in published content (text + voice)** and a **contact form with email notifications**.

Stack: FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL (SQLite for local) · Gemini · vanilla HTML/CSS/JS · three.js (vendored) · pytest + node:test · Docker.

> **Deploying?** Go straight to [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): the ready-to-deploy folder is **`vercel-site/`** (Root Directory on Vercel). It shows your portfolio even without a backend.
> The original repository could not be accessed while building this, so its code was not merged; see [docs/MIGRATION_FROM_EXISTING_SITE.md](docs/MIGRATION_FROM_EXISTING_SITE.md).

## Run locally (Windows PowerShell)
```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env            # put a random value in SECRET_KEY
alembic upgrade head
python -m scripts.create_admin --email you@example.com      # prompts for a 12+ char password
uvicorn app.main:app --reload
```
* Site: http://localhost:8000 · Admin: http://localhost:8000/admin · API docs (dev only): http://localhost:8000/api/v1/docs
* First start seeds editable starter content (skills, projects, education, certification, settings).
* Tests: `pytest` (backend, 73 tests) and `npm install && npm test` (frontend, 21 tests incl. admin, public boot and static-host deploy). Lint: `ruff check .`

## Where things are
| Need | Where |
|---|---|
| Change text, links, theme defaults, animations, SEO | Admin → Website content / Design & animation |
| Add/edit/reorder/publish projects | Admin → Projects (drafts are private; chatbot only learns published content) |
| Upload profile image / project thumbnails / CV PDF | Admin → Media library, then select it in the relevant form |
| Read contact messages, retry failed emails | Admin → Messages |
| Turn the chatbot on/off, suggested questions | Admin → Chatbot |

## Docs
[Architecture](docs/ARCHITECTURE.md) · [Security](docs/SECURITY.md) · [Deployment](docs/DEPLOYMENT.md) · [Email setup](docs/EMAIL_SETUP.md) ·
[Admin guide](docs/ADMIN_GUIDE.md) · [Migration from existing site](docs/MIGRATION_FROM_EXISTING_SITE.md) · [Implementation report & limitations](docs/IMPLEMENTATION_REPORT.md)

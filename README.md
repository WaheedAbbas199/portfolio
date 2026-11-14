# Waheed Abbas | AI Engineer Portfolio

<p align="center">
  <strong>A Modern, Interactive & Production-Oriented AI Engineering Portfolio</strong>
</p>

<p align="center">
  A full-stack portfolio platform featuring immersive 3D visuals, an AI-powered conversational assistant, dynamic content management, and a responsive user experience.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-Database-4169E1?logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Google-Gemini-8E75B2?logo=googlegemini" alt="Gemini">
  <img src="https://img.shields.io/badge/Three.js-3D%20Graphics-black?logo=threedotjs" alt="Three.js">
  <img src="https://img.shields.io/badge/Testing-pytest%20%7C%20node:test-green" alt="Testing">
</p>

---

## 1. Project Overview

**Waheed Abbas AI Portfolio** is a full-stack web application designed to showcase my professional journey, technical expertise, AI engineering projects, and development capabilities.

The platform combines an interactive 3D frontend with a secure backend, an AI-powered chatbot, and a private content management system.

Unlike a traditional static portfolio, this application provides an interactive experience where visitors can explore projects, discover technical skills, communicate with an AI assistant, and contact me directly.

The platform also includes an administrative dashboard that allows website content to be managed without modifying source code.

### Project Goals

- Showcase AI engineering and software development expertise.
- Deliver an immersive and modern user experience.
- Provide AI-powered interaction using Google Gemini.
- Manage portfolio content through a private admin dashboard.
- Enable direct communication through an email-enabled contact system.
- Maintain a modular, testable, and deployment-ready architecture.

---

## 2. Key Features

### Interactive Frontend Experience

- Immersive 3D animated background powered by Three.js.
- Interactive 3D tilt effects on portfolio cards.
- Smooth page transitions and animations.
- Modern hover effects and micro-interactions.
- Responsive layouts for desktop, tablet, and mobile.
- Dynamic dark and light themes.
- Theme persistence across visits.
- Modern UI with performance-conscious animations.

### AI-Powered Portfolio Chatbot

- Integrated Google Gemini AI.
- Answers questions about my professional background.
- Retrieves information from published portfolio content.
- Grounded responses based on available portfolio information.
- Text-based conversational interaction.
- Voice input and output capabilities.
- Suggested questions for visitors.
- Chatbot enable/disable controls through the admin dashboard.
- Draft and unpublished content is excluded from chatbot knowledge.

### Private Admin Dashboard

A dedicated administrative interface for managing the complete portfolio.

**Content Management**
- Edit personal information and professional introduction.
- Manage technical skills and expertise.
- Add, edit, delete, reorder, and publish projects.
- Manage education and certifications.
- Update social links and website settings.
- Manage SEO and website metadata.

**Design Management**
- Configure theme defaults.
- Manage animation and design settings.
- Update website appearance and content.

**Media Library**
- Upload profile images.
- Manage project thumbnails.
- Upload and manage CV/resume PDF files.
- Select uploaded media for relevant portfolio sections.

**Message Management**
- View contact form submissions.
- Manage incoming messages.
- Retry failed email notifications.

**Chatbot Management**
- Enable or disable the AI chatbot.
- Manage suggested questions.
- Control chatbot-related settings.

### Contact & Email Notifications

- Functional contact form.
- Backend request validation.
- Email notifications for incoming messages.
- Error handling for failed email delivery.
- Admin-side message management.
- Retry support for failed notifications.

### Backend & Database

- FastAPI-based backend.
- SQLAlchemy 2 ORM.
- PostgreSQL for production.
- SQLite for local development.
- Alembic database migrations.
- Structured API endpoints.
- Environment-based configuration.
- Authentication and authorization for administrative functionality.

---

## 3. Technology Stack

| Category | Technologies |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| 3D Graphics | Three.js |
| AI Integration | Google Gemini |
| ORM | SQLAlchemy 2 |
| Database | PostgreSQL, SQLite |
| Migrations | Alembic |
| Authentication | Backend authentication system |
| Testing | pytest, node:test |
| Frontend Testing | jsdom |
| Code Quality | Ruff |
| Deployment | Vercel, Docker |
| Version Control | Git, GitHub |

---

## 4. System Architecture

The application follows a modular full-stack architecture.

```text
                  VISITORS
                     |
                     v
             PUBLIC PORTFOLIO
                     |
       +-------------+-------------+
       |             |             |
       v             v             v
   Frontend      AI Chatbot    Contact Form
       |             |             |
       +-------------+-------------+
                     |
                     v
                FASTAPI
                     |
       +-------------+-------------+
       |             |             |
       v             v             v
   API Layer    AI Integration   Email Service
       |
       v
  SQLALCHEMY ORM
       |
       v
  POSTGRESQL / SQLITE
       |
       v
  CONTENT & APPLICATION DATA


             ADMIN DASHBOARD
                    |
                    v
              FASTAPI APIs
                    |
                    v
          CONTENT MANAGEMENT
                    |
          +---------+---------+
          |         |         |
          v         v         v
       Projects  Settings   Media
          |
          v
    PUBLISHED CONTENT
          |
          v
     CHATBOT KNOWLEDGE
```

**Architecture principle:** Public visitors access published portfolio content, while authorized administrators manage content through a separate protected dashboard.

---

## 5. Project Structure

```text
waheed-portfolio/
│
├── app/
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── auth/
│   └── ...
│
├── admin/
│   └── Admin dashboard files
│
├── public/
│   └── Public website assets
│
├── data/
│   └── Application data
│
├── alembic/
│   └── Database migrations
│
├── scripts/
│   └── Utility and management scripts
│
├── tests/
│   ├── Backend tests
│   └── Frontend tests
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── SECURITY.md
│   ├── DEPLOYMENT.md
│   ├── EMAIL_SETUP.md
│   ├── ADMIN_GUIDE.md
│   ├── MIGRATION_FROM_EXISTING_SITE.md
│   └── IMPLEMENTATION_REPORT.md
│
├── vercel-site/
│   └── Static deployment-ready website
│
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── package.json
├── README.md
└── ...
```

*Note: The structure above is a logical overview. Refer to the actual repository for the complete file structure.*

---

## 6. Installation & Local Development

### Prerequisites

Install the following tools before starting:

- Python 3.11 or newer (compatible with the project configuration).
- Git.
- Node.js and npm.
- PostgreSQL (optional for local development; SQLite is supported).
- Google Gemini API credentials for AI functionality.

### Step 1: Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/waheed-portfolio.git
```

```bash
cd waheed-portfolio
```

### Step 2: Create Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```powershell
pip install -e ".[dev]"
```

### Step 4: Configure Environment Variables

Create your environment file:

```powershell
Copy-Item .env.example .env
```

Configure the required values in `.env`.

Example configuration (use the actual variable names from `.env.example`):

```env
SECRET_KEY=replace_with_a_long_random_secret
DATABASE_URL=sqlite:///./portfolio.db

GEMINI_API_KEY=your_gemini_api_key

# Configure email credentials according to EMAIL_SETUP.md
```

**Security:** Never commit `.env`, API keys, database passwords, or other secrets to GitHub.

### Step 5: Run Database Migrations

```powershell
alembic upgrade head
```

### Step 6: Create Admin Account

```powershell
python -m scripts.create_admin --email you@example.com
```

The script prompts for an administrator password. Use a strong password of at least 12 characters.

### Step 7: Start Development Server

```powershell
uvicorn app.main:app --reload
```

### Step 8: Open Application

| Application | URL |
|---|---|
| Public Portfolio | http://localhost:8000 |
| Admin Dashboard | http://localhost:8000/admin |
| API Documentation | http://localhost:8000/api/v1/docs |

API documentation is intended for development use and should be restricted or disabled in production according to the deployment configuration.

---

## 7. Testing & Quality Assurance

Testing is an important part of maintaining application reliability.

The project includes backend and frontend automated tests.

### Backend Tests

Framework: pytest

Run:

```bash
pytest -v
```

### Frontend Tests

Framework: node:test with jsdom.

Install dependencies:

```bash
npm install
```

Run:

```bash
npm test
```

### Code Quality

Run Ruff:

```bash
ruff check .
```

### Current Test Coverage Report

The implementation's original reported test results:

| Test Suite | Reported Tests |
|---|---:|
| Backend | 73 |
| Frontend | 21 |
| Total | 94 |

These are reported test counts, not a claim of 100% code coverage or a guarantee of production reliability. Re-run the suites after changes to verify the current results.

---

## 8. Deployment

The project provides a dedicated static deployment option for Vercel.

### Vercel Deployment

**Deployment directory: `vercel-site/`**

Steps:

1. Push the repository to GitHub.
2. Open Vercel.
3. Import the GitHub repository.
4. Set the Root Directory to `vercel-site/`.
5. Configure the appropriate build settings as documented.
6. Deploy the application.

The static portfolio is designed to display without requiring the FastAPI backend.

**Important:** The static deployment does not automatically provide backend-dependent functionality such as authenticated admin operations, database-backed content management, Gemini API integration, or email processing. These require the appropriate backend services and configuration.

### Docker Deployment

The project also includes Docker-related configuration.

Refer to the repository's Dockerfile and deployment documentation for the correct build and runtime commands.

### Full Deployment Documentation

See:

`docs/DEPLOYMENT.md`

---

## 9. Documentation

Detailed technical documentation is maintained separately.

| Document | Purpose |
|---|---|
| `docs/ARCHITECTURE.md` | System architecture and technical design |
| `docs/SECURITY.md` | Security implementation and considerations |
| `docs/DEPLOYMENT.md` | Deployment instructions |
| `docs/EMAIL_SETUP.md` | Email configuration |
| `docs/ADMIN_GUIDE.md` | Admin dashboard usage |
| `docs/MIGRATION_FROM_EXISTING_SITE.md` | Existing website migration notes |
| `docs/IMPLEMENTATION_REPORT.md` | Implementation report and known limitations |

---

## 10. Security Considerations

Security is an important consideration for a public-facing portfolio with administrative functionality.

The application includes security-related mechanisms such as:

- Protected administrative functionality.
- Environment-based secret configuration.
- Server-side validation.
- Controlled database access.
- Separation of public and administrative functionality.
- Configuration-based origin validation.

Before production deployment, verify:

- HTTPS is enabled.
- Strong administrator credentials are configured.
- Secret keys and API credentials are stored securely.
- Debug mode is disabled.
- Database backups are configured.
- Administrative endpoints are protected.
- Rate limiting and abuse protection are configured where required.
- Email and chatbot endpoints have appropriate safeguards.

See `docs/SECURITY.md` for implementation details and limitations.

---

## 11. Future Improvements

Potential future enhancements include:

- Advanced AI agent capabilities.
- Retrieval evaluation and chatbot quality monitoring.
- Advanced analytics dashboard.
- Improved voice conversation experience.
- Portfolio visitor analytics.
- More advanced SEO optimization.
- Performance monitoring and observability.
- Automated CI/CD pipelines.
- Expanded integration testing.
- Enhanced accessibility.

These are future improvement opportunities, not claims that these features are already implemented.

---

## 12. Project Status

**Project:** Waheed Abbas AI Portfolio

**Type:** Full-Stack Web Application

**Focus Areas:** AI Engineering, Interactive Web Development, Backend Engineering, and Automation.

**Development Approach:** Modular architecture, automated testing, documentation, and deployment preparation.

For the current implementation status, refer to:

`docs/IMPLEMENTATION_REPORT.md`

---

## 13. Author

**Waheed Abbas**

AI Engineer | Machine Learning | Deep Learning | Agentic AI | AI Automation | Full-Stack Development

I am passionate about building intelligent applications and practical AI-powered solutions that solve real-world problems.

**Connect with me:**

- GitHub: https://github.com/WaheedAbbas199
- LinkedIn: linkedin.com/in/waheed-abbas-415b03327
- Portfolio: YOUR_DEPLOYED_WEBSITE_URL
- Email: waheedabbass2211@gmail.com

---

## 14. License

Add an appropriate license before distributing or allowing reuse of this project.

---

<p align="center">
  <strong>Building Intelligent Solutions. Turning Ideas into Real-World Products.</strong>
</p>

<p align="center">
  Thank you for visiting my portfolio repository!
</p>
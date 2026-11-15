from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE = {"", "CHANGE_ME_TO_A_LONG_RANDOM_VALUE", "changeme", "secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    # Set automatically by Vercel (VERCEL=1, VERCEL_ENV=production|preview|development, VERCEL_PROJECT_PRODUCTION_URL=host).
    vercel: str = ""
    vercel_env: str = ""
    vercel_project_production_url: str = ""
    log_level: str = "INFO"
    log_json: bool = True
    database_url: str = "sqlite:///./data/portfolio.db"

    secret_key: str = "CHANGE_ME_TO_A_LONG_RANDOM_VALUE"
    session_hours: int = 8
    public_origins: str = "http://localhost:8000"
    site_url: str = ""  # empty -> derived from Vercel (https://<production url>) or http://localhost:8000
    google_site_verification: str = ""
    login_max_attempts: int = 5
    login_window_seconds: int = 600

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    llm_timeout_seconds: int = 20
    llm_max_retries: int = 0
    chat_rate_per_minute: int = 12
    chat_max_message_chars: int = 800

    email_provider: Literal["disabled", "resend", "smtp"] = "disabled"
    resend_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    email_from: str = "Portfolio <onboarding@resend.dev>"
    notify_email: str = ""
    contact_rate_per_hour: int = 5

    # Serverless-aware behaviour. "auto" picks the right thing for the platform (see properties below).
    rate_limit_backend: Literal["auto", "memory", "db"] = "auto"
    email_send_mode: Literal["auto", "inline", "background"] = "auto"
    trust_proxy_headers: Literal["auto", "true", "false"] = "auto"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.public_origins.split(",") if o.strip()]

    @property
    def on_vercel(self) -> bool:
        return bool(self.vercel)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production" or self.vercel_env == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.is_production or self.on_vercel  # Vercel always serves HTTPS

    @property
    def effective_site_url(self) -> str:
        if self.site_url:
            return self.site_url.rstrip("/")
        if self.vercel_project_production_url:
            return "https://" + self.vercel_project_production_url.removeprefix("https://").rstrip("/")
        return "http://localhost:8000"

    @property
    def effective_rate_limit_backend(self) -> str:
        """Serverless instances don't share memory, so production uses the database for rate limits."""
        if self.rate_limit_backend != "auto":
            return self.rate_limit_backend
        return "db" if (self.is_production or self.on_vercel) else "memory"

    @property
    def email_inline(self) -> bool:
        """Serverless functions may be frozen right after the response, so email is sent before replying."""
        if self.email_send_mode != "auto":
            return self.email_send_mode == "inline"
        return self.on_vercel

    @property
    def trust_proxy(self) -> bool:
        """Only trust X-Forwarded-For when a known proxy (Vercel) sets it; otherwise clients could spoof their IP."""
        if self.trust_proxy_headers != "auto":
            return self.trust_proxy_headers == "true"
        return self.on_vercel

    @property
    def llm_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def email_configured(self) -> bool:
        if self.email_provider == "resend":
            return bool(self.resend_api_key and self.notify_email)
        if self.email_provider == "smtp":
            return bool(self.smtp_host and self.notify_email)
        return False

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        return normalize_database_url(v)

    @model_validator(mode="after")
    def _prod(self) -> "Settings":
        if self.on_vercel and self.database_url.startswith("sqlite"):
            raise ValueError("DATABASE_URL must be a managed PostgreSQL URL on Vercel (SQLite files are not persistent there)")
        if self.is_production:
            if self.secret_key in INSECURE or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be random and >= 32 chars in production")
            if "*" in self.origins:
                raise ValueError("PUBLIC_ORIGINS must not contain '*' in production")
        return self


def normalize_database_url(v: str) -> str:
    """Accept the URLs providers hand out (postgres://, postgresql://) and make them SQLAlchemy/psycopg2 URLs."""
    v = v.strip()
    for prefix in ("postgres://", "postgresql://"):
        if v.startswith(prefix):
            return "postgresql+psycopg2://" + v[len(prefix) :]
    return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


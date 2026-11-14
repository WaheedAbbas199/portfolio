"""Password hashing, cookie sessions (JWT) with CSRF binding, login rate limiter."""

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import Settings
from app.core.exceptions import AuthenticationFailed, RateLimited

ALGO = "HS256"
SESSION_COOKIE = "pf_session"
CSRF_COOKIE = "pf_csrf"


def hash_password(password: str) -> str:
    data = password.encode()
    if len(data) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return bcrypt.hashpw(data, bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def validate_password_strength(pw: str) -> None:
    if len(pw) < 12:
        raise ValueError("Password must be at least 12 characters")
    if pw.lower() == pw or pw.upper() == pw or not any(c.isdigit() for c in pw):
        raise ValueError("Password needs upper case, lower case and a digit")


def new_session_token(settings: Settings, admin_id: str) -> tuple[str, str]:
    """Returns (jwt, csrf). The CSRF value is embedded in the signed token and also handed to the SPA."""
    csrf = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": admin_id,
            "csrf": csrf,
            "iss": "pf",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=settings.session_hours)).timestamp()),
        },
        settings.secret_key,
        algorithm=ALGO,
    )
    return token, csrf


def decode_session(settings: Settings, token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGO], issuer="pf", options={"require": ["exp", "sub", "iss", "csrf"]})
    except jwt.PyJWTError as exc:
        raise AuthenticationFailed("Session is invalid or expired") from exc


def csrf_matches(claim: str, header: str | None) -> bool:
    return bool(header) and hmac.compare_digest(claim, header)


class SlidingLimiter:
    """In-memory sliding window (per process). Documented limitation: use Redis when running several workers."""

    def __init__(self, max_hits: int, window_seconds: int, message: str = "Too many requests. Please try again later."):
        self.max_hits, self.window, self.message = max_hits, window_seconds, message
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def check(self, key: str) -> None:
        with self._lock:
            if len(self._prune(key, time.monotonic())) >= self.max_hits:
                raise RateLimited(self.message)

    def hit(self, key: str) -> None:
        with self._lock:
            self._prune(key, time.monotonic()).append(time.monotonic())

    def check_and_hit(self, key: str) -> None:
        with self._lock:
            q = self._prune(key, time.monotonic())
            if len(q) >= self.max_hits:
                raise RateLimited(self.message)
            q.append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


class DbLimiter:
    """Sliding-window limiter backed by the database so ALL serverless instances see the same counters.
    Same interface as SlidingLimiter. Keys are hashed before storage (no IPs or emails at rest)."""

    def __init__(self, session_factory, max_hits: int, window_seconds: int, message: str = "Too many requests. Please try again later."):
        self.factory, self.max_hits, self.window, self.message = session_factory, max_hits, window_seconds, message

    @staticmethod
    def _k(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    def _count(self, s, k: str) -> int:
        from sqlalchemy import func, select

        from app.db.base import utcnow
        from app.models import RateLimitEvent

        since = utcnow() - timedelta(seconds=self.window)
        return s.scalar(select(func.count()).select_from(RateLimitEvent).where(RateLimitEvent.key == k, RateLimitEvent.created_at >= since)) or 0

    def check(self, key: str) -> None:
        with self.factory() as s:
            if self._count(s, self._k(key)) >= self.max_hits:
                raise RateLimited(self.message)

    def hit(self, key: str) -> None:
        from sqlalchemy import delete

        from app.db.base import utcnow
        from app.models import RateLimitEvent

        k = self._k(key)
        with self.factory() as s:
            s.add(RateLimitEvent(key=k))
            s.execute(delete(RateLimitEvent).where(RateLimitEvent.key == k, RateLimitEvent.created_at < utcnow() - timedelta(seconds=self.window)))
            s.commit()

    def check_and_hit(self, key: str) -> None:
        self.check(key)
        self.hit(key)

    def reset(self, key: str) -> None:
        from sqlalchemy import delete

        from app.models import RateLimitEvent

        with self.factory() as s:
            s.execute(delete(RateLimitEvent).where(RateLimitEvent.key == self._k(key)))
            s.commit()

"""
auth/security.py — Password hashing, JWT tokens, and auth cookie management.

Ported from a production-tested reference implementation. Adapted for:
  - Sync PyMongo (reference used async Motor)
  - This project's flat config.py pattern (reference used pydantic Settings)

Security model:
  - Passwords: HMAC-SHA256 pepper (server secret) → bcrypt (auto-salted)
    Even a full DB dump is uncrackable without the server-side PEPPER.
  - JWT: short-lived access token (30 min) + longer refresh token (7 days)
  - Cookies: httpOnly (JS can't read them — defeats XSS token theft)
  - CSRF: double-submit pattern — separate readable cookie + header must match
"""

from __future__ import annotations

import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Response

from config import (
    SECRET_KEY, PEPPER, ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    ENVIRONMENT,
)

# Cookie names — shared between auth endpoints and the auth dependency
ACCESS_TOKEN_COOKIE  = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"
CSRF_TOKEN_COOKIE    = "csrf_token"
CSRF_TOKEN_HEADER    = "X-CSRF-Token"
REFRESH_TOKEN_COOKIE_PATH = "/alerts"  # narrow path; adjust if you mount auth elsewhere — see note below

# bcrypt auto-salts; we pepper before bcrypt ever sees the raw password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Pepper ──────────────────────────────────────────────────────────────────

def _apply_pepper(plain_password: str) -> str:
    """
    HMAC-SHA256 the password with a server-side secret (PEPPER) before bcrypt.

    bcrypt's salt protects against rainbow tables. Pepper protects against
    offline brute force even if the entire database is stolen — the attacker
    also needs the PEPPER, which lives only in your server's environment.

    WARNING: never change PEPPER after users exist. Doing so makes every
    existing password unverifiable (effectively locks everyone out).
    """
    return hmac.new(
        PEPPER.encode("utf-8"),
        plain_password.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(_apply_pepper(plain_password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(_apply_pepper(plain_password), hashed_password)


def validate_password_strength(password: str) -> Optional[str]:
    """Returns an error message if the password is too weak, else None."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
        return "Password must contain at least one special character (!@#$%^&* etc)."
    return None


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT. Returns the payload dict, or None on any failure."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── CSRF + cookie helpers ─────────────────────────────────────────────────────

def generate_csrf_token() -> str:
    """Random hex token for double-submit CSRF protection."""
    return secrets.token_hex(32)


def _cross_origin_cookie_params(*, httponly: bool) -> dict:
    """
    Production (frontend and API on different domains): SameSite=None + Secure.
    Development (localhost): Lax + non-secure, since localhost has no HTTPS.
    """
    is_production = ENVIRONMENT == "production"
    return {
        "httponly": httponly,
        "secure": is_production,
        "samesite": "none" if is_production else "lax",
    }


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    """Set httpOnly JWT cookies plus a readable CSRF cookie after login/register/google."""
    common = _cross_origin_cookie_params(httponly=True)
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **common,
    )
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        path="/",  # kept broad for simplicity; narrow to /auth/refresh if you prefer
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **common,
    )
    response.set_cookie(
        key=CSRF_TOKEN_COOKIE,
        value=csrf_token,
        path="/",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        **_cross_origin_cookie_params(httponly=False),
    )
    # Cross-origin frontends can't read API-domain cookies directly — echo via header
    response.headers[CSRF_TOKEN_HEADER] = csrf_token


def set_access_token_cookie(response: Response, access_token: str) -> None:
    """Update only the access token cookie after a refresh."""
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **_cross_origin_cookie_params(httponly=True),
    )


def clear_auth_cookies(response: Response) -> None:
    """Expire all auth-related cookies on logout."""
    common = _cross_origin_cookie_params(httponly=True)
    response.set_cookie(key=ACCESS_TOKEN_COOKIE,  value="", max_age=0, path="/", **common)
    response.set_cookie(key=REFRESH_TOKEN_COOKIE, value="", max_age=0, path="/", **common)
    response.set_cookie(
        key=CSRF_TOKEN_COOKIE, value="", max_age=0, path="/",
        **_cross_origin_cookie_params(httponly=False),
    )
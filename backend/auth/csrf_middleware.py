"""
auth/csrf_middleware.py — Double-submit CSRF protection.

How it works:
  1. After login, the server sets a CSRF token in a *readable* cookie
     and echoes it in the X-CSRF-Token response header.
  2. The frontend's axios/fetch interceptor reads the header and attaches
     it as X-CSRF-Token on every mutating request (POST/PUT/PATCH/DELETE).
  3. This middleware checks that the header value matches the cookie value.

Why this stops CSRF: a malicious site can trigger a cross-origin POST
(cookies are sent automatically), but it cannot read the CSRF cookie's
value (cross-origin pages can't read each other's cookies) — so it can't
produce a matching header.

Auth endpoints (login/register/refresh) are exempt since they run before
a CSRF token exists yet.
"""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from auth.security import CSRF_TOKEN_COOKIE, CSRF_TOKEN_HEADER

EXEMPT_PATHS = {
    "/auth/login",
    "/auth/register/initiate",
    "/auth/register/verify",
    "/auth/forgot-password/initiate",
    "/auth/forgot-password/verify",
    "/auth/google",
    "/auth/refresh",
    "/auth/logout",
}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in SAFE_METHODS or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # Only enforce CSRF on requests that carry the access token cookie
        # (i.e. browser-authenticated requests). Bearer-token clients (CLI, scripts)
        # don't rely on cookies and so aren't vulnerable to CSRF.
        if "access_token" not in request.cookies:
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_TOKEN_COOKIE)
        header_token = request.headers.get(CSRF_TOKEN_HEADER)

        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid."},
            )

        return await call_next(request)
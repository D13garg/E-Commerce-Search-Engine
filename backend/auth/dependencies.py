"""
auth/dependencies.py — FastAPI dependency for extracting the current user.

Single role (customer) — no admin/associate variants needed.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo.database import Database

from api.dependencies import get_db
from auth.auth_service import AuthService
from auth.models import UserModel
from auth.security import ACCESS_TOKEN_COOKIE
from auth.exceptions import UnauthorizedException

# auto_error=False so cookie-based browser auth doesn't require a Bearer header
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Database = Depends(get_db),
) -> UserModel:
    """
    Core auth dependency. Reads the access token from the httpOnly cookie first,
    falls back to a Bearer header for non-browser clients (CLI, scripts).

    Usage:
        @router.get("/me")
        def me(current_user: UserModel = Depends(get_current_user)):
            ...
    """
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token and credentials:
        token = credentials.credentials
    if not token:
        raise UnauthorizedException("Not authenticated.")

    service = AuthService(db)
    return service.get_current_user_by_token(token)


def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Database = Depends(get_db),
) -> Optional[UserModel]:
    """
    Like get_current_user, but returns None instead of raising when not authenticated.
    Use for endpoints that behave differently for logged-in vs anonymous users
    without requiring login (e.g. personalised vs generic results).
    """
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token and credentials:
        token = credentials.credentials
    if not token:
        return None

    try:
        service = AuthService(db)
        return service.get_current_user_by_token(token)
    except UnauthorizedException:
        return None
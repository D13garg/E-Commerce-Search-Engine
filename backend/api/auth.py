"""
api/auth.py — Auth API endpoints.

Endpoints:
  POST /auth/register/initiate    Step 1: validate + send OTP
  POST /auth/register/verify      Step 2: verify OTP → create account → tokens
  POST /auth/login                Email + password login
  POST /auth/forgot-password/initiate
  POST /auth/forgot-password/verify
  POST /auth/google               Google OAuth
  POST /auth/refresh              Exchange refresh token for new access token
  POST /auth/logout               Clear auth cookies
  GET  /auth/me                   Current user profile
"""

from fastapi import APIRouter, Depends, Request, Response
from pymongo.database import Database

from api.dependencies import get_db
from auth.dependencies import get_current_user
from auth.auth_service import AuthService
from auth.security import (
    REFRESH_TOKEN_COOKIE, CSRF_TOKEN_COOKIE, CSRF_TOKEN_HEADER,
    generate_csrf_token, set_auth_cookies, set_access_token_cookie, clear_auth_cookies,
)
from auth.exceptions import UnauthorizedException
from auth.models import (
    LoginRequest, RefreshTokenRequest, TokenResponse, AccessTokenResponse,
    UserResponse, RegisterInitiateRequest, OTPVerifyRequest, OTPInitiateResponse,
    ForgotPasswordInitiateRequest, ForgotPasswordVerifyRequest, MessageResponse,
    GoogleAuthRequest, UserModel,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Registration (2-step) ────────────────────────────────────────────────────

@router.post("/register/initiate", response_model=OTPInitiateResponse, status_code=200)
def register_initiate(data: RegisterInitiateRequest, db: Database = Depends(get_db)):
    """Step 1: validate registration data, send OTP to email."""
    service = AuthService(db)
    return service.register_initiate(data)


@router.post("/register/verify", response_model=TokenResponse, status_code=201)
def register_verify(response: Response, data: OTPVerifyRequest, db: Database = Depends(get_db)):
    """Step 2: verify OTP, create account, return tokens. OTP expires in 3 minutes, single-use."""
    service = AuthService(db)
    result = service.register_verify(data)
    set_auth_cookies(response, result.access_token, result.refresh_token, generate_csrf_token())
    return result


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(response: Response, data: LoginRequest, db: Database = Depends(get_db)):
    """Login with email and password."""
    service = AuthService(db)
    result = service.login(data)
    set_auth_cookies(response, result.access_token, result.refresh_token, generate_csrf_token())
    return result


# ── Forgot password (2-step) ──────────────────────────────────────────────────

@router.post("/forgot-password/initiate", response_model=MessageResponse, status_code=200)
def forgot_password_initiate(data: ForgotPasswordInitiateRequest, db: Database = Depends(get_db)):
    """Send OTP for password reset. Always returns 200 — prevents email enumeration."""
    service = AuthService(db)
    service.forgot_password_initiate(data.email)
    return MessageResponse(message="If that email is registered, a verification code has been sent.")


@router.post("/forgot-password/verify", response_model=MessageResponse, status_code=200)
def forgot_password_verify(data: ForgotPasswordVerifyRequest, db: Database = Depends(get_db)):
    """Verify OTP and reset password."""
    service = AuthService(db)
    service.forgot_password_verify(data)
    return MessageResponse(message="Password reset successfully. You can now sign in.")


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.post("/google", response_model=TokenResponse, status_code=200)
def google_auth(response: Response, data: GoogleAuthRequest, db: Database = Depends(get_db)):
    """Authenticate with a Google ID token. Creates account on first login."""
    service = AuthService(db)
    result = service.google_auth(data)
    set_auth_cookies(response, result.access_token, result.refresh_token, generate_csrf_token())
    return result


# ── Token refresh ─────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_token(request: Request, response: Response, data: RefreshTokenRequest, db: Database = Depends(get_db)):
    """Exchange a valid refresh token (cookie or body) for a new access token."""
    refresh = request.cookies.get(REFRESH_TOKEN_COOKIE) or data.refresh_token
    if not refresh:
        raise UnauthorizedException("Refresh token required.")

    service = AuthService(db)
    result = service.refresh(refresh)
    set_access_token_cookie(response, result.access_token)
    return result


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    """Clear all auth cookies."""
    clear_auth_cookies(response)
    return MessageResponse(message="Logged out successfully.")


# ── Current user ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_me(request: Request, response: Response, current_user: UserModel = Depends(get_current_user)):
    """Returns the currently authenticated user's profile."""
    csrf = request.cookies.get(CSRF_TOKEN_COOKIE)
    if csrf:
        response.headers[CSRF_TOKEN_HEADER] = csrf
    return UserResponse(
        id=current_user.id, name=current_user.name, email=current_user.email,
        is_active=current_user.is_active, phone=current_user.phone,
        created_at=current_user.created_at, updated_at=current_user.updated_at,
    )
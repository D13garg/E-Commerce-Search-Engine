"""
auth/auth_service.py — Orchestrates registration, login, OTP, Google OAuth, refresh.

Ported from a production-tested reference, simplified to a single role (customer)
and adapted to sync PyMongo.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from pymongo.database import Database

from auth.user_repository import UserRepository
from auth.otp_service import OTPService
from auth.email import send_otp_email
from auth.models import (
    LoginRequest, TokenResponse, AccessTokenResponse, UserResponse,
    RegisterInitiateRequest, OTPVerifyRequest,
    ForgotPasswordVerifyRequest, GoogleAuthRequest, OTPInitiateResponse,
    UserModel,
)
from auth.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from auth.exceptions import ConflictException, UnauthorizedException, BadRequestException
from config import GOOGLE_CLIENT_ID

logger = logging.getLogger(__name__)


def _to_user_response(user: UserModel) -> UserResponse:
    return UserResponse(
        id=user.id, name=user.name, email=user.email,
        is_active=user.is_active, phone=user.phone,
        created_at=user.created_at, updated_at=user.updated_at,
    )


def _make_tokens(user: UserModel) -> dict:
    payload = {"sub": user.id}
    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload),
    }


class AuthService:
    def __init__(self, db: Database):
        self.user_repo = UserRepository(db)
        self.otp_service = OTPService(db)
        self.db = db

    # ── Registration step 1: validate, store pending, send OTP ──────────────

    def register_initiate(self, data: RegisterInitiateRequest) -> OTPInitiateResponse:
        if self.user_repo.email_exists(data.email):
            raise ConflictException("A user with this email already exists.")

        # Hash the password now — never stored plain, even temporarily
        pending_data = {
            "name": data.name,
            "email": data.email,
            "hashed_password": hash_password(data.password),
            "phone": data.phone,
        }

        code = self.otp_service.create_otp(
            email=data.email, purpose="register", pending_data=pending_data,
        )
        sent = send_otp_email(data.email, code, purpose="register")
        if not sent:
            raise BadRequestException(
                "Could not send verification email. Please try again in a moment, "
                "or contact support if this persists."
            )

        return OTPInitiateResponse(
            message="Verification code sent to your email. It expires in 3 minutes.",
            email=data.email,
        )

    # ── Registration step 2: verify OTP → create account → tokens ──────────

    def register_verify(self, data: OTPVerifyRequest) -> TokenResponse:
        pending_data = self.otp_service.verify_otp(
            email=data.email, code=data.code, purpose="register",
        )
        if not pending_data:
            raise BadRequestException("Registration data not found. Please start over.")

        if self.user_repo.email_exists(data.email):
            raise ConflictException("A user with this email already exists.")

        now = datetime.now(timezone.utc)
        user_doc = {
            "name": pending_data["name"],
            "email": pending_data["email"],
            "hashed_password": pending_data["hashed_password"],
            "is_active": True,
            "phone": pending_data.get("phone"),
            "created_at": now,
            "updated_at": now,
        }
        user = self.user_repo.create(user_doc)

        tokens = _make_tokens(user)
        return TokenResponse(**tokens, user=_to_user_response(user))

    # ── Login ─────────────────────────────────────────────────────────────

    def login(self, data: LoginRequest) -> TokenResponse:
        user = self.user_repo.find_by_email(data.email)
        if not user:
            raise UnauthorizedException("Invalid email or password.")

        if not user.hashed_password:
            raise UnauthorizedException(
                "This account uses Google Sign-In. Please sign in with Google."
            )

        if not verify_password(data.password, user.hashed_password):
            raise UnauthorizedException("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedException("Your account has been deactivated.")

        tokens = _make_tokens(user)
        return TokenResponse(**tokens, user=_to_user_response(user))

    # ── Forgot password step 1: send OTP ────────────────────────────────────

    def forgot_password_initiate(self, email: str) -> None:
        """
        Always returns without error — prevents email enumeration.
        Silently no-ops if the email doesn't exist or is a Google-only account.
        """
        user = self.user_repo.find_by_email(email)
        if not user or not user.hashed_password:
            logger.info(f"[auth] forgot-password requested for non-existent/Google email: {email}")
            return

        code = self.otp_service.create_otp(email=email, purpose="forgot_password", pending_data=None)
        sent = send_otp_email(email, code, purpose="forgot_password")
        if not sent:
            # Don't raise — would leak that the email exists. Log loudly instead.
            logger.error(f"[auth] forgot-password OTP email FAILED to send to {email}")

    # ── Forgot password step 2: verify OTP → reset password ────────────────

    def forgot_password_verify(self, data: ForgotPasswordVerifyRequest) -> None:
        self.otp_service.verify_otp(email=data.email, code=data.code, purpose="forgot_password")

        user = self.user_repo.find_by_email(data.email)
        if not user:
            raise UnauthorizedException("Invalid or expired verification code.")

        self.user_repo.update(user.id, {
            "hashed_password": hash_password(data.new_password),
            "updated_at": datetime.now(timezone.utc),
        })

    # ── Google OAuth ─────────────────────────────────────────────────────────

    def google_auth(self, data: GoogleAuthRequest) -> TokenResponse:
        """
        Verify the Google ID token via the official google-auth library
        (validates signature, expiry, and audience in one call).
        Creates an account on first login, finds the existing one otherwise.
        """
        try:
            google_data = id_token.verify_oauth2_token(
                data.id_token, google_requests.Request(), GOOGLE_CLIENT_ID,
            )
        except ValueError:
            raise UnauthorizedException("Invalid Google token. Please try again.")

        if not google_data.get("email_verified"):
            raise UnauthorizedException("Google account email is not verified.")

        email = google_data.get("email")
        if not email:
            raise UnauthorizedException("Could not retrieve email from Google account.")
        name = google_data.get("name") or email.split("@")[0]

        user = self.user_repo.find_by_email(email)
        if not user:
            now = datetime.now(timezone.utc)
            user = self.user_repo.create({
                "name": name,
                "email": email,
                "hashed_password": None,  # Google accounts have no password
                "is_active": True,
                "phone": None,
                "created_at": now,
                "updated_at": now,
            })
        elif not user.is_active:
            raise UnauthorizedException("Your account has been deactivated.")

        tokens = _make_tokens(user)
        return TokenResponse(**tokens, user=_to_user_response(user))

    # ── Refresh token ─────────────────────────────────────────────────────

    def refresh(self, refresh_token: str) -> AccessTokenResponse:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise UnauthorizedException("Invalid or expired refresh token.")

        user = self.user_repo.find_by_id(payload["sub"])
        if not user or not user.is_active:
            raise UnauthorizedException("User no longer exists.")

        return AccessTokenResponse(access_token=create_access_token({"sub": user.id}))

    # ── Get current user from token ──────────────────────────────────────

    def get_current_user_by_token(self, token: str) -> UserModel:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            raise UnauthorizedException("Invalid or expired access token.")

        user = self.user_repo.find_by_id(payload["sub"])
        if not user or not user.is_active:
            raise UnauthorizedException("User not found or deactivated.")

        return user
"""
auth/models.py — User document model + request/response schemas.

Single role: customer. No admin/associate tiers (unlike the reference project).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Any

from pydantic import BaseModel, EmailStr, Field, field_validator
from bson import ObjectId

USERS_COLLECTION = "users"
OTPS_COLLECTION = "otps"


# ── Internal DB model ──────────────────────────────────────────────────────────

class UserModel(BaseModel):
    """Represents a user document as stored in MongoDB. Never returned directly from the API."""
    id: Optional[str] = Field(default=None, alias="_id")
    name: str
    email: EmailStr
    hashed_password: Optional[str] = None   # None for Google-only accounts
    is_active: bool = True
    phone: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("id", mode="before")
    @classmethod
    def validate_id(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)

    model_config = {"populate_by_name": True}


# ── Request schemas ────────────────────────────────────────────────────────────

class RegisterInitiateRequest(BaseModel):
    """Step 1 of registration — validate + send OTP."""
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    phone: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        from auth.security import validate_password_strength
        error = validate_password_strength(v)
        if error:
            raise ValueError(error)
        return v

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v: str) -> str:
        if not any(c.isalpha() for c in v):
            raise ValueError("Name must contain at least some letters.")
        return v.strip()


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=4)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None


class ForgotPasswordInitiateRequest(BaseModel):
    email: EmailStr


class ForgotPasswordVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=4)
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        from auth.security import validate_password_strength
        error = validate_password_strength(v)
        if error:
            raise ValueError(error)
        return v


class GoogleAuthRequest(BaseModel):
    id_token: str


# ── Response schemas ────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    is_active: bool
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str


class OTPInitiateResponse(BaseModel):
    message: str
    email: str
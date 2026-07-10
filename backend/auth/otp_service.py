"""
auth/otp_service.py — One-time password generation, storage, and verification.

Ported from a production-tested reference. Sync PyMongo version.

Security model:
  - 4-digit codes, generated with secrets.randbelow (cryptographically secure)
  - Hashed with bcrypt before storage — a DB dump reveals nothing usable
  - Constant-time bcrypt verify — no timing side-channel
  - Max 5 wrong attempts → OTP burned (0.05% brute-force odds before lockout)
  - Max 3 sends per email per hour — blocks flooding
  - Single-use: burned immediately on first correct verification
  - TTL: 3 minutes
  - Purpose-scoped: a 'register' OTP cannot satisfy 'forgot_password' and vice versa
"""

from __future__ import annotations

import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
from pymongo.database import Database

from auth.models import OTPS_COLLECTION

logger = logging.getLogger(__name__)

OTP_EXPIRE_MINUTES  = 3
MAX_ATTEMPTS        = 5
MAX_SENDS_PER_HOUR  = 3

# Lower bcrypt cost for OTPs is fine — already rate-limited + 3 min TTL
_otp_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=8)


def _generate_code() -> str:
    """Cryptographically secure 4-digit code, zero-padded."""
    return f"{secrets.randbelow(10000):04d}"


def _hash_code(code: str) -> str:
    return _otp_ctx.hash(code)


def _verify_code(code: str, code_hash: str) -> bool:
    return _otp_ctx.verify(code, code_hash)


class OTPService:
    def __init__(self, db: Database):
        self.db = db
        self.col = db[OTPS_COLLECTION]

    def setup_indexes(self):
        self.col.create_index("expires_at", expireAfterSeconds=0, name="otp_ttl")
        self.col.create_index([("email", 1), ("purpose", 1)], name="email_purpose_idx")

    # ── Rate limit ────────────────────────────────────────────────────────

    def _check_send_rate_limit(self, email: str, purpose: str) -> None:
        from auth.exceptions import TooManyRequestsException
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        count = self.col.count_documents({
            "email": email,
            "purpose": purpose,
            "created_at": {"$gte": one_hour_ago},
        })
        if count >= MAX_SENDS_PER_HOUR:
            raise TooManyRequestsException(
                "Too many verification emails sent. Please wait before requesting another."
            )

    def _invalidate_existing(self, email: str, purpose: str) -> None:
        self.col.update_many(
            {"email": email, "purpose": purpose, "used": False},
            {"$set": {"used": True}},
        )

    # ── Create ────────────────────────────────────────────────────────────

    def create_otp(self, email: str, purpose: str, pending_data: Optional[dict] = None) -> str:
        """Generate, hash, and store a new OTP. Returns the raw code (caller emails it)."""
        self._check_send_rate_limit(email, purpose)
        self._invalidate_existing(email, purpose)

        code = _generate_code()
        doc = {
            "email": email,
            "code_hash": _hash_code(code),
            "purpose": purpose,
            "used": False,
            "attempts": 0,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
            "created_at": datetime.now(timezone.utc),
            "pending_data": pending_data,
        }
        self.col.insert_one(doc)
        logger.info(f"[otp] created [email={email}, purpose={purpose}]")  # never log the code
        return code

    # ── Verify ────────────────────────────────────────────────────────────

    def verify_otp(self, email: str, code: str, purpose: str) -> Optional[dict]:
        """
        Verify a submitted OTP. Returns pending_data (may be None) on success.
        Raises UnauthorizedException on any failure.
        """
        from auth.exceptions import UnauthorizedException
        now = datetime.now(timezone.utc)

        otp_doc = self.col.find_one(
            {"email": email, "purpose": purpose, "used": False, "expires_at": {"$gt": now}},
            sort=[("created_at", -1)],
        )

        if otp_doc is None:
            raise UnauthorizedException("Invalid or expired verification code. Please request a new one.")

        if otp_doc["attempts"] >= MAX_ATTEMPTS:
            self.col.update_one({"_id": otp_doc["_id"]}, {"$set": {"used": True}})
            raise UnauthorizedException("Too many incorrect attempts. Please request a new verification code.")

        if not _verify_code(code, otp_doc["code_hash"]):
            new_attempts = otp_doc["attempts"] + 1
            if new_attempts >= MAX_ATTEMPTS:
                self.col.update_one({"_id": otp_doc["_id"]}, {"$set": {"used": True, "attempts": new_attempts}})
                raise UnauthorizedException("Too many incorrect attempts. Please request a new verification code.")
            self.col.update_one({"_id": otp_doc["_id"]}, {"$inc": {"attempts": 1}})
            remaining = MAX_ATTEMPTS - new_attempts
            raise UnauthorizedException(f"Incorrect code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.")

        # Correct — burn immediately (single-use)
        self.col.update_one({"_id": otp_doc["_id"]}, {"$set": {"used": True}})
        logger.info(f"[otp] verified [email={email}, purpose={purpose}]")
        return otp_doc.get("pending_data")
"""
alerts/models.py — Alert schema and MongoDB repository.

Collection: alerts
Schema:
  {
    _id:            ObjectId,
    token:          str,          # unsubscribe / manage token (UUID)
    email:          str,
    phone:          str | None,   # E.164 format for WhatsApp e.g. "+919876543210"
    slug:           str,          # product slug
    source_store:   str | None,   # None = any store
    trigger:        "below_price" | "any_drop",
    target_price:   float | None, # only for "below_price"
    currency:       str,          # "INR"
    active:         bool,
    created_at:     datetime,
    last_triggered: datetime | None,
    trigger_count:  int,
  }
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, field_validator
from pymongo import ASCENDING
from pymongo.database import Database

ALERTS_COLLECTION = "alerts"


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AlertCreate(BaseModel):
    """Request body for POST /alerts."""
    email: EmailStr
    phone: Optional[str] = None          # E.164, e.g. "+919876543210"
    slug: str
    source_store: Optional[str] = None   # None = track across all stores
    trigger: Literal["below_price", "any_drop"] = "any_drop"
    target_price: Optional[float] = None
    currency: str = "INR"

    @field_validator("target_price")
    @classmethod
    def target_required_for_below(cls, v, info):
        if info.data.get("trigger") == "below_price" and v is None:
            raise ValueError("target_price is required when trigger='below_price'")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v is not None and not v.startswith("+"):
            raise ValueError("phone must be in E.164 format, e.g. '+919876543210'")
        return v


class AlertResponse(BaseModel):
    """Returned from GET /alerts/{email} and POST /alerts."""
    id: str
    token: str
    email: str
    phone: Optional[str]
    slug: str
    source_store: Optional[str]
    trigger: str
    target_price: Optional[float]
    currency: str
    active: bool
    created_at: str
    last_triggered: Optional[str]
    trigger_count: int


# ── Repository ────────────────────────────────────────────────────────────────

class AlertRepository:
    """All MongoDB operations for the alerts collection."""

    def __init__(self, db: Database):
        self.col = db[ALERTS_COLLECTION]

    def setup_indexes(self):
        self.col.create_index("email", name="email_idx")
        self.col.create_index("token", unique=True, name="token_unique")
        self.col.create_index(
            [("slug", ASCENDING), ("source_store", ASCENDING), ("active", ASCENDING)],
            name="slug_store_active_idx",
        )
        self.col.create_index("active", name="active_idx")

    # ── Write ─────────────────────────────────────────────────────────────

    def create(self, data: AlertCreate) -> dict:
        doc = {
            "token": str(uuid.uuid4()),
            "email": data.email,
            "phone": data.phone,
            "slug": data.slug,
            "source_store": data.source_store,
            "trigger": data.trigger,
            "target_price": data.target_price,
            "currency": data.currency,
            "active": True,
            "created_at": datetime.now(timezone.utc),
            "last_triggered": None,
            "trigger_count": 0,
        }
        result = self.col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def deactivate_by_token(self, token: str) -> bool:
        result = self.col.update_one(
            {"token": token},
            {"$set": {"active": False}},
        )
        return result.matched_count > 0

    def deactivate_by_id(self, alert_id: str) -> bool:
        from bson import ObjectId
        result = self.col.update_one(
            {"_id": ObjectId(alert_id)},
            {"$set": {"active": False}},
        )
        return result.matched_count > 0

    def mark_triggered(self, alert_id, triggered_at: datetime | None = None):
        from bson import ObjectId
        self.col.update_one(
            {"_id": ObjectId(alert_id)},
            {
                "$set": {"last_triggered": triggered_at or datetime.now(timezone.utc)},
                "$inc": {"trigger_count": 1},
            },
        )

    # ── Read ──────────────────────────────────────────────────────────────

    def get_by_email(self, email: str, active_only: bool = True) -> list[dict]:
        q: dict = {"email": email}
        if active_only:
            q["active"] = True
        return list(self.col.find(q, {"_id": 1, "token": 1, "email": 1, "phone": 1,
                                      "slug": 1, "source_store": 1, "trigger": 1,
                                      "target_price": 1, "currency": 1, "active": 1,
                                      "created_at": 1, "last_triggered": 1,
                                      "trigger_count": 1}))

    def get_active_for_slug(self, slug: str, source_store: str | None) -> list[dict]:
        """
        Return all active alerts for a product.
        Matches alerts scoped to this specific store OR to any store (source_store=None).
        """
        q: dict = {
            "slug": slug,
            "active": True,
            "$or": [
                {"source_store": source_store},
                {"source_store": None},
            ],
        }
        return list(self.col.find(q))

    def get_all_active(self) -> list[dict]:
        return list(self.col.find({"active": True}))

    def stats(self) -> dict:
        total = self.col.count_documents({})
        active = self.col.count_documents({"active": True})
        triggered = self.col.count_documents({"trigger_count": {"$gt": 0}})
        return {"total": total, "active": active, "ever_triggered": triggered}

    # ── Serialisation ─────────────────────────────────────────────────────

    @staticmethod
    def to_response(doc: dict) -> AlertResponse:
        return AlertResponse(
            id=str(doc["_id"]),
            token=doc["token"],
            email=doc["email"],
            phone=doc.get("phone"),
            slug=doc["slug"],
            source_store=doc.get("source_store"),
            trigger=doc["trigger"],
            target_price=doc.get("target_price"),
            currency=doc.get("currency", "INR"),
            active=doc.get("active", True),
            created_at=doc["created_at"].isoformat(),
            last_triggered=doc["last_triggered"].isoformat() if doc.get("last_triggered") else None,
            trigger_count=doc.get("trigger_count", 0),
        )
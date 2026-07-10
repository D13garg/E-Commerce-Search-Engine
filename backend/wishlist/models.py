"""
wishlist/models.py — Wishlist schema and MongoDB repository.

Collection: wishlist
Schema:
  {
    _id:            ObjectId,
    user_id:        str,           # references users._id
    slug:           str,
    source_store:   str,
    title:          str,           # denormalised snapshot — survives if product is later removed
    image_url:      str | None,
    added_price:    float | None,  # price at the time it was saved — for "price since you saved" comparison
    currency:       str,
    created_at:     datetime,
  }

Unique on (user_id, slug, source_store) — saving twice is a no-op, not a duplicate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel
from pymongo import ASCENDING
from pymongo.database import Database

WISHLIST_COLLECTION = "wishlist"


# ── Schemas ───────────────────────────────────────────────────────────────────

class WishlistAddRequest(BaseModel):
    slug: str
    source_store: str
    title: str
    image_url: Optional[str] = None
    added_price: Optional[float] = None
    currency: str = "INR"


class WishlistItemResponse(BaseModel):
    id: str
    slug: str
    source_store: str
    title: str
    image_url: Optional[str]
    added_price: Optional[float]
    current_price: Optional[float] = None   # filled in by the service layer
    price_change: Optional[float] = None    # current - added; negative = price dropped
    currency: str
    created_at: str


# ── Repository ────────────────────────────────────────────────────────────────

class WishlistRepository:
    def __init__(self, db: Database):
        self.col = db[WISHLIST_COLLECTION]

    def setup_indexes(self):
        self.col.create_index(
            [("user_id", ASCENDING), ("slug", ASCENDING), ("source_store", ASCENDING)],
            unique=True, name="user_product_unique",
        )
        self.col.create_index("user_id", name="user_id_idx")

    # ── Write ─────────────────────────────────────────────────────────────

    def add(self, user_id: str, data: WishlistAddRequest) -> dict:
        """
        Upsert — if already saved, just returns the existing doc (no duplicate,
        no error). This makes the frontend's "heart" toggle idempotent.
        """
        existing = self.col.find_one({
            "user_id": user_id, "slug": data.slug, "source_store": data.source_store,
        })
        if existing:
            return existing

        doc = {
            "user_id": user_id,
            "slug": data.slug,
            "source_store": data.source_store,
            "title": data.title,
            "image_url": data.image_url,
            "added_price": data.added_price,
            "currency": data.currency,
            "created_at": datetime.now(timezone.utc),
        }
        result = self.col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    def remove(self, user_id: str, slug: str, source_store: str) -> bool:
        result = self.col.delete_one({
            "user_id": user_id, "slug": slug, "source_store": source_store,
        })
        return result.deleted_count > 0

    def remove_by_id(self, user_id: str, item_id: str) -> bool:
        try:
            result = self.col.delete_one({"_id": ObjectId(item_id), "user_id": user_id})
        except Exception:
            return False
        return result.deleted_count > 0

    # ── Read ──────────────────────────────────────────────────────────────

    def get_all(self, user_id: str) -> list[dict]:
        return list(self.col.find({"user_id": user_id}).sort("created_at", -1))

    def get_slugs(self, user_id: str) -> set[tuple[str, str]]:
        """Return {(slug, source_store)} pairs — used by the frontend to render heart state in bulk."""
        docs = self.col.find({"user_id": user_id}, {"slug": 1, "source_store": 1})
        return {(d["slug"], d["source_store"]) for d in docs}

    def is_saved(self, user_id: str, slug: str, source_store: str) -> bool:
        return self.col.count_documents(
            {"user_id": user_id, "slug": slug, "source_store": source_store}, limit=1,
        ) > 0

    def count(self, user_id: str) -> int:
        return self.col.count_documents({"user_id": user_id})
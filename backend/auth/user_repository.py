"""
auth/user_repository.py — All MongoDB operations for the users collection.

Sync PyMongo, matching this project's existing storage pattern
(see storage/mongo.py, alerts/models.py for the same style).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.database import Database

from auth.models import UserModel, USERS_COLLECTION


class UserRepository:
    def __init__(self, db: Database):
        self.col = db[USERS_COLLECTION]

    def setup_indexes(self):
        self.col.create_index("email", unique=True, name="email_unique")

    # ── Read ──────────────────────────────────────────────────────────────

    def find_by_email(self, email: str) -> Optional[UserModel]:
        doc = self.col.find_one({"email": email})
        return UserModel(**doc) if doc else None

    def find_by_id(self, user_id: str) -> Optional[UserModel]:
        try:
            doc = self.col.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None
        return UserModel(**doc) if doc else None

    def email_exists(self, email: str) -> bool:
        return self.col.count_documents({"email": email}, limit=1) > 0

    # ── Write ─────────────────────────────────────────────────────────────

    def create(self, user_doc: dict) -> UserModel:
        result = self.col.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        return UserModel(**user_doc)

    def update(self, user_id: str, fields: dict) -> None:
        self.col.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": fields},
        )
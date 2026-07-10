"""
core/database.py — Database client and dependency provider.
"""

from pymongo import MongoClient
from pymongo.database import Database
from functools import lru_cache

from core.config import settings


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    """
    Create a single MongoClient for the lifetime of the process.
    lru_cache ensures this is only called once.
    """
    return MongoClient(settings.MONGO_URI)


def get_db() -> Database:
    """Returns the pymongo database instance."""
    return get_client()[settings.MONGO_DB_NAME]

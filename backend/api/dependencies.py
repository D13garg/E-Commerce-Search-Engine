"""
api/dependencies.py — Shared dependencies for FastAPI routes.

Why a separate dependencies file?
  FastAPI uses dependency injection — you declare what a route needs
  and FastAPI provides it. This means:
  - One MongoDB connection shared across all requests (not one per request)
  - Easy to swap the DB in tests (inject a test DB instead)
  - No global state scattered across files

The db() function is called by FastAPI on every request via Depends(get_db).
It returns the same MongoClient connection pool each time.
"""

from pymongo import MongoClient
from pymongo.database import Database
from functools import lru_cache
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MONGO_URI, MONGO_DB_NAME


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    """
    Create a single MongoClient for the lifetime of the process.
    lru_cache ensures this is only called once — connection pooling handled by pymongo.
    """
    return MongoClient(MONGO_URI)


def get_db() -> Database:
    """FastAPI dependency — returns the searchengine database."""
    return get_client()[MONGO_DB_NAME]
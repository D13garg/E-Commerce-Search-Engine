"""
services/match_service.py — Business logic for cross-store product matching.
"""

from pymongo.database import Database

from core.exceptions import MatchNotFound
from repositories import match_repo


def get_match_by_sku(db: Database, sku: str) -> dict:
    """Fetch product match listings by SKU. Raises MatchNotFound if empty."""
    match = match_repo.get_match_by_sku(db, sku)
    if not match:
        raise MatchNotFound(f"No match found for SKU '{sku}'")
    return match


def get_match_by_slug(db: Database, slug: str, store: str) -> dict:
    """Fetch product matches by specific slug/store. Raises MatchNotFound if empty."""
    match = match_repo.get_match_by_slug(db, slug=slug, store=store)
    if not match:
        raise MatchNotFound(f"No cross-store match found for '{slug}' on '{store}'")
    return match


def get_best_deals(db: Database, limit: int = 20, min_spread: float = 500) -> list[dict]:
    """Retrieve matched products offering the biggest price savings."""
    return match_repo.get_best_deals(db, limit=limit, min_spread=min_spread)


def get_match_stats(db: Database) -> dict:
    """Return summary statistics about product matches."""
    return match_repo.get_match_stats(db)

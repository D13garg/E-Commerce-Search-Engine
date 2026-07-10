"""
services/price_service.py — Business logic for price history and drops.
"""

from pymongo.database import Database

from core.exceptions import PriceHistoryNotFound
from repositories import price_repo


def get_price_history(
    db: Database,
    slug: str,
    store: str = None,
    limit: int = 100,
) -> list[dict]:
    """Fetch price history for a product. Raises PriceHistoryNotFound if empty."""
    history = price_repo.get_price_history(db, slug=slug, source_store=store, limit=limit)
    if not history:
        raise PriceHistoryNotFound(f"No price history found for '{slug}'")

    # Format datetime objects to strings
    for record in history:
        if "recorded_at" in record:
            record["recorded_at"] = record["recorded_at"].isoformat()

    return history


def get_price_drops(
    db: Database,
    since_hours: int = 168,
    store: str = None,
    min_drop_pct: float = 5.0,
) -> list[dict]:
    """Find products whose prices dropped recently."""
    return price_repo.get_price_drops(
        db,
        since_hours=since_hours,
        store=store,
        min_drop_pct=min_drop_pct,
    )

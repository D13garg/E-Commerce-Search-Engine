"""
repositories/price_repo.py — MongoDB queries and indexing for price history tracking.
"""

from datetime import datetime, timezone, timedelta
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database

PRICE_HISTORY_COLLECTION = "price_history"


def setup_indexes(db: Database):
    col = db[PRICE_HISTORY_COLLECTION]
    col.create_index(
        [("slug", ASCENDING), ("source_store", ASCENDING), ("recorded_at", DESCENDING)],
        name="slug_store_time_idx",
    )
    col.create_index("recorded_at", name="recorded_at_idx")
    print("[price_repo] Price history indexes ensured.")


def record_price(db: Database, slug: str, source_store: str, price: float, currency: str = "INR") -> bool:
    """Record a price event if the price has changed since last record."""
    if price is None:
        return False

    col = db[PRICE_HISTORY_COLLECTION]

    last = col.find_one(
        {"slug": slug, "source_store": source_store},
        sort=[("recorded_at", DESCENDING)],
    )

    if last and last.get("price") == price:
        return False

    col.insert_one({
        "slug": slug,
        "source_store": source_store,
        "price": price,
        "currency": currency,
        "recorded_at": datetime.now(timezone.utc),
    })

    return True


def get_price_history(
    db: Database,
    slug: str,
    source_store: str = None,
    limit: int = 100,
) -> list[dict]:
    col = db[PRICE_HISTORY_COLLECTION]

    filter_dict = {"slug": slug}
    if source_store:
        filter_dict["source_store"] = source_store

    cursor = (
        col.find(filter_dict, {"_id": 0})
        .sort("recorded_at", DESCENDING)
        .limit(limit)
    )

    return list(cursor)


def get_price_drops(
    db: Database,
    since_hours: int = 168,
    store: str = None,
    min_drop_pct: float = 5.0,
) -> list[dict]:
    """Find products whose price dropped within the last N hours."""
    col = db[PRICE_HISTORY_COLLECTION]
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    recent_match = {"recorded_at": {"$gte": since}}
    if store:
        recent_match["source_store"] = store

    recent_pairs = col.distinct(
        "slug",
        {**recent_match, **({"source_store": store} if store else {})}
    )

    if not recent_pairs:
        return []

    results = []

    for slug in recent_pairs:
        filter_dict = {"slug": slug}
        if store:
            filter_dict["source_store"] = store

        records = list(
            col.find(filter_dict, {"_id": 0})
            .sort("recorded_at", DESCENDING)
            .limit(2)
        )

        if len(records) < 2:
            continue

        current = records[0]
        previous = records[1]

        current_price = current["price"]
        previous_price = previous["price"]

        if previous_price <= 0:
            continue

        drop_pct = ((previous_price - current_price) / previous_price) * 100

        if drop_pct >= min_drop_pct:
            results.append({
                "slug": slug,
                "source_store": current["source_store"],
                "current_price": current_price,
                "previous_price": previous_price,
                "drop_amount": round(previous_price - current_price, 2),
                "drop_pct": round(drop_pct, 1),
                "currency": current.get("currency", "INR"),
                "recorded_at": current["recorded_at"].isoformat(),
            })

    results.sort(key=lambda x: x["drop_pct"], reverse=True)
    return results

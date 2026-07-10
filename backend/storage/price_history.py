"""
storage/price_history.py — Price history tracking.

Collection schema:
  {
    slug:         str,
    source_store: str,
    price:        float,
    currency:     str,
    recorded_at:  datetime,
  }
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
    print("[price_history] Indexes ensured.")


def record_price(db: Database, slug: str, source_store: str, price: float, currency: str = "INR") -> bool:
    """
    Record a price event if the price has changed since last record.
    Returns True if a new record was written, False if price unchanged.
    """
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
    """
    Find products whose price dropped within the last N hours.

    Single aggregation pipeline — replaces N+1 per-slug queries.
    Old approach: distinct() + for loop = O(N) round trips, 60s+ on 108K docs.
    New approach: one pipeline with $lookup = O(1) round trips, <2s.
    """
    col = db[PRICE_HISTORY_COLLECTION]
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)

    match_stage: dict = {"recorded_at": {"$gte": since}}
    if store:
        match_stage["source_store"] = store

    pipeline = [
        # Step 1: only recent records — hits recorded_at_idx
        {"$match": match_stage},

        # Step 2: per (slug, source_store) — get the most recent price in window
        {"$sort": {"recorded_at": -1}},
        {"$group": {
            "_id": {"slug": "$slug", "source_store": "$source_store"},
            "current_price": {"$first": "$price"},
            "currency":      {"$first": "$currency"},
            "recorded_at":   {"$first": "$recorded_at"},
        }},

        # Step 3: lookup the immediately-prior price record (before current)
        {"$lookup": {
            "from": PRICE_HISTORY_COLLECTION,
            "let": {
                "slug":         "$_id.slug",
                "source_store": "$_id.source_store",
                "recorded_at":  "$recorded_at",
            },
            "pipeline": [
                {"$match": {"$expr": {"$and": [
                    {"$eq": ["$slug",         "$$slug"]},
                    {"$eq": ["$source_store", "$$source_store"]},
                    {"$lt": ["$recorded_at",  "$$recorded_at"]},
                ]}}},
                {"$sort":  {"recorded_at": -1}},
                {"$limit": 1},
                {"$project": {"_id": 0, "price": 1}},
            ],
            "as": "prev",
        }},

        # Step 4: skip products with no prior record
        {"$match": {"prev.0": {"$exists": True}}},
        {"$addFields": {"previous_price": {"$arrayElemAt": ["$prev.price", 0]}}},

        # Step 5: compute drop_pct, require positive previous price
        {"$match": {"previous_price": {"$gt": 0}}},
        {"$addFields": {
            "drop_pct": {"$multiply": [
                {"$divide": [
                    {"$subtract": ["$previous_price", "$current_price"]},
                    "$previous_price",
                ]},
                100,
            ]}
        }},

        # Step 6: filter by threshold and sort
        {"$match": {"drop_pct": {"$gte": min_drop_pct}}},
        {"$sort": {"drop_pct": -1}},
        {"$limit": 200},

        # Step 7: project clean output
        {"$project": {
            "_id":            0,
            "slug":           "$_id.slug",
            "source_store":   "$_id.source_store",
            "current_price":  1,
            "previous_price": 1,
            "drop_amount":    {"$subtract": ["$previous_price", "$current_price"]},
            "drop_pct":       {"$round": ["$drop_pct", 1]},
            "currency":       1,
            "recorded_at":    1,
        }},
    ]

    results = list(col.aggregate(pipeline, allowDiskUse=True))
    for r in results:
        if isinstance(r.get("recorded_at"), datetime):
            r["recorded_at"] = r["recorded_at"].isoformat()
        r["drop_amount"] = round(r.get("drop_amount", 0), 2)
    return results
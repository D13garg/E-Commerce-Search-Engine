"""
scripts/backfill_price_history.py — Seed price_history from existing products.

We have 27k products already in MongoDB with no price history.
This script reads every product and writes their current price
as the baseline entry in price_history.

This only needs to be run ONCE. After this, every re-crawl
will automatically record price changes via MongoStorage.upsert_product().

The record_price() function won't create duplicates — if you run
this twice, it skips products where price hasn't changed.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from core.config import settings
from repositories.price_repo import record_price, setup_indexes

def backfill():
    print("Connecting to MongoDB...")
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]

    setup_indexes(db)

    total = db[settings.PRODUCTS_COLLECTION].count_documents({})
    print(f"Found {total} products to backfill.\n")

    written = 0
    skipped = 0

    cursor = db[settings.PRODUCTS_COLLECTION].find(
        {"price": {"$ne": None}},
        {"slug": 1, "source_store": 1, "price": 1, "currency": 1, "_id": 0}
    )

    for i, doc in enumerate(cursor, 1):
        recorded = record_price(
            db=db,
            slug=doc["slug"],
            source_store=doc["source_store"],
            price=doc["price"],
            currency=doc.get("currency", "INR"),
        )
        if recorded:
            written += 1
        else:
            skipped += 1

        if i % 1000 == 0:
            print(f"  [{i}/{total}] written: {written}, skipped: {skipped}")

    print(f"\n✓ Backfill complete.")
    print(f"  Written: {written}")
    print(f"  Skipped: {skipped} (already had history)")
    client.close()

if __name__ == "__main__":
    backfill()
EOF
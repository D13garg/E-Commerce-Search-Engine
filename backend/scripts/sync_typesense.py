"""
scripts/sync_typesense.py — Sync all products from MongoDB to Typesense.

Strategy: full rebuild, not incremental.

Why full rebuild instead of incremental sync?
  Incremental sync (only changed documents) is more efficient but complex:
    - Need to track what changed since last sync
    - Need to handle deletes (product removed from store)
    - Need to handle schema changes
  
  Full rebuild is simpler and fast enough:
    - 27k products imported in batches of 500 → ~54 API calls
    - Typesense handles bulk import at ~100k docs/second
    - Total time: under 30 seconds
    - Run after every bulk crawl

  In production at millions of products, you'd switch to incremental.
  At our scale, full rebuild wins on simplicity.

Usage:
  python scripts/sync_typesense.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
import typesense

from core.config import settings
from core.typesense_client import get_client, setup_collection, COLLECTION_NAME

BATCH_SIZE = 500  # Typesense recommends 100-500 per batch


def mongo_to_typesense(doc: dict) -> dict | None:
    """
    Convert a MongoDB product document to a Typesense document.

    Key differences:
      - Typesense requires string IDs
      - MongoDB _id is ObjectId, must be converted to string
      - None values must be handled (Typesense rejects null for non-optional fields)
      - has_available is computed from variants
    """
    slug = doc.get("slug", "")
    source_store = doc.get("source_store", "")

    if not slug or not source_store:
        return None

    # Compute has_available from variants
    variants = doc.get("variants", [])
    has_available = any(v.get("available", False) for v in variants)

    # Available sizes list
    available_sizes = [
        v.get("size", "") for v in variants
        if v.get("available", False) and v.get("size")
    ]

    # Typesense ID must be a string and unique
    # Use slug + store as composite ID
    ts_id = f"{slug}__{source_store}"

    price = doc.get("price")

    return {
        "id":             ts_id,
        "title":          doc.get("title", ""),
        "brand":          doc.get("brand") or "",
        "sku":            doc.get("sku") or "",
        "slug":           slug,
        "category":       doc.get("category") or "",
        "source_store":   source_store,
        "price":          float(price) if price is not None else 999999.0,
        "has_available":  has_available,
        "available_sizes": available_sizes,
        "image_url":      doc.get("image_url") or "",
        "product_url":    doc.get("product_url") or "",
    }


def sync():
    print("=" * 50)
    print("Typesense Sync")
    print("=" * 50)

    # Connect to MongoDB
    mongo_client = MongoClient(settings.MONGO_URI)
    db = mongo_client[settings.MONGO_DB_NAME]
    total_mongo = db[settings.PRODUCTS_COLLECTION].count_documents({})
    print(f"\nMongoDB products: {total_mongo}")

    # Connect to Typesense
    ts_client = get_client()

    # Recreate collection (full rebuild)
    setup_collection(ts_client, force_recreate=True)

    # Stream products from MongoDB in batches
    print(f"\nSyncing in batches of {BATCH_SIZE}...")

    cursor = db[settings.PRODUCTS_COLLECTION].find(
        {},
        {
            "slug": 1, "title": 1, "brand": 1, "sku": 1,
            "category": 1, "source_store": 1, "price": 1,
            "variants": 1, "image_url": 1, "product_url": 1, "_id": 0
        }
    )

    batch = []
    total_synced = 0
    total_skipped = 0

    for doc in cursor:
        ts_doc = mongo_to_typesense(doc)
        if ts_doc is None:
            total_skipped += 1
            continue

        batch.append(ts_doc)

        if len(batch) >= BATCH_SIZE:
            result = ts_client.collections[COLLECTION_NAME].documents.import_(
                batch, {"action": "upsert"}
            )
            total_synced += len(batch)
            print(f"  Synced {total_synced}/{total_mongo}...")
            batch = []

    # Final batch
    if batch:
        ts_client.collections[COLLECTION_NAME].documents.import_(
            batch, {"action": "upsert"}
        )
        total_synced += len(batch)

    # Verify
    collection_info = ts_client.collections[COLLECTION_NAME].retrieve()
    print(f"\n✓ Sync complete")
    print(f"  MongoDB:   {total_mongo}")
    print(f"  Synced:    {total_synced}")
    print(f"  Skipped:   {total_skipped}")
    print(f"  Typesense: {collection_info['num_documents']}")

    mongo_client.close()


if __name__ == "__main__":
    sync()
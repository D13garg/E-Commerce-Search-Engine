"""
scripts/run_matching.py — Run product matching across all stores.

Safe to run multiple times — upserts matches, never duplicates.
Run after every bulk crawl to keep matches fresh.

Usage:
  python scripts/run_matching.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from core.config import settings
from repositories.match_repo import run_matching, get_match_stats


def main():
    print("Connecting to MongoDB...")
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]

    print("\nRunning product matching...\n")
    stats = run_matching(db)

    print("\n── Results ──────────────────────────")
    print(f"  Total products scanned: {stats['total_products']}")
    print(f"  SKU matches (high):     {stats['sku_matches']}")
    print(f"  Slug matches (medium):  {stats['slug_matches']}")
    print(f"  Total matches:          {stats['total_matches']}")

    summary = get_match_stats(db)
    print(f"\n── Match Collection ─────────────────")
    print(f"  Total in DB:    {summary['total_matches']}")
    print(f"  By type:        {summary['by_type']}")
    print(f"  By confidence:  {summary['by_confidence']}")

    client.close()


if __name__ == "__main__":
    main()
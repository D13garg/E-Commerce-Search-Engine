"""
pipeline/bulk_hypefly.py — Full HypeFly crawl via GraphQL API.

Architecture change from original plan:
  BEFORE: sitemap discovery → individual Next.js fetch per product
  NOW:    GraphQL paginated query → full product data in batches

Why this is better:
  - Sitemap was broken (products-sitemap.xml returned 404)
  - GraphQL returns complete product data per batch — no second fetch needed
  - 100 products per request instead of 1 = 100x fewer HTTP requests
  - Cleaner pagination with total count upfront

Usage:
  python pipeline/bulk_hypefly.py
  python pipeline/bulk_hypefly.py --limit 20
  python pipeline/bulk_hypefly.py --dry-run
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.hypefly.graphql import HypeflyGraphQL
from crawlers.hypefly.parser import HypeflyParser
from storage.mongo import MongoStorage


def run(limit: int = None, dry_run: bool = False):
    print(f"\n{'='*60}")
    print(f"  HypeFly Bulk Pipeline (GraphQL)")
    if limit:
        print(f"  Limit: {limit} products")
    if dry_run:
        print(f"  DRY RUN — no storage")
    print(f"{'='*60}\n")

    parser = HypeflyParser()
    stats = {"success": 0, "failed": 0}
    failed = []
    processed = 0

    with HypeflyGraphQL() as client:
        if dry_run:
            print("[pipeline] Fetching first batch to preview slugs...\n")
            batch = next(client.iter_all_products())
            for p in batch[:20]:
                print(f"  {p.get('slug')}")
            print(f"\n  ... (showing first 20 of batch)")
            return

        with MongoStorage() as storage:
            for batch in client.iter_all_products():
                for raw in batch:
                    slug = raw.get("slug", "?")
                    processed += 1
                    print(f"\n[{processed}] {slug}")

                    try:
                        product = parser.parse_graphql_product(raw)
                        result = storage.upsert_product(product)
                        action = "inserted" if result["upserted_id"] else "updated"
                        print(f"  ✓ {product.title} — {action}")
                        stats["success"] += 1
                    except Exception as e:
                        print(f"  ✗ Failed: {e}")
                        stats["failed"] += 1
                        failed.append(slug)

                    if limit and processed >= limit:
                        print(f"\n[pipeline] Limit of {limit} reached.")
                        break

                if limit and processed >= limit:
                    break

    print(f"\n{'='*60}")
    print(f"  Crawl Complete")
    print(f"  ✓ Success: {stats['success']}")
    print(f"  ✗ Failed:  {stats['failed']}")
    if failed:
        print(f"\n  Failed slugs:")
        for s in failed:
            print(f"    - {s}")
    print(f"{'='*60}")


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="HypeFly bulk crawl via GraphQL")
    arg_parser.add_argument("--limit", type=int, default=None)
    arg_parser.add_argument("--dry-run", action="store_true")
    args = arg_parser.parse_args()
    run(limit=args.limit, dry_run=args.dry_run)
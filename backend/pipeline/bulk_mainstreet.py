"""
pipeline/bulk_mainstreet.py — Full Mainstreet crawl: discover all slugs, fetch and store each.

Mainstreet is Shopify, which gives us an optimisation HypeFly doesn't have:
  The collection discovery endpoint already returns full product JSON.
  We could parse directly from discovery without a second fetch per product.

However, we still use the separate fetch → parse pattern for two reasons:
  1. Consistency — same pipeline shape as HypeFly
  2. The collection JSON sometimes omits fields that the product endpoint includes
     (e.g. detailed variant inventory). The dedicated product endpoint is always fuller.

For Phase 1, correctness > performance. We fetch each product individually.
Optimisation (batch from collection JSON) is a valid Phase 2 improvement.

Usage:
  python pipeline/bulk_mainstreet.py
  python pipeline/bulk_mainstreet.py --limit 10
  python pipeline/bulk_mainstreet.py --dry-run
  python pipeline/bulk_mainstreet.py --collection all   # crawl all categories
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.mainstreet.fetcher import MainstreetFetcher
from crawlers.mainstreet.parser import MainstreetParser
from crawlers.mainstreet.discovery import MainstreetDiscovery
from storage.mongo import MongoStorage


def run(limit: int = None, dry_run: bool = False, collection: str = "all-sneakers"):
    print(f"\n{'='*60}")
    print(f"  Mainstreet Bulk Pipeline")
    print(f"  Collection: {collection}")
    if limit:
        print(f"  Limit: {limit} products")
    if dry_run:
        print(f"  DRY RUN — discovery only, no storage")
    print(f"{'='*60}\n")

    parser = MainstreetParser()
    stats = {"success": 0, "failed": 0}
    failed_slugs = []

    with MainstreetFetcher() as fetcher:

        # ── Step 1: Discovery ────────────────────────────────────────────
        discovery = MainstreetDiscovery(fetcher)
        slugs = discovery.get_all_slugs(collection_handle=collection)

        if not slugs:
            print("[pipeline] ✗ No slugs discovered. Check collection handle.")
            sys.exit(1)

        print(f"\n[pipeline] Discovered {len(slugs)} product slugs.")

        if limit:
            slugs = slugs[:limit]
            print(f"[pipeline] Limited to first {limit} slugs.\n")

        if dry_run:
            print("[pipeline] Dry run — listing slugs only:")
            for s in slugs:
                print(f"  {s}")
            return

        # ── Step 2: Crawl each slug ──────────────────────────────────────
        with MongoStorage() as storage:
            for i, slug in enumerate(slugs, 1):
                print(f"\n[{i}/{len(slugs)}] {slug}")
                try:
                    raw = fetcher.fetch_product(slug)
                    product = parser.parse_product(raw)
                    result = storage.upsert_product(product)

                    action = "inserted" if result["upserted_id"] else "updated"
                    print(f"  ✓ {product.title} — {action}")
                    stats["success"] += 1

                except Exception as e:
                    print(f"  ✗ Failed: {e}")
                    stats["failed"] += 1
                    failed_slugs.append(slug)

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Crawl Complete")
    print(f"  ✓ Success:  {stats['success']}")
    print(f"  ✗ Failed:   {stats['failed']}")
    if failed_slugs:
        print(f"\n  Failed slugs:")
        for s in failed_slugs:
            print(f"    - {s}")
    print(f"{'='*60}")


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Mainstreet bulk crawl pipeline")
    arg_parser.add_argument("--limit", type=int, default=None,
                            help="Max number of products to crawl (default: all)")
    arg_parser.add_argument("--dry-run", action="store_true",
                            help="Discover slugs only, do not fetch or store")
    arg_parser.add_argument("--collection", default="all-sneakers",
                            help="Shopify collection handle (default: all-sneakers)")
    args = arg_parser.parse_args()
    run(limit=args.limit, dry_run=args.dry_run, collection=args.collection)
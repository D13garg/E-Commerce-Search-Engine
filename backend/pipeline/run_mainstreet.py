"""
pipeline/run_mainstreet.py — Mainstreet single-product pipeline.

Notice how similar this is to run_hypefly.py.
The orchestration logic is identical — only the fetcher and parser change.
This validates the architecture: adding a store = add crawler modules,
touch nothing else.
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.mainstreet.fetcher import MainstreetFetcher
from crawlers.mainstreet.parser import MainstreetParser
from storage.mongo import MongoStorage

DEFAULT_SLUG = "adidas-yeezy-500-enflame"


def run(slug: str):
    print(f"\n{'='*60}")
    print(f"  Mainstreet Pipeline")
    print(f"  Target slug: {slug}")
    print(f"{'='*60}\n")

    # Step 1: Fetch — simple Shopify .json endpoint, no build ID needed
    with MainstreetFetcher() as fetcher:
        raw = fetcher.fetch_product(slug)

    print(f"[pipeline] Raw JSON keys: {list(raw.keys())}")

    # Step 2: Parse
    parser = MainstreetParser()
    try:
        product = parser.parse_product(raw)
    except ValueError as e:
        print(f"\n[pipeline] ✗ Parse failed: {e}")
        import json
        print(json.dumps(raw, indent=2)[:2000])
        sys.exit(1)

    print(f"\n[pipeline] Parsed product:")
    print(f"  Title:    {product.title}")
    print(f"  Brand:    {product.brand}")
    print(f"  SKU:      {product.sku}")
    print(f"  Price:    {product.currency} {product.price}")
    print(f"  Variants: {len(product.variants)}")
    print(f"  URL:      {product.product_url}")

    # Step 3: Store — same storage layer, zero changes
    with MongoStorage() as storage:
        result = storage.upsert_product(product)

    print(f"\n[pipeline] ✓ Done.")
    if result["upserted_id"]:
        print(f"  MongoDB document ID: {result['upserted_id']}")
    else:
        print(f"  Product already existed — document updated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mainstreet single-product pipeline")
    parser.add_argument(
        "--slug",
        default=DEFAULT_SLUG,
        help="Product slug from marketplace.mainstreet.co.in/products/{slug}",
    )
    args = parser.parse_args()
    run(args.slug)
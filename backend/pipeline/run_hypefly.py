"""
pipeline/run_hypefly.py — Milestone 1 pipeline.

This is the orchestrator. It knows nothing about HTTP or MongoDB directly.
Its job is: call modules in order, handle top-level errors, report results.

Current state: hardcoded slug (milestone 1 — no discovery yet).
Next state:    slug list comes from discovery module (milestone 2).

Usage:
    python pipeline/run_hypefly.py
    python pipeline/run_hypefly.py --slug nike-dunk-low-panda-dd1391-100

Why sys.path manipulation at the top?
  - We're running from the project root but modules reference each other
    as top-level imports (e.g. `from config import ...`).
  - Adding the project root to sys.path makes all imports resolve correctly
    without needing to install the package.
  - In production you'd install the package instead; fine for now.
"""

import sys
import os
import argparse

# Add project root to path so all modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.hypefly.fetcher import HypeflyFetcher
from crawlers.hypefly.parser import HypeflyParser
from storage.mongo import MongoStorage


# ── Default test slug ──────────────────────────────────────────────────────
# Replace this with any slug from hypefly.co.uk/products/{slug}
DEFAULT_SLUG = "adidas-yeezy-boost-bright-blue-700"


def run(slug: str):
    print(f"\n{'='*60}")
    print(f"  HypeFly Pipeline — Milestone 1")
    print(f"  Target slug: {slug}")
    print(f"{'='*60}\n")

    # Step 1: Fetch
    # Using context manager ensures the HTTP session is closed on exit.
    with HypeflyFetcher() as fetcher:
        raw = fetcher.fetch_product(slug)

    print(f"[pipeline] Raw JSON keys: {list(raw.keys())}")

    # Step 2: Parse
    parser = HypeflyParser()
    try:
        product = parser.parse_product(raw)
    except ValueError as e:
        print(f"\n[pipeline] ✗ Parse failed: {e}")
        print("\nRaw JSON snippet for debugging:")
        import json
        print(json.dumps(raw, indent=2)[:2000])  # First 2000 chars to avoid terminal flood
        sys.exit(1)

    print(f"\n[pipeline] Parsed product:")
    print(f"  Title:    {product.title}")
    print(f"  Brand:    {product.brand}")
    print(f"  SKU:      {product.sku}")
    print(f"  Price:    {product.currency} {product.price}")
    print(f"  Variants: {len(product.variants)}")
    print(f"  URL:      {product.product_url}")

    # Step 3: Store
    with MongoStorage() as storage:
        result = storage.upsert_product(product)

    print(f"\n[pipeline] ✓ Done.")
    if result["upserted_id"]:
        print(f"  MongoDB document ID: {result['upserted_id']}")
    else:
        print(f"  Product already existed — document updated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HypeFly single-product pipeline")
    parser.add_argument(
        "--slug",
        default=DEFAULT_SLUG,
        help="Product slug from hypefly.co.uk/products/{slug}",
    )
    args = parser.parse_args()
    run(args.slug)
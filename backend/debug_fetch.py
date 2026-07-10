"""
debug_fetch.py — Quick utility to inspect raw HypeFly JSON.

Run this BEFORE the full pipeline to understand what data HypeFly
actually returns. This is critical for validating/adjusting the parser.

Usage:
    python debug_fetch.py
    python debug_fetch.py --slug some-other-slug

The output is saved to raw_product.json so you can:
  - Inspect it without re-fetching
  - Use it as a fixture for testing the parser
  - Share it for debugging without running the crawler
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawlers.hypefly.fetcher import HypeflyFetcher
from crawlers.hypefly.parser import HypeflyParser

DEFAULT_SLUG = "adidas-yeezy-boost-bright-blue-700"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", default=DEFAULT_SLUG)
    args = parser.parse_args()

    print(f"Fetching: {args.slug}\n")

    with HypeflyFetcher() as fetcher:
        raw = fetcher.fetch_product(args.slug)

    # Save raw JSON
    output_path = "raw_product.json"
    with open(output_path, "w") as f:
        json.dump(raw, f, indent=2)
    print(f"✓ Raw JSON saved to {output_path}")
    print(f"  Top-level keys: {list(raw.keys())}")

    page_props = raw.get("pageProps", {})
    print(f"  pageProps keys: {list(page_props.keys())}")

    # Try parsing
    print("\nAttempting parse...")
    hypefly_parser = HypeflyParser()
    try:
        product = hypefly_parser.parse_product(raw)
        print(f"✓ Parse succeeded!")
        print(f"  title:    {product.title}")
        print(f"  brand:    {product.brand}")
        print(f"  price:    {product.price} {product.currency}")
        print(f"  variants: {len(product.variants)}")
        if product.variants:
            print(f"  first variant: {product.variants[0]}")
    except Exception as e:
        print(f"✗ Parse failed: {e}")
        print("\nOpen raw_product.json and look at the structure to fix the parser.")
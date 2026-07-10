"""
pipeline/run_generic.py — Universal pipeline for any JSON-configured store.

Replaces run_mainstreet.py and will cover all future Shopify stores.
HypeFly stays on its own runner (too custom for generic config).

Usage:
    # Crawl all products from a store
    python pipeline/run_generic.py --store dawntown

    # Single product
    python pipeline/run_generic.py --store dawntown --slug nike-dunk-low-panda

    # Full path to a config
    python pipeline/run_generic.py --config /path/to/custom.json

    # List all available stores
    python pipeline/run_generic.py --list

    # Dry run (parse only, no writes to MongoDB)
    python pipeline/run_generic.py --store dawntown --dry-run --limit 10
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.generic import (
    load_store_config,
    load_all_store_configs,
    list_store_configs,
    ShopifyCrawler,
    StoreConfig,
)
from storage.mongo import MongoStorage


# ── Single-product run ────────────────────────────────────────────────────────

def run_single(config: StoreConfig, slug: str, dry_run: bool = False):
    print(f"\n{'='*60}")
    print(f"  {config.display_name} — Single Product")
    print(f"  Slug: {slug}")
    print(f"{'='*60}\n")

    with ShopifyCrawler(config) as crawler:
        product = crawler.fetch_product(slug)

    print(f"\n[pipeline] Parsed product:")
    print(f"  Title:    {product.title}")
    print(f"  Brand:    {product.brand}")
    print(f"  SKU:      {product.sku}")
    print(f"  Price:    {product.currency} {product.price}")
    print(f"  Category: {product.category}")
    print(f"  Variants: {len(product.variants)}")
    print(f"  URL:      {product.product_url}")

    if dry_run:
        print(f"\n[pipeline] Dry run — skipping MongoDB write.")
        return

    with MongoStorage() as storage:
        result = storage.upsert_product(product)

    print(f"\n[pipeline] ✓ Done.")
    if result.get("upserted_id"):
        print(f"  New document: {result['upserted_id']}")
    else:
        print(f"  Existing document updated.")


# ── Bulk run ──────────────────────────────────────────────────────────────────

def run_bulk(config: StoreConfig, dry_run: bool = False, limit: int | None = None):
    print(f"\n{'='*60}")
    print(f"  {config.display_name} — Bulk Crawl")
    print(f"  Collection: {config.discovery.collection_handle}")
    if dry_run:
        print(f"  Mode: DRY RUN (no writes)")
    if limit:
        print(f"  Limit: {limit} products")
    print(f"{'='*60}\n")

    stats = {"success": 0, "failed": 0, "skipped": 0}

    with ShopifyCrawler(config) as crawler:
        storage_ctx = MongoStorage() if not dry_run else None

        try:
            with (storage_ctx or _NullContextManager()) as storage:
                for batch in crawler.iter_all_products():
                    for product in batch:
                        if limit and stats["success"] + stats["failed"] >= limit:
                            print(f"\n[pipeline] Limit of {limit} reached — stopping.")
                            return

                        try:
                            if not dry_run:
                                storage.upsert_product(product)
                            else:
                                # In dry-run: just print first 5
                                if stats["success"] < 5:
                                    print(
                                        f"  [dry-run] {product.title} "
                                        f"({product.currency} {product.price})"
                                    )
                            stats["success"] += 1
                        except Exception as e:
                            print(f"  [pipeline] ✗ {product.slug}: {e}")
                            stats["failed"] += 1

        except Exception as e:
            print(f"\n[pipeline] Crawl aborted: {e}")

    print(f"\n{'='*60}")
    print(f"  {config.display_name} complete")
    print(f"  ✓ {stats['success']} products {'parsed' if dry_run else 'upserted'}")
    print(f"  ✗ {stats['failed']} failed")
    print(f"{'='*60}\n")

    return stats


# ── Null context manager for dry-run mode ────────────────────────────────────

class _NullContextManager:
    """Placeholder used when dry_run=True to skip MongoStorage."""
    def __enter__(self): return self
    def __exit__(self, *args): pass


# ── Public API (used by scheduler) ───────────────────────────────────────────

def run_store(store_name: str, dry_run: bool = False) -> dict:
    """
    Run a full bulk crawl for a named store.
    Called by the scheduler for all JSON-configured stores.

    Returns stats dict: {"success": int, "failed": int}
    """
    config = load_store_config(store_name)
    return run_bulk(config, dry_run=dry_run) or {}


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generic store crawler — runs any JSON-configured Shopify store.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline/run_generic.py --list
  python pipeline/run_generic.py --store dawntown
  python pipeline/run_generic.py --store dawntown --dry-run --limit 20
  python pipeline/run_generic.py --store dawntown --slug nike-dunk-low-panda
  python pipeline/run_generic.py --config /path/to/mystore.json
        """,
    )

    parser.add_argument("--store",   help="Store name (matches stores/{name}.json)")
    parser.add_argument("--config",  help="Path to a store config JSON file")
    parser.add_argument("--slug",    help="Crawl a single product slug")
    parser.add_argument("--list",    action="store_true", help="List available store configs")
    parser.add_argument("--dry-run", action="store_true", help="Parse only — no MongoDB writes")
    parser.add_argument("--limit",   type=int, help="Stop after N products (bulk mode)")

    args = parser.parse_args()

    if args.list:
        configs = list_store_configs()
        if configs:
            print(f"\nAvailable store configs ({len(configs)}):")
            for name in sorted(configs):
                cfg = load_store_config(name)
                print(f"  {name:<20} {cfg.display_name}  [{cfg.platform}]  {cfg.base_url}")
        else:
            print("No store configs found in backend/stores/")
        return

    if not args.store and not args.config:
        parser.error("Provide --store NAME or --config PATH (or --list to see options)")

    config = (
        load_store_config(args.config or args.store)
    )

    if config.platform != "shopify":
        print(
            f"[pipeline] '{config.name}' uses platform '{config.platform}' "
            f"which is not handled by run_generic.py. "
            f"Use the dedicated runner instead."
        )
        sys.exit(1)

    if args.slug:
        run_single(config, args.slug, dry_run=args.dry_run)
    else:
        run_bulk(config, dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
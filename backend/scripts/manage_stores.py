"""
scripts/manage_stores.py — Store config management tool.

Usage:
    # List all configured stores
    python scripts/manage_stores.py list

    # Validate a store config (checks JSON schema, not connectivity)
    python scripts/manage_stores.py validate dawntown
    python scripts/manage_stores.py validate --all

    # Test connectivity to a store (live HTTP request, no writes)
    python scripts/manage_stores.py test dawntown

    # Scaffold a new store config (interactive)
    python scripts/manage_stores.py new

    # Print the config for a store (formatted)
    python scripts/manage_stores.py show dawntown
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.generic import (
    load_store_config,
    load_all_store_configs,
    list_store_configs,
    ShopifyCrawler,
)
from crawlers.generic.store_config import STORES_DIR, StoreConfig


# ── list ──────────────────────────────────────────────────────────────────────

def cmd_list():
    names = list_store_configs()
    if not names:
        print("No store configs found in backend/stores/")
        return

    print(f"\n{'NAME':<20} {'DISPLAY':<20} {'PLATFORM':<18} {'URL'}")
    print("-" * 80)
    for name in sorted(names):
        try:
            cfg = load_store_config(name)
            print(f"{cfg.name:<20} {cfg.display_name:<20} {cfg.platform:<18} {cfg.base_url}")
        except Exception as e:
            print(f"{name:<20} {'ERROR':<20} {str(e)}")
    print()


# ── validate ──────────────────────────────────────────────────────────────────

def cmd_validate(name: str | None, all_stores: bool):
    targets = list_store_configs() if all_stores else [name]

    ok = 0
    errors = 0
    for target in targets:
        try:
            cfg = load_store_config(target)
            print(f"  ✓ {cfg.name} — valid ({cfg.platform}, {cfg.base_url})")
            ok += 1
        except Exception as e:
            print(f"  ✗ {target} — {e}")
            errors += 1

    print(f"\n{ok} valid, {errors} invalid")
    if errors:
        sys.exit(1)


# ── test ──────────────────────────────────────────────────────────────────────

def cmd_test(name: str):
    """
    Live connectivity test — fetches page 1 of the collection, parses products,
    and prints a summary. No MongoDB writes.
    """
    cfg = load_store_config(name)
    print(f"\nTesting {cfg.display_name} ({cfg.base_url}) ...")

    if cfg.platform != "shopify":
        print(f"Platform '{cfg.platform}' not testable via this tool.")
        sys.exit(1)

    with ShopifyCrawler(cfg) as crawler:
        batches = crawler.iter_all_products()
        first_batch = next(batches, [])

    if not first_batch:
        print("✗ No products returned — check collection_handle or base_url.")
        sys.exit(1)

    print(f"\n✓ Got {len(first_batch)} products from first page")
    print(f"\nSample products:")
    for p in first_batch[:5]:
        avail = sum(1 for v in p.variants if v.available)
        print(
            f"  {p.title[:48]:<50} "
            f"{p.currency} {p.price:<10} "
            f"{avail}/{len(p.variants)} sizes available"
        )

    # Variant check
    sample = first_batch[0]
    print(f"\nVariant detail for '{sample.title}':")
    for v in sample.variants[:6]:
        status = "✓" if v.available else "✗"
        print(f"  {status} {v.size:<10} {sample.currency} {v.price}")

    print(f"\n✓ {cfg.display_name} looks good.\n")


# ── show ──────────────────────────────────────────────────────────────────────

def cmd_show(name: str):
    cfg = load_store_config(name)
    print(f"\n{cfg.model_dump_json(indent=2)}\n")


# ── new ───────────────────────────────────────────────────────────────────────

def cmd_new():
    """Interactive scaffold for a new store config."""
    print("\n── New Store Config ──────────────────────────────────────\n")

    name = input("Store slug (e.g. 'dawntown', 'superkicks'): ").strip().lower()
    if not name:
        print("Name required.")
        sys.exit(1)

    out_path = STORES_DIR / f"{name}.json"
    if out_path.exists():
        print(f"Config already exists: {out_path}")
        sys.exit(1)

    display_name = input(f"Display name [{name.title()}]: ").strip() or name.title()
    base_url = input("Base URL (e.g. https://superkicks.in): ").strip().rstrip("/")
    collection = input("Collection handle ['all' for whole store]: ").strip() or "all"
    size_option = input("Size variant option ['option1']: ").strip() or "option1"
    currency = input("Currency ['INR']: ").strip() or "INR"
    delay = input("Request delay in seconds ['1.0']: ").strip() or "1.0"

    config = {
        "name": name,
        "display_name": display_name,
        "base_url": base_url,
        "platform": "shopify",
        "currency": currency,
        "discovery": {
            "method": "shopify_collection_api",
            "collection_handle": collection,
            "page_size": 250
        },
        "field_map": {
            "title": "title",
            "brand": "vendor",
            "slug": "handle",
            "sku": "variants[0].sku",
            "image": "images[0].src",
            "category": "product_type"
        },
        "variant_options": {
            "size_option": size_option,
            "shipping_keywords": ["shipping", "ship", "instant", "same day", "days", "hours", "eta"]
        },
        "category_map": {
            "sneakers": "Sneakers",
            "slides": "Slides",
            "apparel": "Apparel",
            "accessories": "Accessories"
        },
        "crawl": {
            "delay_seconds": float(delay),
            "max_retries": 3
        }
    }

    STORES_DIR.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n✓ Created: {out_path}")
    print(f"\nNext steps:")
    print(f"  1. Review and edit {out_path} if needed")
    print(f"  2. Test connectivity:  python scripts/manage_stores.py test {name}")
    print(f"  3. Dry-run crawl:      python pipeline/run_generic.py --store {name} --dry-run --limit 20")
    print(f"  4. Full crawl:         python pipeline/run_generic.py --store {name}")
    print(f"  5. The scheduler will auto-pick it up on the next run.\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Store config management tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List all store configs")

    val = sub.add_parser("validate", help="Validate store config(s)")
    val.add_argument("name", nargs="?", help="Store name")
    val.add_argument("--all", action="store_true", dest="all_stores")

    tst = sub.add_parser("test", help="Live connectivity + parse test (no writes)")
    tst.add_argument("name", help="Store name")

    shw = sub.add_parser("show", help="Print store config JSON")
    shw.add_argument("name", help="Store name")

    sub.add_parser("new", help="Interactive scaffold for a new store")

    args = parser.parse_args()

    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "validate":
        cmd_validate(getattr(args, "name", None), getattr(args, "all_stores", False))
    elif args.cmd == "test":
        cmd_test(args.name)
    elif args.cmd == "show":
        cmd_show(args.name)
    elif args.cmd == "new":
        cmd_new()


if __name__ == "__main__":
    main()
"""
scheduler/crawler_scheduler.py — Scheduled re-crawl of all stores.

Uses APScheduler to run crawls on a cron schedule.
Runs as a standalone process alongside the API.

Design decisions:

SMART RE-CRAWL:
  We don't blindly re-crawl every product every time.
  We check last_seen and only re-crawl products older than
  a threshold. This means:
  - First run: crawls everything (all products are "stale")
  - Subsequent runs: only crawls products not seen recently
  - Saves time, reduces load on target servers

SEQUENTIAL STORES:
  HypeFly first (faster — GraphQL batch), then Mainstreet.
  Running them sequentially avoids hammering both sites at once.

SCHEDULE:
  Default: daily at 2:00 AM
  Configurable via environment variables.

Usage:
  python scheduler/crawler_scheduler.py

  # Run once immediately (useful for testing)
  python scheduler/crawler_scheduler.py --now

  # Custom schedule (every 12 hours)
  python scheduler/crawler_scheduler.py --hours 12
"""

import sys
import os
import argparse

import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from scripts.sync_typesense import sync as sync_typesense

from crawlers.hypefly.graphql import HypeflyGraphQL
from crawlers.hypefly.parser import HypeflyParser
from crawlers.mainstreet.fetcher import MainstreetFetcher
from crawlers.mainstreet.parser import MainstreetParser
from crawlers.mainstreet.discovery import MainstreetDiscovery
from crawlers.generic import load_all_store_configs, ShopifyCrawler
from pipeline.run_generic import run_bulk as run_generic_bulk
from storage.mongo import MongoStorage
from config import MONGO_URI, MONGO_DB_NAME, PRODUCTS_COLLECTION

from pymongo import MongoClient

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scheduler")

# How old a product must be before we re-crawl it (in hours)
STALE_AFTER_HOURS = 23


def get_stale_slugs(db, source_store: str) -> list[str]:
    """
    Return slugs of products not seen in the last STALE_AFTER_HOURS.

    On first run: all products are stale (no last_seen or very old)
    On subsequent runs: only products whose data is outdated
    """
    threshold = datetime.now(timezone.utc) - timedelta(hours=STALE_AFTER_HOURS)

    col = db[PRODUCTS_COLLECTION]
    stale = col.find(
        {
            "source_store": source_store,
            "$or": [
                {"last_seen": {"$lt": threshold}},
                {"last_seen": {"$exists": False}},
            ]
        },
        {"slug": 1, "_id": 0}
    )

    return [doc["slug"] for doc in stale]


def crawl_hypefly():
    """
    Re-crawl HypeFly via GraphQL.

    GraphQL returns full product data in batches of 100 —
    we process every product and let MongoStorage handle
    the upsert + price history delta automatically.
    """
    log.info("=" * 50)
    log.info("Starting HypeFly re-crawl")
    log.info("=" * 50)

    parser = HypeflyParser()
    stats = {"success": 0, "failed": 0, "price_changes": 0}

    try:
        with HypeflyGraphQL() as client, MongoStorage() as storage:
            for batch in client.iter_all_products():
                for raw in batch:
                    slug = raw.get("slug", "?")
                    try:
                        product = parser.parse_graphql_product(raw)
                        result = storage.upsert_product(product)
                        stats["success"] += 1
                    except Exception as e:
                        log.warning(f"[hypefly] Failed {slug}: {e}")
                        stats["failed"] += 1

    except Exception as e:
        log.error(f"[hypefly] Crawl aborted: {e}")

    log.info(
        f"HypeFly complete — "
        f"✓ {stats['success']} updated, "
        f"✗ {stats['failed']} failed"
    )


def crawl_mainstreet():
    """
    Re-crawl Mainstreet — smart mode: only stale products.

    Unlike HypeFly (which returns all data via GraphQL),
    Mainstreet requires a separate fetch per product.
    We use last_seen to skip recently-crawled products.
    """
    log.info("=" * 50)
    log.info("Starting Mainstreet re-crawl")
    log.info("=" * 50)

    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]

    # Find products that need re-crawling
    stale_slugs = get_stale_slugs(db, "mainstreet")
    client.close()

    total = len(stale_slugs)
    log.info(f"[mainstreet] {total} stale products to re-crawl")

    if total == 0:
        log.info("[mainstreet] Nothing to do — all products are fresh.")
        return

    parser = MainstreetParser()
    stats = {"success": 0, "failed": 0}

    try:
        with MainstreetFetcher() as fetcher, MongoStorage() as storage:
            for i, slug in enumerate(stale_slugs, 1):
                if i % 100 == 0:
                    log.info(f"[mainstreet] Progress: {i}/{total}")
                try:
                    raw = fetcher.fetch_product(slug)
                    product = parser.parse_product(raw)
                    storage.upsert_product(product)
                    stats["success"] += 1
                except Exception as e:
                    log.warning(f"[mainstreet] Failed {slug}: {e}")
                    stats["failed"] += 1

    except Exception as e:
        log.error(f"[mainstreet] Crawl aborted: {e}")

    log.info(
        f"Mainstreet complete — "
        f"✓ {stats['success']} updated, "
        f"✗ {stats['failed']} failed"
    )


def crawl_generic_stores():
    """
    Auto-discover and crawl all JSON-configured stores in backend/stores/.

    Any store config with platform="shopify" is handled here.
    Adding a new Shopify store = drop a JSON file in stores/ — no code changes needed.

    NOTE: mainstreet.json is intentionally included here so it runs through the
    generic engine. The legacy crawl_mainstreet() function is kept for manual use
    but is no longer called from the scheduler.
    """
    configs = load_all_store_configs()
    shopify_configs = [c for c in configs if c.platform == "shopify"]

    if not shopify_configs:
        log.info("[generic] No Shopify store configs found in backend/stores/ — skipping.")
        return

    log.info(f"[generic] Found {len(shopify_configs)} Shopify store(s): "
             f"{[c.name for c in shopify_configs]}")

    for config in shopify_configs:
        log.info(f"\n[generic] Starting crawl: {config.display_name}")
        try:
            stats = run_generic_bulk(config)
            log.info(
                f"[generic] {config.display_name} done — "
                f"✓ {stats.get('success', 0)} upserted, "
                f"✗ {stats.get('failed', 0)} failed"
            )
        except Exception as e:
            log.error(f"[generic] {config.display_name} crawl failed: {e}", exc_info=True)


def run_all_crawls():
    """Run all store crawls in sequence."""
    log.info(f"\n{'='*50}")
    log.info(f"Scheduled crawl starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"{'='*50}")

    # HypeFly uses a custom GraphQL/Strapi API — stays on its dedicated crawler
    crawl_hypefly()

    # All Shopify stores are driven by JSON configs in backend/stores/
    # (includes mainstreet, dawntown, and any future stores)
    crawl_generic_stores()

    sync_typesense()

    log.info(f"\n{'='*50}")
    log.info("All crawls complete.")
    log.info(f"{'='*50}\n")


def main():
    arg_parser = argparse.ArgumentParser(description="Crawl scheduler")
    arg_parser.add_argument(
        "--now",
        action="store_true",
        help="Run all crawls immediately then exit",
    )
    arg_parser.add_argument(
        "--hours",
        type=int,
        default=None,
        help="Run every N hours instead of daily cron",
    )
    arg_parser.add_argument(
        "--hour",
        type=int,
        default=2,
        help="Hour of day to run daily crawl (default: 2 = 2:00 AM)",
    )
    args = arg_parser.parse_args()

    if args.now:
        log.info("Running crawls immediately (--now flag)")
        run_all_crawls()
        return

    scheduler = BlockingScheduler(timezone="Asia/Kolkata")

    if args.hours:
        # Run every N hours
        trigger = IntervalTrigger(hours=args.hours)
        log.info(f"Scheduled: every {args.hours} hours")
    else:
        # Run daily at specified hour
        trigger = CronTrigger(hour=args.hour, minute=0)
        log.info(f"Scheduled: daily at {args.hour:02d}:00 IST")

    scheduler.add_job(
        run_all_crawls,
        trigger=trigger,
        name="full_crawl",
        max_instances=1,        # Never run two crawls simultaneously
        misfire_grace_time=3600, # If missed by up to 1hr, still run it
    )

    log.info("Scheduler started. Press Ctrl+C to stop.")

    try:
        scheduler.start()
        # Log next run time after scheduler is live
        jobs = scheduler.get_jobs()
        if jobs and hasattr(jobs[0], "next_run_time"):
            log.info(f"Next run: {jobs[0].next_run_time}")
    except KeyboardInterrupt:
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
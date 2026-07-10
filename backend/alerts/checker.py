"""
alerts/checker.py — Evaluate all active alerts after each crawl.

Called by the scheduler immediately after crawl_generic_stores() and crawl_hypefly().

Logic per alert:
  1. Look up the product's latest and previous price from price_history
  2. Check if the trigger condition is met:
     - "any_drop":     current < previous
     - "below_price":  current < target_price  (and hasn't already fired for this price level)
  3. Fire notifications via notifier.dispatch()
  4. Mark the alert as triggered (last_triggered, trigger_count++)

Deduplication:
  - "any_drop" alerts fire once per price drop event. They won't re-fire if
    the price drops further until it first goes up and comes back down.
    We track this by comparing last_triggered against the price_history recorded_at.
  - "below_price" alerts fire once when crossing the threshold. They re-arm
    only after the price rises above target and drops below again.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pymongo.database import Database

from alerts.models import AlertRepository
from alerts.notifier import build_alert_payload, dispatch
from storage.price_history import PRICE_HISTORY_COLLECTION

log = logging.getLogger(__name__)


# ── Main entry point ──────────────────────────────────────────────────────────

def check_alerts(db: Database) -> dict:
    """
    Evaluate all active alerts. Called by the scheduler after each crawl.

    Returns:
        {"checked": int, "fired": int, "errors": int}
    """
    repo = AlertRepository(db)
    stats = {"checked": 0, "fired": 0, "errors": 0}

    alerts = repo.get_all_active()
    if not alerts:
        log.info("[alerts] No active alerts to check.")
        return stats

    log.info(f"[alerts] Checking {len(alerts)} active alerts...")

    for alert in alerts:
        stats["checked"] += 1
        try:
            fired = _evaluate_alert(db, repo, alert)
            if fired:
                stats["fired"] += 1
        except Exception as e:
            log.error(
                f"[alerts] Error evaluating alert {alert.get('_id')} "
                f"({alert.get('email')}, {alert.get('slug')}): {e}",
                exc_info=True,
            )
            stats["errors"] += 1

    log.info(
        f"[alerts] Done — checked: {stats['checked']}, "
        f"fired: {stats['fired']}, errors: {stats['errors']}"
    )
    return stats


# ── Per-alert evaluation ──────────────────────────────────────────────────────

def _evaluate_alert(db: Database, repo: AlertRepository, alert: dict) -> bool:
    """
    Evaluate a single alert. Returns True if a notification was sent.
    """
    slug = alert["slug"]
    source_store = alert.get("source_store")  # None = any store

    # Get latest 2 price records for this product
    price_event = _get_price_event(db, slug, source_store)
    if not price_event:
        return False  # No price history yet

    current_price = price_event["current_price"]
    previous_price = price_event["previous_price"]
    recorded_at = price_event["recorded_at"]

    # No drop — nothing to do
    if current_price >= previous_price:
        return False

    trigger = alert.get("trigger", "any_drop")

    # ── Trigger check ─────────────────────────────────────────────────────

    if trigger == "any_drop":
        # Fire if there's a drop and we haven't already fired for this specific event
        if not _already_fired_for_event(alert, recorded_at):
            return _fire(db, repo, alert, price_event)

    elif trigger == "below_price":
        target = alert.get("target_price")
        if target is None:
            return False

        # Fire if current price is now below target
        if current_price < target:
            # Don't re-fire if we already fired since the last time it was above target
            if not _already_fired_for_event(alert, recorded_at):
                return _fire(db, repo, alert, price_event)

    return False


def _already_fired_for_event(alert: dict, event_time: datetime) -> bool:
    """
    Returns True if the alert already fired for this specific price drop event.

    We consider it already-fired if last_triggered >= event_time (the recorded_at
    of the current price drop). This prevents duplicate notifications within the
    same crawl cycle or on scheduler restarts.
    """
    last = alert.get("last_triggered")
    if not last:
        return False
    # Ensure both are timezone-aware for comparison
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    return last >= event_time


# ── Price event lookup ────────────────────────────────────────────────────────

def _get_price_event(
    db: Database,
    slug: str,
    source_store: str | None,
) -> dict | None:
    """
    Get the latest price drop event for a product.

    Returns None if:
      - No price history exists
      - Only 1 record exists (can't compute a drop)
      - Price hasn't dropped (current >= previous)

    If source_store is None, uses the store with the lowest current price.
    """
    col = db[PRICE_HISTORY_COLLECTION]

    if source_store:
        records = list(
            col.find({"slug": slug, "source_store": source_store})
            .sort("recorded_at", -1)
            .limit(2)
        )
        if len(records) < 2:
            return None
        return {
            "current_price": records[0]["price"],
            "previous_price": records[1]["price"],
            "drop_pct": _pct_drop(records[0]["price"], records[1]["price"]),
            "drop_amount": round(records[1]["price"] - records[0]["price"], 2),
            "currency": records[0].get("currency", "INR"),
            "source_store": source_store,
            "recorded_at": records[0]["recorded_at"],
        }

    # No store filter — find the store with the lowest current price
    # Get latest record per store
    pipeline = [
        {"$match": {"slug": slug}},
        {"$sort": {"recorded_at": -1}},
        {"$group": {
            "_id": "$source_store",
            "price": {"$first": "$price"},
            "currency": {"$first": "$currency"},
            "recorded_at": {"$first": "$recorded_at"},
        }},
        {"$sort": {"price": 1}},
        {"$limit": 1},
    ]
    best = list(col.aggregate(pipeline))
    if not best:
        return None

    best_store = best[0]["_id"]
    # Now get 2 records for that store
    return _get_price_event(db, slug, best_store)


def _pct_drop(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return round(((previous - current) / previous) * 100, 1)


# ── Fire notification ─────────────────────────────────────────────────────────

def _fire(
    db: Database,
    repo: AlertRepository,
    alert: dict,
    price_event: dict,
) -> bool:
    """
    Build payload, dispatch notifications, mark alert as triggered.
    Returns True if at least one channel succeeded.
    """
    # Fetch product document for title / product_url
    product = db["products"].find_one(
        {"slug": alert["slug"]},
        {"title": 1, "product_url": 1, "image_url": 1},
    ) or {}

    payload = build_alert_payload(alert, product, price_event)
    results = dispatch(alert, payload)

    success = any(results.values())

    if success:
        repo.mark_triggered(alert["_id"], triggered_at=price_event["recorded_at"])
        log.info(
            f"[alerts] 🔔 Fired for {alert['email']} — "
            f"{alert['slug']} dropped to {price_event['currency']} "
            f"{price_event['current_price']:,.0f} "
            f"(channels: {results})"
        )
    else:
        log.warning(
            f"[alerts] All channels failed for {alert['email']} / {alert['slug']}. "
            f"Results: {results}"
        )

    return success
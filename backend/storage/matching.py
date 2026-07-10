"""
storage/matching.py — Cross-store product matching.

Matching cascade:
  Tier 1: SKU match       — sku field identical across stores (high confidence)
  Tier 2: Slug match      — normalized slug is identical (medium confidence)

Normalization for slug matching:
  "adidas-yeezy-boost-700-bright-blue" 
  "adidas-yeezy-boost-bright-blue-700"
  Both normalize to a sorted word set: {adidas, yeezy, boost, 700, bright, blue}
  If word sets match → same product

Why sorted word sets and not string similarity?
  String similarity (Levenshtein) is sensitive to word order.
  "bright blue 700" vs "700 bright blue" would score low similarity
  even though they're clearly the same product.
  Word set comparison is order-insensitive and fast.
"""

import re
from datetime import datetime, timezone
from pymongo import ASCENDING
from pymongo.database import Database

MATCHES_COLLECTION = "product_matches"
PRODUCTS_COLLECTION = "products"

# Words that add no matching value — ignore them
STOP_WORDS = {
    "the", "a", "an", "and", "or", "in", "of", "for",
    "retro", "og", "sp", "se", "gs", "wmns", "mens", "low", "high", "mid",
}


def setup_indexes(db: Database):
    col = db[MATCHES_COLLECTION]
    col.create_index("sku", name="sku_idx", sparse=True)
    col.create_index("best_price", name="best_price_idx")
    col.create_index(
        [("listings.slug", ASCENDING), ("listings.store", ASCENDING)],
        name="listings_idx"
    )
    print("[matching] Indexes ensured.")


def normalize_slug(slug: str) -> frozenset:
    """
    Convert a slug to a normalized word set for comparison.

    "adidas-yeezy-boost-bright-blue-700" → frozenset({adidas, yeezy, boost, bright, blue, 700})
    Numbers are kept — "700" and "350" are meaningfully different.
    Stop words are removed.
    """
    words = re.split(r"[-_\s]+", slug.lower())
    return frozenset(w for w in words if w and w not in STOP_WORDS)


def run_matching(db: Database) -> dict:
    """
    Find and store all product matches across stores.

    This is designed to be re-runnable — it upserts matches,
    so running it after a new crawl updates existing matches
    and adds new ones without creating duplicates.

    Returns a stats dict.
    """
    setup_indexes(db)

    products_col = db[PRODUCTS_COLLECTION]
    matches_col = db[MATCHES_COLLECTION]

    # Load all products with their key fields
    print("[matching] Loading all products...")
    all_products = list(products_col.find(
        {},
        {"slug": 1, "source_store": 1, "sku": 1, "title": 1, "price": 1, "currency": 1, "_id": 0}
    ))
    print(f"[matching] Loaded {len(all_products)} products")

    # ── Tier 1: SKU Matching ──────────────────────────────────────────────────
    # Group all products by SKU
    sku_groups: dict[str, list] = {}
    no_sku = []

    for p in all_products:
        sku = p.get("sku")
        if sku and sku.strip():
            sku_groups.setdefault(sku.strip().upper(), []).append(p)
        else:
            no_sku.append(p)

    sku_matches = 0
    for sku, products in sku_groups.items():
        # Only a match if products come from more than one store
        stores = {p["source_store"] for p in products}
        if len(stores) < 2:
            continue

        _upsert_match(matches_col, sku=sku, match_type="sku",
                      confidence="high", products=products)
        sku_matches += 1

    print(f"[matching] Tier 1 (SKU): {sku_matches} matches found")

    # ── Tier 2: Slug Word-Set Matching ───────────────────────────────────────
    # Only run on products that weren't matched by SKU
    matched_skus = set(sku_groups.keys())
    unmatched = [
        p for p in all_products
        if not (p.get("sku") and p["sku"].strip().upper() in matched_skus
                and len({q["source_store"] for q in sku_groups.get(p["sku"].strip().upper(), [])}) > 1)
    ]

    # Group by normalized slug word set
    slug_groups: dict[frozenset, list] = {}
    for p in unmatched:
        key = normalize_slug(p["slug"])
        if len(key) >= 3:  # Require at least 3 meaningful words to avoid false matches
            slug_groups.setdefault(key, []).append(p)

    slug_matches = 0
    for word_set, products in slug_groups.items():
        stores = {p["source_store"] for p in products}
        if len(stores) < 2:
            continue

        # Use the most common SKU if any products have one
        skus = [p.get("sku") for p in products if p.get("sku")]
        sku = skus[0] if skus else None

        _upsert_match(matches_col, sku=sku, match_type="slug",
                      confidence="medium", products=products,
                      word_set=word_set)
        slug_matches += 1

    print(f"[matching] Tier 2 (Slug): {slug_matches} matches found")

    total = sku_matches + slug_matches
    print(f"[matching] Total: {total} cross-store matches")

    return {
        "total_products": len(all_products),
        "sku_matches": sku_matches,
        "slug_matches": slug_matches,
        "total_matches": total,
    }


def _upsert_match(col, sku, match_type, confidence, products, word_set=None):
    """Write or update a match document."""
    now = datetime.now(timezone.utc)

    listings = []
    for p in products:
        listings.append({
            "slug": p["slug"],
            "store": p["source_store"],
            "price": p.get("price"),
            "currency": p.get("currency", "INR"),
        })

    # Compute best price across all listings
    prices = [l["price"] for l in listings if l["price"] is not None]
    best_price = min(prices) if prices else None
    best_store = None
    if best_price is not None:
        for l in listings:
            if l["price"] == best_price:
                best_store = l["store"]
                break

    # Price spread — how much you save by picking the best store
    price_spread = None
    if len(prices) >= 2:
        price_spread = round(max(prices) - min(prices), 2)

    # Build filter key — prefer SKU, fall back to sorted word set string
    if sku:
        filter_key = {"sku": sku}
    else:
        filter_key = {"word_set_key": str(sorted(word_set))}

    doc = {
        "sku": sku,
        "match_type": match_type,
        "confidence": confidence,
        "listings": listings,
        "stores": list({l["store"] for l in listings}),
        "best_price": best_price,
        "best_price_store": best_store,
        "price_spread": price_spread,
        "updated_at": now,
    }

    if word_set:
        doc["word_set_key"] = str(sorted(word_set))

    col.update_one(
        filter_key,
        {
            "$set": doc,
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def get_match_by_sku(db: Database, sku: str) -> dict | None:
    """Get a match document by SKU."""
    return db[MATCHES_COLLECTION].find_one({"sku": sku.upper()}, {"_id": 0})


def get_match_by_slug(db: Database, slug: str, store: str) -> dict | None:
    """Find the match document that contains a specific product listing."""
    return db[MATCHES_COLLECTION].find_one(
        {"listings": {"$elemMatch": {"slug": slug, "store": store}}},
        {"_id": 0}
    )


def get_best_deals(db: Database, limit: int = 20, min_spread: float = 500) -> list[dict]:
    """
    Return matched products with the biggest price difference across stores.
    Sorted by price_spread descending — biggest savings opportunity first.
    """
    col = db[MATCHES_COLLECTION]
    cursor = (
        col.find(
            {"price_spread": {"$gte": min_spread}},
            {"_id": 0}
        )
        .sort("price_spread", -1)
        .limit(limit)
    )
    return list(cursor)


def get_match_stats(db: Database) -> dict:
    """Return summary stats about the matching collection."""
    col = db[MATCHES_COLLECTION]
    total = col.count_documents({})
    by_type = list(col.aggregate([
        {"$group": {"_id": "$match_type", "count": {"$sum": 1}}}
    ]))
    by_confidence = list(col.aggregate([
        {"$group": {"_id": "$confidence", "count": {"$sum": 1}}}
    ]))
    return {
        "total_matches": total,
        "by_type": {d["_id"]: d["count"] for d in by_type},
        "by_confidence": {d["_id"]: d["count"] for d in by_confidence},
    }
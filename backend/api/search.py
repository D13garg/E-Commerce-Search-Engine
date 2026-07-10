"""
api/search.py — MongoDB query construction and execution.

Why separate from main.py?
  Routes declare WHAT endpoints exist.
  This file handles HOW to query MongoDB.
  Keeping them separate means you can test query logic independently
  from HTTP handling, and swap query strategies without touching routes.

MongoDB Text Search explained:
  We use $text search which requires a text index on title/brand/category.
  The index is created in setup_indexes() called at startup.

  $text search is:
    - Fast (index-backed)
    - Multi-field (searches title AND brand AND category simultaneously)
    - Language-aware (handles stemming: "running" matches "run")
    - Limitation: no fuzzy matching (typos won't match)

  For fuzzy/semantic search, we'd replace $text with Atlas Search or
  a vector similarity query — but the route signatures stay the same.

Query building strategy:
  We build a MongoDB filter dict incrementally.
  Each optional parameter adds a clause only if provided.
  This avoids messy if/else chains and is easy to extend.
"""

from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING, TEXT
from api.schemas import ProductResponse, VariantResponse, SearchResponse

PRODUCTS_COLLECTION = "products"


def setup_indexes(db: Database):
    """
    Create indexes needed for search.
    Called once at API startup.

    Text index: enables $text search across title, brand, category.
    Compound index on (source_store, category): speeds up filtered queries.
    Price index: speeds up range queries and sorting.

    Why not create these in storage.py?
      storage.py creates indexes for write performance (upsert key).
      These indexes are for read performance (search queries).
      Separating them makes the purpose of each index clear.
    """
    col = db[PRODUCTS_COLLECTION]

    # Text index for full-text search
    # weights control how much each field contributes to relevance score
    col.create_index(
        [("title", TEXT), ("brand", TEXT), ("category", TEXT)],
        weights={"title": 10, "brand": 5, "category": 3},
        name="text_search_idx",
        default_language="english",
    )

    # Indexes for filtered queries
    col.create_index("source_store", name="source_store_idx")
    col.create_index("brand", name="brand_idx")
    col.create_index("category", name="category_idx")
    col.create_index("price", name="price_idx")

    print("[api] Search indexes ensured.")


def build_filter(
    q: str = None,
    brand: str = None,
    store: str = None,
    category: str = None,
    min_price: float = None,
    max_price: float = None,
    available: bool = None,
) -> dict:
    """
    Build a MongoDB filter dict from search parameters.

    Each parameter is optional — only adds a clause if provided.
    This produces the minimal query needed, which is fastest.
    """
    filter_dict = {}

    # Full text search — requires text index
    if q and q.strip():
        filter_dict["$text"] = {"$search": q.strip()}

    # Exact match filters
    if brand:
        # case-insensitive brand match
        filter_dict["brand"] = {"$regex": f"^{brand}$", "$options": "i"}

    if store:
        filter_dict["source_store"] = store.lower()

    if category:
        filter_dict["category"] = {"$regex": f"^{category}$", "$options": "i"}

    # Price range filter
    if min_price is not None or max_price is not None:
        price_filter = {}
        if min_price is not None:
            price_filter["$gte"] = min_price
        if max_price is not None:
            price_filter["$lte"] = max_price
        filter_dict["price"] = price_filter

    # Availability filter — checks if any variant is available
    if available is True:
        filter_dict["variants"] = {"$elemMatch": {"available": True}}
    elif available is False:
        filter_dict["variants"] = {"$not": {"$elemMatch": {"available": True}}}

    return filter_dict


def search_products(
    db: Database,
    q: str = None,
    brand: str = None,
    store: str = None,
    category: str = None,
    min_price: float = None,
    max_price: float = None,
    available: bool = None,
    page: int = 1,
    limit: int = 20,
) -> SearchResponse:
    """
    Execute a product search and return paginated results.

    Sorting strategy:
      - With text query: sort by text relevance score (best match first)
      - Without text query: sort by price ascending (browsing mode)
    """
    col = db[PRODUCTS_COLLECTION]
    filter_dict = build_filter(q, brand, store, category, min_price, max_price, available)

    # Count total matching documents (for pagination metadata)
    total = col.count_documents(filter_dict)

    # Pagination
    skip = (page - 1) * limit
    pages = max(1, -(-total // limit))  # ceiling division

    # Build projection — only fetch fields we need
    projection = {
        "_id": 0,
        "title": 1,
        "brand": 1,
        "sku": 1,
        "slug": 1,
        "category": 1,
        "price": 1,
        "currency": 1,
        "image_url": 1,
        "product_url": 1,
        "source_store": 1,
        "variants": 1,
    }

    # Sort: by text score if searching, by price if browsing
    #
    # Availability boost — the key ranking improvement:
    #   We add "has_available" as the PRIMARY sort key (descending).
    #   This means all in-stock products rank above all OOS products.
    #   Within each group, text score (BM25) determines order.
    #
    #   Why two-level sort instead of score multiplication?
    #     MongoDB does not support score multiplication in find() queries.
    #     An aggregation pipeline could do it but is significantly slower
    #     and more complex. Two-level sort achieves the same user-visible
    #     result: available products always come first.
    #
    #   "has_available" is a boolean field we add to the projection
    #   by computing it from variants at query time using $addFields.
    #   We use an aggregation pipeline here instead of find() to support this.
    if q and q.strip():
        projection["score"] = {"$meta": "textScore"}

        pipeline = [
            # Step 1: filter matching documents
            {"$match": {"$and": [
                {"$text": {"$search": q.strip()}},
                *[{k: v} for k, v in filter_dict.items() if k != "$text"]
            ]}},
            # Step 2: add textScore and has_available as computed fields
            {"$addFields": {
                "score": {"$meta": "textScore"},
                # has_available = true if any variant has available: true
                "has_available": {
                    "$anyElementTrue": {
                        "$map": {
                            "input": {"$ifNull": ["$variants", []]},
                            "as": "v",
                            "in": {"$eq": ["$$v.available", True]}
                        }
                    }
                }
            }},
            # Step 3: sort — available first, then by BM25 score
            {"$sort": {"has_available": -1, "score": -1}},
            # Step 4: pagination
            {"$skip": skip},
            {"$limit": limit},
            # Step 5: project only needed fields
            {"$project": {k: v for k, v in projection.items()}},
        ]

        cursor = col.aggregate(pipeline)
    else:
        # No text query — browsing mode
        # Sort: available first, then by price ascending
        pipeline = [
            {"$match": filter_dict},
            {"$addFields": {
                "has_available": {
                    "$anyElementTrue": {
                        "$map": {
                            "input": {"$ifNull": ["$variants", []]},
                            "as": "v",
                            "in": {"$eq": ["$$v.available", True]}
                        }
                    }
                }
            }},
            {"$sort": {"has_available": -1, "price": 1}},
            {"$skip": skip},
            {"$limit": limit},
            {"$project": {k: v for k, v in projection.items()}},
        ]
        cursor = col.aggregate(pipeline)

    results = [_to_response(doc) for doc in cursor]

    return SearchResponse(
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        results=results,
    )


def get_product(db: Database, slug: str, store: str = None) -> ProductResponse | None:
    """Fetch a single product by slug, optionally filtered by store."""
    col = db[PRODUCTS_COLLECTION]
    filter_dict = {"slug": slug}
    if store:
        filter_dict["source_store"] = store.lower()

    doc = col.find_one(filter_dict, {"_id": 0})
    return _to_response(doc) if doc else None


def get_brands(db: Database, store: str = None) -> list[str]:
    """Return all unique brands, optionally filtered by store."""
    col = db[PRODUCTS_COLLECTION]
    filter_dict = {"brand": {"$ne": None}}
    if store:
        filter_dict["source_store"] = store.lower()

    brands = col.distinct("brand", filter_dict)
    return sorted(b for b in brands if b)


def get_stores(db: Database) -> list[str]:
    """Return all indexed store names."""
    return sorted(db[PRODUCTS_COLLECTION].distinct("source_store"))


def get_categories(db: Database, store: str = None) -> list[str]:
    """Return all unique categories, optionally filtered by store."""
    col = db[PRODUCTS_COLLECTION]
    filter_dict = {}
    if store:
        filter_dict["source_store"] = store.lower()
    categories = col.distinct("category", filter_dict)
    return sorted(c for c in categories if c)


def _to_response(doc: dict) -> ProductResponse:
    """Convert a raw MongoDB document to a ProductResponse."""
    variants = [
        VariantResponse(
            size=v.get("size", ""),
            price=v.get("price"),
            available=v.get("available", False),
        )
        for v in doc.get("variants", [])
    ]

    available_sizes = [v.size for v in variants if v.available]

    return ProductResponse(
        title=doc.get("title", ""),
        brand=doc.get("brand"),
        sku=doc.get("sku"),
        slug=doc.get("slug", ""),
        category=doc.get("category", ""),
        price=doc.get("price"),
        currency=doc.get("currency", "INR"),
        image_url=doc.get("image_url"),
        product_url=doc.get("product_url", ""),
        source_store=doc.get("source_store", ""),
        variants=variants,
        available_sizes=available_sizes,
    )


# ── Autocomplete Suggestions ──────────────────────────────────────────────────

SUGGESTIONS_COLLECTION = "suggestions"

def get_suggestions(
    db: Database,
    q: str,
    limit: int = 8,
) -> list[dict]:
    """
    Return autocomplete suggestions for a prefix query.

    Strategy:
      1. Anchor prefix match on term_lower (^q) — fast with index
      2. Rank by: type priority (brand > model > product), then count
      3. Deduplicate — don't show "Nike" and "nike" both

    Why regex prefix and not $text?
      $text search tokenizes and stems — it's designed for full-word matching.
      Autocomplete needs PREFIX matching — "ni" should match "Nike", not
      search for documents containing "ni" as a word.
      Anchored regex (^prefix) on an indexed field is the right tool here.

    Performance:
      MongoDB uses the term_lower index for anchored regex (^pattern).
      At 27k unique suggestion terms, this is sub-5ms.
      At 500k terms you'd switch to Atlas Search's autocomplete operator.
    """
    if not q or len(q.strip()) < 1:
        return []

    prefix = q.strip().lower()
    col = db[SUGGESTIONS_COLLECTION]

    # Anchored prefix regex — uses index efficiently
    regex = {"$regex": f"^{re.escape(prefix)}", "$options": "i"}

    # Type priority for ranking: brand first, then model, then product
    type_priority = {"brand": 0, "model": 1, "product": 2}

    raw = list(
        col.find(
            {"term_lower": regex},
            {"_id": 0, "term": 1, "type": 1, "count": 1,
             "brands": 1, "min_price": 1, "has_available": 1}
        )
        .sort("count", -1)
        .limit(limit * 3)  # fetch more, we'll re-rank and trim
    )

    # Re-rank: type priority first, then count
    raw.sort(key=lambda x: (type_priority.get(x["type"], 3), -x["count"]))

    # Deduplicate by normalized term (case-insensitive)
    seen = set()
    results = []
    for item in raw:
        key = item["term"].lower()
        if key not in seen:
            seen.add(key)
            results.append(item)
        if len(results) >= limit:
            break

    return results


import re  # needed for re.escape in get_suggestions
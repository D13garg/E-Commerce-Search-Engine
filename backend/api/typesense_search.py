"""
api/typesense_search.py — Search via Typesense instead of MongoDB.

This replaces the MongoDB $text search in search.py for the /search endpoint.
MongoDB remains the source of truth for all other operations (price history,
matching, product detail). Only the search query goes through Typesense.

Why keep MongoDB for everything else?
  Typesense is optimised for search. It lacks:
    - Aggregation pipelines (price history, matching)
    - Complex joins (cross-store matching)
    - Time-series queries (price drops)
  MongoDB handles those well. Use the right tool for each job.

Typesense search parameters explained:
  q             — the search query
  query_by      — which fields to search, in priority order
  query_by_weights — relative importance of each field
  num_typos     — how many character errors to tolerate (2 = "Adidass" → Adidas)
  prefix        — match partial words ("jor" → "Jordan")
  filter_by     — structured filters (price range, store, availability)
  sort_by       — ranking formula
  per_page      — results per page
  page          — page number
"""

import typesense
from api.typesense_client import get_client, COLLECTION_NAME
from api.schemas import ProductResponse, SearchResponse, VariantResponse
from pymongo.database import Database
from config import PRODUCTS_COLLECTION


def typesense_search(
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
    Search products via Typesense with fuzzy matching and fast ranking.

    Falls back to MongoDB search if Typesense is unavailable.
    This ensures the API never goes down just because Typesense restarted.
    """
    try:
        return _typesense_search(
            db, q, brand, store, category,
            min_price, max_price, available, page, limit
        )
    except Exception as e:
        print(f"[typesense] Search failed, falling back to MongoDB: {e}")
        from api.search import search_products
        return search_products(
            db=db, q=q, brand=brand, store=store, category=category,
            min_price=min_price, max_price=max_price,
            available=available, page=page, limit=limit
        )


def _typesense_search(
    db, q, brand, store, category,
    min_price, max_price, available, page, limit
) -> SearchResponse:

    client = get_client()

    # ── Build filter_by string ────────────────────────────────────────────────
    # Typesense filter syntax: "field:=value && field:>100"
    filters = []

    if store:
        filters.append(f"source_store:={store}")

    if brand:
        # Case-insensitive brand filter
        filters.append(f"brand:={brand}")

    if category:
        filters.append(f"category:={category}")

    if available is True:
        filters.append("has_available:=true")

    if min_price is not None and max_price is not None:
        filters.append(f"price:[{int(min_price)}..{int(max_price)}]")
    elif min_price is not None:
        filters.append(f"price:>={int(min_price)}")
    elif max_price is not None:
        filters.append(f"price:<={int(max_price)}]")

    filter_by = " && ".join(filters) if filters else ""

    # ── Sort formula ──────────────────────────────────────────────────────────
    # has_available DESC → available products first
    # _text_match DESC   → then by relevance
    # price ASC          → then by price (cheapest first)
    if q and q.strip():
        sort_by = "has_available:desc,_text_match:desc,price:asc"
    else:
        sort_by = "has_available:desc,price:asc"

    # ── Search parameters ─────────────────────────────────────────────────────
    search_params = {
        "q":                  q.strip() if q and q.strip() else "*",
        "query_by":           "title,brand,sku,category",
        "query_by_weights":   "10,5,3,2",
        # num_typos: 0=exact, 1=one typo, 2=two typos
        # 2 handles "Adidass", "Niike", "Yezy" etc.
        "num_typos":          "2",
        # prefix: true means "jor" matches "Jordan"
        "prefix":             "true",
        # highlight_full_fields for better relevance on short titles
        "highlight_full_fields": "title,brand",
        "per_page":           limit,
        "page":               page,
        "sort_by":            sort_by,
    }

    if filter_by:
        search_params["filter_by"] = filter_by

    # ── Execute search ────────────────────────────────────────────────────────
    result = client.collections[COLLECTION_NAME].documents.search(search_params)

    total = result["found"]
    pages = max(1, -(-total // limit))  # ceiling division

    # ── Fetch full documents from MongoDB ─────────────────────────────────────
    # Typesense stores a subset of fields for search.
    # For the full product (variants, etc.) we fetch from MongoDB.
    # This is a deliberate tradeoff — Typesense for search, MongoDB for data.
    hits = result.get("hits", [])
    slugs_stores = []
    for hit in hits:
        doc = hit["document"]
        slugs_stores.append((doc["slug"], doc["source_store"]))

    if not slugs_stores:
        return SearchResponse(total=total, page=page, limit=limit, pages=pages, results=[])

    # Fetch full documents from MongoDB preserving Typesense order
    mongo_col = db[PRODUCTS_COLLECTION]
    or_clauses = [{"slug": s, "source_store": st} for s, st in slugs_stores]
    mongo_docs = {
        f"{d['slug']}__{d['source_store']}": d
        for d in mongo_col.find(
            {"$or": or_clauses},
            {"_id": 0}
        )
    }

    # Reconstruct results in Typesense ranking order
    results = []
    for slug, store_name in slugs_stores:
        key = f"{slug}__{store_name}"
        doc = mongo_docs.get(key)
        if not doc:
            continue

        variants = [
            VariantResponse(
                size=v.get("size", ""),
                price=v.get("price"),
                available=v.get("available", False),
            )
            for v in doc.get("variants", [])
        ]

        results.append(ProductResponse(
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
            available_sizes=[v.size for v in variants if v.available],
        ))

    return SearchResponse(
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        results=results,
    )
"""
services/typesense_service.py — Search execution via Typesense with database fallback support.
"""

from pymongo.database import Database
import typesense

from core.typesense_client import get_client, COLLECTION_NAME
from schemas.product import ProductResponse, VariantResponse, SearchResponse
from repositories import product_repo


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
    Search products via Typesense.
    If Typesense fails, it will raise an exception that caller can handle (e.g. fallback).
    """
    client = get_client()

    # Build filter_by string for Typesense
    filters = []
    if store:
        filters.append(f"source_store:={store}")
    if brand:
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
        filters.append(f"price:<={int(max_price)}")

    filter_by = " && ".join(filters) if filters else ""

    # Sort order
    if q and q.strip():
        sort_by = "has_available:desc,_text_match:desc,price:asc"
    else:
        sort_by = "has_available:desc,price:asc"

    search_params = {
        "q":                  q.strip() if q and q.strip() else "*",
        "query_by":           "title,brand,sku,category",
        "query_by_weights":   "10,5,3,2",
        "num_typos":          "2",
        "prefix":             "true",
        "highlight_full_fields": "title,brand",
        "per_page":           limit,
        "page":               page,
        "sort_by":            sort_by,
    }

    if filter_by:
        search_params["filter_by"] = filter_by

    result = client.collections[COLLECTION_NAME].documents.search(search_params)

    total = result["found"]
    pages = max(1, -(-total // limit))

    hits = result.get("hits", [])
    slugs_stores = []
    for hit in hits:
        doc = hit["document"]
        slugs_stores.append((doc["slug"], doc["source_store"]))

    if not slugs_stores:
        return SearchResponse(total=total, page=page, limit=limit, pages=pages, results=[])

    # Fetch full documents from MongoDB using repository
    raw_docs = product_repo.get_products_by_slugs_and_stores(db, slugs_stores)
    mongo_docs = {
        f"{d['slug']}__{d['source_store']}": d
        for d in raw_docs
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

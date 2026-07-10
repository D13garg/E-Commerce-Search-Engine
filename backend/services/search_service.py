"""
services/search_service.py — Business logic for sneaker searches, suggestions, and aggregation filters.
"""

from pymongo.database import Database

from core.exceptions import ProductNotFound
from schemas.product import SearchResponse, ProductResponse, VariantResponse
from repositories import product_repo
from services.query_parser import parse_query
from services.typesense_service import typesense_search


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
    Search products across stores. Integrates NLP query understanding and falls back
    to MongoDB if the Typesense service is unavailable.
    """
    # 1. NLP Query understanding: Only run if other filters are not explicitly set
    if q and (min_price is None and max_price is None
              and available is None and store is None and brand is None):
        parsed = parse_query(q)
        if parsed.has_extracted_anything():
            q = parsed.q
            min_price = parsed.min_price
            max_price = parsed.max_price
            available = parsed.available
            store = parsed.store or store

    # 2. Search via Typesense with database fallback
    try:
        return typesense_search(
            db=db,
            q=q,
            brand=brand,
            store=store,
            category=category,
            min_price=min_price,
            max_price=max_price,
            available=available,
            page=page,
            limit=limit,
        )
    except Exception as e:
        print(f"[search_service] Typesense search failed, falling back to MongoDB: {e}")
        total, docs = product_repo.search_products(
            db=db,
            q=q,
            brand=brand,
            store=store,
            category=category,
            min_price=min_price,
            max_price=max_price,
            available=available,
            page=page,
            limit=limit,
        )

        results = [_map_to_response(doc) for doc in docs]
        pages = max(1, -(-total // limit))

        return SearchResponse(
            total=total,
            page=page,
            limit=limit,
            pages=pages,
            results=results,
        )


def get_product_by_slug(db: Database, slug: str, store: str = None) -> list[ProductResponse]:
    """Fetch product details by slug. Raises ProductNotFound if not found."""
    if store:
        doc = product_repo.get_product(db, slug, store)
        if not doc:
            raise ProductNotFound(slug, store)
        return [_map_to_response(doc)]

    results = []
    stores = product_repo.get_stores(db)
    for s in stores:
        doc = product_repo.get_product(db, slug, s)
        if doc:
            results.append(_map_to_response(doc))

    if not results:
        raise ProductNotFound(slug)

    return results


def get_suggestions(db: Database, q: str, limit: int = 8) -> list[dict]:
    """Autocomplete suggestions for front-end search box."""
    raw = product_repo.get_suggestions(db, q, limit)

    type_priority = {"brand": 0, "model": 1, "product": 2}
    raw.sort(key=lambda x: (type_priority.get(x["type"], 3), -x["count"]))

    # Deduplicate terms case-insensitively
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


def get_brands(db: Database, store: str = None) -> list[str]:
    """Get all unique brands, optionally filtered by store."""
    return product_repo.get_brands(db, store)


def get_stores(db: Database) -> list[str]:
    """Get all unique store names."""
    return product_repo.get_stores(db)


def get_categories(db: Database, store: str = None) -> list[str]:
    """Get all unique categories, optionally filtered by store."""
    return product_repo.get_categories(db, store)


def setup_indexes(db: Database):
    """Ensure MongoDB indexes are initialized."""
    product_repo.setup_indexes(db)


def get_total_count(db: Database) -> int:
    """Return the total count of products in the database."""
    return product_repo.get_total_count(db)



def _map_to_response(doc: dict) -> ProductResponse:
    """Helper to map MongoDB document dict to ProductResponse schema."""
    variants = [
        VariantResponse(
            size=v.get("size", ""),
            price=v.get("price"),
            available=v.get("available", False),
        )
        for v in doc.get("variants", [])
    ]

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
        available_sizes=[v.size for v in variants if v.available],
    )

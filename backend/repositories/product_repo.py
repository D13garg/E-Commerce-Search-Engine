"""
repositories/product_repo.py — MongoDB queries and indexing for products.
"""

import re
from datetime import datetime, timezone
from pymongo import TEXT, ASCENDING
from pymongo.database import Database

from core.config import settings
from models.product import Product
from repositories import price_repo


def setup_indexes(db: Database):
    """Create all read/write indexes for the products collection."""
    col = db[settings.PRODUCTS_COLLECTION]

    # Unique index for upserts
    col.create_index(
        [("slug", ASCENDING), ("source_store", ASCENDING)],
        unique=True,
        name="slug_store_unique"
    )

    # Text index for full-text search
    col.create_index(
        [("title", TEXT), ("brand", TEXT), ("category", TEXT)],
        weights={"title": 10, "brand": 5, "category": 3},
        name="text_search_idx",
        default_language="english",
    )

    # Helper indexes for filters and sorting
    col.create_index("source_store", name="source_store_idx")
    col.create_index("brand", name="brand_idx")
    col.create_index("category", name="category_idx")
    col.create_index("price", name="price_idx")

    print("[product_repo] Product indexes ensured.")


def upsert_product(db: Database, product: Product) -> dict:
    """Insert or update a product document, and record price history if changed."""
    now = datetime.now(timezone.utc)
    col = db[settings.PRODUCTS_COLLECTION]

    doc = product.model_dump(exclude={"scraped_at", "last_seen"})
    doc["last_seen"] = now

    result = col.update_one(
        {"slug": product.slug, "source_store": product.source_store},
        {
            "$set": doc,
            "$setOnInsert": {"scraped_at": now},
        },
        upsert=True,
    )

    # Record price history — only writes if price changed
    if product.price is not None:
        price_changed = price_repo.record_price(
            db=db,
            slug=product.slug,
            source_store=product.source_store,
            price=product.price,
            currency=product.currency,
        )
        if price_changed and result.matched_count > 0:
            print(f"[product_repo] 💰 Price change recorded for: {product.title}")

    return {
        "matched_count": result.matched_count,
        "upserted_id": result.upserted_id,
    }


def get_product(db: Database, slug: str, store: str = None) -> dict | None:
    """Fetch a single raw product document by slug, optionally filtered by store."""
    col = db[settings.PRODUCTS_COLLECTION]
    filter_dict = {"slug": slug}
    if store:
        filter_dict["source_store"] = store.lower()

    return col.find_one(filter_dict, {"_id": 0})


def get_products_by_slugs_and_stores(db: Database, list_of_pairs: list) -> list[dict]:
    """Fetch multiple product documents by slug & store pairs, maintaining no specific order."""
    col = db[settings.PRODUCTS_COLLECTION]
    or_clauses = [{"slug": s, "source_store": st} for s, st in list_of_pairs]
    return list(col.find({"$or": or_clauses}, {"_id": 0}))


def get_brands(db: Database, store: str = None) -> list[str]:
    """Return all unique brands, optionally filtered by store."""
    col = db[settings.PRODUCTS_COLLECTION]
    filter_dict = {"brand": {"$ne": None}}
    if store:
        filter_dict["source_store"] = store.lower()

    brands = col.distinct("brand", filter_dict)
    return sorted(b for b in brands if b)


def get_stores(db: Database) -> list[str]:
    """Return all unique store names."""
    return sorted(db[settings.PRODUCTS_COLLECTION].distinct("source_store"))


def get_categories(db: Database, store: str = None) -> list[str]:
    """Return all unique categories, optionally filtered by store."""
    col = db[settings.PRODUCTS_COLLECTION]
    filter_dict = {}
    if store:
        filter_dict["source_store"] = store.lower()
    categories = col.distinct("category", filter_dict)
    return sorted(c for c in categories if c)


def build_filter(
    q: str = None,
    brand: str = None,
    store: str = None,
    category: str = None,
    min_price: float = None,
    max_price: float = None,
    available: bool = None,
) -> dict:
    """Build a MongoDB query filter dict from parameters."""
    filter_dict = {}

    if q and q.strip():
        filter_dict["$text"] = {"$search": q.strip()}

    if brand:
        filter_dict["brand"] = {"$regex": f"^{brand}$", "$options": "i"}

    if store:
        filter_dict["source_store"] = store.lower()

    if category:
        filter_dict["category"] = {"$regex": f"^{category}$", "$options": "i"}

    if min_price is not None or max_price is not None:
        price_filter = {}
        if min_price is not None:
            price_filter["$gte"] = min_price
        if max_price is not None:
            price_filter["$lte"] = max_price
        filter_dict["price"] = price_filter

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
) -> tuple[int, list[dict]]:
    """Execute product search on MongoDB, returning (total_count, documents)."""
    col = db[settings.PRODUCTS_COLLECTION]
    filter_dict = build_filter(q, brand, store, category, min_price, max_price, available)

    total = col.count_documents(filter_dict)
    skip = (page - 1) * limit

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

    if q and q.strip():
        projection["score"] = {"$meta": "textScore"}
        pipeline = [
            {"$match": {"$and": [
                {"$text": {"$search": q.strip()}},
                *[{k: v} for k, v in filter_dict.items() if k != "$text"]
            ]}},
            {"$addFields": {
                "score": {"$meta": "textScore"},
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
            {"$sort": {"has_available": -1, "score": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {"$project": projection},
        ]
        cursor = col.aggregate(pipeline)
    else:
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
            {"$project": projection},
        ]
        cursor = col.aggregate(pipeline)

    return total, list(cursor)


SUGGESTIONS_COLLECTION = "suggestions"


def get_suggestions(db: Database, q: str, limit: int = 8) -> list[dict]:
    """Query autocomplete suggestions from suggestions collection."""
    if not q or len(q.strip()) < 1:
        return []

    prefix = q.strip().lower()
    col = db[SUGGESTIONS_COLLECTION]
    regex = {"$regex": f"^{re.escape(prefix)}", "$options": "i"}

    # Retrieve more candidate documents than limit, since we re-rank and dedup in service
    cursor = (
        col.find(
            {"term_lower": regex},
            {"_id": 0, "term": 1, "type": 1, "count": 1,
             "brands": 1, "min_price": 1, "has_available": 1}
        )
        .sort("count", -1)
        .limit(limit * 3)
    )
    return list(cursor)


def get_total_count(db: Database) -> int:
    """Return the total number of products in the database."""
    return db[settings.PRODUCTS_COLLECTION].count_documents({})


"""
core/typesense_client.py — Typesense connection and collection schema.
"""

import typesense
from core.config import settings

COLLECTION_NAME = "products"


def get_client() -> typesense.Client:
    return typesense.Client({
        "nodes": [{
            "host": settings.TYPESENSE_HOST,
            "port": settings.TYPESENSE_PORT,
            "protocol": "http",
        }],
        "api_key": settings.TYPESENSE_API_KEY,
        "connection_timeout_seconds": 5,
    })


# Collection schema — defines what Typesense indexes and how
PRODUCTS_SCHEMA = {
    "name": COLLECTION_NAME,
    "fields": [
        # Searchable text fields
        {"name": "title",        "type": "string"},
        {"name": "brand",        "type": "string",   "optional": True, "facet": True},
        {"name": "sku",          "type": "string",   "optional": True},
        {"name": "slug",         "type": "string"},
        {"name": "category",     "type": "string",   "optional": True, "facet": True},
        {"name": "source_store", "type": "string",   "facet": True},

        # Numeric — for range filtering and sorting
        {"name": "price",        "type": "float",    "optional": False},

        # Boolean — availability boost
        {"name": "has_available","type": "bool",     "facet": True},

        # String array — size faceting (future)
        {"name": "available_sizes", "type": "string[]", "facet": True, "optional": True},

        # Stored but not searchable — returned in results only
        {"name": "image_url",    "type": "string",   "optional": True, "index": False},
        {"name": "product_url",  "type": "string",   "index": False},
    ],
    # Default sorting when no query — available first, then cheapest
    "default_sorting_field": "price",
    # Token separators — treat hyphens as word separators
    "token_separators": ["-", "_", "/"],
}


def setup_collection(client: typesense.Client, force_recreate: bool = False):
    """
    Create the products collection in Typesense.
    If force_recreate=True, drops and recreates (used during sync).
    """
    try:
        existing = client.collections[COLLECTION_NAME].retrieve()
        if force_recreate:
            print(f"[typesense] Dropping existing collection...")
            client.collections[COLLECTION_NAME].delete()
            raise typesense.exceptions.ObjectNotFound
        else:
            print(f"[typesense] Collection exists with {existing['num_documents']} documents.")
            return existing
    except typesense.exceptions.ObjectNotFound:
        print(f"[typesense] Creating collection '{COLLECTION_NAME}'...")
        result = client.collections.create(PRODUCTS_SCHEMA)
        print(f"[typesense] Collection created.")
        return result

"""
api/typesense_client.py — Typesense connection and collection schema.

Why this schema design:

  FIELDS:
    title, brand, sku, slug, category — standard searchable text fields
    source_store — facet field: filter by store without full-text search
    price — float: range filtering (min_price, max_price)
    has_available — bool: filter to in-stock products
    available_sizes — string[]: facet for size filtering later
    image_url, product_url — stored but not indexed (no search on these)

  RANKING RULES (in priority order):
    1. text_match    — BM25 relevance score (how well query matches)
    2. has_available — in-stock products rank above OOS
    3. price         — cheaper products rank higher within same relevance

  TYPO TOLERANCE:
    Typesense uses a trie-based index with configurable typo distance.
    num_typos=2 means "Adidass" (2 typos) still finds "Adidas".
    This is built into the C++ core — zero extra code needed.

  PREFIX SEARCH:
    "jor" matches "Jordan" automatically.
    "dunk l" matches "Dunk Low".
    This replaces the need for a separate suggestion index for search
    (we keep the suggestion index for the dropdown, but search itself
     now handles partial queries natively).
"""

import typesense
from config import TYPESENSE_HOST, TYPESENSE_PORT, TYPESENSE_API_KEY

COLLECTION_NAME = "products"


def get_client() -> typesense.Client:
    return typesense.Client({
        "nodes": [{
            "host": TYPESENSE_HOST,
            "port": TYPESENSE_PORT,
            "protocol": "http",
        }],
        "api_key": TYPESENSE_API_KEY,
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
    # "dunk-low" becomes ["dunk", "low"] so "dunk low" matches "dunk-low"
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
"""
scripts/build_suggestions.py — Build the suggestion index from existing products.

What this does:
  Scans all 27k products and extracts meaningful suggestion terms:
    - Brand names (Nike, Adidas, YEEZY...)
    - Product titles normalized to key phrases
    - SKU prefixes (for power users)

  Stores them in a `suggestions` collection with a count field
  representing how many products match that term. Count drives ranking —
  more products = more likely what the user wants.

Why pre-compute instead of querying live?
  Autocomplete needs to be fast — under 50ms.
  Computing suggestions at query time across 27k products would be slow.
  Pre-computing means the suggest endpoint just does a simple prefix lookup.

Run after every bulk crawl:
  python scripts/build_suggestions.py
"""

import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient, ASCENDING
from core.config import settings

SUGGESTIONS_COLLECTION = "suggestions"

# Words that add no value to suggestions
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'in', 'of', 'for', 'by', 'with',
    'retro', 'og', 'sp', 'se', 'gs', 'wmns', 'mens', 'tb', 'pe',
    'low', 'high', 'mid',  # too generic on their own
}


def normalize_title(title: str) -> str:
    """Clean a product title for use as a suggestion term."""
    # Remove content in parentheses e.g. (2024), (Restock)
    title = re.sub(r'\([^)]*\)', '', title)
    # Remove trailing numbers that look like restock indicators
    title = re.sub(r'\s+\d+$', '', title)
    return title.strip()


def extract_key_phrase(title: str) -> str | None:
    """
    Extract the most meaningful searchable phrase from a title.

    "Nike Dunk Low 'Panda' 2024" → "Nike Dunk Low Panda"
    "Adidas Yeezy Boost 350 V2 Zebra" → "Adidas Yeezy Boost 350 V2 Zebra"

    We keep the full normalized title — users search for specific colorways.
    """
    phrase = normalize_title(title)
    # Remove single quotes used for colorway names
    phrase = phrase.replace("'", "").replace('"', '')
    # Collapse multiple spaces
    phrase = re.sub(r'\s+', ' ', phrase).strip()
    return phrase if len(phrase) > 3 else None


def build_suggestions(db):
    products_col = db[settings.PRODUCTS_COLLECTION]
    suggestions_col = db[SUGGESTIONS_COLLECTION]

    print("Loading products...")
    products = list(products_col.find(
        {},
        {"title": 1, "brand": 1, "sku": 1, "source_store": 1, "price": 1,
         "available_sizes": 1, "_id": 0}
    ))
    print(f"Loaded {len(products)} products")

    # ── Aggregate term counts ──────────────────────────────────────────────────
    # term → {count, type, brands, min_price, has_available}
    term_data: dict[str, dict] = {}

    def add_term(term: str, term_type: str, brand: str | None,
                 price: float | None, available: bool):
        key = term.lower()
        if key not in term_data:
            term_data[key] = {
                "term": term,           # original casing
                "term_lower": key,
                "type": term_type,
                "count": 0,
                "brands": set(),
                "min_price": None,
                "has_available": False,
            }
        d = term_data[key]
        d["count"] += 1
        if brand:
            d["brands"].add(brand)
        if price is not None:
            if d["min_price"] is None or price < d["min_price"]:
                d["min_price"] = price
        if available:
            d["has_available"] = True

    for p in products:
        title = p.get("title", "")
        brand = p.get("brand")
        price = p.get("price")
        available = len(p.get("available_sizes", [])) > 0

        # 1. Full normalized title
        phrase = extract_key_phrase(title)
        if phrase:
            add_term(phrase, "product", brand, price, available)

        # 2. Brand name
        if brand and len(brand) > 1:
            add_term(brand, "brand", brand, price, available)

        # 3. Brand + first model word (e.g. "Nike Dunk", "Adidas Yeezy")
        if brand and title:
            words = title.split()
            if len(words) >= 2:
                # Find brand position and take next word
                brand_words = brand.lower().split()
                title_lower = title.lower()
                # Simple: just take words[0] + words[1] if not a stop word
                if len(words) > 1 and words[1].lower() not in STOP_WORDS:
                    combo = f"{words[0]} {words[1]}"
                    if combo.lower() != brand.lower():
                        add_term(combo, "model", brand, price, available)

    # ── Filter and write ───────────────────────────────────────────────────────
    # Only keep terms with at least 1 product
    # Convert sets to lists for MongoDB
    docs = []
    for key, d in term_data.items():
        if d["count"] < 1:
            continue
        docs.append({
            "term": d["term"],
            "term_lower": d["term_lower"],
            "type": d["type"],
            "count": d["count"],
            "brands": list(d["brands"]),
            "min_price": d["min_price"],
            "has_available": d["has_available"],
        })

    # Sort by count descending before inserting
    docs.sort(key=lambda x: x["count"], reverse=True)

    print(f"Built {len(docs)} suggestion terms")

    # ── Rebuild collection ─────────────────────────────────────────────────────
    print("Rebuilding suggestions collection...")
    suggestions_col.drop()

    if docs:
        suggestions_col.insert_many(docs, ordered=False)

    # Create prefix search index
    suggestions_col.create_index(
        [("term_lower", ASCENDING)],
        name="term_lower_idx"
    )
    # Also index by count for ranking
    suggestions_col.create_index(
        [("count", -1)],
        name="count_idx"
    )
    # Compound: prefix search + ranked by count
    suggestions_col.create_index(
        [("term_lower", ASCENDING), ("count", -1)],
        name="term_prefix_count_idx"
    )

    print(f"✓ Suggestion index built: {len(docs)} terms")

    # Stats
    brands = [d for d in docs if d["type"] == "brand"]
    products_terms = [d for d in docs if d["type"] == "product"]
    models = [d for d in docs if d["type"] == "model"]
    print(f"  Brands:   {len(brands)}")
    print(f"  Products: {len(products_terms)}")
    print(f"  Models:   {len(models)}")
    print(f"\nTop 10 suggestions by count:")
    for d in docs[:10]:
        print(f"  [{d['count']:4d}] {d['term']} ({d['type']})")


if __name__ == "__main__":
    client = MongoClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]
    build_suggestions(db)
    client.close()

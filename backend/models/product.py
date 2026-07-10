"""
models/product.py — The canonical product schema.

Why Pydantic?
  - Validation happens at the boundary (parser → model).
    If a parser returns garbage, you get a clear error here,
    not a silent bad write to MongoDB.
  - .model_dump() gives you a plain dict ready for pymongo.
  - Type hints serve as living documentation.

Why this schema and not a simpler dict?
  - The schema is your contract between layers.
    The parser speaks "HypeFly JSON"; the model speaks "product".
    The storage layer only ever sees the model.
  - When you add Mainstreet, its parser also produces this model.
    Storage doesn't change at all.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, field_validator


class ProductVariant(BaseModel):
    """
    A single size/option of a product.

    Stored as a list on the parent Product.
    Why a separate class? Because variants have their own price
    (some stores charge more for larger sizes) and availability.
    """
    size: str
    price: Optional[float] = None
    available: bool = True


class Product(BaseModel):
    # ── Identity ──────────────────────────────────────────────────────────
    title: str
    brand: Optional[str] = None
    sku: Optional[str] = None          # Future matching key across stores
    slug: str                          # URL-safe identifier; upsert key with source_store
    category: str = "sneakers"

    # ── Pricing ───────────────────────────────────────────────────────────
    price: Optional[float] = None      # Base/lowest price; may differ per variant
    currency: str = "GBP"

    # ── Media & URLs ──────────────────────────────────────────────────────
    image_url: Optional[str] = None
    product_url: str                   # Full canonical URL to the product page

    # ── Source ────────────────────────────────────────────────────────────
    source_store: str                  # e.g. "hypefly", "mainstreet", "dawntown"

    # ── Variants ──────────────────────────────────────────────────────────
    variants: list[ProductVariant] = []

    # ── Timestamps ────────────────────────────────────────────────────────
    # scraped_at: set on first insert, never updated (via $setOnInsert in mongo)
    # last_seen:  updated every crawl (via $set in mongo)
    scraped_at: datetime = None        # type: ignore  (set in storage layer)
    last_seen: datetime = None         # type: ignore  (set in storage layer)

    @field_validator("price", mode="before")
    @classmethod
    def coerce_price(cls, v):
        """
        Prices from APIs sometimes arrive as strings ("£120.00") or ints.
        Strip currency symbols and cast to float.
        """
        if v is None:
            return None
        if isinstance(v, str):
            v = v.replace("£", "").replace("$", "").replace(",", "").strip()
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

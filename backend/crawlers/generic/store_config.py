"""
crawlers/generic/store_config.py — JSON store config schema + loader.

A store config fully describes how to crawl a store without writing Python.
Currently supported platforms:
  - "shopify"         → standard /products.json + /collections/{handle}/products.json
  - "shopify_graphql" → Shopify Storefront GraphQL (future)
  - "nextjs_strapi"   → custom HypeFly-style (not handled here; uses dedicated crawler)

Config shape (JSON):
{
  "name": "dawntown",
  "display_name": "Dawntown",
  "base_url": "https://dawntown.co",
  "platform": "shopify",
  "currency": "INR",
  "discovery": {
    "method": "shopify_collection_api",
    "collection_handle": "sneakers",   // or "all" for full store
    "page_size": 250
  },
  "field_map": {
    // Override how fields map from Shopify JSON → our Product model.
    // Optional — defaults work for standard Shopify stores.
    "title":    "title",
    "brand":    "vendor",
    "slug":     "handle",
    "sku":      "variants[0].sku",   // dot-path supported
    "image":    "images[0].src",
    "category": "product_type"        // or "tags" for tag-based inference
  },
  "variant_options": {
    // Which Shopify variant option holds the size? Default: "option1"
    "size_option":     "option1",
    // Words that indicate a shipping option (not a size) — used to filter noise
    "shipping_keywords": ["shipping", "ship", "instant", "same day"]
  },
  "category_map": {
    // Optional tag→category overrides. Falls back to product_type, then "Sneakers".
    "sneakers": "Sneakers",
    "slides":   "Slides"
  },
  "crawl": {
    // Per-store rate limiting overrides
    "delay_seconds": 1.0,
    "max_retries": 3
  }
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, field_validator


# ── Sub-models ────────────────────────────────────────────────────────────────

class DiscoveryConfig(BaseModel):
    method: str = "shopify_collection_api"
    collection_handle: str = "all"
    page_size: int = 250


class FieldMap(BaseModel):
    """
    Maps Shopify JSON fields → our Product model fields.
    Supports simple key names. For nested access use dot-paths like "images[0].src".
    """
    title:    str = "title"
    brand:    str = "vendor"
    slug:     str = "handle"
    sku:      str = "variants[0].sku"
    image:    str = "images[0].src"
    # "product_type" = direct field; "tags" = tag-based inference
    category: str = "product_type"


class VariantOptions(BaseModel):
    size_option: str = "option1"
    shipping_keywords: list[str] = [
        "shipping", "ship", "instant", "same day", "days", "hours", "eta"
    ]


class CrawlConfig(BaseModel):
    delay_seconds: float = 1.0
    max_retries: int = 3


# ── Main config model ─────────────────────────────────────────────────────────

class StoreConfig(BaseModel):
    name: str                          # e.g. "dawntown" — used as source_store in DB
    display_name: str                  # e.g. "Dawntown" — shown in UI
    base_url: str                      # e.g. "https://dawntown.co"
    platform: str                      # "shopify" | "nextjs_strapi"
    currency: str = "INR"

    discovery: DiscoveryConfig = DiscoveryConfig()
    field_map: FieldMap = FieldMap()
    variant_options: VariantOptions = VariantOptions()
    category_map: dict[str, str] = {}
    crawl: CrawlConfig = CrawlConfig()

    @field_validator("base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        supported = {"shopify", "nextjs_strapi"}
        if v not in supported:
            raise ValueError(
                f"Unsupported platform '{v}'. "
                f"Supported: {sorted(supported)}"
            )
        return v


# ── Loader ────────────────────────────────────────────────────────────────────

STORES_DIR = Path(__file__).parent.parent.parent / "stores"


def load_store_config(name_or_path: str) -> StoreConfig:
    """
    Load a store config from:
      - A store name (looks up stores/{name}.json), or
      - A full/relative file path.

    Examples:
        load_store_config("dawntown")
        load_store_config("/path/to/custom.json")
    """
    path = Path(name_or_path)

    if not path.suffix:
        # Treat as a store name — look up in stores/ directory
        path = STORES_DIR / f"{name_or_path}.json"

    if not path.exists():
        raise FileNotFoundError(
            f"Store config not found: {path}\n"
            f"Available configs: {list_store_configs()}"
        )

    with open(path) as f:
        data = json.load(f)

    return StoreConfig(**data)


def list_store_configs() -> list[str]:
    """Return names of all store configs in the stores/ directory."""
    if not STORES_DIR.exists():
        return []
    return [p.stem for p in STORES_DIR.glob("*.json")]


def load_all_store_configs() -> list[StoreConfig]:
    """Load every store config in stores/. Used by the scheduler."""
    configs = []
    for name in list_store_configs():
        try:
            configs.append(load_store_config(name))
        except Exception as e:
            print(f"[store_config] ⚠ Failed to load '{name}': {e}")
    return configs
"""
crawlers/generic/shopify_parser.py — Parse any Shopify store's JSON → Product model.

Shopify's /products.json and /products/{slug}.json have a consistent structure
across all stores. The differences between stores are:
  - Which variant option holds the size (option1, option2, option3)
  - Whether shipping options contaminate variant rows (like Mainstreet)
  - Whether category comes from product_type or tags
  - What tags map to our category names

All of these are controlled by StoreConfig — no Python edits needed per store.

Field resolution supports simple dot-path notation:
  "variants[0].sku"   → d["variants"][0]["sku"]
  "images[0].src"     → d["images"][0]["src"]
  "vendor"            → d["vendor"]

Comparison to MainstreetParser:
  This is a generalised version of MainstreetParser. If you configure a store
  config that matches Mainstreet exactly, this parser produces identical output.
  MainstreetParser is kept as-is (it works); this is the engine for new stores.
"""

from __future__ import annotations

import re
from typing import Any

from models.product import Product, ProductVariant
from crawlers.generic.store_config import StoreConfig


def _resolve_path(d: dict, path: str) -> Any:
    """
    Resolve a dot-path against a dict, supporting array indexing.

    Examples:
        _resolve_path(d, "vendor")              → d["vendor"]
        _resolve_path(d, "images[0].src")       → d["images"][0]["src"]
        _resolve_path(d, "variants[0].sku")     → d["variants"][0]["sku"]

    Returns None on any KeyError / IndexError / TypeError — never raises.
    """
    # Tokenise: "images[0].src" → ["images", 0, "src"]
    tokens: list[str | int] = []
    for part in path.split("."):
        m = re.match(r"^(\w+)\[(\d+)\]$", part)
        if m:
            tokens.append(m.group(1))
            tokens.append(int(m.group(2)))
        else:
            tokens.append(part)

    current: Any = d
    for token in tokens:
        try:
            if isinstance(token, int):
                current = current[token]
            else:
                current = current[token]
        except (KeyError, IndexError, TypeError):
            return None

    return current if current != "" else None


class ShopifyParser:
    """
    Platform-generic Shopify JSON parser driven by StoreConfig.

    Usage:
        config = load_store_config("dawntown")
        parser = ShopifyParser(config)
        products = parser.parse_collection(raw_json)
    """

    def __init__(self, config: StoreConfig):
        self.config = config
        self._shipping_kws = {
            kw.lower() for kw in config.variant_options.shipping_keywords
        }

    # ── Public entry points ───────────────────────────────────────────────

    def parse_product(self, raw: dict) -> Product:
        """
        Parse a single-product response (/products/{slug}.json).
        Shopify wraps the product under a "product" key.
        """
        product_data = raw.get("product")
        if not product_data:
            raise ValueError(
                f"[{self.config.name}] Expected 'product' key. "
                f"Got keys: {list(raw.keys())}"
            )
        return self._map_product(product_data)

    def parse_collection(self, raw: dict) -> list[Product]:
        """
        Parse a collection page (/collections/{handle}/products.json or /products.json).
        Returns only successfully parsed products; logs and skips failures.
        """
        results = []
        for item in raw.get("products", []):
            try:
                results.append(self._map_product(item))
            except Exception as e:
                slug = item.get("handle", "?")
                print(f"[{self.config.name}] ⚠ Skipped '{slug}': {e}")
        return results

    # ── Core mapping ──────────────────────────────────────────────────────

    def _map_product(self, d: dict) -> Product:
        fm = self.config.field_map

        slug = _resolve_path(d, fm.slug) or ""
        title = _resolve_path(d, fm.title) or ""

        if not slug or not title:
            raise ValueError(
                f"[{self.config.name}] Product missing slug or title. "
                f"Keys: {list(d.keys())}"
            )

        variants = self._extract_variants(d)
        price = self._extract_base_price(variants)
        image_url = _resolve_path(d, fm.image)
        brand = _resolve_path(d, fm.brand) or None
        sku = self._extract_sku(d)
        category = self._extract_category(d)

        return Product(
            title=title,
            brand=brand,
            sku=sku,
            slug=slug,
            category=category,
            price=price,
            currency=self.config.currency,
            image_url=image_url,
            product_url=f"{self.config.base_url}/products/{slug}",
            source_store=self.config.name,
            variants=variants,
        )

    # ── Variant extraction ────────────────────────────────────────────────

    def _extract_variants(self, d: dict) -> list[ProductVariant]:
        """
        Extract and deduplicate variants by size.

        Shopify often has multiple rows per size (one per shipping option).
        We collapse them: one ProductVariant per unique size.
        Dedup rules: available=True if ANY row is available; price=lowest.

        The option holding the size is configurable via variant_options.size_option.
        """
        size_option = self.config.variant_options.size_option
        by_size: dict[str, dict] = {}

        for v in d.get("variants", []):
            size = v.get(size_option) or v.get("title") or "Unknown"

            if self._is_shipping_text(size):
                continue

            price = self._parse_price(v.get("price"))
            available = bool(v.get("available", False))

            if size not in by_size:
                by_size[size] = {"price": price, "available": available}
            else:
                existing = by_size[size]
                # Keep lowest price
                if price is not None:
                    if existing["price"] is None or price < existing["price"]:
                        existing["price"] = price
                # available = True if any option is available
                if available:
                    existing["available"] = True

        return [
            ProductVariant(size=size, price=data["price"], available=data["available"])
            for size, data in by_size.items()
        ]

    def _extract_base_price(self, variants: list[ProductVariant]) -> float | None:
        available_prices = [v.price for v in variants if v.price is not None and v.price > 0 and v.available]
        if available_prices:
            return min(available_prices)
        all_prices = [v.price for v in variants if v.price is not None and v.price > 0]
        return min(all_prices) if all_prices else None

    def _extract_sku(self, d: dict) -> str | None:
        """
        SKU resolution order:
          1. field_map.sku dot-path (default: variants[0].sku)
          2. First non-empty SKU from any variant
        """
        fm_sku = _resolve_path(d, self.config.field_map.sku)
        if fm_sku:
            return str(fm_sku)

        for v in d.get("variants", []):
            if v.get("sku"):
                return str(v["sku"])

        return None

    # ── Category resolution ───────────────────────────────────────────────

    def _extract_category(self, d: dict) -> str:
        """
        Category resolution order:
          1. product_type field (if non-empty and not explicitly overridden)
          2. Tags — matched against config.category_map
          3. Default: "Sneakers"

        If field_map.category == "tags", skip step 1 and go straight to tags.
        """
        fm_category_field = self.config.field_map.category

        if fm_category_field != "tags":
            product_type = d.get(fm_category_field, "").strip()
            if product_type:
                # Apply category_map if there's a mapping, else use raw value
                return self.config.category_map.get(
                    product_type.lower(), product_type
                )

        # Fall back to tags
        tags = d.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        for tag in tags:
            mapped = self.config.category_map.get(tag.lower().strip())
            if mapped:
                return mapped

        return "Sneakers"

    # ── Helpers ───────────────────────────────────────────────────────────

    def _is_shipping_text(self, text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in self._shipping_kws)

    @staticmethod
    def _parse_price(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return None
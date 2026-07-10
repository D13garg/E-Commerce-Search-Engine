"""
crawlers/mainstreet/parser.py — Translate Mainstreet (Shopify) JSON → Product model.

Key discoveries from real JSON:

1. MULTI-OPTION VARIANTS
   Mainstreet uses two variant options:
     option1 = size        (e.g. "UK 7")
     option2 = shipping    (e.g. "Same Day Shipping", "Instant Ship In 48 Hours")
   This means the same size appears as 2-3 rows in the variants list.
   We must deduplicate by size, keeping the lowest price and
   marking available=True if ANY shipping option for that size is available.

2. EMPTY product_type
   product_type is "" on all observed products.
   Category must be inferred from tags instead.
   Known tag→category mappings: "sneakers" → "Sneakers", "slides" → "Slides"

3. AVAILABLE is a flat boolean
   v["available"] is True/False directly — clean and simple.

4. PRICE is a string with 2 decimal places
   "12999.00" → 12999.0 INR (already rupees, not paise)

5. SKU lives on variants, not the product root.
   Take the first non-empty one.
"""

from models.product import Product, ProductVariant
from config import MAINSTREET_BASE_URL

# Tags that map to a known category
_TAG_CATEGORY_MAP = {
    "sneakers": "Sneakers",
    "slides": "Slides",
    "apparel": "Apparel",
    "accessories": "Accessories",
    "watches": "Watches",
}

# Shipping option strings — used to identify option2 (not size)
_SHIPPING_KEYWORDS = {"shipping", "ship", "instant", "same day", "days", "hours", "eta"}


class MainstreetParser:

    def parse_product(self, raw: dict) -> Product:
        product_data = raw.get("product")
        if not product_data:
            raise ValueError(
                f"Could not locate 'product' key in response. "
                f"Top-level keys: {list(raw.keys())}"
            )
        return self._map_product(product_data)

    def parse_collection(self, raw: dict) -> list[Product]:
        """Parse a collection products.json response (list of products)."""
        results = []
        for item in raw.get("products", []):
            try:
                results.append(self._map_product(item))
            except Exception as e:
                print(f"[mainstreet] ⚠ Skipped '{item.get('handle', '?')}': {e}")
        return results

    def _map_product(self, d: dict) -> Product:
        slug = d.get("handle", "")
        title = d.get("title", "")

        if not slug or not title:
            raise ValueError(f"Product missing handle or title. Keys: {list(d.keys())}")

        variants = self._extract_variants(d)
        base_price = self._extract_base_price(variants)
        image_url = self._extract_image(d)
        sku = self._extract_sku(d)
        category = self._extract_category(d)

        return Product(
            title=title,
            brand=d.get("vendor") or None,
            sku=sku,
            slug=slug,
            category=category,
            price=base_price,
            currency="INR",
            image_url=image_url,
            product_url=f"{MAINSTREET_BASE_URL}/products/{slug}",
            source_store="mainstreet",
            variants=variants,
        )

    def _extract_variants(self, d: dict) -> list[ProductVariant]:
        """
        Deduplicate variants by size.

        Mainstreet lists the same size multiple times — once per shipping option.
        We collapse them: one ProductVariant per unique size.

        Dedup logic:
          - available = True if ANY shipping option for that size is available
          - price = lowest price across all shipping options for that size
        """
        # size → {"price": float|None, "available": bool}
        by_size: dict[str, dict] = {}

        for v in d.get("variants", []):
            size = v.get("option1") or v.get("title") or "Unknown"
            # Skip if option1 looks like a shipping description, not a size
            if self._is_shipping_text(size):
                continue

            price = self._parse_price(v.get("price"))
            available = bool(v.get("available", False))

            if size not in by_size:
                by_size[size] = {"price": price, "available": available}
            else:
                # Keep lowest price
                existing = by_size[size]
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
        available_prices = [v.price for v in variants if v.price is not None and v.available]
        if available_prices:
            return min(available_prices)
        all_prices = [v.price for v in variants if v.price is not None]
        return min(all_prices) if all_prices else None

    def _extract_image(self, d: dict) -> str | None:
        images = d.get("images", [])
        if images and isinstance(images[0], dict):
            return images[0].get("src")
        return None

    def _extract_sku(self, d: dict) -> str | None:
        for v in d.get("variants", []):
            sku = v.get("sku")
            if sku:
                return sku
        return None

    def _extract_category(self, d: dict) -> str:
        """
        product_type is empty on Mainstreet.
        Infer category from tags list instead.
        """
        tags = d.get("tags", [])
        # tags can be a list or a comma-separated string
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        for tag in tags:
            mapped = _TAG_CATEGORY_MAP.get(tag.lower().strip())
            if mapped:
                return mapped

        return "Sneakers"  # safe default for this store

    @staticmethod
    def _is_shipping_text(text: str) -> bool:
        """Return True if the text looks like a shipping option, not a size."""
        lower = text.lower()
        return any(kw in lower for kw in _SHIPPING_KEYWORDS)

    @staticmethod
    def _parse_price(value) -> float | None:
        if value is None:
            return None
        try:
            return round(float(value), 2)
        except (ValueError, TypeError):
            return None
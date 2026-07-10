"""
crawlers/hypefly/parser.py — Translate HypeFly India JSON → Product model.

Two entry points:
  parse_product()         → for Next.js pageProps responses (single product page)
  parse_graphql_product() → for GraphQL API responses (bulk discovery)

Both resolve to the same _map_product() because the Strapi field structure
is identical in both cases — GraphQL just skips the pageProps wrapper.
"""

from models.product import Product, ProductVariant
from config import HYPEFLY_BASE_URL


class HypeflyParser:

    def parse_product(self, raw: dict) -> Product:
        """Parse a Next.js product page response (pageProps.product)."""
        page_props = raw.get("pageProps", {})
        product_data = page_props.get("product")

        if not product_data:
            raise ValueError(
                f"Could not locate 'product' key in pageProps. "
                f"pageProps keys: {list(page_props.keys())}"
            )

        return self._map_product(product_data)

    def parse_graphql_product(self, attributes: dict) -> Product:
        """
        Parse a product attributes dict from the GraphQL API response.

        GraphQL returns each product as { "attributes": { name, slug, ... } }
        The caller unwraps attributes before passing here, so the structure
        is identical to pageProps.product. We reuse _map_product directly.
        """
        return self._map_product(attributes)

    def _map_product(self, d: dict) -> Product:
        slug = d.get("slug", "")
        title = d.get("name", "")

        if not slug or not title:
            raise ValueError(f"Product missing slug or name. Keys present: {list(d.keys())}")

        variants = self._extract_variants(d)
        base_price = self._extract_base_price(d)
        image_url = self._extract_image(d)
        brand = self._extract_brand(d)
        category = self._extract_category(d)

        return Product(
            title=title,
            brand=brand,
            sku=d.get("sku"),
            slug=slug,
            category=category,
            price=base_price,
            currency="INR",
            image_url=image_url,
            product_url=f"{HYPEFLY_BASE_URL}/products/{slug}",
            source_store="hypefly",
            variants=variants,
        )

    def _extract_brand(self, d: dict) -> str | None:
        try:
            return d["brands"]["data"][0]["attributes"]["name"]
        except (KeyError, IndexError, TypeError):
            return None

    def _extract_category(self, d: dict) -> str:
        try:
            return d["productType"]["data"]["attributes"]["name"]
        except (KeyError, TypeError):
            return "sneakers"

    def _extract_image(self, d: dict) -> str | None:
        try:
            return d["images"]["data"][0]["attributes"]["url"]
        except (KeyError, IndexError, TypeError):
            return None

    def _extract_base_price(self, d: dict) -> float | None:
        val = d.get("lowestPrice")
        if val is not None:
            return float(val)
        return None

    def _extract_variants(self, d: dict) -> list[ProductVariant]:
        raw_variants = d.get("productVariants", [])
        result = []

        for v in raw_variants:
            size = v.get("size", "Unknown")
            available = (v.get("quantity") or 0) > 0

            price = None
            prices = v.get("prices", [])
            if prices:
                price_val = prices[0].get("salePrice")
                if price_val is not None:
                    price = float(price_val)

            result.append(ProductVariant(
                size=str(size),
                price=price,
                available=available,
            ))

        return result
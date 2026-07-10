"""
crawlers/mainstreet/fetcher.py — Mainstreet Marketplace fetch logic.

Mainstreet runs on Shopify. This changes everything compared to HypeFly:

  HypeFly (Strapi + Next.js):
    - Need to extract buildId from HTML first
    - Hit /_next/data/{buildId}/products/{slug}.json

  Mainstreet (Shopify):
    - No build ID. No dynamic keys.
    - Shopify exposes a public JSON API on EVERY store, always at:
        /products/{slug}.json          → single product
        /products.json?limit=250&page=N → paginated product list (for discovery)
        /collections/{handle}/products.json → collection-scoped product list

  This is why we have separate fetchers per store — the fetch strategy
  is completely different even though the output (raw JSON) feeds the
  same parser → model → storage pipeline.

Architecture note:
  MainstreetFetcher does NOT subclass HypeflyFetcher.
  Both subclass BaseFetcher independently.
  They share HTTP logic (retries, headers, rate limiting) but nothing else.
"""

from crawlers.base.fetcher import BaseFetcher
from config import MAINSTREET_BASE_URL


class MainstreetFetcher(BaseFetcher):

    def __init__(self):
        super().__init__(base_url=MAINSTREET_BASE_URL)

    def fetch_product(self, slug: str) -> dict:
        """
        Fetch a single product by slug using Shopify's public JSON API.

        Shopify product JSON is at: /products/{slug}.json
        Returns the raw JSON dict — parsing happens in the parser layer.
        """
        url = f"{self.base_url}/products/{slug}.json"
        print(f"[mainstreet] Fetching product: {url}")

        response = self.get(url)
        try:
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to parse product JSON for slug '{slug}': {e}")

    def fetch_collection_page(self, handle: str = "all-sneakers", limit: int = 250, page: int = 1) -> dict:
        """
        Fetch a paginated page of products from a collection.

        Used for discovery — get all slugs without crawling HTML.
        Shopify paginates collections via ?limit=N&page=N (max 250 per page).

        Args:
            handle: Collection handle, e.g. "all-sneakers", "nike", "adidas"
            limit:  Products per page (max 250 for Shopify)
            page:   Page number, starting at 1

        Returns:
            Raw JSON dict with a "products" list.
        """
        url = f"{self.base_url}/collections/{handle}/products.json?limit={limit}&page={page}"
        print(f"[mainstreet] Fetching collection page {page}: {url}")

        response = self.get(url)
        try:
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to parse collection JSON: {e}")
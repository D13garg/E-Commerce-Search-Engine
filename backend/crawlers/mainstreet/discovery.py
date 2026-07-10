"""
crawlers/mainstreet/discovery.py — Discover all Mainstreet product slugs.

Why the Shopify collection API over sitemap?
  Mainstreet is Shopify. Shopify's /products.json endpoint is:
  - Paginated and reliable (250 products per page max)
  - Returns structured JSON including handle (slug), not just URLs
  - Faster than parsing XML since we can extract slugs directly
  - The same data format the parser already understands

  We could use the sitemap too, but the collection API is cleaner
  for Shopify because it was designed for exactly this use case.

Pagination strategy:
  Shopify uses page-based pagination (not cursor-based like modern APIs).
  We increment page number until we get an empty products list.

  Page 1: /products.json?limit=250&page=1   → 250 products
  Page 2: /products.json?limit=250&page=2   → 250 products
  Page 3: /products.json?limit=250&page=3   → 47 products
  Page 4: /products.json?limit=250&page=4   → 0 products → stop

Scope options:
  /products.json               → ALL products in the store
  /collections/{handle}/products.json  → only products in that collection

  We use the collection endpoint with "all-sneakers" to scope
  discovery to just sneakers. This is intentional — we don't want
  to accidentally crawl apparel, watches, etc. in Phase 1.
  Change the handle to "all" to crawl everything.
"""

from crawlers.base.fetcher import BaseFetcher
from config import MAINSTREET_BASE_URL

MAX_PER_PAGE = 250   # Shopify's maximum


class MainstreetDiscovery:

    def __init__(self, fetcher: BaseFetcher):
        self.fetcher = fetcher

    def get_all_slugs(self, collection_handle: str = "all-sneakers") -> list[str]:
        """
        Return all product slugs in the given collection via pagination.

        Args:
            collection_handle: Shopify collection handle.
                "all-sneakers" → only sneakers
                "all"          → entire store catalogue

        Returns:
            List of product slugs (handles), e.g. ["adidas-yeezy-500-enflame", ...]
        """
        all_slugs = []
        page = 1

        while True:
            url = (
                f"{MAINSTREET_BASE_URL}/collections/{collection_handle}"
                f"/products.json?limit={MAX_PER_PAGE}&page={page}"
            )
            print(f"[mainstreet:discovery] Fetching page {page}: {url}")

            response = self.fetcher.get(url)
            data = response.json()
            products = data.get("products", [])

            if not products:
                print(f"[mainstreet:discovery] Empty page — discovery complete.")
                break

            slugs = [p["handle"] for p in products if p.get("handle")]
            all_slugs.extend(slugs)
            print(f"[mainstreet:discovery] Page {page}: {len(slugs)} slugs found (total: {len(all_slugs)})")

            # If we got fewer than the max, this was the last page
            if len(products) < MAX_PER_PAGE:
                break

            page += 1

        return all_slugs
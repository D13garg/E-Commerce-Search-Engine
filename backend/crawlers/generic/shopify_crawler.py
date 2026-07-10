"""
crawlers/generic/shopify_crawler.py — Full Shopify crawl driven by StoreConfig.

Handles:
  - Discovery: paginate /collections/{handle}/products.json to get all slugs
  - Bulk fetch: parse collection pages directly (no per-product requests needed)
  - Single fetch: /products/{slug}.json for targeted updates

Why bulk via collection pages instead of per-product fetches?
  Shopify's collection endpoint returns full product data, not just slugs.
  We parse the products directly from the paginated discovery response.
  This halves the number of HTTP requests vs discover-then-fetch-each approach.

  Mainstreet's original crawler did slug-discovery + per-product fetches.
  This engine does collection-page crawling — same data, half the requests.
  The per-product fetch is still available for targeted slug crawls.
"""

from __future__ import annotations

from typing import Generator

from crawlers.base.fetcher import BaseFetcher
from crawlers.generic.store_config import StoreConfig
from crawlers.generic.shopify_parser import ShopifyParser
from models.product import Product


class ShopifyCrawler:
    """
    A full Shopify store crawler driven entirely by a StoreConfig.

    Usage:
        config = load_store_config("dawntown")
        crawler = ShopifyCrawler(config)

        # Iterate all products (memory-efficient generator)
        for batch in crawler.iter_all_products():
            for product in batch:
                storage.upsert_product(product)

        # Or fetch all at once (careful with large catalogues)
        all_products = crawler.fetch_all_products()

        # Or a single product
        product = crawler.fetch_product("nike-dunk-low-panda")
    """

    def __init__(self, config: StoreConfig):
        self.config = config
        self.parser = ShopifyParser(config)
        self._fetcher: BaseFetcher | None = None

    # ── Context manager support ───────────────────────────────────────────

    def __enter__(self) -> "ShopifyCrawler":
        self._fetcher = BaseFetcher(
            base_url=self.config.base_url,
            delay=self.config.crawl.delay_seconds,
            max_retries=self.config.crawl.max_retries,
        )
        return self

    def __exit__(self, *args):
        if self._fetcher:
            self._fetcher.close()
            self._fetcher = None

    @property
    def fetcher(self) -> BaseFetcher:
        if self._fetcher is None:
            raise RuntimeError(
                "ShopifyCrawler must be used as a context manager: "
                "`with ShopifyCrawler(config) as crawler:`"
            )
        return self._fetcher

    # ── Collection-based bulk crawl (primary method) ──────────────────────

    def iter_all_products(self) -> Generator[list[Product], None, None]:
        """
        Yield batches of products from the configured collection.

        Uses Shopify's collection endpoint which returns full product data,
        so we parse products directly from each page — no extra per-product requests.

        Yields:
            list[Product] — one batch per collection page (up to page_size products)
        """
        cfg = self.config.discovery
        handle = cfg.collection_handle
        page_size = cfg.page_size
        page = 1

        while True:
            url = self._collection_url(handle, page_size, page)
            print(f"[{self.config.name}] Fetching page {page}: {url}")

            response = self.fetcher.get(url)
            raw = response.json()

            products_raw = raw.get("products", [])
            if not products_raw:
                print(f"[{self.config.name}] Empty page {page} — discovery complete.")
                break

            batch = self.parser.parse_collection(raw)
            print(
                f"[{self.config.name}] Page {page}: "
                f"{len(products_raw)} raw → {len(batch)} parsed"
            )
            yield batch

            if len(products_raw) < page_size:
                # Last page — fewer results than requested
                break

            page += 1

    def fetch_all_products(self) -> list[Product]:
        """
        Fetch all products into memory.
        For large catalogues (>5000 products), prefer iter_all_products().
        """
        all_products: list[Product] = []
        for batch in self.iter_all_products():
            all_products.extend(batch)
        print(f"[{self.config.name}] Total products fetched: {len(all_products)}")
        return all_products

    def get_all_slugs(self) -> list[str]:
        """
        Discover all product slugs without fully parsing products.
        Useful for smart re-crawl: get slugs, filter stale, fetch-and-parse only those.
        """
        cfg = self.config.discovery
        handle = cfg.collection_handle
        page_size = cfg.page_size
        page = 1
        all_slugs: list[str] = []

        while True:
            url = self._collection_url(handle, page_size, page)
            response = self.fetcher.get(url)
            raw = response.json()

            products = raw.get("products", [])
            if not products:
                break

            slugs = [p["handle"] for p in products if p.get("handle")]
            all_slugs.extend(slugs)

            if len(products) < page_size:
                break

            page += 1

        print(f"[{self.config.name}] Discovered {len(all_slugs)} slugs")
        return all_slugs

    # ── Single product fetch ──────────────────────────────────────────────

    def fetch_product(self, slug: str) -> Product:
        """
        Fetch and parse a single product by slug.
        Used for targeted updates and the smart re-crawl scheduler.
        """
        url = f"{self.config.base_url}/products/{slug}.json"
        print(f"[{self.config.name}] Fetching product: {url}")

        response = self.fetcher.get(url)
        raw = response.json()
        return self.parser.parse_product(raw)

    # ── URL builders ──────────────────────────────────────────────────────

    def _collection_url(self, handle: str, page_size: int, page: int) -> str:
        if handle == "all":
            # All products, not scoped to a collection
            return (
                f"{self.config.base_url}/products.json"
                f"?limit={page_size}&page={page}"
            )
        return (
            f"{self.config.base_url}/collections/{handle}/products.json"
            f"?limit={page_size}&page={page}"
        )
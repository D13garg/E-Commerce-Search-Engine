"""
crawlers/hypefly/graphql.py — HypeFly GraphQL API client.

Discovery: We found a public GraphQL endpoint at https://graph.hypefly.co.in/graphql
that powers the /products page. It accepts POST requests with no authentication.

This completely replaces:
  - The sitemap-based discovery (sitemap was broken anyway)
  - The individual Next.js product fetches for discovery

Instead of:
  discovery → list of slugs → fetch each slug individually

We now do:
  GraphQL paginated query → full product data for all products at once

This is superior because:
  1. One API designed for data consumption — stable and structured
  2. Returns full product data (name, slug, price, variants, images)
     so we can parse directly without a second fetch per product
  3. Clean server-side pagination via start/limit
  4. No buildId dependency

Query structure (from Network tab observation):
  - operationName: "products"
  - filter: { publishedAt: { ne: null } }  ← all published products
  - limit: up to 100 per page (we'll test limits)
  - start: offset for pagination
  - sortBy: ["name:asc"]
"""

import time
import httpx
from config import CRAWL_DELAY_SECONDS, DEFAULT_HEADERS

GRAPHQL_URL = "https://graph.hypefly.co.in/graphql"
PAGE_SIZE = 100  # Request 100 products per query; adjust if server rejects

# The exact query observed from Network tab
PRODUCTS_QUERY = """
query products($filter: ProductFiltersInput, $limit: Int!, $start: Int!, $sortBy: [String]) {
  products(
    filters: $filter
    pagination: {start: $start, limit: $limit}
    sort: $sortBy
  ) {
    data {
      attributes {
        name
        slug
        lowestPrice
        outOfStock
        sku
        productVariants(sort: "id:desc", pagination: {limit: 50}) {
          id
          size
          prices {
            salePrice
            compareAtPrice
            shippingMode
          }
          quantity
        }
        images {
          data {
            attributes {
              url
              name
              alternativeText
            }
          }
        }
        brands {
          data {
            attributes {
              name
            }
          }
        }
        productType {
          data {
            attributes {
              name
            }
          }
        }
      }
    }
    meta {
      pagination {
        total
      }
    }
  }
}
"""


class HypeflyGraphQL:
    """
    Fetches all HypeFly products via their GraphQL API.

    Usage:
        client = HypeflyGraphQL()
        for batch in client.iter_all_products():
            for raw_product in batch:
                product = parser.parse_graphql_product(raw_product)
                storage.upsert_product(product)
    """

    def __init__(self, delay: float = CRAWL_DELAY_SECONDS):
        self.delay = delay
        self.session = httpx.Client(
            headers={
                **DEFAULT_HEADERS,
                "Content-Type": "application/json",
                "Origin": "https://hypefly.co.in",
                "Referer": "https://hypefly.co.in/products",
            },
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0),
        )

    def fetch_page(self, start: int = 0, limit: int = PAGE_SIZE) -> dict:
        """
        Fetch one page of products from GraphQL.

        Args:
            start: Offset (0-based)
            limit: Number of products to fetch

        Returns:
            Raw GraphQL response dict
        """
        payload = {
            "operationName": "products",
            "query": PRODUCTS_QUERY,
            "variables": {
                "filter": {"publishedAt": {"ne": None}},
                "limit": limit,
                "start": start,
                "sortBy": ["name:asc"],
            },
        }

        response = self.session.post(GRAPHQL_URL, json=payload)
        response.raise_for_status()
        time.sleep(self.delay)
        return response.json()

    def iter_all_products(self):
        """
        Paginate through all products, yielding one batch at a time.

        Yields:
            list of raw product attribute dicts (ready for parser)
        """
        start = 0
        total = None

        while True:
            print(f"[hypefly:graphql] Fetching products {start}–{start + PAGE_SIZE}...")
            data = self.fetch_page(start=start, limit=PAGE_SIZE)

            try:
                products_data = data["data"]["products"]
                items = products_data["data"]
                total = products_data["meta"]["pagination"]["total"]
            except (KeyError, TypeError) as e:
                raise RuntimeError(f"Unexpected GraphQL response structure: {e}\n{data}")

            if not items:
                print("[hypefly:graphql] No more products.")
                break

            # Extract the attributes dict from each item
            batch = [item["attributes"] for item in items if item.get("attributes")]
            print(f"[hypefly:graphql] Got {len(batch)} products (total: {total})")
            yield batch

            start += PAGE_SIZE
            if start >= total:
                break

    def get_all_slugs(self) -> list[str]:
        """
        Convenience method: return just the slugs for all products.
        Used when you only need discovery without full product data.
        """
        slugs = []
        for batch in self.iter_all_products():
            slugs.extend(p["slug"] for p in batch if p.get("slug"))
        return slugs

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
"""
crawlers/hypefly/fetcher.py — HypeFly-specific fetch logic.

Key problem this solves:
  Next.js data endpoints are keyed by a build ID:
    /_next/data/{buildId}/products/{slug}.json

  The buildId changes every time HypeFly deploys. You cannot hardcode it.
  Strategy: fetch the homepage HTML once, extract __NEXT_DATA__ which
  always contains the current buildId, then use it to construct product URLs.

Why not just scrape the HTML product page?
  - HTML is presentation layer: it can change without warning.
  - The JSON endpoint is the data layer: it's consumed by React internally
    and tends to be much more stable in structure.
  - JSON parsing is trivial; HTML parsing is fragile (CSS class names change).
"""

import json
import re
from selectolax.parser import HTMLParser

from crawlers.base.fetcher import BaseFetcher
from config import HYPEFLY_BASE_URL


class HypeflyFetcher(BaseFetcher):

    def __init__(self):
        super().__init__(base_url=HYPEFLY_BASE_URL)
        self._build_id: str | None = None

    # ── Build ID ──────────────────────────────────────────────────────────

    def get_build_id(self, force_refresh: bool = False) -> str:
        """
        Extract Next.js buildId from the __NEXT_DATA__ script tag.

        __NEXT_DATA__ is a JSON blob injected into every Next.js page:
          <script id="__NEXT_DATA__" type="application/json">
            {"props": {...}, "buildId": "abc123", ...}
          </script>

        We cache the buildId in memory for the lifetime of the fetcher.
        Set force_refresh=True if you suspect a deployment happened mid-crawl.

        Why selectolax over BeautifulSoup?
          - selectolax is ~10x faster (Rust-backed Modest parser)
          - We only need one element; selectolax handles this with minimal overhead
        """
        if self._build_id and not force_refresh:
            return self._build_id

        print(f"[hypefly] Fetching build ID from {self.base_url} ...")
        response = self.get(self.base_url)

        tree = HTMLParser(response.text)
        script = tree.css_first("script#__NEXT_DATA__")

        if not script:
            raise RuntimeError(
                "Could not find __NEXT_DATA__ script tag on HypeFly homepage. "
                "The site structure may have changed."
            )

        try:
            next_data = json.loads(script.text())
            build_id = next_data["buildId"]
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Failed to parse __NEXT_DATA__: {e}")

        print(f"[hypefly] Build ID: {build_id}")
        self._build_id = build_id
        return build_id

    # ── Product Fetching ──────────────────────────────────────────────────

    def fetch_product(self, slug: str) -> dict:
        """
        Fetch structured product JSON for a given product slug.

        Returns the raw JSON dict — parsing into a Product model happens
        in the parser layer, not here. The fetcher's only job is HTTP.

        Args:
            slug: The product slug, e.g. "nike-dunk-low-panda-dd1391-100"

        Returns:
            Raw JSON dict from the Next.js data endpoint.
        """
        build_id = self.get_build_id()
        url = f"{self.base_url}/_next/data/{build_id}/products/{slug}.json"

        print(f"[hypefly] Fetching product: {url}")
        response = self.get(url)

        try:
            return response.json()
        except Exception as e:
            raise RuntimeError(f"Failed to parse product JSON for slug '{slug}': {e}")

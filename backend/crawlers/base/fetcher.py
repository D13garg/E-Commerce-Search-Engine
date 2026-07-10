"""
crawlers/base/fetcher.py — Shared HTTP logic for all crawlers.

Why a base fetcher?
  - Every crawler needs HTTP: retries, headers, timeouts, error handling.
  - Centralising this means: fix a bug once, all crawlers benefit.
  - The HypeFly fetcher subclasses this and adds only HypeFly-specific logic.

Why httpx over requests?
  - httpx supports both sync and async; when you scale to concurrent
    crawling later, you switch to async without rewriting HTTP logic.
  - Built-in timeout objects (connect vs read vs total) are cleaner.
"""

import time
import httpx
from config import DEFAULT_HEADERS, CRAWL_DELAY_SECONDS


class BaseFetcher:
    """
    Thin wrapper around httpx with:
      - Shared headers (User-Agent, Accept-Language)
      - Configurable timeouts
      - Basic retry logic (network hiccups happen)
      - Polite delay between requests
    """

    def __init__(
        self,
        base_url: str,
        delay: float = CRAWL_DELAY_SECONDS,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.max_retries = max_retries

        # A persistent session reuses the TCP connection.
        # This is faster and more polite than opening a new connection per request.
        self.session = httpx.Client(
            headers=DEFAULT_HEADERS,
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0),
            follow_redirects=True,
        )

    def get(self, url: str, **kwargs) -> httpx.Response:
        """
        GET a URL with retry logic.

        Retries on connection errors and 5xx responses (server-side transient).
        Does NOT retry on 4xx (your request is wrong; retrying won't help).
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, **kwargs)

                if response.status_code == 200:
                    time.sleep(self.delay)   # polite delay after every successful fetch
                    return response

                if 400 <= response.status_code < 500:
                    # Client error — don't retry
                    response.raise_for_status()

                # 5xx — wait and retry
                print(f"[fetcher] {response.status_code} on attempt {attempt}: {url}")
                time.sleep(self.delay * attempt)   # exponential-ish backoff

            except httpx.RequestError as e:
                last_error = e
                print(f"[fetcher] Network error on attempt {attempt}: {e}")
                time.sleep(self.delay * attempt)

        raise RuntimeError(
            f"Failed to fetch {url} after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )

    def close(self):
        self.session.close()

    # Allow use as a context manager: `with BaseFetcher(...) as f:`
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

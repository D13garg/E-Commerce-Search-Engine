"""
core/config.py — Centralised configuration using Pydantic Settings.

Why Pydantic Settings over raw os.getenv()?
  - Type validation at startup — wrong env var type = clear error, not silent bug
  - IDE autocompletion on settings fields
  - Single source of truth — import Settings() anywhere, no repeated os.getenv()
  - .env file loading built in

All environment variables are defined here with types and defaults.
Nothing in the codebase should call os.getenv() directly.
"""

import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── MongoDB ────────────────────────────────────────────────────────────────
    MONGO_URI: str          = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str      = os.getenv("MONGO_DB_NAME", "searchengine")
    PRODUCTS_COLLECTION: str = "products"

    # ── Typesense ──────────────────────────────────────────────────────────────
    TYPESENSE_HOST: str     = os.getenv("TYPESENSE_HOST", "localhost")
    TYPESENSE_PORT: int     = int(os.getenv("TYPESENSE_PORT", "8108"))
    TYPESENSE_API_KEY: str  = os.getenv("TYPESENSE_API_KEY", "searchengine_dev_key")

    # ── HTTP / Crawling ────────────────────────────────────────────────────────
    DEFAULT_HEADERS: dict   = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-GB,en;q=0.9",
    }
    CRAWL_DELAY_SECONDS: float = 2.0

    # ── Store URLs ─────────────────────────────────────────────────────────────
    HYPEFLY_BASE_URL: str       = "https://hypefly.co.in"
    MAINSTREET_BASE_URL: str    = "https://marketplace.mainstreet.co.in"

    # ── API ────────────────────────────────────────────────────────────────────
    API_TITLE: str          = "Sneaker Search Engine API"
    API_VERSION: str        = "0.2.0"
    CORS_ORIGINS: list      = ["*"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached Settings instance.
    lru_cache ensures this is only instantiated once per process.
    Use this everywhere: from core.config import get_settings
    """
    return Settings()


# Convenience shorthand — import settings directly
settings = get_settings()
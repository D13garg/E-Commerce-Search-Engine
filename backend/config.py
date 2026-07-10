"""
config.py — Central configuration.

Why here and not inline?
  - One place to change a value (MONGO_URI, timeouts, etc.)
  - Secrets never appear in source code; they come from .env
  - Every module imports from here, not from os.environ directly
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── MongoDB ──────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "searchengine")
PRODUCTS_COLLECTION = "products"

# ── HTTP ─────────────────────────────────────────────────────────────────────
# A realistic browser User-Agent reduces the chance of being blocked.
# This is not deceptive — it's standard practice for crawlers.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}

# Seconds to wait between requests to the same domain.
# Being polite matters: aggressive crawling gets you IP-banned.
CRAWL_DELAY_SECONDS = 2.0

# ── Stores ───────────────────────────────────────────────────────────────────
HYPEFLY_BASE_URL = "https://hypefly.co.in"
MAINSTREET_BASE_URL = "https://marketplace.mainstreet.co.in"

# ── Typesense ─────────────────────────────────────────────────────────────────
TYPESENSE_HOST    = os.getenv("TYPESENSE_HOST", "localhost")
TYPESENSE_PORT    = int(os.getenv("TYPESENSE_PORT", "8108"))
TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY", "searchengine_dev_key")
# "http" for local dev (default Typesense binary), "https" for Typesense Cloud
TYPESENSE_PROTOCOL = os.getenv("TYPESENSE_PROTOCOL", "http")

# ── Auth ─────────────────────────────────────────────────────────────────────
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = os.getenv("SECRET_KEY", "")
PEPPER     = os.getenv("PEPPER", "")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS   = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000")

# Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

# Email (reuses ALERT_* SMTP config already set up for price alerts)
# Email (Resend — used for both auth OTP emails and price alerts)
RESEND_API_KEY    = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "")
RESEND_FROM_NAME  = os.getenv("RESEND_FROM_NAME", "MarketLens")
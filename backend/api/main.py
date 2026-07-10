"""
api/main.py — FastAPI application and route definitions.

Run with:
  uvicorn api.main:app --reload --port 8000

Then visit:
  http://localhost:8000/docs        ← interactive Swagger UI
  http://localhost:8000/redoc       ← alternative docs

Route design:
  Routes are thin — they only handle HTTP concerns:
    - Parse query parameters
    - Call search.py functions
    - Return responses or raise HTTPException

  No MongoDB logic lives here. That's all in search.py.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo.database import Database
from typing import Optional

from api.dependencies import get_db
from api.schemas import SearchResponse, ProductResponse, AggregationResponse
from api.search import setup_indexes, search_products, get_product, get_brands, get_stores, get_categories
from api.query_parser import parse_query
from api.typesense_search import typesense_search
from api.auth import router as auth_router
from api.wishlist import router as wishlist_router
from auth.user_repository import UserRepository
from auth.otp_service import OTPService
from wishlist.models import WishlistRepository
from auth.csrf_middleware import CSRFMiddleware
from config import APP_BASE_URL, ENVIRONMENT

app = FastAPI(
    title="Sneaker Search Engine API",
    description="Search across HypeFly and Mainstreet product catalogues",
    version="0.1.0",
)

# CSRF double-submit check — must run before route handlers
app.add_middleware(CSRFMiddleware)

# CORS — allows your frontend to call this API with cookies attached.
# allow_credentials=True is REQUIRED for httpOnly auth cookies to work cross-origin,
# and that means allow_origins CANNOT be "*" — must be an explicit origin list.
_cors_origins = [APP_BASE_URL, "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-CSRF-Token"],
)

app.include_router(auth_router)
app.include_router(wishlist_router)


@app.on_event("startup")
def startup():
    """Create search and auth indexes when the API starts."""
    db = get_db()
    setup_indexes(db)
    UserRepository(db).setup_indexes()
    OTPService(db).setup_indexes()
    WishlistRepository(db).setup_indexes()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    """Check API and database connectivity."""
    db = get_db()
    count = db["products"].count_documents({})
    return {"status": "ok", "total_products": count}


# ── Search ────────────────────────────────────────────────────────────────────

@app.get("/search", response_model=SearchResponse, tags=["Search"])
def search(
    q: Optional[str] = Query(None, description="Search query (title, brand, category)"),
    brand: Optional[str] = Query(None, description="Filter by brand e.g. Nike, Adidas"),
    store: Optional[str] = Query(None, description="Filter by store: hypefly, mainstreet"),
    category: Optional[str] = Query(None, description="Filter by category e.g. Sneakers"),
    min_price: Optional[float] = Query(None, description="Minimum price in INR"),
    max_price: Optional[float] = Query(None, description="Maximum price in INR"),
    available: Optional[bool] = Query(None, description="Filter by availability"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    db: Database = Depends(get_db),
):
    """
    Search products across all indexed stores.

    Supports natural language queries:
    - /search?q=jordan 1 under 10k
    - /search?q=nike dunk available below 15000
    - /search?q=yeezy on hypefly

    Explicit filter params always override parsed values.
    Examples:
    - /search?q=yeezy
    - /search?q=dunk low&store=mainstreet
    - /search?brand=Nike&min_price=5000&max_price=20000
    - /search?q=jordan 1&available=true&page=2
    """
    # Query understanding:
    # Only parse the query if the user hasn't explicitly set filters via UI.
    # Explicit params (from filter panel) always take priority over parsed values.
    # This prevents the parser from overriding intentional filter selections.
    # Query parser: extract structured filters from natural language.
    # Only parse what the user hasn't already set explicitly via UI filters.
    # Rule: if price/store/brand/available already set by UI → skip those extractions.
    # Category is intentionally NOT in this check — user can pick a category
    # AND type "nike under 10k" and both should work together.
    if q:
        # Only run parser if at least one NL-extractable thing isn't already set
        explicit_price    = min_price is not None or max_price is not None
        explicit_store    = store is not None
        explicit_brand    = brand is not None
        explicit_avail    = available is not None
        all_explicit      = explicit_price and explicit_store and explicit_brand and explicit_avail

        if not all_explicit:
            parsed = parse_query(q)
            if parsed.has_extracted_anything():
                q = parsed.q
                # Only apply parsed value if UI didn't already set it
                if not explicit_price:
                    min_price = parsed.min_price
                    max_price = parsed.max_price
                if not explicit_store:
                    store = parsed.store or store
                if not explicit_avail:
                    available = parsed.available
                # brand: never override explicit UI brand filter

    # Use Typesense for search (fuzzy matching, <10ms, C++ core)
    # Falls back to MongoDB automatically if Typesense is down
    return typesense_search(
        db=db,
        q=q,
        brand=brand,
        store=store,
        category=category,
        min_price=min_price,
        max_price=max_price,
        available=available,
        page=page,
        limit=limit,
    )


# ── Single Product ────────────────────────────────────────────────────────────

@app.get("/products/{slug}", response_model=list[ProductResponse], tags=["Products"])
def get_product_by_slug(
    slug: str,
    store: Optional[str] = Query(None, description="Specific store listing"),
    db: Database = Depends(get_db),
):
    """
    Get product listing(s) by slug.

    Returns a list because the same product slug may exist
    across multiple stores (e.g. hypefly + mainstreet).

    Use ?store=hypefly to get a specific store's listing.
    """
    if store:
        product = get_product(db, slug, store)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product '{slug}' not found in store '{store}'")
        return [product]

    # Return all store listings for this slug
    results = []
    for store_name in get_stores(db):
        product = get_product(db, slug, store_name)
        if product:
            results.append(product)

    if not results:
        raise HTTPException(status_code=404, detail=f"Product '{slug}' not found")

    return results


# ── Aggregations ──────────────────────────────────────────────────────────────

@app.get("/brands", response_model=AggregationResponse, tags=["Filters"])
def list_brands(
    store: Optional[str] = Query(None, description="Filter brands by store"),
    db: Database = Depends(get_db),
):
    """List all unique brands in the index."""
    brands = get_brands(db, store)
    return AggregationResponse(values=brands, total=len(brands))


@app.get("/stores", response_model=AggregationResponse, tags=["Filters"])
def list_stores(db: Database = Depends(get_db)):
    """List all indexed stores."""
    stores = get_stores(db)
    return AggregationResponse(values=stores, total=len(stores))


@app.get("/categories", response_model=AggregationResponse, tags=["Filters"])
def list_categories(
    store: Optional[str] = Query(None, description="Filter categories by store"),
    db: Database = Depends(get_db),
):
    """List all unique categories in the index."""
    categories = get_categories(db, store)
    return AggregationResponse(values=categories, total=len(categories))


# ── Autocomplete ──────────────────────────────────────────────────────────────

from api.search import get_suggestions
from api.alerts import router as alerts_router
app.include_router(alerts_router)

@app.get("/suggest", tags=["Search"])
def suggest(
    q: str = Query(..., min_length=1, description="Prefix to autocomplete"),
    limit: int = Query(8, ge=1, le=20),
    db: Database = Depends(get_db),
):
    """
    Autocomplete suggestions for the search box.

    Returns up to 8 suggestions ranked by:
      1. Type: brands first, then model families, then specific products
      2. Count: more products matching = higher rank

    Designed to be called on every keystroke with debounce.
    Typical response time: <10ms (prefix index lookup).
    """
    results = get_suggestions(db, q=q, limit=limit)
    return {"q": q, "suggestions": results}


# ── Price History ─────────────────────────────────────────────────────────────

from storage.price_history import get_price_history, get_price_drops

@app.get("/products/{slug}/price-history", tags=["Price History"])
def price_history(
    slug: str,
    store: Optional[str] = Query(None, description="Filter by store"),
    limit: int = Query(100, ge=1, le=500),
    db: Database = Depends(get_db),
):
    """
    Get price history for a product.
    Returns records ordered newest first.
    """
    history = get_price_history(db, slug=slug, source_store=store, limit=limit)
    if not history:
        raise HTTPException(status_code=404, detail=f"No price history found for '{slug}'")

    for record in history:
        if "recorded_at" in record:
            record["recorded_at"] = record["recorded_at"].isoformat()

    return {"slug": slug, "store": store, "count": len(history), "history": history}


@app.get("/price-drops", tags=["Price History"])
def price_drops(
    hours: int = Query(168, description="Look back window in hours (default 7 days)"),
    store: Optional[str] = Query(None, description="Filter by store"),
    min_drop_pct: float = Query(5.0, description="Minimum drop percentage to include"),
    db: Database = Depends(get_db),
):
    """
    Find products whose price dropped recently.
    Sorted by biggest drop percentage first.
    """
    drops = get_price_drops(db, since_hours=hours, store=store, min_drop_pct=min_drop_pct)

    return {
        "since_hours": hours,
        "min_drop_pct": min_drop_pct,
        "count": len(drops),
        "drops": drops,
    }


# ── Product Matching ──────────────────────────────────────────────────────────

from storage.matching import get_match_by_sku, get_match_by_slug, get_best_deals, get_match_stats

@app.get("/matches/sku/{sku}", tags=["Matching"])
def match_by_sku(sku: str, db: Database = Depends(get_db)):
    """
    Get all store listings for a product by SKU.
    Shows price across every store that carries it.
    """
    match = get_match_by_sku(db, sku)
    if not match:
        raise HTTPException(status_code=404, detail=f"No match found for SKU '{sku}'")
    return match


@app.get("/matches/product/{slug}", tags=["Matching"])
def match_by_slug(
    slug: str,
    store: str = Query(..., description="Store this slug belongs to"),
    db: Database = Depends(get_db),
):
    """
    Given a product slug and store, find its cross-store match.
    Returns all store listings for the same physical product.
    """
    match = get_match_by_slug(db, slug=slug, store=store)
    if not match:
        raise HTTPException(
            status_code=404,
            detail=f"No cross-store match found for '{slug}' on '{store}'"
        )
    return match


@app.get("/deals", tags=["Matching"])
def best_deals(
    min_spread: float = Query(500, description="Minimum price difference in INR"),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
):
    """
    Products with the biggest price difference across stores.
    Sorted by price spread descending — biggest savings first.
    """
    deals = get_best_deals(db, limit=limit, min_spread=min_spread)
    return {"count": len(deals), "min_spread": min_spread, "deals": deals}


@app.get("/matches/stats", tags=["Matching"])
def matching_stats(db: Database = Depends(get_db)):
    """Summary statistics about the product matching index."""
    return get_match_stats(db)
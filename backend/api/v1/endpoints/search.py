"""
api/v1/endpoints/search.py — Product search, suggestions, and aggregation filters endpoints.
"""

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database
from typing import Optional

from core.database import get_db
from schemas.product import SearchResponse, AggregationResponse
from services import search_service

router = APIRouter()


@router.get("/search", response_model=SearchResponse, tags=["Search"])
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
    """
    return search_service.search_products(
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


@router.get("/suggest", tags=["Search"])
def suggest(
    q: str = Query(..., min_length=1, description="Prefix to autocomplete"),
    limit: int = Query(8, ge=1, le=20),
    db: Database = Depends(get_db),
):
    """
    Autocomplete suggestions for the search box.

    Returns suggestions ranked by type priority and query count.
    """
    results = search_service.get_suggestions(db, q=q, limit=limit)
    return {"q": q, "suggestions": results}


@router.get("/brands", response_model=AggregationResponse, tags=["Filters"])
def list_brands(
    store: Optional[str] = Query(None, description="Filter brands by store"),
    db: Database = Depends(get_db),
):
    """List all unique brands in the index."""
    brands = search_service.get_brands(db, store)
    return AggregationResponse(values=brands, total=len(brands))


@router.get("/stores", response_model=AggregationResponse, tags=["Filters"])
def list_stores(db: Database = Depends(get_db)):
    """List all indexed stores."""
    stores = search_service.get_stores(db)
    return AggregationResponse(values=stores, total=len(stores))


@router.get("/categories", response_model=AggregationResponse, tags=["Filters"])
def list_categories(
    store: Optional[str] = Query(None, description="Filter categories by store"),
    db: Database = Depends(get_db),
):
    """List all unique categories in the index."""
    categories = search_service.get_categories(db, store)
    return AggregationResponse(values=categories, total=len(categories))

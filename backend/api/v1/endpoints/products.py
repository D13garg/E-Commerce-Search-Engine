"""
api/v1/endpoints/products.py — Product details and product price history endpoints.
"""

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database
from typing import Optional

from core.database import get_db
from schemas.product import ProductResponse
from services import search_service, price_service

router = APIRouter()


@router.get("/products/{slug}", response_model=list[ProductResponse], tags=["Products"])
def get_product_by_slug(
    slug: str,
    store: Optional[str] = Query(None, description="Specific store listing"),
    db: Database = Depends(get_db),
):
    """
    Get product listing(s) by slug.
    Returns a list because the same product slug may exist across multiple stores.
    """
    return search_service.get_product_by_slug(db, slug, store)


@router.get("/products/{slug}/price-history", tags=["Price History"])
def price_history(
    slug: str,
    store: Optional[str] = Query(None, description="Filter by store"),
    limit: int = Query(100, ge=1, le=500),
    db: Database = Depends(get_db),
):
    """Get price history for a product."""
    history = price_service.get_price_history(db, slug=slug, store=store, limit=limit)
    return {"slug": slug, "store": store, "count": len(history), "history": history}

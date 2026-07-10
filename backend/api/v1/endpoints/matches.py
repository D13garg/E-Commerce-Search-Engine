"""
api/v1/endpoints/matches.py — Sneaker store matching and deals endpoints.
"""

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from core.database import get_db
from services import match_service

router = APIRouter()


@router.get("/matches/sku/{sku}", tags=["Matching"])
def match_by_sku(sku: str, db: Database = Depends(get_db)):
    """
    Get all store listings for a product by SKU.
    Shows price across every store that carries it.
    """
    return match_service.get_match_by_sku(db, sku)


@router.get("/matches/product/{slug}", tags=["Matching"])
def match_by_slug(
    slug: str,
    store: str = Query(..., description="Store this slug belongs to"),
    db: Database = Depends(get_db),
):
    """
    Given a product slug and store, find its cross-store match.
    Returns all store listings for the same physical product.
    """
    return match_service.get_match_by_slug(db, slug=slug, store=store)


@router.get("/deals", tags=["Matching"])
def best_deals(
    min_spread: float = Query(500, description="Minimum price difference in INR"),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
):
    """
    Products with the biggest price difference across stores.
    Sorted by price spread descending — biggest savings first.
    """
    deals = match_service.get_best_deals(db, limit=limit, min_spread=min_spread)
    return {"count": len(deals), "min_spread": min_spread, "deals": deals}


@router.get("/matches/stats", tags=["Matching"])
def matching_stats(db: Database = Depends(get_db)):
    """Summary statistics about the product matching index."""
    return match_service.get_match_stats(db)

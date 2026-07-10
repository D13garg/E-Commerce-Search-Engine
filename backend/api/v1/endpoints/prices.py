"""
api/v1/endpoints/prices.py — Price drops and history endpoints.
"""

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database
from typing import Optional

from core.database import get_db
from services import price_service

router = APIRouter()


@router.get("/price-drops", tags=["Price History"])
def price_drops(
    hours: int = Query(168, description="Look back window in hours (default 7 days)"),
    store: Optional[str] = Query(None, description="Filter by store"),
    min_drop_pct: float = Query(5.0, description="Minimum drop percentage to include"),
    db: Database = Depends(get_db),
):
    """Find products whose price dropped recently."""
    drops = price_service.get_price_drops(
        db,
        since_hours=hours,
        store=store,
        min_drop_pct=min_drop_pct,
    )
    return {
        "since_hours": hours,
        "min_drop_pct": min_drop_pct,
        "count": len(drops),
        "drops": drops,
    }

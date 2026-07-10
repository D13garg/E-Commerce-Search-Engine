"""
api/v1/endpoints/health.py — Health check endpoint.
"""

from fastapi import APIRouter, Depends
from pymongo.database import Database

from core.database import get_db
from services import search_service

router = APIRouter()


@router.get("/health", tags=["System"])
def health(db: Database = Depends(get_db)):
    """Check API and database connectivity."""
    count = search_service.get_total_count(db)
    return {"status": "ok", "total_products": count}

"""
api/v1/router.py — Root API router for v1 endpoints.
"""

from fastapi import APIRouter

from api.v1.endpoints import health, search, products, prices, matches

api_router = APIRouter()

# Register all endpoint sub-routers
api_router.include_router(health.router)
api_router.include_router(search.router)
api_router.include_router(products.router)
api_router.include_router(prices.router)
api_router.include_router(matches.router)

"""
main.py — Main application entry point for the sneaker search engine API.
"""

import os
import sys

# Ensure all absolute imports resolve correctly from the backend root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import get_db
from services import search_service
from middleware.error_handler import register_error_handlers
from middleware.logging import LoggingMiddleware
from api.v1.router import api_router

app = FastAPI(
    title="Sneaker Search Engine API",
    description="Search across HypeFly and Mainstreet product catalogues",
    version="0.1.0",
)

# CORS — allows frontend applications to consume the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Custom Request/Response Logging Middleware
app.add_middleware(LoggingMiddleware)

# Register AppException to HTTP response mapper
register_error_handlers(app)

# Include all aggregated API endpoints
app.include_router(api_router)


@app.on_event("startup")
def startup():
    """Create search indexes when the API starts."""
    db = get_db()
    search_service.setup_indexes(db)

"""
api/schemas.py — Request and response models for the API.

Why separate from models/product.py?
  models/product.py is the storage schema — it's shaped for MongoDB.
  API schemas are shaped for HTTP responses — they may differ:
    - We don't expose scraped_at/last_seen to API consumers
    - We add computed fields like available_sizes
    - We flatten nested structures for easier frontend consumption
    - Response models control exactly what JSON the client receives

This separation means you can change the internal storage schema
without breaking the API contract, and vice versa.
"""

from typing import Optional
from pydantic import BaseModel


class VariantResponse(BaseModel):
    size: str
    price: Optional[float] = None
    available: bool


class ProductResponse(BaseModel):
    title: str
    brand: Optional[str] = None
    sku: Optional[str] = None
    slug: str
    category: str
    price: Optional[float] = None
    currency: str
    image_url: Optional[str] = None
    product_url: str
    source_store: str
    variants: list[VariantResponse] = []
    available_sizes: list[str] = []   # computed: sizes where available=True


class SearchResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    results: list[ProductResponse]


class AggregationResponse(BaseModel):
    values: list[str]
    total: int
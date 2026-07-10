"""
schemas/product.py — Request and response schemas for the API.
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

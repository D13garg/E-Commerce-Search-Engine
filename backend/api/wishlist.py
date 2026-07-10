"""
api/wishlist.py — Wishlist endpoints. All require authentication.

Endpoints:
  POST   /wishlist              Add a product (idempotent)
  GET    /wishlist               List saved products with current prices
  GET    /wishlist/slugs         Compact {slug, source_store} set for bulk heart-state rendering
  DELETE /wishlist/{item_id}     Remove by wishlist item ID
  DELETE /wishlist/by-product    Remove by (slug, source_store) — convenient for the heart toggle
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from api.dependencies import get_db
from auth.dependencies import get_current_user
from auth.models import UserModel
from wishlist.models import WishlistRepository, WishlistAddRequest, WishlistItemResponse

router = APIRouter(prefix="/wishlist", tags=["Wishlist"])


def _to_response(doc: dict, current_price: float | None) -> WishlistItemResponse:
    added = doc.get("added_price")
    price_change = (
        round(current_price - added, 2)
        if current_price is not None and added is not None
        else None
    )
    return WishlistItemResponse(
        id=str(doc["_id"]),
        slug=doc["slug"],
        source_store=doc["source_store"],
        title=doc["title"],
        image_url=doc.get("image_url"),
        added_price=added,
        current_price=current_price,
        price_change=price_change,
        currency=doc.get("currency", "INR"),
        created_at=doc["created_at"].isoformat(),
    )


@router.post("", response_model=WishlistItemResponse, status_code=201)
def add_to_wishlist(
    body: WishlistAddRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Save a product. Idempotent — saving an already-saved product just returns it."""
    repo = WishlistRepository(db)
    repo.setup_indexes()
    doc = repo.add(current_user.id, body)
    return _to_response(doc, current_price=body.added_price)


@router.get("", response_model=list[WishlistItemResponse])
def get_wishlist(
    current_user: UserModel = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """
    List all saved products with their current price looked up live from `products`,
    so the "price since you saved" comparison is always fresh.
    """
    repo = WishlistRepository(db)
    items = repo.get_all(current_user.id)

    if not items:
        return []

    # Batch-fetch current prices in one query instead of N queries
    pairs = [(i["slug"], i["source_store"]) for i in items]
    products_col = db["products"]
    current_prices: dict[tuple[str, str], float | None] = {}

    cursor = products_col.find(
        {"$or": [{"slug": s, "source_store": st} for s, st in pairs]},
        {"slug": 1, "source_store": 1, "price": 1},
    )
    for p in cursor:
        current_prices[(p["slug"], p["source_store"])] = p.get("price")

    return [
        _to_response(item, current_prices.get((item["slug"], item["source_store"])))
        for item in items
    ]


@router.get("/slugs")
def get_wishlist_slugs(
    current_user: UserModel = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """
    Compact list for bulk heart-icon rendering on search/listing pages —
    avoids fetching full wishlist details just to know what's saved.
    """
    repo = WishlistRepository(db)
    pairs = repo.get_slugs(current_user.id)
    return {"items": [{"slug": s, "source_store": st} for s, st in pairs]}


@router.delete("/by-product")
def remove_by_product(
    slug: str = Query(...),
    source_store: str = Query(...),
    current_user: UserModel = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Remove by (slug, source_store) — used by the heart toggle on product cards."""
    repo = WishlistRepository(db)
    removed = repo.remove(current_user.id, slug, source_store)
    if not removed:
        raise HTTPException(status_code=404, detail="Item not found in wishlist.")
    return {"status": "removed"}


@router.delete("/{item_id}")
def remove_from_wishlist(
    item_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Remove by wishlist item ID."""
    repo = WishlistRepository(db)
    removed = repo.remove_by_id(current_user.id, item_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Item not found.")
    return {"status": "removed"}
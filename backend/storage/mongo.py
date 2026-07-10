"""
storage/mongo.py — MongoDB connection and product persistence.

Updated to record price history on every upsert.
Price history is written ONLY when the price actually changes —
see storage/price_history.py for the delta strategy.
"""

from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.collection import Collection

from models.product import Product
from config import MONGO_URI, MONGO_DB_NAME, PRODUCTS_COLLECTION
from storage.price_history import record_price, setup_indexes as setup_price_indexes


class MongoStorage:

    def __init__(self):
        print(f"[storage] Connecting to MongoDB: {MONGO_URI}")
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        self.products: Collection = self.db[PRODUCTS_COLLECTION]
        self._ensure_indexes()

    def _ensure_indexes(self):
        self.products.create_index(
            [("slug", 1), ("source_store", 1)],
            unique=True,
            name="slug_store_unique"
        )
        self.products.create_index("source_store", name="source_store_idx")
        self.products.create_index("brand", name="brand_idx")
        # Setup price history indexes too
        setup_price_indexes(self.db)
        print("[storage] Indexes ensured.")

    def upsert_product(self, product: Product) -> dict:
        """
        Insert or update a product document, and record price history if changed.
        """
        now = datetime.now(timezone.utc)

        doc = product.model_dump(exclude={"scraped_at", "last_seen"})
        doc["last_seen"] = now

        result = self.products.update_one(
            {"slug": product.slug, "source_store": product.source_store},
            {
                "$set": doc,
                "$setOnInsert": {"scraped_at": now},
            },
            upsert=True,
        )

        # Record price history — only writes if price changed
        if product.price is not None:
            price_changed = record_price(
                db=self.db,
                slug=product.slug,
                source_store=product.source_store,
                price=product.price,
                currency=product.currency,
            )
            if price_changed and result.matched_count > 0:
                print(f"[storage] 💰 Price change recorded for: {product.title}")

        if result.upserted_id:
            print(f"[storage] ✓ Inserted new product: {product.title} (id: {result.upserted_id})")
        else:
            print(f"[storage] ↻ Updated existing product: {product.title}")

        return {
            "matched_count": result.matched_count,
            "upserted_id": result.upserted_id,
        }

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
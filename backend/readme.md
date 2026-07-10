# Domain-Specific E-Commerce Search Engine

A search engine for sneakers and footwear, aggregating product data across multiple Indian stores. Built as a learning project to explore crawling, information retrieval, and product aggregation.

## What It Does

- Crawls product data from HypeFly and Mainstreet Marketplace
- Normalises products into a canonical schema
- Tracks price history and detects price drops
- Matches the same product across stores using SKU
- Exposes a search and comparison API

## Architecture

```
Stores (HypeFly, Mainstreet)
        ↓
   Crawlers (store-specific fetch + parse)
        ↓
   MongoDB (products, price_history, product_matches)
        ↓
   FastAPI (search, filters, price drops, deals)
```

## Project Structure

```
searchengine/
├── crawlers/
│   ├── base/           # Shared HTTP logic (retries, rate limiting)
│   ├── hypefly/        # HypeFly crawler (GraphQL API)
│   └── mainstreet/     # Mainstreet crawler (Shopify JSON API)
├── models/
│   └── product.py      # Canonical product schema (Pydantic)
├── storage/
│   ├── mongo.py        # Product upsert logic
│   ├── price_history.py # Price change tracking
│   └── matching.py     # Cross-store product matching
├── pipeline/
│   ├── run_hypefly.py      # Single product — HypeFly
│   ├── run_mainstreet.py   # Single product — Mainstreet
│   ├── bulk_hypefly.py     # Full HypeFly crawl
│   └── bulk_mainstreet.py  # Full Mainstreet crawl
├── api/
│   ├── main.py         # FastAPI routes
│   ├── search.py       # MongoDB query logic
│   ├── schemas.py      # API response models
│   └── dependencies.py # Shared DB connection
├── scheduler/
│   └── crawler_scheduler.py  # APScheduler re-crawl scheduler
└── scripts/
    ├── backfill_price_history.py  # One-time price history seed
    └── run_matching.py            # Cross-store product matching
```

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| HTTP client | httpx |
| HTML parsing | selectolax |
| Data validation | Pydantic v2 |
| Database | MongoDB (local or Atlas) |
| API framework | FastAPI + uvicorn |
| Scheduler | APScheduler |

## Setup

**1. Clone and create virtual environment**
```bash
git clone <repo>
cd searchengine
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Configure environment**
```bash
cp .env.example .env
# Edit .env — set MONGO_URI to your MongoDB connection string
```

**4. Start MongoDB**
```bash
# Local
sudo systemctl start mongod

# Or use MongoDB Atlas — paste connection string in .env
```

## Running

### Single product (development/testing)
```bash
python pipeline/run_hypefly.py --slug adidas-yeezy-boost-bright-blue-700
python pipeline/run_mainstreet.py --slug adidas-yeezy-500-enflame
```

### Full bulk crawl
```bash
# Test with 20 products first
python pipeline/bulk_hypefly.py --limit 20
python pipeline/bulk_mainstreet.py --limit 20

# Full crawl (background)
nohup python pipeline/bulk_hypefly.py > crawl_hypefly.log 2>&1 &
nohup python pipeline/bulk_mainstreet.py > crawl_mainstreet.log 2>&1 &
```

### One-time setup scripts (run after first bulk crawl)
```bash
# Seed price history baseline
python scripts/backfill_price_history.py

# Build cross-store product matches
python scripts/run_matching.py
```

### Start the API
```bash
uvicorn api.main:app --reload --port 8000
```
Visit `http://localhost:8000/docs` for interactive API documentation.

### Start the scheduler (daily re-crawl)
```bash
# Daily at 2:00 AM IST
nohup python scheduler/crawler_scheduler.py > scheduler.log 2>&1 &

# Custom interval
python scheduler/crawler_scheduler.py --hours 12

# Run immediately (testing)
python scheduler/crawler_scheduler.py --now
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | API status and total product count |
| GET | `/search` | Full-text search with filters |
| GET | `/products/{slug}` | Get all store listings for a product |
| GET | `/products/{slug}/price-history` | Price history for a product |
| GET | `/brands` | List all indexed brands |
| GET | `/stores` | List all indexed stores |
| GET | `/categories` | List all indexed categories |
| GET | `/price-drops` | Products with recent price drops |
| GET | `/deals` | Products with biggest cross-store price spread |
| GET | `/matches/sku/{sku}` | Cross-store match by SKU |
| GET | `/matches/product/{slug}` | Cross-store match by product slug |
| GET | `/matches/stats` | Matching index statistics |

### Example Queries
```
/search?q=yeezy
/search?q=dunk low&store=mainstreet&max_price=15000
/search?brand=Nike&available=true&page=2
/price-drops?hours=24&min_drop_pct=10
/deals?min_spread=5000
/matches/sku/GZ0541
```

## Data Sources

| Store | CMS | Discovery Method |
|---|---|---|
| HypeFly (hypefly.co.in) | Strapi + Next.js | GraphQL API (`graph.hypefly.co.in/graphql`) |
| Mainstreet (marketplace.mainstreet.co.in) | Shopify | Collection JSON API (`/products.json`) |

## Current Scale

- ~27,000 products indexed across 2 stores
- 738 cross-store product matches
- Price history tracked on every re-crawl
- Daily re-crawl scheduled at 2:00 AM IST

## Roadmap

- [ ] Frontend (React/Next.js search UI)
- [ ] Dawntown — third store
- [ ] Price alerts
- [ ] Semantic search (embeddings)
- [ ] Image search
- [ ] Multi-category expansion beyond sneakers
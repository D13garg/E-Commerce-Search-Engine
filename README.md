# E-Commerce Search Engine

A domain-specific search engine for sneakers, built to learn search systems, crawling, information retrieval, and product aggregation.

## Project Status
**Phase 1 & 2A Complete** — Production-ready backend with search, crawling, price tracking, cross-store matching, and a Next.js frontend.

## Architecture

```
Stores (HypeFly, Mainstreet)
        ↓
   Crawlers (store-specific fetch + parse)
        ↓
   MongoDB (source of truth)
        ↓
   Typesense (search index, C++, <10ms)
        ↓
   FastAPI (REST API)
        ↓
   Next.js Frontend
```

## Tech Stack

| Layer | Technology | Language |
|---|---|---|
| Crawlers | httpx, selectolax, Pydantic | Python |
| Storage | MongoDB Atlas / Local | — |
| Search | Typesense 27.0 | C++ |
| API | FastAPI + uvicorn | Python |
| Frontend | Next.js 16, React 19, Tailwind | TypeScript |
| Scheduler | APScheduler | Python |

## Project Structure

```
E-Commerce Search Engine/
├── backend/
│   ├── core/                      # config, database, exceptions, typesense client
│   ├── crawlers/
│   │   ├── base/                  # shared HTTP logic (retries, rate limiting)
│   │   ├── hypefly/               # HypeFly crawler (Strapi + GraphQL API)
│   │   └── mainstreet/            # Mainstreet crawler (Shopify JSON API)
│   ├── models/                    # canonical product schema (Pydantic)
│   ├── repositories/              # MongoDB query layer only
│   ├── services/                  # business logic layer
│   ├── schemas/                   # API request/response shapes
│   ├── middleware/                 # error handling, logging
│   ├── api/v1/endpoints/          # FastAPI route handlers
│   ├── pipeline/                  # crawl orchestrators
│   ├── scheduler/                 # APScheduler daily re-crawl
│   └── scripts/                   # one-time and utility scripts
└── frontend/
    ├── app/                       # Next.js app router pages
    ├── components/                # Navbar, ProductCard, Ticker
    └── lib/                       # API client, formatters
```

## Data Sources

| Store | CMS | Discovery |
|---|---|---|
| HypeFly (hypefly.co.in) | Strapi + Next.js | GraphQL API at graph.hypefly.co.in/graphql |
| Mainstreet (marketplace.mainstreet.co.in) | Shopify | Collection JSON API /products.json |

## Current Scale
- ~27,000 products indexed across 2 stores
- 738 cross-store product matches (SKU-based + slug similarity)
- Price history tracked on every re-crawl
- Daily re-crawl at 2:00 AM IST

## Features Built

### Backend
- **Multi-store crawling** — HypeFly via GraphQL (100 products/request), Mainstreet via Shopify API
- **Canonical schema** — Pydantic model normalises all store data into one shape
- **MongoDB storage** — upsert pattern, compound indexes, `scraped_at` / `last_seen` timestamps
- **Price history** — delta-based tracking, only records when price changes
- **Cross-store matching** — Tier 1: SKU match (high confidence), Tier 2: slug word-set match (medium)
- **Typesense search** — fuzzy matching, prefix search, availability boost, BM25 ranking
- **Query understanding** — regex parser extracts price/availability/store from natural language
- **Autocomplete** — pre-computed suggestion index with debounced prefix search
- **Synonyms** — sneaker community terms (aj1→Air Jordan 1, yzy→Yeezy, bred→Black Red, etc.)
- **Scheduler** — APScheduler daily re-crawl, smart re-crawl skips recently seen products
- **Layered architecture** — core / repositories / services / api/v1/endpoints

### Frontend
- Dark editorial design (Bebas Neue, DM Mono, Inter)
- Live ticker showing top deals
- Search with autocomplete dropdown (debounced, AbortController)
- Filter panel (store, brand, price range, availability)
- Product cards with store badges, price, available sizes
- Product detail page with cross-store comparison + price history chart (Recharts)
- Deals page — biggest price spreads across stores
- Price drops page — recent price decreases

## Setup

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your MongoDB URI
```

### Typesense
```bash
# Download from https://typesense.org/docs/guide/install-typesense.html
./typesense-server --data-dir=/tmp/typesense-data --api-key=searchengine_dev_key --enable-cors &
```

### Running
```bash
# 1. Run full crawl
python pipeline/bulk_hypefly.py
python pipeline/bulk_mainstreet.py

# 2. One-time setup scripts
python scripts/backfill_price_history.py
python scripts/run_matching.py
python scripts/sync_typesense.py
python scripts/build_suggestions.py
python scripts/setup_synonyms.py

# 3. Start API
uvicorn api.main:app --reload --port 8000

# 4. Start scheduler (daily re-crawl)
nohup python scheduler/crawler_scheduler.py > scheduler.log 2>&1 &
```

### Frontend
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
# Visit http://localhost:3000
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | API status + total product count |
| GET | `/search` | Full-text search with NL query understanding |
| GET | `/suggest` | Autocomplete suggestions |
| GET | `/products/{slug}` | All store listings for a product |
| GET | `/products/{slug}/price-history` | Price history chart data |
| GET | `/brands` | All unique brands |
| GET | `/stores` | All indexed stores |
| GET | `/categories` | All unique categories |
| GET | `/price-drops` | Recent price decreases |
| GET | `/deals` | Biggest cross-store price spreads |
| GET | `/matches/sku/{sku}` | Cross-store match by SKU |
| GET | `/matches/product/{slug}` | Cross-store match by slug |
| GET | `/matches/stats` | Matching index statistics |

### Natural Language Search Examples
```
/search?q=jordan 1 under 10k
/search?q=nike dunk available below 15000
/search?q=yeezy on hypefly
/search?q=adidas samba between 5k and 20k
```

## Roadmap

### Phase 2B (next)
- [ ] Generic crawler engine — configure new stores via JSON, no Python per store
- [ ] Go API migration — rewrite FastAPI in Go for better concurrency
- [ ] Price alerts — email/WhatsApp notification when price drops below threshold

### Phase 3
- [ ] Semantic search — sentence-transformers + Faiss (C++ backed)
- [ ] Image search — upload photo, find the shoe
- [ ] Multi-category expansion beyond sneakers
- [ ] ML-based product matching beyond SKU
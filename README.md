# E-Commerce Search Engine (working title: MarketLens)

A search engine and price-intelligence platform for Indian D2C stores, built to learn search systems, crawling, information retrieval, and product aggregation. Started as a sneaker-only project; the crawler layer has since generalised and the frontend has already been rebranded to **"MarketLens — Price Intelligence"**, though the repo name and most backend strings haven't caught up yet.

## Project Status — mid-refactor, not "done"

The core search/crawl/match pipeline (Phase 1 & 2A) is solid and working. Since then, several features were built ahead of the roadmap, but the project is currently **split across two FastAPI apps** and needs integration work before the newer features are actually usable end-to-end.

**What's live and working (via `backend/main.py`, the layered app):**
- Search, autocomplete, product detail, price history, cross-store matching, deals/price-drops — all migrated into the new `core / repositories / services / api/v1/endpoints` architecture.

**What's built but NOT wired into that app yet:**
- **Auth** (`backend/auth/`, `backend/api/auth.py`) — full OTP email verification, login/register/forgot-password, Google OAuth, CSRF, JWT access + refresh tokens.
- **Wishlist** (`backend/wishlist/`, `backend/api/wishlist.py`) — save/remove products, list by slug.
- **Price alerts** (`backend/alerts/`) — checker + email notifier via Resend, no API/UI wiring finished.
- These three only run under the **older monolithic app**, `backend/api/main.py` (still referenced in `backend/readme.md`'s run instructions) — they are not included in `backend/main.py`'s router yet. Whichever app you run, you only get half the features.
- **The frontend already assumes the merged state.** `frontend/lib/auth.ts` and `frontend/lib/wishlist.ts` call `/auth/*` and `/wishlist/*`, and there are working pages for login, register, OTP verification, forgot-password, and wishlist — none of which will function against `backend/main.py` as it stands today.

**Ahead of the old roadmap, already built:**
- **Generic crawler engine** (`backend/crawlers/generic/`) — configure a new Shopify store via a JSON file (`backend/stores/*.json`), no per-store Python needed. 22 store configs already exist, spanning sneakers/streetwear, fashion, beauty, electronics, and watches/accessories — well beyond the original "sneakers only" scope. HypeFly stays on its own custom crawler since it's not Shopify.
- Not all 22 are confirmed crawled at production scale yet — `verify_stores.py` is a discovery/validation script for finding new candidate stores, and `scripts/manage_stores.py` can validate or test-connect a config, but there's no committed record of which of the 22 have had a full bulk crawl run.

**Known housekeeping debt:**
- Two config files exist side by side — `backend/config.py` (plain `os.getenv`, used by the old app + auth/alerts) and `backend/core/config.py` (Pydantic Settings, used by the new app). They haven't been merged.
- `.env.example` only documents `MONGO_URI` / `MONGO_DB_NAME`. It's missing `TYPESENSE_*`, `SECRET_KEY`, `PEPPER`, `GOOGLE_CLIENT_ID`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `APP_BASE_URL`, and `ENVIRONMENT`, all of which `config.py` reads.
- The "~27,000 products / 738 matches" scale numbers below are from the original 2-store (HypeFly + Mainstreet) crawl and haven't been recomputed since the generic crawler and extra store configs were added.

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
│   ├── main.py                    # NEW app entry point — search/products/prices/matches only
│   ├── config.py                  # legacy config (os.getenv) — used by api/main.py, auth, alerts
│   ├── core/                      # NEW config (Pydantic Settings), database, exceptions, typesense client
│   ├── crawlers/
│   │   ├── base/                  # shared HTTP logic (retries, rate limiting)
│   │   ├── hypefly/                # HypeFly crawler (Strapi + GraphQL API, custom)
│   │   ├── mainstreet/             # Mainstreet crawler (Shopify JSON API, custom)
│   │   └── generic/                # JSON-configured Shopify crawler for any new store
│   ├── stores/                    # JSON configs for the generic crawler (22 stores)
│   ├── models/                    # canonical product schema (Pydantic)
│   ├── repositories/               # MongoDB query layer — used by the NEW app
│   ├── services/                  # business logic layer — used by the NEW app
│   ├── schemas/                   # API request/response shapes — used by the NEW app
│   ├── middleware/                 # error handling, logging
│   ├── api/
│   │   ├── main.py                # OLD app entry point — still the only one with auth/wishlist/alerts wired
│   │   ├── v1/endpoints/          # FastAPI route handlers for the NEW app
│   │   ├── auth.py, wishlist.py, alerts.py   # endpoints, only mounted on the OLD app
│   │   └── search.py, schemas.py  # OLD app's MongoDB query logic
│   ├── auth/                      # OTP auth, JWT, CSRF, Google OAuth — built, not yet on the NEW app
│   ├── wishlist/                  # wishlist model/repo — built, not yet on the NEW app
│   ├── alerts/                    # price alert checker + email notifier — no API/UI wiring yet
│   ├── storage/                   # price history + cross-store matching (used by both apps)
│   ├── pipeline/                  # crawl orchestrators, incl. run_generic.py for any store config
│   ├── scheduler/                 # APScheduler daily re-crawl (HypeFly + Mainstreet only)
│   └── scripts/                   # one-time scripts, incl. manage_stores.py for store configs
└── frontend/
    ├── app/                       # Next.js app router pages — includes login/register/wishlist pages
    │                              #   that call endpoints only the OLD backend app serves
    ├── contexts/                  # AuthContext, WishlistContext
    ├── components/                # Navbar, ProductCard, Ticker
    └── lib/                       # API client, auth client, wishlist client, formatters
```

## Data Sources

**Live in the current index (custom crawlers, run and confirmed):**

| Store | CMS | Discovery |
|---|---|---|
| HypeFly (hypefly.co.in) | Strapi + Next.js | GraphQL API at graph.hypefly.co.in/graphql |
| Mainstreet (marketplace.mainstreet.co.in) | Shopify | Collection JSON API /products.json |

**Configured for the generic crawler (`backend/stores/*.json`), not yet confirmed crawled at scale:**

22 additional Shopify stores across sneakers/streetwear, fashion, beauty, electronics, and watches/accessories — e.g. Superkicks, Dawntown, Crepdogcrew, Neemans, Minimalist, boAt, Noise, Sassafras, Chumbak, and others. Run `python scripts/manage_stores.py list` for the full set, or `python pipeline/run_generic.py --store <name> --dry-run` to test one before crawling for real.

## Current Scale
- ~27,000 products indexed, 738 cross-store matches — **this reflects only the original HypeFly + Mainstreet crawl** and predates the generic crawler / extra store configs above, so it's understated for what the codebase can now cover.
- Price history tracked on every re-crawl
- Daily re-crawl at 2:00 AM IST (HypeFly + Mainstreet only, via the scheduler below)

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
- **Generic Shopify crawler** — JSON-configured, 22 stores set up, no per-store Python
- **Auth** — OTP email verification, JWT access/refresh, Google OAuth, CSRF *(built, only runs on `api/main.py`, see Project Status)*
- **Wishlist** — save/remove/list products per user *(built, only runs on `api/main.py`)*
- **Price alerts** — checker + Resend email notifier *(logic built, no API/UI wiring yet)*

### Frontend
- Dark editorial design (Bebas Neue, DM Mono, Inter)
- Live ticker showing top deals
- Search with autocomplete dropdown (debounced, AbortController)
- Filter panel (store, brand, price range, availability)
- Product cards with store badges, price, available sizes
- Product detail page with cross-store comparison + price history chart (Recharts)
- Deals page — biggest price spreads across stores
- Price drops page — recent price decreases
- Login, register, OTP verification, forgot-password, and wishlist pages *(built, but need the OLD backend app running to actually work — see Project Status)*

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

# 3. Start the API — pick ONE, they are not equivalent right now:

# 3a. New layered app — search/products/prices/matches only, no auth/wishlist/alerts
uvicorn main:app --reload --port 8000

# 3b. OLD monolithic app — adds auth, wishlist, and alerts, but not the newer
#     layered internals. Needed if you want the frontend's login/wishlist pages to work.
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

Served by both apps (`main.py` and `api/main.py`):

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

Served **only** by `api/main.py` (see Project Status):

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register/initiate`, `/auth/register/verify` | Email OTP registration |
| POST | `/auth/login`, `/auth/google` | Login (password or Google OAuth) |
| POST | `/auth/forgot-password/initiate`, `/auth/forgot-password/verify` | Password reset via OTP |
| POST | `/auth/refresh`, `/auth/logout` | Token refresh / logout |
| GET | `/auth/me` | Current user |
| GET/POST | `/wishlist`, `/wishlist/slugs`, `/wishlist/by-product` | Wishlist read/write |
| DELETE | `/wishlist/{itemId}` | Remove a wishlist item |
| — | `/alerts/*` (`api/alerts.py`) | Price alert endpoints — exist but not yet exercised by the frontend |

### Natural Language Search Examples
```
/search?q=jordan 1 under 10k
/search?q=nike dunk available below 15000
/search?q=yeezy on hypefly
/search?q=adidas samba between 5k and 20k
```

## Roadmap

### Immediate — finish the in-progress merge
- [ ] Wire `auth`, `wishlist`, and `alerts` routers into `backend/main.py` / `api/v1/router.py` so the layered app has full parity with `backend/api/main.py`
- [ ] Retire `backend/api/main.py` once parity is reached, and update `backend/readme.md`'s run instructions off it
- [ ] Merge `backend/config.py` into `backend/core/config.py` (Pydantic Settings) and delete the duplicate
- [ ] Bring `.env.example` up to date with everything `config.py` actually reads (Typesense, JWT secret/pepper, Google OAuth, Resend)
- [ ] Run a full bulk crawl across the 22 generic-crawler store configs and refresh the "current scale" numbers
- [ ] Decide on the MarketLens rebrand — either commit to it repo-wide (rename, update `backend/readme.md`, package names) or revert the frontend title/email sender name

### Phase 2B
- [x] Generic crawler engine — configure new stores via JSON, no Python per store
- [ ] Go API migration — rewrite FastAPI in Go for better concurrency
- [ ] Price alerts — checker/notifier logic exists (`backend/alerts/`); needs an API + frontend UI to actually be user-facing

### Phase 3
- [ ] Semantic search — sentence-transformers + Faiss (C++ backed)
- [ ] Image search — upload photo, find the product
- [ ] ML-based product matching beyond SKU

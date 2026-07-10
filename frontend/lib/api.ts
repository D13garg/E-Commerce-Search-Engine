// lib/api.ts — Centralised API client

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Variant {
  size: string
  price: number | null
  available: boolean
}

export interface Product {
  title: string
  brand: string | null
  sku: string | null
  slug: string
  category: string
  price: number | null
  currency: string
  image_url: string | null
  product_url: string
  source_store: string
  variants: Variant[]
  available_sizes: string[]
}

export interface SearchResponse {
  total: number
  page: number
  limit: number
  pages: number
  results: Product[]
}

export interface PriceHistoryEntry {
  slug: string
  source_store: string
  price: number
  currency: string
  recorded_at: string
}

export interface PriceDrop {
  slug: string
  source_store: string
  current_price: number
  previous_price: number
  drop_amount: number
  drop_pct: number
  currency: string
  recorded_at: string
}

export interface MatchListing {
  slug: string
  store: string
  price: number | null
  currency: string
}

export interface ProductMatch {
  sku: string | null
  match_type: string
  confidence: string
  listings: MatchListing[]
  stores: string[]
  best_price: number | null
  best_price_store: string | null
  price_spread: number | null
}

export interface Deal {
  sku: string | null
  best_price: number | null
  best_price_store: string | null
  confidence: string
  listings: MatchListing[]
  match_type: string
  price_spread: number | null
  stores: string[]
}

async function apiFetch<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`)
  if (params) {
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        url.searchParams.set(key, String(val))
      }
    })
  }
  const res = await fetch(url.toString(), {
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json()
}

export interface SearchParams {
  q?: string
  brand?: string
  store?: string
  category?: string
  min_price?: number
  max_price?: number
  available?: boolean
  page?: number
  limit?: number
}

export const searchProducts = (params: SearchParams): Promise<SearchResponse> =>
  apiFetch<SearchResponse>('/search', params as Record<string, string | number | boolean | undefined>)

export const getProduct = (slug: string): Promise<Product[]> =>
  apiFetch<Product[]>(`/products/${slug}`)

export const getPriceHistory = (slug: string, store?: string) =>
  apiFetch<{ slug: string; store: string | null; count: number; history: PriceHistoryEntry[] }>(
    `/products/${slug}/price-history`, store ? { store } : undefined
  )

export const getPriceDrops = (params?: { hours?: number; store?: string; min_drop_pct?: number }) =>
  apiFetch<{ since_hours: number; min_drop_pct: number; count: number; drops: PriceDrop[] }>(
    '/price-drops', params as Record<string, string | number | boolean | undefined>
  )

export const getDeals = (params?: { min_spread?: number; limit?: number }) =>
  apiFetch<{ count: number; min_spread: number; deals: Deal[] }>(
    '/deals', params as Record<string, string | number | boolean | undefined>
  )

export const getMatchBySku = (sku: string): Promise<ProductMatch> =>
  apiFetch(`/matches/sku/${sku}`)

export const getMatchBySlug = (slug: string, store: string): Promise<ProductMatch> =>
  apiFetch(`/matches/product/${slug}`, { store })

// ── Alerts ────────────────────────────────────────────────────────────────────

export interface Alert {
  id: string
  token: string
  email: string
  phone: string | null
  slug: string
  source_store: string | null
  trigger: 'any_drop' | 'below_price'
  target_price: number | null
  currency: string
  active: boolean
  created_at: string
  last_triggered: string | null
  trigger_count: number
}

export const getAlerts = (email: string): Promise<Alert[]> =>
  apiFetch<Alert[]>(`/alerts/${encodeURIComponent(email)}`)

export const deleteAlert = (id: string): Promise<{ status: string }> =>
  fetch(`${API_BASE}/alerts/${id}`, { method: 'DELETE' }).then(r => r.json())

export const getBrands = (store?: string) =>
  apiFetch<{ values: string[]; total: number }>('/brands', store ? { store } : undefined)

export const getStores = () =>
  apiFetch<{ values: string[]; total: number }>('/stores')

export const getHealth = () =>
  apiFetch<{ status: string; total_products: number }>('/health')

export const formatPrice = (price: number | null, currency = 'INR'): string => {
  if (price === null || price === undefined || price <= 0) return '—'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(price)
}

export const formatStore = (store: string): string => {
  const map: Record<string, string> = {
    hypefly:        'HypeFly',
    mainstreet:     'Mainstreet',
    dawntown:       'Dawntown',
    crepdogcrew:    'Crepdog Crew',
    sneakwear:      'Sneakwear',
    hypeelixir:     'Hype Elixir',
    kicksmachine:   'Kicks Machine',
    yoursneakerstore: 'Your Sneaker Store',
    '10hillsstudio': '10 Hills Studio',
    superkicks:     'Superkicks',
    snitch:         'Snitch',
    sassafras:      'Sassafras',
    chumbak:        'Chumbak',
    neemans:        'Neemans',
    minimalist:     'Minimalist',
    mcaffeine:      'mCaffeine',
    plum:           'Plum',
    sugarpop:       'SUGAR Cosmetics',
    boat:           'boAt',
    noise:          'Noise',
    portronics:     'Portronics',
    zebronics:      'Zebronics',
    crossbeats:     'Crossbeats',
  }
  return map[store] || store.charAt(0).toUpperCase() + store.slice(1)
}

export const timeAgo = (dateStr: string): string => {
  const diff = Date.now() - new Date(dateStr).getTime()
  const hours = Math.floor(diff / 3600000)
  if (hours < 1) return 'just now'
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
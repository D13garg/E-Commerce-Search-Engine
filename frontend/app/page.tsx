'use client'
import { useState, useCallback, useEffect, useRef } from 'react'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import { searchProducts, Product, SearchResponse, formatPrice, formatStore, getStores, getBrands } from '@/lib/api'
import ProductCard from '@/components/ProductCard'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Suggestion {
  term: string
  type: string
  count: number
  brands: string[]
  min_price: number | null
  has_available: boolean
}

const TYPE_ICON: Record<string, string> = {
  brand:   '🏷',
  model:   '👟',
  product: '🔍',
}

const TYPE_LABEL: Record<string, string> = {
  brand:   'BRAND',
  model:   'MODEL',
  product: 'PRODUCT',
}

export default function HomePage() {
  const [query, setQuery]             = useState('')
  const [store, setStore]             = useState('')
  const [brand, setBrand]             = useState('')
  const [minPrice, setMinPrice]       = useState('')
  const [maxPrice, setMaxPrice]       = useState('')
  const [available, setAvailable]     = useState(false)
  const [page, setPage]               = useState(1)
  const [results, setResults]         = useState<SearchResponse | null>(null)
  const [loading, setLoading]         = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)

  // Dynamic stores and brands from API
  const [stores, setStores] = useState<string[]>([])
  const [brands, setBrands] = useState<string[]>([])

  useEffect(() => {
    getStores().then(data => setStores(data.values ?? [])).catch(() => {})
    getBrands().then(data => setBrands(data.values ?? [])).catch(() => {})
  }, [])

  // Autocomplete state
  const [suggestions, setSuggestions]         = useState<Suggestion[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [activeSuggestion, setActiveSuggestion] = useState(-1)
  const [fetchingSuggestions, setFetchingSuggestions] = useState(false)

  const searchRef = useRef<HTMLDivElement>(null)

  // Debounce + AbortController pattern
  // Why AbortController?
  //   setTimeout alone prevents extra renders but the fetch still fires.
  //   AbortController cancels in-flight HTTP requests too — no wasted bandwidth.
  //   Result: only ONE network request per completed pause, zero duplicates.
  useEffect(() => {
    if (query.trim().length < 2) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }

    const controller = new AbortController()

    const timer = setTimeout(() => {
      setFetchingSuggestions(true)
      fetch(
        `${API_BASE}/suggest?q=${encodeURIComponent(query.trim())}&limit=8`,
        { signal: controller.signal }
      )
        .then(r => r.json())
        .then(data => {
          setSuggestions(data.suggestions || [])
          setShowSuggestions(true)
          setActiveSuggestion(-1)
        })
        .catch(e => {
          if (e.name !== 'AbortError') setSuggestions([])
        })
        .finally(() => setFetchingSuggestions(false))
    }, 300)

    // Cleanup: cancel both the timer AND any in-flight request
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const doSearch = useCallback(async (q: string, p = 1) => {
    setLoading(true)
    setHasSearched(true)
    setShowSuggestions(false)
    try {
      const res = await searchProducts({
        q: q || undefined,
        store: store || undefined,
        brand: brand || undefined,
        min_price: minPrice ? Number(minPrice) : undefined,
        max_price: maxPrice ? Number(maxPrice) : undefined,
        available: available || undefined,
        page: p,
        limit: 24,
      })
      setResults(res)
      setPage(p)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [store, brand, minPrice, maxPrice, available])

  const handleKey = (e: React.KeyboardEvent) => {
    if (showSuggestions && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveSuggestion(i => Math.min(i + 1, suggestions.length - 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveSuggestion(i => Math.max(i - 1, -1))
        return
      }
      if (e.key === 'Escape') {
        setShowSuggestions(false)
        return
      }
      if (e.key === 'Enter' && activeSuggestion >= 0) {
        const term = suggestions[activeSuggestion].term
        setQuery(term)
        doSearch(term, 1)
        return
      }
    }
    if (e.key === 'Enter') doSearch(query, 1)
  }

  const selectSuggestion = (term: string) => {
    setQuery(term)
    doSearch(term, 1)
    setShowSuggestions(false)
  }

  const clearFilters = () => {
    setStore(''); setBrand(''); setMinPrice(''); setMaxPrice(''); setAvailable(false)
  }

  const hasFilters = store || brand || minPrice || maxPrice || available

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>

      {/* ── Hero / Search ────────────────────────────────────────────────── */}
      <div style={{
        borderBottom: '1px solid var(--border)',
        padding: hasSearched ? '28px 28px 0' : '80px 28px 0',
        transition: 'padding 0.3s ease',
      }}>
        <div style={{ maxWidth: '860px', margin: '0 auto' }}>

          {/* Title — only visible before first search */}
          {!hasSearched && (
            <div className="animate-fade-up" style={{ textAlign: 'center', marginBottom: '36px' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
                color: 'var(--text-3)',
                letterSpacing: '0.14em',
                marginBottom: '14px',
              }}>
                PRICE INTELLIGENCE ENGINE
              </div>
              <h1 style={{
                fontFamily: 'var(--font-display)',
                fontSize: 'clamp(52px, 8vw, 96px)',
                letterSpacing: '0.04em',
                lineHeight: 0.9,
                color: 'var(--text)',
                marginBottom: '16px',
              }}>
                FIND THE BEST<br />
                <span style={{ color: 'var(--accent)' }}>PRICE</span> ANYWHERE
              </h1>
              <p style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                color: 'var(--text-3)',
                letterSpacing: '0.06em',
              }}>
                {stores.length > 0 ? stores.length : '20'}+ STORES · 100K+ PRODUCTS · REAL-TIME
              </p>
            </div>
          )}

          {/* Search bar */}
          <div ref={searchRef} style={{ position: 'relative', marginBottom: '0' }}>
            <div style={{
              display: 'flex',
              gap: '8px',
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderBottom: showFilters ? '1px solid var(--border)' : '1px solid var(--border)',
              borderRadius: hasSearched ? '6px 6px 0 0' : '6px',
              padding: '8px',
              transition: 'border-color 0.15s, box-shadow 0.15s',
            }}>
              {/* Search icon */}
              <div style={{ display: 'flex', alignItems: 'center', paddingLeft: '6px', color: 'var(--text-3)' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
              </div>

              {/* Input */}
              <input
                className="search-input"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Search anything — nike under ₹10,000, dunk available, yeezy…"
                style={{
                  flex: 1,
                  border: 'none',
                  background: 'transparent',
                  fontSize: '15px',
                  padding: '6px 0',
                  boxShadow: 'none',
                }}
                autoFocus
              />

              {/* Clear */}
              {query && (
                <button
                  onClick={() => { setQuery(''); setSuggestions([]); setShowSuggestions(false) }}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--text-3)', display: 'flex', alignItems: 'center', padding: '0 4px',
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6 6 18M6 6l12 12"/>
                  </svg>
                </button>
              )}

              {/* Filter toggle */}
              <button
                onClick={() => setShowFilters(f => !f)}
                style={{
                  background: showFilters ? 'var(--accent)' : 'var(--surface-2)',
                  border: `1px solid ${showFilters ? 'var(--accent)' : 'var(--border)'}`,
                  borderRadius: '4px',
                  color: showFilters ? '#fff' : 'var(--text-2)',
                  cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '5px',
                  padding: '6px 12px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '10px',
                  letterSpacing: '0.08em',
                  transition: 'all 0.15s',
                  position: 'relative',
                }}
              >
                {hasFilters && (
                  <span style={{
                    position: 'absolute', top: '-3px', right: '-3px',
                    width: '7px', height: '7px', borderRadius: '50%',
                    background: 'var(--accent)', border: '1px solid var(--bg)',
                  }} />
                )}
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="4" y1="6" x2="20" y2="6"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="11" y1="18" x2="13" y2="18"/>
                </svg>
                FILTERS
              </button>

              {/* Search button */}
              <button
                onClick={() => doSearch(query, 1)}
                style={{
                  background: 'var(--accent)',
                  border: 'none',
                  borderRadius: '4px',
                  color: '#fff',
                  cursor: 'pointer',
                  padding: '6px 18px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  fontWeight: 500,
                  letterSpacing: '0.08em',
                  transition: 'opacity 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
                onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
              >
                SEARCH
              </button>
            </div>

            {/* Suggestions dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 50,
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderTop: 'none',
                borderRadius: '0 0 6px 6px',
                overflow: 'hidden',
              }}>
                {suggestions.map((s, i) => (
                  <div
                    key={s.term}
                    onClick={() => selectSuggestion(s.term)}
                    style={{
                      padding: '10px 16px',
                      cursor: 'pointer',
                      background: i === activeSuggestion ? 'var(--surface-2)' : 'transparent',
                      borderBottom: i < suggestions.length - 1 ? '1px solid var(--border)' : 'none',
                      display: 'flex', alignItems: 'center', gap: '10px',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--surface-2)')}
                    onMouseLeave={e => (e.currentTarget.style.background = i === activeSuggestion ? 'var(--surface-2)' : 'transparent')}
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2">
                      <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                    </svg>
                    <span style={{ fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text)' }}>
                      {s.term}
                    </span>
                    {s.count && (
                      <span style={{ marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)' }}>
                        {s.count}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Filter panel */}
            {showFilters && (
              <div style={{
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderTop: 'none',
                borderRadius: '0 0 6px 6px',
                padding: '16px',
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr 1fr auto',
                gap: '10px',
                alignItems: 'end',
              }}>
                {/* Store */}
                <div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)', letterSpacing: '0.1em', marginBottom: '6px' }}>
                    STORE
                  </div>
                  <select
                    value={store}
                    onChange={e => setStore(e.target.value)}
                    style={{
                      width: '100%', padding: '8px 10px', background: 'var(--surface-2)',
                      border: '1px solid var(--border)', borderRadius: '4px',
                      color: store ? 'var(--text)' : 'var(--text-3)',
                      fontFamily: 'var(--font-mono)', fontSize: '11px',
                      cursor: 'pointer',
                    }}
                  >
                    <option value="">All Stores</option>
                    {stores.map(s => <option key={s} value={s}>{formatStore(s)}</option>)}
                  </select>
                </div>

                {/* Brand */}
                <div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)', letterSpacing: '0.1em', marginBottom: '6px' }}>
                    BRAND
                  </div>
                  <select
                    value={brand}
                    onChange={e => setBrand(e.target.value)}
                    style={{
                      width: '100%', padding: '8px 10px', background: 'var(--surface-2)',
                      border: '1px solid var(--border)', borderRadius: '4px',
                      color: brand ? 'var(--text)' : 'var(--text-3)',
                      fontFamily: 'var(--font-mono)', fontSize: '11px',
                      cursor: 'pointer',
                    }}
                  >
                    <option value="">All Brands</option>
                    {brands.map(b => <option key={b} value={b}>{b}</option>)}
                  </select>
                </div>

                {/* Min price */}
                <div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)', letterSpacing: '0.1em', marginBottom: '6px' }}>
                    MIN PRICE (₹)
                  </div>
                  <input
                    type="number"
                    value={minPrice}
                    onChange={e => setMinPrice(e.target.value)}
                    placeholder="0"
                    className="search-input"
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '4px', fontSize: '12px' }}
                  />
                </div>

                {/* Max price */}
                <div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)', letterSpacing: '0.1em', marginBottom: '6px' }}>
                    MAX PRICE (₹)
                  </div>
                  <input
                    type="number"
                    value={maxPrice}
                    onChange={e => setMaxPrice(e.target.value)}
                    placeholder="∞"
                    className="search-input"
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '4px', fontSize: '12px' }}
                  />
                </div>

                {/* In stock + clear */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={available}
                      onChange={e => setAvailable(e.target.checked)}
                      style={{ accentColor: 'var(--accent)', width: '13px', height: '13px' }}
                    />
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-2)', letterSpacing: '0.08em', whiteSpace: 'nowrap' }}>
                      IN STOCK
                    </span>
                  </label>
                  {hasFilters && (
                    <button
                      onClick={clearFilters}
                      style={{
                        background: 'none', border: '1px solid var(--border)', borderRadius: '4px',
                        color: 'var(--text-3)', cursor: 'pointer', padding: '5px 10px',
                        fontFamily: 'var(--font-mono)', fontSize: '9px', letterSpacing: '0.06em',
                        transition: 'border-color 0.15s, color 0.15s',
                        whiteSpace: 'nowrap',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-2)'; e.currentTarget.style.color = 'var(--text-2)' }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-3)' }}
                    >
                      CLEAR
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Quick searches — only before first search */}
          {!hasSearched && (
            <div className="animate-fade-up" style={{
              display: 'flex', gap: '8px', flexWrap: 'wrap',
              padding: '16px 0 28px', justifyContent: 'center',
            }}>
              {['Jordan 1', 'Nike Dunk', 'Yeezy', 'New Balance', 'On Running'].map(term => (
                <button
                  key={term}
                  className="filter-pill"
                  onClick={() => { setQuery(term); doSearch(term, 1) }}
                >
                  {term}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Results ──────────────────────────────────────────────────────── */}
      <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '0 28px 80px' }}>

        {/* Result meta */}
        {hasSearched && !loading && results && (
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '16px 0', borderBottom: '1px solid var(--border)', marginBottom: '24px',
          }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)', letterSpacing: '0.06em' }}>
              <span style={{ color: 'var(--text)', fontWeight: 500 }}>
                {results.total.toLocaleString('en-IN')}
              </span>
              {' '}RESULTS{query ? ` FOR "${query.toUpperCase()}"` : ''}
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)' }}>
              PAGE {results.page} / {Math.ceil(results.total / (results.limit || 24))}
            </div>
          </div>
        )}

        {/* Loading skeletons */}
        {loading && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: '12px',
            paddingTop: '24px',
          }}>
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: '320px' }} />
            ))}
          </div>
        )}

        {/* Empty */}
        {hasSearched && !loading && results?.results.length === 0 && (
          <div style={{ textAlign: 'center', padding: '100px 0' }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: '56px', color: 'var(--text-4)', marginBottom: '12px' }}>
              NO RESULTS
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)' }}>
              Try a different search or remove some filters
            </div>
          </div>
        )}

        {/* Grid */}
        {!loading && results && results.results.length > 0 && (
          <div
            className="animate-fade-in"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
              gap: '12px',
            }}
          >
            {results.results.map((product, i) => (
              <div key={`${product.slug}-${product.source_store}-${i}`} className="animate-fade-up"
                style={{ animationDelay: `${Math.min(i * 30, 300)}ms`, animationFillMode: 'both', opacity: 0 }}>
                <ProductCard
                  product={product}
                  bestPrice={product.best_price}
                  bestStore={product.best_store}
                  spread={product.price_spread}
                />
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {results && results.total > (results.limit || 24) && !loading && (
          <div style={{
            display: 'flex', justifyContent: 'center', gap: '8px',
            paddingTop: '48px',
          }}>
            {results.page > 1 && (
              <button
                className="filter-pill"
                onClick={() => { const p = results.page - 1; setPage(p); doSearch(query, p) }}
              >
                ← PREV
              </button>
            )}
            <span style={{
              fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-3)',
              padding: '5px 16px', border: '1px solid var(--border)', borderRadius: '20px',
            }}>
              {results.page} / {Math.ceil(results.total / (results.limit || 24))}
            </span>
            {results.page < Math.ceil(results.total / (results.limit || 24)) && (
              <button
                className="filter-pill"
                onClick={() => { const p = results.page + 1; setPage(p); doSearch(query, p) }}
              >
                NEXT →
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
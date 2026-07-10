'use client'
import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import { ExternalLink, TrendingDown, TrendingUp, Minus, ArrowLeft, Heart } from 'lucide-react'
import { useRouter } from 'next/navigation'
import {
  getProduct, getPriceHistory, getMatchBySlug,
  Product, PriceHistoryEntry, ProductMatch,
  formatPrice, formatStore
} from '@/lib/api'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import PriceAlertPanel from '@/components/PriceAlertPanel'
import { useWishlist } from '@/contexts/WishlistContext'
import { useAuth } from '@/contexts/AuthContext'

export default function ProductPage() {
  const { slug } = useParams<{ slug: string }>()
  const searchParams = useSearchParams()
  const store = searchParams.get('store') || ''
  const router = useRouter()
  const { isAuthenticated } = useAuth()
  const { isSaved, toggle } = useWishlist()

  const [products, setProducts]       = useState<Product[]>([])
  const [history, setHistory]         = useState<PriceHistoryEntry[]>([])
  const [match, setMatch]             = useState<ProductMatch | null>(null)
  const [loading, setLoading]         = useState(true)
  const [activeStore, setActiveStore] = useState(store)

  useEffect(() => {
    if (!slug) return
    Promise.all([
      getProduct(slug),
      getPriceHistory(slug),
      store ? getMatchBySlug(slug, store).catch(() => null) : Promise.resolve(null),
    ]).then(([prods, hist, matchData]) => {
      setProducts(prods)
      setHistory(hist.history)
      setMatch(matchData)
      if (!activeStore && prods.length > 0) setActiveStore(prods[0].source_store)
    }).finally(() => setLoading(false))
  }, [slug])

  const current = products.find(p => p.source_store === activeStore) || products[0]

  if (loading) {
    return (
      <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '40px 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '40px' }}>
          <div className="skeleton" style={{ height: '440px' }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {[60, 40, 80, 120, 100, 60].map((h, i) => (
              <div key={i} className="skeleton" style={{ height: `${h}px` }} />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (!current) {
    return (
      <div style={{ textAlign: 'center', padding: '120px 24px' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: '56px', color: 'var(--text-4)', marginBottom: '16px' }}>
          PRODUCT NOT FOUND
        </div>
        <button onClick={() => router.back()} className="filter-pill">← BACK</button>
      </div>
    )
  }

  const chartData = [...history].reverse().map(h => ({
    date: new Date(h.recorded_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }),
    price: h.price,
    store: h.source_store,
  }))

  const prices = history.map(h => h.price).filter(p => p > 0)
  const lowestEver  = prices.length ? Math.min(...prices) : null
  const highestEver = prices.length ? Math.max(...prices) : null
  const isAtLowest  = lowestEver !== null && current.price === lowestEver

  const TrendIcon = !history[1] ? Minus
    : history[0].price < history[1].price ? TrendingDown
    : history[0].price > history[1].price ? TrendingUp
    : Minus

  const trendColor = !history[1] ? 'var(--text-3)'
    : history[0].price < history[1].price ? 'var(--green)'
    : history[0].price > history[1].price ? 'var(--accent)'
    : 'var(--text-3)'

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '28px 24px 80px' }}>

      {/* Back */}
      <button
        onClick={() => router.back()}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: '6px',
          color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
          fontSize: '10px', letterSpacing: '0.08em', marginBottom: '28px',
          padding: '0', transition: 'color 0.15s',
        }}
        onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-2)')}
        onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-3)')}
      >
        <ArrowLeft size={12} /> BACK
      </button>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '48px' }}>

        {/* Left */}
        <div>
          {/* Image */}
          <div style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: '40px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '380px', position: 'relative', overflow: 'hidden',
          }}>
            {isAtLowest && (
              <div style={{
                position: 'absolute', top: '16px', left: '16px',
                background: 'var(--green)', color: '#000',
                fontFamily: 'var(--font-mono)', fontSize: '9px', fontWeight: 700,
                letterSpacing: '0.1em', padding: '4px 10px', borderRadius: '3px',
              }}>
                LOWEST EVER
              </div>
            )}
            {current.image_url ? (
              <img
                src={current.image_url} alt={current.title}
                style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
              />
            ) : (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-4)' }}>NO IMAGE</span>
            )}
          </div>

          {/* Store tabs */}
          {products.length > 1 && (
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${products.length}, 1fr)`, gap: '6px', marginTop: '10px' }}>
              {products.map(p => (
                <button
                  key={p.source_store}
                  onClick={() => setActiveStore(p.source_store)}
                  style={{
                    padding: '10px 8px',
                    background: activeStore === p.source_store ? 'var(--surface-2)' : 'var(--surface)',
                    border: `1px solid ${activeStore === p.source_store ? 'var(--border-2)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius)',
                    cursor: 'pointer', textAlign: 'center',
                    transition: 'all 0.15s',
                  }}
                >
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)', letterSpacing: '0.08em', marginBottom: '5px' }}>
                    {formatStore(p.source_store).toUpperCase()}
                  </div>
                  <div className={`price-tag ${match?.best_price_store === p.source_store ? 'best-price' : ''}`}
                    style={{ fontSize: '15px', color: match?.best_price_store === p.source_store ? 'var(--yellow)' : 'var(--text)' }}>
                    {formatPrice(p.price)}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

          {/* Brand + title */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
              {current.brand && (
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--accent)', letterSpacing: '0.1em' }}>
                  {current.brand.toUpperCase()}
                </span>
              )}
              <span className={`store-badge ${current.source_store}`}>{formatStore(current.source_store)}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-4)', letterSpacing: '0.06em' }}>
                {current.category}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
              <h1 style={{
                fontFamily: 'var(--font-display)', fontSize: '36px',
                letterSpacing: '0.03em', lineHeight: 1.05, marginBottom: '8px',
              }}>
                {current.title}
              </h1>
              {isAuthenticated && (
                <button
                  onClick={() => toggle({
                    slug: current.slug,
                    source_store: current.source_store,
                    title: current.title,
                    image_url: current.image_url,
                    added_price: current.price,
                    currency: current.currency,
                  })}
                  aria-label={isSaved(current.slug, current.source_store) ? 'Remove from wishlist' : 'Save to wishlist'}
                  style={{
                    flexShrink: 0, width: '38px', height: '38px', borderRadius: '50%',
                    background: 'var(--surface-2)', border: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer', transition: 'transform 0.15s ease, border-color 0.15s ease',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.08)')}
                  onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
                >
                  <Heart
                    size={16}
                    fill={isSaved(current.slug, current.source_store) ? '#ff3d00' : 'none'}
                    color={isSaved(current.slug, current.source_store) ? '#ff3d00' : 'var(--text-2)'}
                    strokeWidth={2}
                  />
                </button>
              )}
            </div>
            {current.sku && (
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-3)', letterSpacing: '0.06em' }}>
                SKU: {current.sku}
              </span>
            )}
          </div>

          {/* Price + trend */}
          <div style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '20px',
          }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)', letterSpacing: '0.1em', marginBottom: '8px' }}>
              CURRENT PRICE
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
              <div className="price-tag" style={{ fontSize: '48px', fontWeight: 400, lineHeight: 1, color: 'var(--text)' }}>
                {formatPrice(current.price)}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: trendColor, marginBottom: '6px' }}>
                <TrendIcon size={14} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', letterSpacing: '0.06em' }}>
                  {!history[1] ? 'NO CHANGE'
                    : history[0].price < history[1].price ? `↓ ${formatPrice(history[1].price - history[0].price)}`
                    : history[0].price > history[1].price ? `↑ ${formatPrice(history[0].price - history[1].price)}`
                    : 'STABLE'}
                </span>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            {[
              { label: 'LOWEST EVER', value: formatPrice(lowestEver), color: 'var(--green)' },
              { label: 'HIGHEST EVER', value: formatPrice(highestEver), color: 'var(--accent)' },
            ].map(s => (
              <div key={s.label} className="stat-box">
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', color: 'var(--text-3)', letterSpacing: '0.1em', marginBottom: '6px' }}>{s.label}</div>
                <div className="price-tag" style={{ fontSize: '16px', color: s.color }}>{s.value}</div>
              </div>
            ))}
          </div>

          {/* Cross-store */}
          {match && match.listings.length > 1 && (
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)', letterSpacing: '0.1em' }}>
                PRICE COMPARISON
              </div>
              {match.listings.map((l, i) => (
                <div key={`${l.slug}-${l.store}`} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '10px 16px',
                  borderBottom: i < match.listings.length - 1 ? '1px solid var(--border)' : 'none',
                  background: l.store === match.best_price_store ? 'var(--yellow-dim)' : 'transparent',
                }}>
                  <span className={`store-badge ${l.store}`}>{formatStore(l.store)}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {l.store === match.best_price_store && (
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', color: 'var(--yellow)', letterSpacing: '0.1em' }}>BEST</span>
                    )}
                    <span className="price-tag" style={{ fontSize: '15px', color: l.store === match.best_price_store ? 'var(--yellow)' : 'var(--text)' }}>
                      {formatPrice(l.price)}
                    </span>
                  </div>
                </div>
              ))}
              {match.price_spread && (
                <div style={{ padding: '10px 16px', background: 'var(--green-dim)', fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--green)' }}>
                  Save {formatPrice(match.price_spread)} by choosing the best store
                </div>
              )}
            </div>
          )}

          {/* Sizes */}
          {current.variants.length > 0 && (
            <div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)', letterSpacing: '0.1em', marginBottom: '10px' }}>
                SIZES
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {current.variants.map(v => (
                  <div key={v.size} style={{
                    padding: '6px 11px',
                    border: `1px solid ${v.available ? 'var(--border-2)' : 'var(--border)'}`,
                    borderRadius: '4px',
                    fontFamily: 'var(--font-mono)', fontSize: '11px',
                    color: v.available ? 'var(--text)' : 'var(--text-4)',
                    background: v.available ? 'var(--surface-2)' : 'transparent',
                    textDecoration: v.available ? 'none' : 'line-through',
                    position: 'relative',
                  }}>
                    {v.size}
                    {v.available && (
                      <span style={{
                        position: 'absolute', bottom: '-1px', left: '50%', transform: 'translateX(-50%)',
                        width: '3px', height: '3px', borderRadius: '50%',
                        background: 'var(--green)',
                      }} />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CTA */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: 'auto' }}>
            <a
              href={current.product_url} target="_blank" rel="noopener noreferrer"
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                padding: '14px', background: 'var(--accent)', borderRadius: 'var(--radius)',
                color: '#fff', fontFamily: 'var(--font-mono)', fontSize: '11px',
                fontWeight: 500, letterSpacing: '0.1em', textDecoration: 'none',
                transition: 'opacity 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.opacity = '0.88')}
              onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
            >
              BUY ON {formatStore(current.source_store).toUpperCase()}
              <ExternalLink size={13} />
            </a>
            <PriceAlertPanel slug={slug} store={current.source_store} currentPrice={current.price} currency={current.currency} />
          </div>
        </div>
      </div>

      {/* Price history chart */}
      {chartData.length > 1 && (
        <div style={{ marginTop: '56px' }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            marginBottom: '16px',
          }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)', letterSpacing: '0.1em' }}>
              PRICE HISTORY · {chartData.length} RECORDS
            </div>
          </div>
          <div style={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)', padding: '24px 24px 16px',
          }}>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <XAxis dataKey="date"
                  tick={{ fontFamily: 'DM Mono, monospace', fontSize: 10, fill: '#44444e' }}
                  axisLine={false} tickLine={false} />
                <YAxis
                  tick={{ fontFamily: 'DM Mono, monospace', fontSize: 10, fill: '#44444e' }}
                  axisLine={false} tickLine={false}
                  tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`}
                  width={48} />
                {lowestEver && (
                  <ReferenceLine y={lowestEver} stroke="rgba(34,197,94,0.3)" strokeDasharray="4 4" />
                )}
                <Tooltip
                  contentStyle={{
                    background: '#0d0d10', border: '1px solid #1c1c22',
                    borderRadius: '4px', fontFamily: 'DM Mono, monospace', fontSize: '11px',
                    boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
                  }}
                  labelStyle={{ color: '#44444e', marginBottom: '4px' }}
                  formatter={(v: number) => [formatPrice(v), 'Price']}
                />
                <Line
                  type="monotone" dataKey="price"
                  stroke="#ff3d00" strokeWidth={2}
                  dot={false} activeDot={{ r: 4, fill: '#ff3d00', strokeWidth: 0 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  )
}
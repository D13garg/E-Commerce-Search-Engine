'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getDeals, Deal, formatPrice, formatStore } from '@/lib/api'

function slugToTitle(slug: string) {
  return slug.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

export default function DealsPage() {
  const [deals, setDeals]   = useState<Deal[]>([])
  const [loading, setLoading] = useState(true)
  const [spread, setSpread] = useState(1000)
  const router = useRouter()

  const load = async (minSpread: number) => {
    setLoading(true)
    try {
      const res = await getDeals({ min_spread: minSpread, limit: 50 })
      setDeals(res.deals || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(spread) }, [])

  const SPREAD_OPTIONS = [
    { label: 'ANY', value: 0 },
    { label: '₹500+', value: 500 },
    { label: '₹1K+', value: 1000 },
    { label: '₹5K+', value: 5000 },
    { label: '₹10K+', value: 10000 },
  ]

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '48px 24px' }}>

      {/* Header */}
      <div style={{ marginBottom: '36px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '14px', marginBottom: '8px' }}>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '52px', letterSpacing: '0.04em', lineHeight: 1 }}>
            CROSS-STORE <span style={{ color: 'var(--yellow)' }}>DEALS</span>
          </h1>
          {!loading && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)', letterSpacing: '0.06em' }}>
              {deals.length} FOUND
            </span>
          )}
        </div>
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-4)', letterSpacing: '0.06em' }}>
          SAME PRODUCT, DIFFERENT PRICES — SORTED BY SAVINGS
        </p>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '32px', alignItems: 'center' }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-4)', letterSpacing: '0.1em', marginRight: '6px' }}>
          MIN SPREAD
        </span>
        {SPREAD_OPTIONS.map(o => (
          <button key={o.value} onClick={() => { setSpread(o.value); load(o.value) }}
            className={`filter-pill ${spread === o.value ? 'active' : ''}`}>
            {o.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ display: 'grid', gap: '8px' }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: '100px' }} />
          ))}
        </div>
      ) : deals.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '100px 0' }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: '40px', color: 'var(--text-4)', marginBottom: '12px' }}>
            NO DEALS FOUND
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)' }}>
            Try lowering the minimum spread
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '6px' }}>
          {deals.map((deal, i) => {
            const slug = deal.listings?.[0]?.slug || deal.sku || ''
            const title = slugToTitle(slug)
            return (
            <div
              key={`${slug}-${i}`}
              onClick={() => slug && router.push(`/product/${slug}`)}
              className="animate-fade-up"
              style={{
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius)',
                padding: '16px 20px',
                display: 'grid',
                gridTemplateColumns: '32px 1fr auto auto',
                gap: '20px',
                alignItems: 'center',
                cursor: slug ? 'pointer' : 'default',
                transition: 'border-color 0.15s, background 0.15s, transform 0.15s',
                animationDelay: `${Math.min(i * 25, 250)}ms`,
                animationFillMode: 'both',
                opacity: 0,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'var(--border-2)'
                e.currentTarget.style.background = 'var(--surface-2)'
                e.currentTarget.style.transform = 'translateX(2px)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'var(--border)'
                e.currentTarget.style.background = 'var(--surface)'
                e.currentTarget.style.transform = 'translateX(0)'
              }}
            >
              {/* Rank */}
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-4)', textAlign: 'right' }}>
                {String(i + 1).padStart(2, '0')}
              </div>

              {/* Info */}
              <div>
                <div style={{
                  fontFamily: 'var(--font-body)', fontSize: '13px', fontWeight: 500,
                  color: 'var(--text)', marginBottom: '8px',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '500px',
                }}>
                  {title}
                </div>
                <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
                  {deal.listings?.map((l: { store: string; price: number | null; slug: string }) => (
                    <div key={l.store} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className={`store-badge ${l.store}`}>{formatStore(l.store)}</span>
                      <span className="price-tag" style={{
                        fontSize: '13px',
                        color: l.store === deal.best_price_store ? 'var(--yellow)' : 'var(--text-2)',
                      }}>
                        {formatPrice(l.price)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Saving amount */}
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: '8px', color: 'var(--text-4)', letterSpacing: '0.1em', marginBottom: '4px' }}>
                  YOU SAVE
                </div>
                <div className="price-tag" style={{ fontSize: '18px', color: 'var(--yellow)', fontWeight: 400 }}>
                  {formatPrice(deal.price_spread)}
                </div>
              </div>

              {/* Arrow */}
              <div style={{ color: 'var(--text-4)', fontSize: '18px', lineHeight: 1 }}>→</div>
            </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
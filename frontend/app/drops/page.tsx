'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { getPriceDrops, PriceDrop, formatPrice, formatStore, timeAgo } from '@/lib/api'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function slugToTitle(slug: string) {
  return slug.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

export default function DropsPage() {
  const [drops, setDrops]   = useState<PriceDrop[]>([])
  const [loading, setLoading] = useState(true)
  const [hours, setHours]   = useState(168)
  const [minPct, setMinPct] = useState(5)
  const router = useRouter()

  const load = async (h: number, pct: number) => {
    setLoading(true)
    try {
      const res = await getPriceDrops({ hours: h, min_drop_pct: pct })
      setDrops(res.drops)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(hours, minPct) }, [])

  const HOUR_OPTIONS = [
    { label: '24H', value: 24 },
    { label: '7D',  value: 168 },
    { label: '30D', value: 720 },
  ]
  const PCT_OPTIONS = [5, 10, 20, 30]

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '48px 24px' }}>

      {/* Header */}
      <div style={{ marginBottom: '36px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '16px', marginBottom: '8px' }}>
          <h1 style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: '52px', letterSpacing: '0.04em', lineHeight: 1 }}>
            PRICE <span style={{ color: '#22c55e' }}>DROPS</span>
          </h1>
          {!loading && (
            <span style={{ fontFamily: 'DM Mono, monospace', fontSize: '11px', color: '#555', letterSpacing: '0.06em' }}>
              {drops.length} FOUND
            </span>
          )}
        </div>
        <p style={{ fontFamily: 'DM Mono, monospace', fontSize: '11px', color: '#444', letterSpacing: '0.06em' }}>
          PRICE DECREASES ACROSS ALL INDEXED STORES
        </p>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '32px', marginBottom: '32px', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span style={{ fontFamily: 'DM Mono, monospace', fontSize: '10px', color: '#444', letterSpacing: '0.08em', marginRight: '4px' }}>
            WINDOW
          </span>
          {HOUR_OPTIONS.map(o => (
            <button key={o.value} onClick={() => { setHours(o.value); load(o.value, minPct) }}
              className={`filter-pill ${hours === o.value ? 'active' : ''}`}>
              {o.label}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span style={{ fontFamily: 'DM Mono, monospace', fontSize: '10px', color: '#444', letterSpacing: '0.08em', marginRight: '4px' }}>
            MIN DROP
          </span>
          {PCT_OPTIONS.map(p => (
            <button key={p} onClick={() => { setMinPct(p); load(hours, p) }}
              className={`filter-pill ${minPct === p ? 'active' : ''}`}>
              {p}%
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ display: 'grid', gap: '10px' }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: '88px' }} />
          ))}
        </div>
      ) : drops.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '100px 0' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>📉</div>
          <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: '32px', color: '#222', marginBottom: '8px' }}>
            NO DROPS YET
          </div>
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '11px', color: '#444' }}>
            Drops appear after the next scheduled crawl at 2:00 AM IST
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '8px' }}>
          {drops.map((drop, i) => (
            <div
              key={`${drop.slug}-${drop.source_store}-${i}`}
              onClick={() => router.push(`/product/${drop.slug}?store=${drop.source_store}`)}
              style={{
                background: '#0f0f0f',
                border: '1px solid #1e1e1e',
                borderRadius: '6px',
                padding: '16px 20px',
                display: 'grid',
                gridTemplateColumns: '28px 1fr auto',
                gap: '16px',
                alignItems: 'center',
                cursor: 'pointer',
                transition: 'border-color 0.15s, background 0.15s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = '#2e2e2e'
                e.currentTarget.style.background = '#141414'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = '#1e1e1e'
                e.currentTarget.style.background = '#0f0f0f'
              }}
            >
              {/* Rank */}
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '11px',
                color: '#2e2e2e',
                textAlign: 'center',
              }}>
                {String(i + 1).padStart(2, '0')}
              </div>

              {/* Info */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span className={`store-badge ${drop.source_store}`}>{formatStore(drop.source_store)}</span>
                  <span style={{ fontFamily: 'DM Mono, monospace', fontSize: '10px', color: '#3a3a3a', letterSpacing: '0.04em' }}>
                    {timeAgo(drop.recorded_at)}
                  </span>
                </div>
                <div style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '13px',
                  fontWeight: 500,
                  color: '#ccc',
                  marginBottom: '8px',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  maxWidth: '480px',
                }}>
                  {slugToTitle(drop.slug)}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontFamily: 'DM Mono, monospace', fontSize: '13px', color: '#3a3a3a', textDecoration: 'line-through' }}>
                    {formatPrice(drop.previous_price)}
                  </span>
                  <span style={{ color: '#2e2e2e', fontSize: '11px' }}>→</span>
                  <span style={{ fontFamily: 'DM Mono, monospace', fontSize: '16px', color: '#22c55e', fontWeight: 500 }}>
                    {formatPrice(drop.current_price)}
                  </span>
                </div>
              </div>

              {/* Drop badge */}
              <div style={{
                background: 'rgba(34,197,94,0.08)',
                border: '1px solid rgba(34,197,94,0.2)',
                borderRadius: '6px',
                padding: '10px 16px',
                textAlign: 'center',
                minWidth: '90px',
              }}>
                <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: '26px', color: '#22c55e', lineHeight: 1 }}>
                  -{drop.drop_pct}%
                </div>
                <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '9px', color: '#22c55e', opacity: 0.7, marginTop: '2px', letterSpacing: '0.06em' }}>
                  {formatPrice(drop.drop_amount)} OFF
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
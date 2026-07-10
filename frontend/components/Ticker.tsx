'use client'
import { useEffect, useState } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface TickerItem {
  text: string
  type: 'deal' | 'drop' | 'stat'
}

const FALLBACK: TickerItem[] = [
  { text: 'CROSS-STORE PRICE INTELLIGENCE', type: 'stat' },
  { text: '100K+ PRODUCTS INDEXED ACROSS 20+ STORES', type: 'stat' },
  { text: 'REAL-TIME PRICE TRACKING', type: 'stat' },
]

export default function Ticker() {
  const [items, setItems] = useState<TickerItem[]>(FALLBACK)

  useEffect(() => {
    Promise.allSettled([
      fetch(`${API_BASE}/deals?limit=4`).then(r => r.json()),
      fetch(`${API_BASE}/price-drops?hours=24&min_drop_pct=10&limit=4`).then(r => r.json()),
      fetch(`${API_BASE}/health`).then(r => r.json()),
    ]).then(([dealsRes, dropsRes, healthRes]) => {
      const live: TickerItem[] = []

      if (dealsRes.status === 'fulfilled') {
        const deals = dealsRes.value?.deals || []
        deals.slice(0, 4).forEach((d: { title?: string; slug?: string; price_spread?: number }) => {
          const name = d.title || d.slug?.replace(/-/g, ' ').toUpperCase() || ''
          const spread = d.price_spread ? `₹${Math.round(d.price_spread).toLocaleString('en-IN')} SPREAD` : ''
          if (name) live.push({ text: `${name}${spread ? ' — ' + spread : ''}`, type: 'deal' })
        })
      }

      if (dropsRes.status === 'fulfilled') {
        const drops = dropsRes.value?.drops || []
        drops.slice(0, 4).forEach((d: { slug?: string; drop_pct?: number; drop_amount?: number }) => {
          const name = d.slug?.replace(/-/g, ' ').toUpperCase() || ''
          const pct = d.drop_pct ? `↓${d.drop_pct}%` : ''
          if (name) live.push({ text: `${name} ${pct}`, type: 'drop' })
        })
      }

      if (healthRes.status === 'fulfilled') {
        const total = healthRes.value?.total_products
        if (total) live.push({ text: `${total.toLocaleString('en-IN')} PRODUCTS INDEXED`, type: 'stat' })
      }

      if (live.length >= 3) setItems(live)
    })
  }, [])

  const doubled = [...items, ...items]

  const colors: Record<string, string> = {
    deal: '#e8ff00',
    drop: '#22c55e',
    stat: 'rgba(240,240,242,0.4)',
  }
  const dots: Record<string, string> = {
    deal: '◆',
    drop: '▼',
    stat: '·',
  }

  return (
    <div style={{
      background: '#0a0a0d',
      borderBottom: '1px solid #1c1c22',
      height: '30px',
      overflow: 'hidden',
      display: 'flex',
      alignItems: 'center',
    }}>
      <div
        className="animate-ticker"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0',
          whiteSpace: 'nowrap',
          willChange: 'transform',
        }}
      >
        {doubled.map((item, i) => (
          <span
            key={i}
            style={{
              fontFamily: "'DM Mono', monospace",
              fontSize: '10px',
              letterSpacing: '0.07em',
              color: colors[item.type],
              padding: '0 32px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              borderRight: '1px solid #1c1c22',
            }}
          >
            <span style={{ fontSize: '7px', opacity: 0.6 }}>{dots[item.type]}</span>
            {item.text}
          </span>
        ))}
      </div>
    </div>
  )
}
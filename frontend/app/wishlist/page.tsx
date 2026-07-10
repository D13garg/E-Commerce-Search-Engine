'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Heart, TrendingDown, TrendingUp, Minus } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { useWishlist } from '@/contexts/WishlistContext'
import { getWishlist, removeFromWishlistById, WishlistItem } from '@/lib/wishlist'
import { formatPrice, formatStore } from '@/lib/api'

export default function WishlistPage() {
  const router = useRouter()
  const { isAuthenticated, loading: authLoading } = useAuth()
  const { savedKeys } = useWishlist() // re-render trigger when hearts toggle elsewhere

  const [items, setItems] = useState<WishlistItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const data = await getWishlist()
      setItems(data)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login')
      return
    }
    if (isAuthenticated) load()
  }, [authLoading, isAuthenticated])

  // Re-sync the full list whenever the saved-keys set shrinks (item removed via heart elsewhere)
  useEffect(() => {
    if (isAuthenticated && !loading) {
      setItems(prev => prev.filter(i => savedKeys.has(`${i.slug}::${i.source_store}`)))
    }
  }, [savedKeys])

  const handleRemove = async (id: string) => {
    setItems(prev => prev.filter(i => i.id !== id))
    try {
      await removeFromWishlistById(id)
    } catch {
      load() // re-sync on failure
    }
  }

  if (authLoading || (loading && items.length === 0)) {
    return (
      <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '48px 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '12px' }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="skeleton" style={{ height: '320px' }} />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '48px 24px' }}>

      {/* Header */}
      <div style={{ marginBottom: '36px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '14px', marginBottom: '8px' }}>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '52px', letterSpacing: '0.04em', lineHeight: 1 }}>
            YOUR <span style={{ color: 'var(--accent)' }}>WISHLIST</span>
          </h1>
          {!loading && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)', letterSpacing: '0.06em' }}>
              {items.length} SAVED
            </span>
          )}
        </div>
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-4)', letterSpacing: '0.06em' }}>
          TRACK PRICE CHANGES ON PRODUCTS YOU CARE ABOUT
        </p>
      </div>

      {/* Empty state */}
      {items.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '100px 0' }}>
          <Heart size={40} color="var(--text-4)" style={{ marginBottom: '16px' }} />
          <div style={{ fontFamily: 'var(--font-display)', fontSize: '32px', color: 'var(--text-4)', marginBottom: '8px' }}>
            NOTHING SAVED YET
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)', marginBottom: '24px' }}>
            Tap the heart on any product to save it here
          </div>
          <button onClick={() => router.push('/')} className="filter-pill">BROWSE PRODUCTS</button>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '8px' }}>
          {items.map((item, i) => {
            const change = item.price_change
            const TrendIcon = change === null ? Minus : change < 0 ? TrendingDown : change > 0 ? TrendingUp : Minus
            const trendColor = change === null ? 'var(--text-3)' : change < 0 ? 'var(--green)' : change > 0 ? 'var(--accent)' : 'var(--text-3)'

            return (
              <div
                key={item.id}
                className="animate-fade-up"
                style={{
                  background: 'var(--surface)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)', padding: '14px 18px',
                  display: 'grid', gridTemplateColumns: '56px 1fr auto auto', gap: '16px',
                  alignItems: 'center', cursor: 'pointer',
                  animationDelay: `${Math.min(i * 25, 250)}ms`, animationFillMode: 'both', opacity: 0,
                  transition: 'border-color 0.15s',
                }}
                onClick={() => router.push(`/product/${item.slug}?store=${item.source_store}`)}
                onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border-2)')}
                onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
              >
                {/* Thumbnail */}
                <div style={{
                  width: '56px', height: '56px', borderRadius: 'var(--radius-sm)',
                  background: 'var(--surface-2)', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', overflow: 'hidden', flexShrink: 0,
                }}>
                  {item.image_url ? (
                    <img src={item.image_url} alt={item.title} style={{ width: '100%', height: '100%', objectFit: 'contain', padding: '4px' }} />
                  ) : (
                    <Heart size={16} color="var(--text-4)" />
                  )}
                </div>

                {/* Info */}
                <div>
                  <div style={{
                    fontFamily: 'var(--font-body)', fontSize: '13px', fontWeight: 500,
                    color: 'var(--text)', marginBottom: '6px',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '420px',
                  }}>
                    {item.title}
                  </div>
                  <span className={`store-badge ${item.source_store}`}>{formatStore(item.source_store)}</span>
                </div>

                {/* Price + trend */}
                <div style={{ textAlign: 'right' }}>
                  <div className="price-tag" style={{ fontSize: '17px', color: 'var(--text)' }}>
                    {item.current_price ? formatPrice(item.current_price, item.currency) : '—'}
                  </div>
                  {change !== null && change !== 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '3px', color: trendColor, marginTop: '2px' }}>
                      <TrendIcon size={10} />
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px' }}>
                        {formatPrice(Math.abs(change), item.currency)} since saved
                      </span>
                    </div>
                  )}
                </div>

                {/* Remove */}
                <button
                  onClick={(e) => { e.stopPropagation(); handleRemove(item.id) }}
                  aria-label="Remove from wishlist"
                  style={{
                    width: '32px', height: '32px', borderRadius: '50%',
                    background: 'transparent', border: '1px solid var(--border)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer', transition: 'border-color 0.15s, background 0.15s',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,61,0,0.3)'; e.currentTarget.style.background = 'var(--accent-dim)' }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'transparent' }}
                >
                  <Heart size={13} fill="#ff3d00" color="#ff3d00" />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
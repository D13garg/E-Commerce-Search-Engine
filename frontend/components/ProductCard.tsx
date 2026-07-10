'use client'
import { useRouter } from 'next/navigation'
import { Heart } from 'lucide-react'
import { Product, formatPrice, formatStore } from '@/lib/api'
import { useWishlist } from '@/contexts/WishlistContext'
import { useAuth } from '@/contexts/AuthContext'

interface Props {
  product: Product
  bestPrice?: number | null
  bestStore?: string | null
  spread?: number | null
}

export default function ProductCard({ product, bestPrice, bestStore, spread }: Props) {
  const router = useRouter()
  const { isAuthenticated } = useAuth()
  const { isSaved, toggle } = useWishlist()
  const saved = isSaved(product.slug, product.source_store)
  const isBest = bestStore === product.source_store
  const availableCount = product.available_sizes?.length ?? 0
  const isOOS = availableCount === 0
  const hasValidPrice = product.price && product.price > 0

  return (
    <div
      className="product-card"
      onClick={() => router.push(`/product/${product.slug}?store=${product.source_store}`)}
      style={{ opacity: isOOS ? 0.55 : 1 }}
    >
      {/* Image */}
      <div style={{
        height: '196px',
        background: '#0a0a0d',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        position: 'relative',
      }}>
        {isBest && spread && spread > 0 && (
          <div style={{
            position: 'absolute', top: '10px', right: '10px',
            background: 'var(--yellow)',
            color: '#000',
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            fontWeight: 700,
            letterSpacing: '0.06em',
            padding: '3px 7px',
            borderRadius: '3px',
            zIndex: 2,
          }}>
            BEST PRICE
          </div>
        )}
        {isOOS && (
          <div style={{
            position: 'absolute', top: '10px', left: '10px',
            background: 'rgba(0,0,0,0.7)',
            color: '#44444e',
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            letterSpacing: '0.06em',
            padding: '3px 7px',
            borderRadius: '3px',
            border: '1px solid #1c1c22',
            zIndex: 2,
          }}>
            OUT OF STOCK
          </div>
        )}
        {isAuthenticated && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              toggle({
                slug: product.slug,
                source_store: product.source_store,
                title: product.title,
                image_url: product.image_url,
                added_price: product.price,
                currency: product.currency,
              })
            }}
            aria-label={saved ? 'Remove from wishlist' : 'Save to wishlist'}
            style={{
              position: 'absolute', bottom: '10px', right: '10px',
              width: '28px', height: '28px', borderRadius: '50%',
              background: 'rgba(0,0,0,0.55)',
              border: '1px solid rgba(255,255,255,0.1)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', zIndex: 2,
              transition: 'transform 0.15s ease, background 0.15s ease',
            }}
            onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.1)')}
            onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
          >
            <Heart
              size={14}
              fill={saved ? '#ff3d00' : 'none'}
              color={saved ? '#ff3d00' : '#fff'}
              strokeWidth={2}
            />
          </button>
        )}
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.title}
            loading="lazy"
            decoding="async"
            style={{
              width: '100%', height: '100%',
              objectFit: 'contain',
              padding: '14px',
              transition: 'transform 0.35s ease',
            }}
            onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.06)')}
            onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1)')}
          />
        ) : (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-4)' }}>
            NO IMAGE
          </span>
        )}
      </div>

      {/* Body */}
      <div style={{ padding: '12px 14px 14px' }}>
        {/* Store badge + brand */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span className={`store-badge ${product.source_store}`}>
            {formatStore(product.source_store)}
          </span>
          {product.brand && (
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '9px',
              color: 'var(--text-3)',
              letterSpacing: '0.06em',
              maxWidth: '100px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {product.brand.toUpperCase()}
            </span>
          )}
        </div>

        {/* Title */}
        <div style={{
          fontFamily: 'var(--font-body)',
          fontSize: '13px',
          fontWeight: 500,
          color: isOOS ? 'var(--text-3)' : 'var(--text)',
          lineHeight: 1.35,
          marginBottom: '12px',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}>
          {product.title}
        </div>

        {/* Price row */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <div
              className={`price-tag ${isBest && spread ? 'best-price' : ''}`}
              style={{
                fontSize: '20px',
                fontWeight: 400,
                color: !hasValidPrice ? 'var(--text-4)'
                      : isBest && spread ? 'var(--yellow)'
                      : 'var(--text)',
                lineHeight: 1,
              }}
            >
              {hasValidPrice ? formatPrice(product.price) : '—'}
            </div>
            {spread && spread > 0 && (
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '9px',
                color: isBest ? 'var(--green)' : 'var(--text-3)',
                marginTop: '4px',
                letterSpacing: '0.04em',
              }}>
                {isBest
                  ? `SAVE ${formatPrice(spread)}`
                  : `${formatPrice(bestPrice)} elsewhere`}
              </div>
            )}
          </div>

          {/* Size pill */}
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            letterSpacing: '0.06em',
            color: availableCount > 0 ? 'var(--green)' : 'var(--text-4)',
            background: availableCount > 0 ? 'var(--green-dim)' : 'transparent',
            border: `1px solid ${availableCount > 0 ? 'rgba(34,197,94,0.2)' : 'var(--border)'}`,
            padding: '3px 8px',
            borderRadius: '20px',
          }}>
            {availableCount > 0 ? `${availableCount} SIZES` : 'OOS'}
          </div>
        </div>

        {/* SKU */}
        {product.sku && (
          <div style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '9px',
            color: 'var(--text-4)',
            marginTop: '10px',
            letterSpacing: '0.04em',
          }}>
            {product.sku}
          </div>
        )}
      </div>
    </div>
  )
}
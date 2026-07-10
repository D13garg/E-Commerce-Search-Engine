'use client'

/**
 * contexts/WishlistContext.tsx — Global wishlist state.
 *
 * Loads the saved (slug, source_store) set once on login, keeps it in memory.
 * Every heart icon reads from this Set — toggling one updates the Set
 * immediately (optimistic), so all hearts across the page update in sync
 * without a refetch.
 */

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import {
  getWishlistSlugs, addToWishlist, removeFromWishlistByProduct,
  wishlistKey, WishlistAddPayload,
} from '@/lib/wishlist'

interface WishlistContextValue {
  savedKeys: Set<string>
  isSaved: (slug: string, sourceStore: string) => boolean
  toggle: (payload: WishlistAddPayload) => Promise<void>
  loading: boolean
}

const WishlistContext = createContext<WishlistContextValue | undefined>(undefined)

export function WishlistProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const [savedKeys, setSavedKeys] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!isAuthenticated) { setSavedKeys(new Set()); return }
    setLoading(true)
    try {
      const res = await getWishlistSlugs()
      setSavedKeys(new Set(res.items.map(i => wishlistKey(i.slug, i.source_store))))
    } catch {
      setSavedKeys(new Set())
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated])

  useEffect(() => { load() }, [load])

  const isSaved = useCallback(
    (slug: string, sourceStore: string) => savedKeys.has(wishlistKey(slug, sourceStore)),
    [savedKeys],
  )

  const toggle = useCallback(async (payload: WishlistAddPayload) => {
    const key = wishlistKey(payload.slug, payload.source_store)
    const currentlySaved = savedKeys.has(key)

    // Optimistic update — flips instantly, no waiting on network
    setSavedKeys(prev => {
      const next = new Set(prev)
      if (currentlySaved) next.delete(key)
      else next.add(key)
      return next
    })

    try {
      if (currentlySaved) {
        await removeFromWishlistByProduct(payload.slug, payload.source_store)
      } else {
        await addToWishlist(payload)
      }
    } catch {
      // Revert on failure
      setSavedKeys(prev => {
        const next = new Set(prev)
        if (currentlySaved) next.add(key)
        else next.delete(key)
        return next
      })
    }
  }, [savedKeys])

  return (
    <WishlistContext.Provider value={{ savedKeys, isSaved, toggle, loading }}>
      {children}
    </WishlistContext.Provider>
  )
}

export function useWishlist() {
  const ctx = useContext(WishlistContext)
  if (!ctx) throw new Error('useWishlist must be used within WishlistProvider')
  return ctx
}
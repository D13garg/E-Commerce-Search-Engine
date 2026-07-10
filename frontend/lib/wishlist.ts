/**
 * lib/wishlist.ts — Wishlist API client.
 *
 * Reuses authFetch from lib/auth.ts for cookie + CSRF handling.
 * All endpoints require the user to be logged in (401 if not).
 */

import { authFetch } from '@/lib/auth'

export interface WishlistItem {
  id: string
  slug: string
  source_store: string
  title: string
  image_url: string | null
  added_price: number | null
  current_price: number | null
  price_change: number | null   // negative = price dropped since saved
  currency: string
  created_at: string
}

export interface WishlistAddPayload {
  slug: string
  source_store: string
  title: string
  image_url?: string | null
  added_price?: number | null
  currency?: string
}

export const addToWishlist = (payload: WishlistAddPayload) =>
  authFetch<WishlistItem>('/wishlist', { method: 'POST', body: payload })

export const getWishlist = () =>
  authFetch<WishlistItem[]>('/wishlist', { method: 'GET' })

export const getWishlistSlugs = () =>
  authFetch<{ items: { slug: string; source_store: string }[] }>('/wishlist/slugs', { method: 'GET' })

export const removeFromWishlistByProduct = (slug: string, sourceStore: string) =>
  authFetch<{ status: string }>(
    `/wishlist/by-product?slug=${encodeURIComponent(slug)}&source_store=${encodeURIComponent(sourceStore)}`,
    { method: 'DELETE' },
  )

export const removeFromWishlistById = (itemId: string) =>
  authFetch<{ status: string }>(`/wishlist/${itemId}`, { method: 'DELETE' })

/** Builds a fast-lookup Set key for checking saved state: `${slug}::${source_store}` */
export const wishlistKey = (slug: string, sourceStore: string) => `${slug}::${sourceStore}`
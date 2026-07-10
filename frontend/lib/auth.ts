/**
 * lib/auth.ts — Auth API client.
 *
 * Separate from lib/api.ts because auth requests need:
 *   - credentials: 'include'  → send/receive httpOnly cookies cross-origin
 *   - CSRF token header on every mutating request
 *
 * CSRF flow:
 *   1. Login/register/google response includes X-CSRF-Token header
 *   2. We cache it in memory (not localStorage — XSS would defeat the point)
 *   3. Every subsequent POST/PUT/DELETE attaches it as X-CSRF-Token
 *   4. Backend's CSRFMiddleware checks it matches the csrf_token cookie
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// In-memory CSRF token cache. Lost on page refresh — refreshed automatically
// via /auth/me on app load (see AuthContext).
let csrfToken: string | null = null

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

export function getCsrfToken(): string | null {
  return csrfToken
}

// ── Types ───────────────────────────────────────────────────────────────────

export interface User {
  id: string
  name: string
  email: string
  is_active: boolean
  phone: string | null
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface ApiError {
  detail: string | { msg: string }[]
}

export class AuthApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

// ── Core request helper ────────────────────────────────────────────────────

export async function authFetch<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const { method = 'GET', body } = options

  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (method !== 'GET' && csrfToken) {
    headers['X-CSRF-Token'] = csrfToken
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    credentials: 'include', // send + receive httpOnly cookies
    body: body ? JSON.stringify(body) : undefined,
  })

  // Capture refreshed CSRF token if present
  const newCsrf = res.headers.get('X-CSRF-Token')
  if (newCsrf) setCsrfToken(newCsrf)

  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Something went wrong.' }))
    const message = extractErrorMessage(data)
    throw new AuthApiError(message, res.status)
  }

  // Some endpoints (logout) return a tiny body; guard against empty responses
  const text = await res.text()
  return text ? JSON.parse(text) : (undefined as T)
}

export function extractErrorMessage(data: ApiError): string {
  const { detail } = data
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(d => d.msg).filter(Boolean).join('. ')
  return 'Something went wrong. Please try again.'
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

export const registerInitiate = (data: { name: string; email: string; password: string; phone?: string }) =>
  authFetch<{ message: string; email: string }>('/auth/register/initiate', { method: 'POST', body: data })

export const registerVerify = (data: { email: string; code: string }) =>
  authFetch<TokenResponse>('/auth/register/verify', { method: 'POST', body: data })

export const login = (data: { email: string; password: string }) =>
  authFetch<TokenResponse>('/auth/login', { method: 'POST', body: data })

export const googleAuth = (data: { id_token: string }) =>
  authFetch<TokenResponse>('/auth/google', { method: 'POST', body: data })

export const forgotPasswordInitiate = (data: { email: string }) =>
  authFetch<{ message: string }>('/auth/forgot-password/initiate', { method: 'POST', body: data })

export const forgotPasswordVerify = (data: { email: string; code: string; new_password: string }) =>
  authFetch<{ message: string }>('/auth/forgot-password/verify', { method: 'POST', body: data })

export const refreshToken = () =>
  authFetch<{ access_token: string; token_type: string }>('/auth/refresh', { method: 'POST' })

export const logout = () =>
  authFetch<{ message: string }>('/auth/logout', { method: 'POST' })

export const getMe = () =>
  authFetch<User>('/auth/me', { method: 'GET' })
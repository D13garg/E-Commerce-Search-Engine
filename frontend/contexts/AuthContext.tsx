'use client'

/**
 * contexts/AuthContext.tsx — Global auth state.
 *
 * Equivalent to the reference's Zustand authStore + useAuth hook, rewritten
 * as a React Context since this project uses plain useState, not a state
 * management library.
 *
 * On mount, calls GET /auth/me. The browser sends the httpOnly access_token
 * cookie automatically — if valid, we get the user back and capture the
 * fresh CSRF token from the response header. If the access token expired,
 * we attempt one silent refresh before giving up.
 */

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react'
import * as authApi from '@/lib/auth'
import { setCsrfToken } from '@/lib/auth'
import type { User } from '@/lib/auth'

interface AuthContextValue {
  user: User | null
  loading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  googleLogin: (idToken: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const tryLoadUser = useCallback(async () => {
    try {
      const me = await authApi.getMe()
      setUser(me)
      return true
    } catch {
      return false
    }
  }, [])

  useEffect(() => {
    (async () => {
      const ok = await tryLoadUser()
      if (!ok) {
        // Access token may have expired — try one silent refresh
        try {
          await authApi.refreshToken()
          await tryLoadUser()
        } catch {
          setUser(null)
        }
      }
      setLoading(false)
    })()
  }, [tryLoadUser])

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login({ email, password })
    setUser(res.user)
  }, [])

  const googleLogin = useCallback(async (idToken: string) => {
    const res = await authApi.googleAuth({ id_token: idToken })
    setUser(res.user)
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      setUser(null)
      setCsrfToken(null)
    }
  }, [])

  const refreshUser = useCallback(async () => {
    await tryLoadUser()
  }, [tryLoadUser])

  return (
    <AuthContext.Provider value={{
      user, loading, isAuthenticated: !!user,
      login, googleLogin, logout, refreshUser,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
'use client'
import { useState, useEffect, useRef, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'
import { AuthApiError } from '@/lib/auth'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (res: { credential: string }) => void }) => void
          renderButton: (el: HTMLElement, config: object) => void
        }
      }
    }
  }
}

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || ''

function LoginPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { login, googleLogin } = useAuth()
  const googleBtnRef = useRef<HTMLDivElement>(null)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)

  const successMessage = searchParams.get('message')

  // Load Google Identity Services
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return

    const handleGoogleCredential = async (res: { credential: string }) => {
      setGoogleLoading(true)
      setError('')
      try {
        await googleLogin(res.credential)
        router.push('/')
      } catch (e) {
        setError(e instanceof AuthApiError ? e.message : 'Google sign-in failed.')
      } finally {
        setGoogleLoading(false)
      }
    }

    const initGoogle = () => {
      window.google?.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleCredential,
      })
      if (googleBtnRef.current) {
        window.google?.accounts.id.renderButton(googleBtnRef.current, {
          theme: 'filled_black',
          size: 'large',
          width: 360,
          text: 'signin_with',
          shape: 'rectangular',
        })
      }
    }

    if (window.google) {
      initGoogle()
    } else {
      const script = document.createElement('script')
      script.src = 'https://accounts.google.com/gsi/client'
      script.async = true
      script.defer = true
      script.onload = initGoogle
      document.body.appendChild(script)
    }
  }, [googleLogin, router])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!email || !password) { setError('Email and password are required.'); return }

    setLoading(true)
    try {
      await login(email, password)
      router.push('/')
    } catch (e) {
      setError(e instanceof AuthApiError ? e.message : 'Login failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: 'calc(100vh - 82px)', display: 'flex', alignItems: 'center',
      justifyContent: 'center', padding: '40px 24px',
    }}>
      <div style={{ width: '100%', maxWidth: '400px' }}>

        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '1px', marginBottom: '16px' }}>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: '28px', letterSpacing: '0.1em', color: 'var(--text)' }}>MARKET</span>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: '28px', letterSpacing: '0.1em', color: 'var(--accent)' }}>LENS</span>
          </div>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)', letterSpacing: '0.06em' }}>
            SIGN IN TO YOUR ACCOUNT
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: '32px',
        }}>
          {successMessage && (
            <div style={{
              marginBottom: '20px', padding: '10px 14px', borderRadius: 'var(--radius)',
              background: 'var(--green-dim)', border: '1px solid rgba(34,197,94,0.2)',
              color: 'var(--green)', fontFamily: 'var(--font-mono)', fontSize: '11px',
            }}>
              {successMessage}
            </div>
          )}
          {error && (
            <div style={{
              marginBottom: '20px', padding: '10px 14px', borderRadius: 'var(--radius)',
              background: 'var(--accent-dim)', border: '1px solid rgba(255,61,0,0.2)',
              color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: '11px',
            }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={labelStyle}>EMAIL</label>
              <input
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com" className="search-input" style={inputStyle} autoFocus
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                <label style={{ ...labelStyle, marginBottom: 0 }}>PASSWORD</label>
                <Link href="/forgot-password" style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--accent)', textDecoration: 'none' }}>
                  FORGOT?
                </Link>
              </div>
              <input
                type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="••••••••" className="search-input" style={inputStyle}
              />
            </div>

            <button
              type="submit" disabled={loading || googleLoading}
              style={{
                marginTop: '8px', padding: '12px', background: 'var(--accent)',
                border: 'none', borderRadius: 'var(--radius)', color: '#fff',
                fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 500,
                letterSpacing: '0.08em', cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1, transition: 'opacity 0.15s',
              }}
            >
              {loading ? 'SIGNING IN...' : 'SIGN IN'}
            </button>
          </form>

          {GOOGLE_CLIENT_ID && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', margin: '24px 0' }}>
                <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-4)', letterSpacing: '0.08em' }}>OR</span>
                <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} />
              </div>
              <div ref={googleBtnRef} style={{ display: 'flex', justifyContent: 'center' }} />
            </>
          )}

          <p style={{ marginTop: '24px', textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)' }}>
            No account?{' '}
            <Link href="/register" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Create one</Link>
          </p>
        </div>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)',
  letterSpacing: '0.1em', display: 'block', marginBottom: '6px',
}
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 12px', borderRadius: 'var(--radius)', fontSize: '13px',
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageInner />
    </Suspense>
  )
}
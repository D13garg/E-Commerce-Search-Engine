'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { registerInitiate, AuthApiError } from '@/lib/auth'

export default function RegisterPage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (name.trim().length < 2) { setError('Name must be at least 2 characters.'); return }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }

    setLoading(true)
    try {
      await registerInitiate({ name, email, password, phone: phone || undefined })
      router.push(`/verify-otp?email=${encodeURIComponent(email)}&purpose=register`)
    } catch (e) {
      setError(e instanceof AuthApiError ? e.message : 'Registration failed. Please try again.')
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

        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '1px', marginBottom: '16px' }}>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: '28px', letterSpacing: '0.1em', color: 'var(--text)' }}>MARKET</span>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: '28px', letterSpacing: '0.1em', color: 'var(--accent)' }}>LENS</span>
          </div>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)', letterSpacing: '0.06em' }}>
            CREATE YOUR ACCOUNT
          </p>
        </div>

        <div style={{
          background: 'var(--surface)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: '32px',
        }}>
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
              <label style={labelStyle}>FULL NAME</label>
              <input value={name} onChange={e => setName(e.target.value)} placeholder="Your full name" className="search-input" style={inputStyle} autoFocus />
            </div>
            <div>
              <label style={labelStyle}>EMAIL</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" className="search-input" style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>PASSWORD</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Min. 8 characters" className="search-input" style={inputStyle} />
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-4)', marginTop: '5px' }}>
                Needs uppercase, lowercase, number, and a symbol.
              </div>
            </div>
            <div>
              <label style={labelStyle}>PHONE <span style={{ color: 'var(--text-4)' }}>(OPTIONAL)</span></label>
              <input type="tel" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+91 98765 43210" className="search-input" style={inputStyle} />
            </div>

            <button
              type="submit" disabled={loading}
              style={{
                marginTop: '8px', padding: '12px', background: 'var(--accent)',
                border: 'none', borderRadius: 'var(--radius)', color: '#fff',
                fontFamily: 'var(--font-mono)', fontSize: '11px', fontWeight: 500,
                letterSpacing: '0.08em', cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1, transition: 'opacity 0.15s',
              }}
            >
              {loading ? 'SENDING CODE...' : 'CONTINUE'}
            </button>
          </form>

          <p style={{ marginTop: '16px', textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-4)' }}>
            A 4-digit verification code will be sent to your email.
          </p>

          <p style={{ marginTop: '16px', textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)' }}>
            Already have an account?{' '}
            <Link href="/login" style={{ color: 'var(--accent)', textDecoration: 'none' }}>Sign in</Link>
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
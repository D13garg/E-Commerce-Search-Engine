'use client'
import { useState, useRef, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { registerVerify, forgotPasswordVerify, AuthApiError } from '@/lib/auth'
import { useAuth } from '@/contexts/AuthContext'

function VerifyOTPInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { refreshUser } = useAuth()

  const email = searchParams.get('email') || ''
  const purpose = searchParams.get('purpose') || ''
  const isForgot = purpose === 'forgot_password'

  useEffect(() => {
    if (!email || !purpose) router.replace('/register')
  }, [email, purpose, router])

  const [digits, setDigits] = useState(['', '', '', ''])
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const code = digits.join('')

  const handleDigitChange = (index: number, value: string) => {
    const digit = value.replace(/\D/g, '').slice(-1)
    const next = [...digits]
    next[index] = digit
    setDigits(next)
    if (digit && index < 3) inputRefs.current[index + 1]?.focus()
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 4)
    const next = [...digits]
    pasted.split('').forEach((d, i) => { next[i] = d })
    setDigits(next)
    const lastFilled = Math.min(pasted.length, 3)
    inputRefs.current[lastFilled]?.focus()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (code.length !== 4) return

    if (isForgot) {
      if (!newPassword) { setError('New password is required.'); return }
      if (newPassword !== confirmPassword) { setError('Passwords do not match.'); return }

      setLoading(true)
      try {
        await forgotPasswordVerify({ email, code, new_password: newPassword })
        router.push('/login?message=' + encodeURIComponent('Password reset. You can now sign in.'))
      } catch (e) {
        setError(e instanceof AuthApiError ? e.message : 'Something went wrong.')
      } finally {
        setLoading(false)
      }
    } else {
      setLoading(true)
      try {
        await registerVerify({ email, code })
        await refreshUser()
        router.push('/')
      } catch (e) {
        setError(e instanceof AuthApiError ? e.message : 'Something went wrong.')
      } finally {
        setLoading(false)
      }
    }
  }

  if (!email || !purpose) return null

  return (
    <div style={{
      minHeight: 'calc(100vh - 82px)', display: 'flex', alignItems: 'center',
      justifyContent: 'center', padding: '40px 24px',
    }}>
      <div style={{ width: '100%', maxWidth: '400px' }}>

        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '32px', letterSpacing: '0.04em', marginBottom: '8px' }}>
            {isForgot ? 'RESET PASSWORD' : 'VERIFY EMAIL'}
          </h1>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--text-3)' }}>
            CODE SENT TO <span style={{ color: 'var(--text-2)' }}>{email}</span>
          </p>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-4)', marginTop: '4px' }}>
            EXPIRES IN 3 MINUTES
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

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* 4-digit boxes */}
            <div onPaste={handlePaste} style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
              {digits.map((d, i) => (
                <input
                  key={i}
                  ref={el => { inputRefs.current[i] = el }}
                  type="text" inputMode="numeric" maxLength={1} value={d}
                  onChange={e => handleDigitChange(i, e.target.value)}
                  onKeyDown={e => handleKeyDown(i, e)}
                  style={{
                    width: '52px', height: '60px', textAlign: 'center',
                    fontFamily: 'var(--font-mono)', fontSize: '24px', fontWeight: 500,
                    background: 'var(--surface-2)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)', color: 'var(--text)', outline: 'none',
                    transition: 'border-color 0.15s',
                  }}
                  onFocus={e => (e.currentTarget.style.borderColor = 'var(--accent)')}
                  onBlur={e => (e.currentTarget.style.borderColor = 'var(--border)')}
                />
              ))}
            </div>

            {isForgot && (
              <>
                <div>
                  <label style={labelStyle}>NEW PASSWORD</label>
                  <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="Min. 8 characters" className="search-input" style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>CONFIRM PASSWORD</label>
                  <input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} placeholder="Repeat new password" className="search-input" style={inputStyle} />
                </div>
              </>
            )}

            <button
              type="submit" disabled={loading || code.length !== 4}
              style={{
                padding: '12px', background: 'var(--accent)', border: 'none',
                borderRadius: 'var(--radius)', color: '#fff', fontFamily: 'var(--font-mono)',
                fontSize: '11px', fontWeight: 500, letterSpacing: '0.08em',
                cursor: (loading || code.length !== 4) ? 'not-allowed' : 'pointer',
                opacity: (loading || code.length !== 4) ? 0.5 : 1, transition: 'opacity 0.15s',
              }}
            >
              {loading
                ? (isForgot ? 'RESETTING...' : 'VERIFYING...')
                : (isForgot ? 'RESET PASSWORD' : 'VERIFY & CREATE ACCOUNT')}
            </button>
          </form>

          <p style={{ marginTop: '20px', textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-3)' }}>
            Didn&apos;t receive it?{' '}
            <button
              onClick={() => router.push(isForgot ? '/forgot-password' : '/register')}
              style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: '10px' }}
            >
              Go back and resend
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}

export default function VerifyOTPPage() {
  return (
    <Suspense fallback={null}>
      <VerifyOTPInner />
    </Suspense>
  )
}

const labelStyle: React.CSSProperties = {
  fontFamily: 'var(--font-mono)', fontSize: '9px', color: 'var(--text-3)',
  letterSpacing: '0.1em', display: 'block', marginBottom: '6px',
}
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 12px', borderRadius: 'var(--radius)', fontSize: '13px',
}
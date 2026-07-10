'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type Trigger = 'any_drop' | 'below_price'

interface AlertFormState {
  email: string
  phone: string
  trigger: Trigger
  target_price: string
}

interface PriceAlertPanelProps {
  slug: string
  store?: string
  currentPrice: number | null
  currency?: string
}

export default function PriceAlertPanel({
  slug,
  store,
  currentPrice,
  currency = 'INR',
}: PriceAlertPanelProps) {
  const [open, setOpen] = useState(false)
  const { user } = useAuth()
  const [form, setForm] = useState<AlertFormState>({
    email: '',
    phone: '',
    trigger: 'any_drop',
    target_price: '',
  })
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (user?.email) {
      setForm(f => ({ ...f, email: user.email, phone: user.phone || f.phone }))
    }
  }, [user])

  const handleSubmit = async () => {
    if (!form.email) { setErrorMsg('Email is required.'); return }
    if (form.trigger === 'below_price' && !form.target_price) {
      setErrorMsg('Target price is required for "below price" alerts.')
      return
    }

    setStatus('loading')
    setErrorMsg('')

    const body: Record<string, unknown> = {
      email: form.email,
      slug,
      trigger: form.trigger,
      source_store: store || null,
      currency,
    }
    if (form.phone) body.phone = form.phone
    if (form.trigger === 'below_price') body.target_price = parseFloat(form.target_price)

    try {
      const res = await fetch(`${API_BASE}/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.status === 409) {
        setErrorMsg('You already have this alert set up.')
        setStatus('error')
        return
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || 'Failed to create alert.')
      }
      setStatus('success')
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Something went wrong.')
      setStatus('error')
    }
  }

  const reset = () => {
    setStatus('idle')
    setErrorMsg('')
    setForm({ email: '', phone: '', trigger: 'any_drop', target_price: '' })
    setOpen(false)
  }

  const fmt = (n: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(n)

  // ── Collapsed trigger ────────────────────────────────────────────────────

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'transparent',
          border: '1px solid #2a2a2a',
          borderRadius: '4px',
          color: '#888',
          fontFamily: 'DM Mono, monospace',
          fontSize: '12px',
          letterSpacing: '0.08em',
          padding: '10px 16px',
          cursor: 'pointer',
          width: '100%',
          transition: 'border-color 0.15s, color 0.15s',
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = '#444'
          ;(e.currentTarget as HTMLButtonElement).style.color = '#ccc'
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = '#2a2a2a'
          ;(e.currentTarget as HTMLButtonElement).style.color = '#888'
        }}
      >
        <span style={{ fontSize: '14px' }}>🔔</span>
        SET PRICE ALERT
      </button>
    )
  }

  // ── Success state ────────────────────────────────────────────────────────

  if (status === 'success') {
    return (
      <div style={panelStyle}>
        <div style={{ textAlign: 'center', padding: '8px 0' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px' }}>✓</div>
          <div style={{ fontFamily: 'DM Mono, monospace', fontSize: '13px', color: '#4ade80', marginBottom: '4px' }}>
            Alert created
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginBottom: '20px' }}>
            We&apos;ll notify you at <strong style={{ color: '#aaa' }}>{form.email}</strong>
            {form.phone && <> and <strong style={{ color: '#aaa' }}>{form.phone}</strong></>}.
          </div>
          <button onClick={reset} style={ghostBtn}>Done</button>
        </div>
      </div>
    )
  }

  // ── Form ─────────────────────────────────────────────────────────────────

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <span style={labelStyle}>🔔 PRICE ALERT</span>
        <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', color: '#555', cursor: 'pointer', fontSize: '18px', lineHeight: 1 }}>×</button>
      </div>

      {/* Trigger selector */}
      <div style={{ marginBottom: '16px' }}>
        <div style={labelStyle}>NOTIFY ME WHEN</div>
        <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
          {(['any_drop', 'below_price'] as Trigger[]).map(t => (
            <button
              key={t}
              onClick={() => setForm(f => ({ ...f, trigger: t }))}
              style={{
                flex: 1,
                padding: '8px 4px',
                background: form.trigger === t ? '#1a1a1a' : 'transparent',
                border: `1px solid ${form.trigger === t ? '#444' : '#222'}`,
                borderRadius: '4px',
                color: form.trigger === t ? '#fff' : '#555',
                fontFamily: 'DM Mono, monospace',
                fontSize: '11px',
                letterSpacing: '0.06em',
                cursor: 'pointer',
                transition: 'all 0.1s',
              }}
            >
              {t === 'any_drop' ? 'PRICE DROPS' : 'BELOW TARGET'}
            </button>
          ))}
        </div>
      </div>

      {/* Target price (conditional) */}
      {form.trigger === 'below_price' && (
        <div style={{ marginBottom: '16px' }}>
          <label style={labelStyle}>TARGET PRICE ({currency})</label>
          <input
            type="number"
            placeholder={currentPrice ? `e.g. ${Math.round(currentPrice * 0.9).toLocaleString('en-IN')}` : 'e.g. 8000'}
            value={form.target_price}
            onChange={e => setForm(f => ({ ...f, target_price: e.target.value }))}
            style={inputStyle}
          />
          {currentPrice && (
            <div style={{ fontSize: '11px', color: '#555', marginTop: '4px' }}>
              Current price: {fmt(currentPrice)}
            </div>
          )}
        </div>
      )}

      {/* Email */}
      <div style={{ marginBottom: '16px' }}>
        <label style={labelStyle}>EMAIL *</label>
        <input
          type="email"
          placeholder="you@example.com"
          value={form.email}
          onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
          style={inputStyle}
        />
      </div>

      {/* Phone (optional) */}
      <div style={{ marginBottom: '20px' }}>
        <label style={labelStyle}>WHATSAPP (OPTIONAL)</label>
        <input
          type="tel"
          placeholder="+919876543210"
          value={form.phone}
          onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
          style={inputStyle}
        />
        <div style={{ fontSize: '11px', color: '#444', marginTop: '4px' }}>
          E.164 format — include country code
        </div>
      </div>

      {/* Error */}
      {errorMsg && (
        <div style={{ fontSize: '12px', color: '#f87171', marginBottom: '14px', fontFamily: 'DM Mono, monospace' }}>
          {errorMsg}
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={status === 'loading'}
        style={{
          width: '100%',
          padding: '12px',
          background: status === 'loading' ? '#1a1a1a' : '#fff',
          color: status === 'loading' ? '#555' : '#000',
          border: 'none',
          borderRadius: '4px',
          fontFamily: 'DM Mono, monospace',
          fontSize: '12px',
          fontWeight: 700,
          letterSpacing: '0.08em',
          cursor: status === 'loading' ? 'not-allowed' : 'pointer',
          transition: 'background 0.15s',
        }}
      >
        {status === 'loading' ? 'SETTING UP...' : 'CREATE ALERT'}
      </button>
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const panelStyle: React.CSSProperties = {
  background: '#0d0d0d',
  border: '1px solid #222',
  borderRadius: '4px',
  padding: '20px',
}

const labelStyle: React.CSSProperties = {
  fontFamily: 'DM Mono, monospace',
  fontSize: '10px',
  letterSpacing: '0.1em',
  color: '#555',
  display: 'block',
  marginBottom: '6px',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  background: '#111',
  border: '1px solid #222',
  borderRadius: '4px',
  color: '#f0f0f0',
  fontFamily: 'DM Mono, monospace',
  fontSize: '13px',
  padding: '10px 12px',
  outline: 'none',
  boxSizing: 'border-box',
}

const ghostBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid #333',
  borderRadius: '4px',
  color: '#888',
  fontFamily: 'DM Mono, monospace',
  fontSize: '12px',
  padding: '8px 24px',
  cursor: 'pointer',
}
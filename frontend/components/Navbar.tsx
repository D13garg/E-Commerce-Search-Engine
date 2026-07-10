'use client'
import { useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { TrendingDown, Zap, Search, User, LogOut, Heart } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

const BASE_NAV = [
  { href: '/',      label: 'SEARCH', icon: Search },
  { href: '/deals', label: 'DEALS',  icon: Zap },
  { href: '/drops', label: 'DROPS',  icon: TrendingDown },
]

export default function Navbar() {
  const path = usePathname()
  const router = useRouter()
  const { user, loading, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  const NAV = user
    ? [...BASE_NAV, { href: '/wishlist', label: 'WISHLIST', icon: Heart }]
    : BASE_NAV

  const handleLogout = async () => {
    setMenuOpen(false)
    await logout()
    router.push('/')
  }

  return (
    <nav style={{
      background: 'rgba(6,6,8,0.92)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      borderBottom: '1px solid #1c1c22',
      height: '52px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 28px',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>

      {/* Logo */}
      <Link href="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '1px' }}>
        <span style={{
          fontFamily: "'Bebas Neue', sans-serif",
          fontSize: '20px',
          letterSpacing: '0.1em',
          color: '#f0f0f2',
        }}>
          MARKET
        </span>
        <span style={{
          fontFamily: "'Bebas Neue', sans-serif",
          fontSize: '20px',
          letterSpacing: '0.1em',
          color: '#ff3d00',
        }}>
          LENS
        </span>
      </Link>

      {/* Nav */}
      <div style={{ display: 'flex', gap: '2px' }}>
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = path === href
          return (
            <Link key={href} href={href} style={{ textDecoration: 'none' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: '4px',
                background: active ? 'rgba(255,61,0,0.1)' : 'transparent',
                transition: 'background 0.15s ease',
                position: 'relative',
              }}
              onMouseEnter={e => { if (!active) (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.04)' }}
              onMouseLeave={e => { if (!active) (e.currentTarget as HTMLDivElement).style.background = 'transparent' }}
              >
                <Icon size={12} color={active ? '#ff3d00' : '#44444e'} />
                <span style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: '10px',
                  fontWeight: 500,
                  letterSpacing: '0.1em',
                  color: active ? '#ff3d00' : '#44444e',
                  transition: 'color 0.15s ease',
                }}>
                  {label}
                </span>
                {active && (
                  <div style={{
                    position: 'absolute',
                    bottom: '-1px',
                    left: '14px',
                    right: '14px',
                    height: '1px',
                    background: '#ff3d00',
                    borderRadius: '1px',
                  }} />
                )}
              </div>
            </Link>
          )
        })}
      </div>

      {/* Right — auth + live dot */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>

        {!loading && (
          user ? (
            <div style={{ position: 'relative' }}>
              <button
                onClick={() => setMenuOpen(o => !o)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '6px',
                  background: 'transparent', border: '1px solid #1c1c22',
                  borderRadius: '20px', padding: '4px 12px 4px 4px',
                  cursor: 'pointer', transition: 'border-color 0.15s',
                }}
                onMouseEnter={e => (e.currentTarget.style.borderColor = '#252530')}
                onMouseLeave={e => (e.currentTarget.style.borderColor = '#1c1c22')}
              >
                <div style={{
                  width: '20px', height: '20px', borderRadius: '50%',
                  background: '#ff3d00', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontFamily: "'DM Mono', monospace",
                  fontSize: '10px', fontWeight: 700, color: '#fff',
                }}>
                  {user.name.charAt(0).toUpperCase()}
                </div>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: '10px', color: '#8a8a96', letterSpacing: '0.04em' }}>
                  {user.name.split(' ')[0]}
                </span>
              </button>

              {menuOpen && (
                <>
                  <div onClick={() => setMenuOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 90 }} />
                  <div style={{
                    position: 'absolute', top: '100%', right: 0, marginTop: '8px',
                    background: '#0d0d10', border: '1px solid #1c1c22', borderRadius: '6px',
                    minWidth: '160px', zIndex: 100, overflow: 'hidden',
                  }}>
                    <div style={{ padding: '10px 14px', borderBottom: '1px solid #1c1c22' }}>
                      <div style={{ fontFamily: "'DM Mono', monospace", fontSize: '9px', color: '#44444e', letterSpacing: '0.06em' }}>SIGNED IN AS</div>
                      <div style={{ fontFamily: 'Inter, sans-serif', fontSize: '12px', color: '#f0f0f2', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user.email}</div>
                    </div>
                    <button
                      onClick={handleLogout}
                      style={{
                        width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
                        padding: '10px 14px', background: 'none', border: 'none',
                        color: '#ff3d00', fontFamily: "'DM Mono', monospace", fontSize: '10px',
                        letterSpacing: '0.06em', cursor: 'pointer', textAlign: 'left',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,61,0,0.08)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'none')}
                    >
                      <LogOut size={12} /> LOG OUT
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <Link href="/login" style={{ textDecoration: 'none' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '6px 14px', borderRadius: '4px', border: '1px solid #1c1c22',
                transition: 'border-color 0.15s, background 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = '#252530'; e.currentTarget.style.background = 'rgba(255,255,255,0.03)' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = '#1c1c22'; e.currentTarget.style.background = 'transparent' }}
              >
                <User size={12} color="#8a8a96" />
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: '10px', fontWeight: 500, letterSpacing: '0.08em', color: '#8a8a96' }}>
                  SIGN IN
                </span>
              </div>
            </Link>
          )
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
          <span className="pulse-dot" style={{
            width: '5px', height: '5px', borderRadius: '50%',
            background: '#22c55e', display: 'inline-block',
          }} />
          <span style={{
            fontFamily: "'DM Mono', monospace",
            fontSize: '10px',
            color: '#26262e',
            letterSpacing: '0.06em',
          }}>
            LIVE
          </span>
        </div>
      </div>
    </nav>
  )
}
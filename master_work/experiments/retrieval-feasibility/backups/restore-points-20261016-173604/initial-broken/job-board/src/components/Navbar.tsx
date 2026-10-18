import { Link, useRouter } from '@tanstack/react-router'
import { useAuth } from '#/context/auth'
import { useState } from 'react'

export function Navbar() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)

  function handleLogout() {
    logout()
    router.navigate({ to: '/' })
  }

  return (
    <header
      style={{
        background: 'var(--md-sys-color-surface-container-low)',
        borderBottom: '1px solid var(--md-sys-color-outline-variant)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}
    >
      <nav
        style={{
          maxWidth: 1200,
          margin: '0 auto',
          padding: '0 16px',
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
        }}
      >
        {/* Logo */}
        <Link
          to="/"
          style={{
            fontSize: 'var(--md-sys-typescale-title-large-size)',
            fontWeight: 700,
            color: 'var(--md-sys-color-primary)',
            textDecoration: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexShrink: 0,
          }}
        >
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
            <rect width="28" height="28" rx="8" fill="var(--md-sys-color-primary)" />
            <path d="M7 10h14M7 14h10M7 18h7" stroke="var(--md-sys-color-on-primary)" strokeWidth="2" strokeLinecap="round" />
          </svg>
          JobBoard
        </Link>

        {/* Desktop nav */}
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}
          className="nav-desktop"
        >
          <NavLink to="/jobs">Browse Jobs</NavLink>

          {!user && (
            <>
              <NavLink to="/auth/login">Sign In</NavLink>
              <Link
                to="/auth/register"
                style={{
                  padding: '10px 24px',
                  background: 'var(--md-sys-color-primary)',
                  color: 'var(--md-sys-color-on-primary)',
                  borderRadius: 'var(--md-sys-shape-corner-full)',
                  fontSize: 'var(--md-sys-typescale-label-large-size)',
                  fontWeight: 'var(--md-sys-typescale-label-large-weight)',
                  textDecoration: 'none',
                  transition: 'opacity 150ms',
                }}
              >
                Get Started
              </Link>
            </>
          )}

          {user?.role === 'employer' && (
            <>
              <NavLink to="/employer/dashboard">Dashboard</NavLink>
              <NavLink to="/employer/post-job">Post a Job</NavLink>
            </>
          )}

          {user?.role === 'candidate' && (
            <NavLink to="/candidate/dashboard">Dashboard</NavLink>
          )}

          {user && (
            <button
              onClick={handleLogout}
              style={{
                padding: '8px 16px',
                borderRadius: 'var(--md-sys-shape-corner-full)',
                border: '1px solid var(--md-sys-color-outline)',
                background: 'transparent',
                color: 'var(--md-sys-color-on-surface)',
                cursor: 'pointer',
                fontSize: 'var(--md-sys-typescale-label-large-size)',
                fontWeight: 'var(--md-sys-typescale-label-large-weight)',
              }}
            >
              Sign Out
            </button>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className="nav-mobile-btn"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle menu"
          style={{
            display: 'none',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 8,
            color: 'var(--md-sys-color-on-surface)',
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            {menuOpen
              ? <path d="M19 6.4 17.6 5 12 10.6 6.4 5 5 6.4l5.6 5.6L5 17.6 6.4 19l5.6-5.6 5.6 5.6 1.4-1.4-5.6-5.6z" />
              : <path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z" />
            }
          </svg>
        </button>
      </nav>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div
          className="nav-mobile-menu"
          style={{
            background: 'var(--md-sys-color-surface-container)',
            borderTop: '1px solid var(--md-sys-color-outline-variant)',
            padding: '8px 16px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
          }}
        >
          <MobileNavLink to="/jobs" onClick={() => setMenuOpen(false)}>Browse Jobs</MobileNavLink>
          {!user && (
            <>
              <MobileNavLink to="/auth/login" onClick={() => setMenuOpen(false)}>Sign In</MobileNavLink>
              <MobileNavLink to="/auth/register" onClick={() => setMenuOpen(false)}>Register</MobileNavLink>
            </>
          )}
          {user?.role === 'employer' && (
            <>
              <MobileNavLink to="/employer/dashboard" onClick={() => setMenuOpen(false)}>Dashboard</MobileNavLink>
              <MobileNavLink to="/employer/post-job" onClick={() => setMenuOpen(false)}>Post a Job</MobileNavLink>
            </>
          )}
          {user?.role === 'candidate' && (
            <MobileNavLink to="/candidate/dashboard" onClick={() => setMenuOpen(false)}>Dashboard</MobileNavLink>
          )}
          {user && (
            <button
              onClick={() => { handleLogout(); setMenuOpen(false) }}
              style={{
                textAlign: 'left',
                padding: '12px 16px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--md-sys-color-error)',
                fontSize: 'var(--md-sys-typescale-body-large-size)',
              }}
            >
              Sign Out
            </button>
          )}
        </div>
      )}

      <style>{`
        @media (max-width: 767px) {
          .nav-desktop { display: none !important; }
          .nav-mobile-btn { display: block !important; }
        }
        @media (min-width: 768px) {
          .nav-mobile-menu { display: none !important; }
        }
      `}</style>
    </header>
  )
}

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      style={{
        padding: '8px 12px',
        borderRadius: 'var(--md-sys-shape-corner-full)',
        color: 'var(--md-sys-color-on-surface)',
        textDecoration: 'none',
        fontSize: 'var(--md-sys-typescale-label-large-size)',
        fontWeight: 'var(--md-sys-typescale-label-large-weight)',
        transition: 'background 150ms',
      }}
      activeProps={{ style: { background: 'var(--md-sys-color-secondary-container)', color: 'var(--md-sys-color-on-secondary-container)', padding: '8px 12px', borderRadius: 'var(--md-sys-shape-corner-full)', textDecoration: 'none', fontSize: 'var(--md-sys-typescale-label-large-size)', fontWeight: 'var(--md-sys-typescale-label-large-weight)' } }}
    >
      {children}
    </Link>
  )
}

function MobileNavLink({ to, children, onClick }: { to: string; children: React.ReactNode; onClick: () => void }) {
  return (
    <Link
      to={to}
      onClick={onClick}
      style={{
        padding: '12px 16px',
        borderRadius: 'var(--md-sys-shape-corner-medium)',
        color: 'var(--md-sys-color-on-surface)',
        textDecoration: 'none',
        fontSize: 'var(--md-sys-typescale-body-large-size)',
        display: 'block',
      }}
    >
      {children}
    </Link>
  )
}

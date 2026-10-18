import { createFileRoute, Link, useRouter } from '@tanstack/react-router'
import { useState } from 'react'
import { useAuth } from '#/context/auth'
import { Button, TextField, Alert, Card, Select } from '#/components/ui'

interface SearchParams { role?: string }

export const Route = createFileRoute('/auth/register')({
  validateSearch: (s: Record<string, string>): SearchParams => s,
  component: RegisterPage,
})

function RegisterPage() {
  const { register } = useAuth()
  const router = useRouter()
  const search = Route.useSearch()

  const [role, setRole] = useState<'candidate' | 'employer'>(search.role === 'employer' ? 'employer' : 'candidate')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [companyName, setCompanyName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password.length < 6) { setError('Password must be at least 6 characters'); return }
    setLoading(true)
    try {
      await register({ name, email, password, role, companyName: role === 'employer' ? companyName : undefined })
      router.navigate({ to: role === 'employer' ? '/employer/dashboard' : '/candidate/dashboard' })
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: 'calc(100vh - 200px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 16px' }}>
      <div style={{ width: '100%', maxWidth: 480 }}>
        <h1 style={{ textAlign: 'center', fontSize: 'var(--md-sys-typescale-headline-large-size)', fontWeight: 600, margin: '0 0 8px' }}>
          Create your account
        </h1>
        <p style={{ textAlign: 'center', color: 'var(--md-sys-color-on-surface-variant)', margin: '0 0 32px' }}>
          Join thousands of professionals on JobBoard
        </p>

        {/* Role toggle */}
        <div
          style={{
            display: 'flex',
            border: '1px solid var(--md-sys-color-outline-variant)',
            borderRadius: 'var(--md-sys-shape-corner-extra-large)',
            overflow: 'hidden',
            marginBottom: 24,
          }}
        >
          {(['candidate', 'employer'] as const).map(r => (
            <button
              key={r}
              type="button"
              onClick={() => setRole(r)}
              style={{
                flex: 1,
                padding: '14px',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: 'var(--md-sys-typescale-label-large-size)',
                transition: 'background 200ms, color 200ms',
                background: role === r ? 'var(--md-sys-color-primary)' : 'var(--md-sys-color-surface-container-low)',
                color: role === r ? 'var(--md-sys-color-on-primary)' : 'var(--md-sys-color-on-surface-variant)',
              }}
            >
              {r === 'candidate' ? '🧑 Job Seeker' : '🏢 Employer'}
            </button>
          ))}
        </div>

        <Card>
          {error && <Alert type="error">{error}</Alert>}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: error ? 16 : 0 }}>
            <TextField label="Full name" value={name} onChange={e => setName(e.target.value)} required autoComplete="name" />
            <TextField label="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="email" />
            <TextField label="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} required helperText="Minimum 6 characters" autoComplete="new-password" />
            {role === 'employer' && (
              <TextField label="Company name" value={companyName} onChange={e => setCompanyName(e.target.value)} required />
            )}
            <Button type="submit" loading={loading} style={{ marginTop: 8 }}>
              Create account
            </Button>
          </form>
        </Card>

        <p style={{ textAlign: 'center', marginTop: 24, color: 'var(--md-sys-color-on-surface-variant)' }}>
          Already have an account?{' '}
          <Link to="/auth/login" style={{ color: 'var(--md-sys-color-primary)', fontWeight: 500 }}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}

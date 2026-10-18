import { createFileRoute, Link, useRouter } from '@tanstack/react-router'
import { useState } from 'react'
import { useAuth } from '#/context/auth'
import { Button, TextField, Alert, Card } from '#/components/ui'

export const Route = createFileRoute('/auth/login')({ component: LoginPage })

function LoginPage() {
  const { login } = useAuth()
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      router.navigate({ to: '/' })
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: 'calc(100vh - 200px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 16px' }}>
      <div style={{ width: '100%', maxWidth: 440 }}>
        <h1 style={{ textAlign: 'center', fontSize: 'var(--md-sys-typescale-headline-large-size)', fontWeight: 600, margin: '0 0 8px' }}>
          Welcome back
        </h1>
        <p style={{ textAlign: 'center', color: 'var(--md-sys-color-on-surface-variant)', margin: '0 0 32px' }}>
          Sign in to continue to JobBoard
        </p>

        <Card>
          {error && <Alert type="error" >{error}</Alert>}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: error ? 16 : 0 }}>
            <TextField
              label="Email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
            <Button type="submit" loading={loading} style={{ marginTop: 8 }}>
              Sign In
            </Button>
          </form>
        </Card>

        <p style={{ textAlign: 'center', marginTop: 24, color: 'var(--md-sys-color-on-surface-variant)' }}>
          Don't have an account?{' '}
          <Link to="/auth/register" style={{ color: 'var(--md-sys-color-primary)', fontWeight: 500 }}>
            Create one
          </Link>
        </p>
      </div>
    </div>
  )
}

import { createFileRoute, useRouter } from '@tanstack/react-router'
import { useState } from 'react'
import { useAuth } from '#/context/auth'
import { Button, TextField, Textarea, Select, Card, Alert, PageContainer } from '#/components/ui'

export const Route = createFileRoute('/employer/profile')({ component: EmployerProfilePage })

const COMPANY_SIZES = [
  { value: '1-10', label: '1–10 employees' },
  { value: '11-50', label: '11–50 employees' },
  { value: '51-200', label: '51–200 employees' },
  { value: '201-500', label: '201–500 employees' },
  { value: '500+', label: '500+ employees' },
]

function EmployerProfilePage() {
  const { user, updateUser } = useAuth()
  const router = useRouter()

  const [form, setForm] = useState({
    name: user?.name ?? '',
    companyName: user?.companyName ?? '',
    companyWebsite: user?.companyWebsite ?? '',
    companyDescription: user?.companyDescription ?? '',
    companySize: user?.companySize ?? '',
    industry: user?.industry ?? '',
    location: user?.location ?? '',
  })
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  function set(key: string, value: string) {
    setForm(f => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(''); setSuccess(false)
    setLoading(true)
    try {
      await updateUser(form)
      setSuccess(true)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageContainer style={{ maxWidth: 640 }}>
      <h1 style={{ fontSize: 'var(--md-sys-typescale-headline-large-size)', fontWeight: 600, margin: '0 0 32px' }}>
        Company profile
      </h1>

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">Profile updated successfully.</Alert>}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: 24 }}>
        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Account</h2>
          <TextField label="Your name" value={form.name} onChange={e => set('name', e.target.value)} required />
        </Card>
        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Company details</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <TextField label="Company name" value={form.companyName} onChange={e => set('companyName', e.target.value)} />
            <TextField label="Website" type="url" value={form.companyWebsite} onChange={e => set('companyWebsite', e.target.value)} placeholder="https://example.com" />
            <TextField label="Industry" value={form.industry} onChange={e => set('industry', e.target.value)} placeholder="e.g. Technology, Healthcare" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Select label="Company size" value={form.companySize} onChange={e => set('companySize', e.target.value)} options={COMPANY_SIZES} />
              <TextField label="Location" value={form.location} onChange={e => set('location', e.target.value)} placeholder="e.g. San Francisco, CA" />
            </div>
            <Textarea label="Company description" value={form.companyDescription} onChange={e => set('companyDescription', e.target.value)} rows={5} placeholder="Tell candidates about your company culture, mission, and what makes it a great place to work." />
          </div>
        </Card>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <Button type="button" variant="outlined" onClick={() => router.navigate({ to: '/employer/dashboard' })}>Cancel</Button>
          <Button type="submit" loading={loading}>Save profile</Button>
        </div>
      </form>
    </PageContainer>
  )
}

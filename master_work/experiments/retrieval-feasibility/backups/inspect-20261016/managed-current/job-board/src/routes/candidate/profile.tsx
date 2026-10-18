import { createFileRoute, useRouter } from '@tanstack/react-router'
import { useState } from 'react'
import { useAuth } from '#/context/auth'
import { Button, TextField, Textarea, Card, Alert, PageContainer } from '#/components/ui'

export const Route = createFileRoute('/candidate/profile')({ component: CandidateProfilePage })

function CandidateProfilePage() {
  const { user, updateUser } = useAuth()
  const router = useRouter()

  const [form, setForm] = useState({
    name: user?.name ?? '',
    headline: user?.headline ?? '',
    bio: user?.bio ?? '',
    location: user?.location ?? '',
    skills: user?.skills?.join(', ') ?? '',
    portfolioUrl: (user as any)?.portfolioUrl ?? '',
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
      await updateUser({
        ...form,
        skills: form.skills ? form.skills.split(',').map(s => s.trim()).filter(Boolean) : [],
      })
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
        My profile
      </h1>

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">Profile updated.</Alert>}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: 24 }}>
        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Personal info</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <TextField label="Full name" value={form.name} onChange={e => set('name', e.target.value)} required />
            <TextField label="Professional headline" value={form.headline} onChange={e => set('headline', e.target.value)} placeholder="e.g. Senior Frontend Engineer with 5 years of experience" />
            <TextField label="Location" value={form.location} onChange={e => set('location', e.target.value)} placeholder="e.g. Austin, TX" />
            <Textarea label="Bio" value={form.bio} onChange={e => set('bio', e.target.value)} rows={5} placeholder="Tell employers about your background, what you're looking for, and what makes you unique." />
          </div>
        </Card>

        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Skills & links</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <TextField
              label="Skills (comma-separated)"
              value={form.skills}
              onChange={e => set('skills', e.target.value)}
              placeholder="JavaScript, React, TypeScript, Node.js"
              helperText="These help employers find you in search results."
            />
            {form.skills && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {form.skills.split(',').filter(Boolean).map((s, i) => (
                  <span key={i} style={{ padding: '4px 12px', borderRadius: 'var(--md-sys-shape-corner-full)', background: 'var(--md-sys-color-secondary-container)', color: 'var(--md-sys-color-on-secondary-container)', fontSize: 'var(--md-sys-typescale-label-large-size)' }}>
                    {s.trim()}
                  </span>
                ))}
              </div>
            )}
            <TextField label="Portfolio / website URL" type="url" value={form.portfolioUrl} onChange={e => set('portfolioUrl', e.target.value)} placeholder="https://yoursite.com" />
          </div>
        </Card>

        <div style={{
          padding: 16,
          borderRadius: 'var(--md-sys-shape-corner-medium)',
          background: 'var(--md-sys-color-surface-container)',
          border: '1px solid var(--md-sys-color-outline-variant)',
          fontSize: 'var(--md-sys-typescale-body-medium-size)',
          color: 'var(--md-sys-color-on-surface-variant)',
        }}>
          Resume uploads happen per application when you apply for a specific job.
        </div>

        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <Button type="button" variant="outlined" onClick={() => router.navigate({ to: '/candidate/dashboard' })}>Cancel</Button>
          <Button type="submit" loading={loading}>Save profile</Button>
        </div>
      </form>
    </PageContainer>
  )
}

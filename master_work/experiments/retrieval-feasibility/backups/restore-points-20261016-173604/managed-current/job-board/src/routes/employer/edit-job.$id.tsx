import { createFileRoute, useRouter } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { api } from '#/lib/api'
import { Button, TextField, Textarea, Select, Card, Alert, PageContainer, Spinner } from '#/components/ui'

export const Route = createFileRoute('/employer/edit-job/$id')({ component: EditJobPage })

const JOB_TYPES = [
  { value: 'full-time', label: 'Full-time' },
  { value: 'part-time', label: 'Part-time' },
  { value: 'contract', label: 'Contract' },
  { value: 'internship', label: 'Internship' },
  { value: 'freelance', label: 'Freelance' },
]
const EXP_LEVELS = [
  { value: 'entry', label: 'Entry level' },
  { value: 'mid', label: 'Mid level' },
  { value: 'senior', label: 'Senior level' },
  { value: 'lead', label: 'Lead' },
  { value: 'executive', label: 'Executive' },
]
const CATEGORIES = ['Engineering', 'Design', 'Marketing', 'Sales', 'Finance', 'Healthcare', 'Education', 'Data Science', 'Product', 'Operations', 'Legal', 'HR'].map(c => ({ value: c, label: c }))
const SALARY_PERIODS = [{ value: 'hourly', label: 'Per hour' }, { value: 'monthly', label: 'Per month' }, { value: 'yearly', label: 'Per year' }]

function EditJobPage() {
  const { id } = Route.useParams()
  const router = useRouter()
  const [form, setForm] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(true)

  useEffect(() => {
    api.getJob(id)
      .then((d: any) => {
        const j = d.job
        setForm({
          title: j.title, description: j.description, location: j.location,
          type: j.type, category: j.category, experienceLevel: j.experienceLevel,
          remote: j.remote, salaryMin: j.salaryMin ?? '', salaryMax: j.salaryMax ?? '',
          salaryCurrency: j.salaryCurrency ?? 'USD', salaryPeriod: j.salaryPeriod ?? 'yearly',
          requirements: j.requirements?.join('\n') ?? '', responsibilities: j.responsibilities?.join('\n') ?? '',
          skills: j.skills?.join(', ') ?? '', featured: j.featured,
          applicationDeadline: j.applicationDeadline ? j.applicationDeadline.slice(0, 10) : '',
        })
      })
      .catch(() => setError('Failed to load job'))
      .finally(() => setFetching(false))
  }, [id])

  function set(key: string, value: any) {
    setForm((f: any) => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    const payload = {
      ...form,
      requirements: form.requirements ? form.requirements.split('\n').filter(Boolean) : [],
      responsibilities: form.responsibilities ? form.responsibilities.split('\n').filter(Boolean) : [],
      skills: form.skills ? form.skills.split(',').map((s: string) => s.trim()).filter(Boolean) : [],
      salaryMin: form.salaryMin ? Number(form.salaryMin) : undefined,
      salaryMax: form.salaryMax ? Number(form.salaryMax) : undefined,
      applicationDeadline: form.applicationDeadline || undefined,
    }
    setLoading(true)
    try {
      await api.updateJob(id, payload)
      router.navigate({ to: '/employer/dashboard' })
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (fetching) return <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}><Spinner size={48} color="var(--md-sys-color-primary)" /></div>
  if (!form) return <PageContainer><Alert type="error">{error || 'Job not found'}</Alert></PageContainer>

  return (
    <PageContainer style={{ maxWidth: 760 }}>
      <h1 style={{ fontSize: 'var(--md-sys-typescale-headline-large-size)', fontWeight: 600, margin: '0 0 32px' }}>Edit job</h1>
      {error && <Alert type="error">{error}</Alert>}
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: error ? 24 : 0 }}>
        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Basic information</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <TextField label="Job title" value={form.title} onChange={e => set('title', e.target.value)} required />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Select label="Job type" value={form.type} onChange={e => set('type', e.target.value)} options={JOB_TYPES} required />
              <Select label="Category" value={form.category} onChange={e => set('category', e.target.value)} options={CATEGORIES} required />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <TextField label="Location" value={form.location} onChange={e => set('location', e.target.value)} required />
              <Select label="Experience level" value={form.experienceLevel} onChange={e => set('experienceLevel', e.target.value)} options={EXP_LEVELS} required />
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
              <input type="checkbox" checked={form.remote} onChange={e => set('remote', e.target.checked)} style={{ width: 18, height: 18, accentColor: 'var(--md-sys-color-primary)' }} />
              <span>Remote position</span>
            </label>
          </div>
        </Card>
        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Description</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Textarea label="Job description" value={form.description} onChange={e => set('description', e.target.value)} required rows={8} />
            <Textarea label="Requirements (one per line)" value={form.requirements} onChange={e => set('requirements', e.target.value)} rows={5} />
            <Textarea label="Responsibilities (one per line)" value={form.responsibilities} onChange={e => set('responsibilities', e.target.value)} rows={5} />
            <TextField label="Skills (comma-separated)" value={form.skills} onChange={e => set('skills', e.target.value)} />
          </div>
        </Card>
        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Compensation</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16 }}>
            <TextField label="Min salary" type="number" value={form.salaryMin} onChange={e => set('salaryMin', e.target.value)} />
            <TextField label="Max salary" type="number" value={form.salaryMax} onChange={e => set('salaryMax', e.target.value)} />
            <TextField label="Currency" value={form.salaryCurrency} onChange={e => set('salaryCurrency', e.target.value)} />
            <Select label="Period" value={form.salaryPeriod} onChange={e => set('salaryPeriod', e.target.value)} options={SALARY_PERIODS} />
          </div>
        </Card>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <Button type="button" variant="outlined" onClick={() => router.navigate({ to: '/employer/dashboard' })}>Cancel</Button>
          <Button type="submit" loading={loading}>Save changes</Button>
        </div>
      </form>
    </PageContainer>
  )
}

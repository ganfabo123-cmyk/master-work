import { createFileRoute, useRouter } from '@tanstack/react-router'
import { useState } from 'react'
import { api } from '#/lib/api'
import { useAuth } from '#/context/auth'
import { Button, TextField, Textarea, Select, Card, Alert, PageContainer } from '#/components/ui'

export const Route = createFileRoute('/employer/post-job')({ component: PostJobPage })

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
const SALARY_PERIODS = [
  { value: 'hourly', label: 'Per hour' },
  { value: 'monthly', label: 'Per month' },
  { value: 'yearly', label: 'Per year' },
]

function PostJobPage() {
  useAuth()
  const router = useRouter()

  const [form, setForm] = useState({
    title: '', description: '', location: '', type: '', category: '',
    experienceLevel: '', remote: false, salaryMin: '', salaryMax: '',
    salaryCurrency: 'USD', salaryPeriod: 'yearly',
    requirements: '', responsibilities: '', skills: '',
    applicationDeadline: '', featured: false,
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function set(key: string, value: any) {
    setForm(f => ({ ...f, [key]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    const payload = {
      ...form,
      requirements: form.requirements ? form.requirements.split('\n').filter(Boolean) : [],
      responsibilities: form.responsibilities ? form.responsibilities.split('\n').filter(Boolean) : [],
      skills: form.skills ? form.skills.split(',').map(s => s.trim()).filter(Boolean) : [],
      salaryMin: form.salaryMin ? Number(form.salaryMin) : undefined,
      salaryMax: form.salaryMax ? Number(form.salaryMax) : undefined,
      applicationDeadline: form.applicationDeadline || undefined,
    }

    setLoading(true)
    try {
      await api.createJob(payload)
      router.navigate({ to: '/employer/dashboard' })
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageContainer style={{ maxWidth: 760 }}>
      <h1 style={{ fontSize: 'var(--md-sys-typescale-headline-large-size)', fontWeight: 600, margin: '0 0 8px' }}>
        Post a job
      </h1>
      <p style={{ color: 'var(--md-sys-color-on-surface-variant)', margin: '0 0 32px' }}>
        Fill in the details below to attract the right candidates.
      </p>

      {error && <Alert type="error" >{error}</Alert>}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: error ? 24 : 0 }}>
        {/* Basic info */}
        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Basic information</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <TextField label="Job title" value={form.title} onChange={e => set('title', e.target.value)} required placeholder="e.g. Senior React Developer" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Select label="Job type" value={form.type} onChange={e => set('type', e.target.value)} options={JOB_TYPES} required />
              <Select label="Category" value={form.category} onChange={e => set('category', e.target.value)} options={CATEGORIES} required />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <TextField label="Location" value={form.location} onChange={e => set('location', e.target.value)} required placeholder="e.g. New York, NY" />
              <Select label="Experience level" value={form.experienceLevel} onChange={e => set('experienceLevel', e.target.value)} options={EXP_LEVELS} required />
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
              <input type="checkbox" checked={form.remote} onChange={e => set('remote', e.target.checked)} style={{ width: 18, height: 18, accentColor: 'var(--md-sys-color-primary)' }} />
              <span style={{ fontSize: 'var(--md-sys-typescale-body-large-size)' }}>This is a remote position</span>
            </label>
          </div>
        </Card>

        {/* Description */}
        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Description</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Textarea label="Job description" value={form.description} onChange={e => set('description', e.target.value)} required rows={8} placeholder="Describe the role, what the candidate will work on, team culture, etc." />
            <Textarea label="Requirements (one per line)" value={form.requirements} onChange={e => set('requirements', e.target.value)} rows={5} placeholder={"3+ years of React experience\nStrong TypeScript skills\nExperience with REST APIs"} />
            <Textarea label="Responsibilities (one per line)" value={form.responsibilities} onChange={e => set('responsibilities', e.target.value)} rows={5} placeholder={"Build and maintain frontend components\nCollaborate with design and backend teams\nWrite unit tests"} />
            <TextField label="Skills (comma-separated)" value={form.skills} onChange={e => set('skills', e.target.value)} placeholder="React, TypeScript, Node.js, PostgreSQL" />
          </div>
        </Card>

        {/* Compensation */}
        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Compensation</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16 }}>
            <TextField label="Min salary" type="number" value={form.salaryMin} onChange={e => set('salaryMin', e.target.value)} placeholder="60000" />
            <TextField label="Max salary" type="number" value={form.salaryMax} onChange={e => set('salaryMax', e.target.value)} placeholder="90000" />
            <TextField label="Currency" value={form.salaryCurrency} onChange={e => set('salaryCurrency', e.target.value)} placeholder="USD" />
            <Select label="Period" value={form.salaryPeriod} onChange={e => set('salaryPeriod', e.target.value)} options={SALARY_PERIODS} />
          </div>
        </Card>

        {/* Settings */}
        <Card>
          <h2 style={{ margin: '0 0 20px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Settings</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <TextField label="Application deadline" type="date" value={form.applicationDeadline} onChange={e => set('applicationDeadline', e.target.value)} />
            <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
              <input type="checkbox" checked={form.featured} onChange={e => set('featured', e.target.checked)} style={{ width: 18, height: 18, accentColor: 'var(--md-sys-color-primary)' }} />
              <div>
                <span style={{ fontSize: 'var(--md-sys-typescale-body-large-size)', display: 'block' }}>Feature this job</span>
                <span style={{ fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>Featured jobs appear at the top of search results and on the home page.</span>
              </div>
            </label>
          </div>
        </Card>

        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <Button type="button" variant="outlined" onClick={() => router.navigate({ to: '/employer/dashboard' })}>
            Cancel
          </Button>
          <Button type="submit" loading={loading}>
            Publish job
          </Button>
        </div>
      </form>
    </PageContainer>
  )
}

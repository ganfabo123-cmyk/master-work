import { createFileRoute, Link, useRouter } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { api } from '#/lib/api'
import { useAuth } from '#/context/auth'
import { Button, Card, StatusBadge, Spinner, Alert, PageContainer } from '#/components/ui'

export const Route = createFileRoute('/employer/dashboard')({ component: EmployerDashboard })

function EmployerDashboard() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()

  const [jobs, setJobs] = useState<any[]>([])
  const [applications, setApplications] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'jobs' | 'applications'>('jobs')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!authLoading && user?.role !== 'employer') {
      router.navigate({ to: user ? '/' : '/auth/login' })
    }
  }, [user, authLoading])

  useEffect(() => {
    if (!user || user.role !== 'employer') return
    Promise.all([
      api.getMyJobs().then((d: any) => setJobs(d.jobs)),
      api.getEmployerApplications().then((d: any) => setApplications(d.applications)),
    ])
      .catch(() => setError('Failed to load dashboard data'))
      .finally(() => setLoading(false))
  }, [user])

  async function deleteJob(id: string) {
    if (!confirm('Delete this job posting?')) return
    try {
      await api.deleteJob(id)
      setJobs(j => j.filter(x => x._id !== id))
    } catch (err: any) {
      alert(err.message)
    }
  }

  async function toggleStatus(job: any) {
    const newStatus = job.status === 'active' ? 'closed' : 'active'
    try {
      await api.updateJob(job._id, { status: newStatus })
      setJobs(j => j.map(x => x._id === job._id ? { ...x, status: newStatus } : x))
    } catch (err: any) {
      alert(err.message)
    }
  }

  async function updateAppStatus(appId: string, status: string) {
    try {
      await api.updateApplicationStatus(appId, status)
      setApplications(apps => apps.map(a => a._id === appId ? { ...a, status } : a))
    } catch (err: any) {
      alert(err.message)
    }
  }

  if (authLoading || loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
      <Spinner size={48} color="var(--md-sys-color-primary)" />
    </div>
  )

  const activeJobs = jobs.filter(j => j.status === 'active').length
  const totalApplications = applications.length
  const pendingApplications = applications.filter(a => a.status === 'pending').length

  return (
    <PageContainer>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16, marginBottom: 32 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--md-sys-typescale-headline-large-size)', fontWeight: 600 }}>
            Employer Dashboard
          </h1>
          <p style={{ margin: '4px 0 0', color: 'var(--md-sys-color-on-surface-variant)' }}>
            {user?.companyName ?? user?.name}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link to="/employer/profile">
            <Button variant="outlined">Edit profile</Button>
          </Link>
          <Link to="/employer/post-job">
            <Button>+ Post a job</Button>
          </Link>
        </div>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 32 }}>
        <StatCard label="Active postings" value={activeJobs} color="var(--md-sys-color-primary)" />
        <StatCard label="Total applications" value={totalApplications} color="var(--md-sys-color-tertiary)" />
        <StatCard label="Pending review" value={pendingApplications} color="var(--md-sys-color-secondary)" />
        <StatCard label="Total postings" value={jobs.length} color="var(--md-sys-color-on-surface-variant)" />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--md-sys-color-outline-variant)', marginBottom: 24 }}>
        {(['jobs', 'applications'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '12px 20px',
              border: 'none',
              background: 'none',
              cursor: 'pointer',
              fontWeight: tab === t ? 700 : 400,
              fontSize: 'var(--md-sys-typescale-title-small-size)',
              color: tab === t ? 'var(--md-sys-color-primary)' : 'var(--md-sys-color-on-surface-variant)',
              borderBottom: tab === t ? '2px solid var(--md-sys-color-primary)' : '2px solid transparent',
              transition: 'color 150ms',
              textTransform: 'capitalize',
            }}
          >
            {t} {t === 'jobs' ? `(${jobs.length})` : `(${applications.length})`}
          </button>
        ))}
      </div>

      {/* Jobs tab */}
      {tab === 'jobs' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {jobs.length === 0 ? (
            <Card style={{ textAlign: 'center', padding: 48 }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>📋</div>
              <p style={{ margin: '0 0 16px', color: 'var(--md-sys-color-on-surface-variant)' }}>No job postings yet.</p>
              <Link to="/employer/post-job"><Button>Post your first job</Button></Link>
            </Card>
          ) : jobs.map(job => (
            <Card key={job._id} style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <h3 style={{ margin: '0 0 4px', fontSize: 'var(--md-sys-typescale-title-medium-size)' }}>
                  <Link to="/jobs/$id" params={{ id: job._id }} style={{ color: 'var(--md-sys-color-on-surface)' }}>
                    {job.title}
                  </Link>
                </h3>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <StatusBadge status={job.status} />
                  <span style={{ fontSize: 'var(--md-sys-typescale-label-medium-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>
                    {job.location} · {job.type}
                  </span>
                  <span style={{ fontSize: 'var(--md-sys-typescale-label-medium-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>
                    {job.applicationCount ?? 0} applications · {job.views ?? 0} views
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                <Button variant="tonal" onClick={() => toggleStatus(job)} style={{ padding: '8px 16px' }}>
                  {job.status === 'active' ? 'Close' : 'Reopen'}
                </Button>
                <Link to="/employer/edit-job/$id" params={{ id: job._id }}>
                  <Button variant="outlined" style={{ padding: '8px 16px' }}>Edit</Button>
                </Link>
                <Button variant="text" onClick={() => deleteJob(job._id)} style={{ color: 'var(--md-sys-color-error)', padding: '8px 16px' }}>
                  Delete
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Applications tab */}
      {tab === 'applications' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {applications.length === 0 ? (
            <Card style={{ textAlign: 'center', padding: 48 }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>📨</div>
              <p style={{ color: 'var(--md-sys-color-on-surface-variant)', margin: 0 }}>No applications received yet.</p>
            </Card>
          ) : applications.map(app => (
            <Card key={app._id}>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                <div style={{ flex: 1, minWidth: 200 }}>
                  <h3 style={{ margin: '0 0 4px', fontSize: 'var(--md-sys-typescale-title-medium-size)' }}>
                    {app.candidate?.name}
                  </h3>
                  <p style={{ margin: '0 0 4px', color: 'var(--md-sys-color-on-surface-variant)', fontSize: 'var(--md-sys-typescale-body-medium-size)' }}>
                    {app.candidate?.email}
                    {app.candidate?.headline && ` · ${app.candidate.headline}`}
                  </p>
                  <p style={{ margin: '0 0 8px', fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>
                    Applied for: <Link to="/jobs/$id" params={{ id: app.job?._id }} style={{ color: 'var(--md-sys-color-primary)' }}>{app.job?.title}</Link>
                  </p>
                  {app.candidate?.skills?.length > 0 && (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {app.candidate.skills.slice(0, 5).map((s: string) => (
                        <span key={s} style={{ padding: '2px 8px', borderRadius: 'var(--md-sys-shape-corner-extra-small)', background: 'var(--md-sys-color-surface-container)', fontSize: 'var(--md-sys-typescale-label-small-size)', border: '1px solid var(--md-sys-color-outline-variant)' }}>{s}</span>
                      ))}
                    </div>
                  )}
                  <p style={{ margin: '8px 0 0', fontSize: 'var(--md-sys-typescale-label-small-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>
                    Applied {new Date(app.createdAt).toLocaleDateString()}
                  </p>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
                  <StatusBadge status={app.status} />
                  <select
                    value={app.status}
                    onChange={e => updateAppStatus(app._id, e.target.value)}
                    style={{ padding: '8px 12px', borderRadius: 'var(--md-sys-shape-corner-small)', border: '1px solid var(--md-sys-color-outline)', background: 'var(--md-sys-color-surface-container-lowest)', fontSize: 'var(--md-sys-typescale-label-large-size)', cursor: 'pointer', color: 'var(--md-sys-color-on-surface)' }}
                  >
                    <option value="pending">Pending</option>
                    <option value="reviewing">Reviewing</option>
                    <option value="shortlisted">Shortlisted</option>
                    <option value="rejected">Rejected</option>
                    <option value="hired">Hired</option>
                  </select>
                  {app.resumeUrl && (
                    <a href={`http://localhost:5000${app.resumeUrl}`} target="_blank" rel="noopener noreferrer">
                      <Button variant="outlined" style={{ padding: '8px 16px' }}>View resume</Button>
                    </a>
                  )}
                </div>
              </div>
              {app.coverLetter && (
                <details style={{ marginTop: 12 }}>
                  <summary style={{ cursor: 'pointer', fontSize: 'var(--md-sys-typescale-label-large-size)', color: 'var(--md-sys-color-primary)', userSelect: 'none' }}>
                    Read cover letter
                  </summary>
                  <p style={{ margin: '8px 0 0', lineHeight: 1.7, fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-surface-variant)', whiteSpace: 'pre-wrap' }}>
                    {app.coverLetter}
                  </p>
                </details>
              )}
            </Card>
          ))}
        </div>
      )}
    </PageContainer>
  )
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <Card>
      <p style={{ margin: '0 0 4px', fontSize: 'clamp(1.5rem, 2.5vw, 2.25rem)', fontWeight: 800, color }}>{value}</p>
      <p style={{ margin: 0, fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>{label}</p>
    </Card>
  )
}

import { createFileRoute, Link, useRouter } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { api } from '#/lib/api'
import { useAuth } from '#/context/auth'
import { Card, StatusBadge, Spinner, Alert, PageContainer, Button } from '#/components/ui'

export const Route = createFileRoute('/candidate/dashboard')({ component: CandidateDashboard })

function CandidateDashboard() {
  const { user, loading: authLoading } = useAuth()
  const router = useRouter()

  const [applications, setApplications] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!authLoading && user?.role !== 'candidate') {
      router.navigate({ to: user ? '/' : '/auth/login' })
    }
  }, [user, authLoading])

  useEffect(() => {
    if (!user || user.role !== 'candidate') return
    api.getMyApplications()
      .then((d: any) => setApplications(d.applications))
      .catch(() => setError('Failed to load applications'))
      .finally(() => setLoading(false))
  }, [user])

  if (authLoading || loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
      <Spinner size={48} color="var(--md-sys-color-primary)" />
    </div>
  )

  const counts = {
    total: applications.length,
    pending: applications.filter(a => a.status === 'pending').length,
    reviewing: applications.filter(a => a.status === 'reviewing').length,
    shortlisted: applications.filter(a => a.status === 'shortlisted').length,
    hired: applications.filter(a => a.status === 'hired').length,
  }

  return (
    <PageContainer>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16, marginBottom: 32 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--md-sys-typescale-headline-large-size)', fontWeight: 600 }}>My Dashboard</h1>
          <p style={{ margin: '4px 0 0', color: 'var(--md-sys-color-on-surface-variant)' }}>Welcome back, {user?.name}</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link to="/candidate/profile"><Button variant="outlined">Edit profile</Button></Link>
          <Link to="/jobs"><Button>Browse jobs</Button></Link>
        </div>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16, marginBottom: 32 }}>
        <StatCard label="Total applied" value={counts.total} color="var(--md-sys-color-primary)" />
        <StatCard label="Pending" value={counts.pending} color="var(--md-sys-color-on-surface-variant)" />
        <StatCard label="In review" value={counts.reviewing} color="var(--md-sys-color-secondary)" />
        <StatCard label="Shortlisted" value={counts.shortlisted} color="var(--md-sys-color-tertiary)" />
        <StatCard label="Hired" value={counts.hired} color="#16a34a" />
      </div>

      {/* Profile completeness */}
      {(!user?.headline || !user?.skills?.length || !user?.bio) && (
        <div style={{ marginBottom: 24, padding: 20, borderRadius: 'var(--md-sys-shape-corner-medium)', background: 'var(--md-sys-color-secondary-container)', border: '1px solid var(--md-sys-color-secondary)' }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 'var(--md-sys-typescale-title-medium-size)', color: 'var(--md-sys-color-on-secondary-container)' }}>
            Complete your profile
          </h3>
          <p style={{ margin: '0 0 12px', fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-secondary-container)', opacity: 0.85 }}>
            A complete profile increases your chances of being noticed by employers.
          </p>
          <Link to="/candidate/profile">
            <Button variant="outlined" style={{ borderColor: 'var(--md-sys-color-secondary)', color: 'var(--md-sys-color-on-secondary-container)' }}>
              Complete profile →
            </Button>
          </Link>
        </div>
      )}

      {/* Applications list */}
      <h2 style={{ fontSize: 'var(--md-sys-typescale-title-large-size)', margin: '0 0 16px' }}>My applications</h2>

      {applications.length === 0 ? (
        <Card style={{ textAlign: 'center', padding: 56 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>📋</div>
          <h3 style={{ margin: '0 0 8px' }}>No applications yet</h3>
          <p style={{ color: 'var(--md-sys-color-on-surface-variant)', margin: '0 0 20px' }}>Start browsing jobs and apply to positions that fit your skills.</p>
          <Link to="/jobs"><Button>Browse jobs</Button></Link>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {applications.map(app => (
            <Card key={app._id} style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <h3 style={{ margin: '0 0 4px', fontSize: 'var(--md-sys-typescale-title-medium-size)' }}>
                  <Link to="/jobs/$id" params={{ id: app.job?._id }} style={{ color: 'var(--md-sys-color-on-surface)' }}>
                    {app.job?.title}
                  </Link>
                </h3>
                <p style={{ margin: '0 0 6px', color: 'var(--md-sys-color-on-surface-variant)', fontSize: 'var(--md-sys-typescale-body-medium-size)' }}>
                  {app.job?.companyName}
                  {app.job?.location && ` · ${app.job.location}`}
                  {app.job?.type && ` · ${app.job.type}`}
                </p>
                <p style={{ margin: 0, fontSize: 'var(--md-sys-typescale-label-small-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>
                  Applied {new Date(app.createdAt).toLocaleDateString()}
                </p>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
                <StatusBadge status={app.status} />
                {getStatusHint(app.status) && (
                  <p style={{ margin: 0, fontSize: 'var(--md-sys-typescale-label-small-size)', color: 'var(--md-sys-color-on-surface-variant)', textAlign: 'right' }}>
                    {getStatusHint(app.status)}
                  </p>
                )}
              </div>
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

function getStatusHint(status: string) {
  const hints: Record<string, string> = {
    pending: 'Waiting for employer review',
    reviewing: 'Employer is reviewing your application',
    shortlisted: 'You\'ve been shortlisted!',
    rejected: 'Not selected for this role',
    hired: '🎉 Congratulations!',
  }
  return hints[status] ?? ''
}

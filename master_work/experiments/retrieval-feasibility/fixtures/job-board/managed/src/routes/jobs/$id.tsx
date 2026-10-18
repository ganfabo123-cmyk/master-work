import { createFileRoute, Link, useRouter } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { api } from '#/lib/api'
import { useAuth } from '#/context/auth'
import { Button, Card, StatusBadge, Spinner, Alert, Textarea, PageContainer } from '#/components/ui'

export const Route = createFileRoute('/jobs/$id')({ component: JobDetailPage })

function JobDetailPage() {
  const { id } = Route.useParams()
  const { user } = useAuth()
  const router = useRouter()

  const [job, setJob] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [applying, setApplying] = useState(false)
  const [applyError, setApplyError] = useState('')
  const [applySuccess, setApplySuccess] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [coverLetter, setCoverLetter] = useState('')
  const [resume, setResume] = useState<File | null>(null)

  useEffect(() => {
    api.getJob(id)
      .then((d: any) => setJob(d.job))
      .catch(() => setError('Job not found'))
      .finally(() => setLoading(false))
  }, [id])

  async function handleApply(e: React.FormEvent) {
    e.preventDefault()
    if (!resume) { setApplyError('Please attach your resume'); return }
    if (!coverLetter.trim()) { setApplyError('Cover letter is required'); return }

    const fd = new FormData()
    fd.append('jobId', id)
    fd.append('coverLetter', coverLetter)
    fd.append('resume', resume)

    setApplying(true)
    setApplyError('')
    try {
      await api.apply(fd)
      setApplySuccess(true)
      setShowForm(false)
    } catch (err: any) {
      setApplyError(err.message)
    } finally {
      setApplying(false)
    }
  }

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
      <Spinner size={48} color="var(--md-sys-color-primary)" />
    </div>
  )

  if (error || !job) return (
    <PageContainer style={{ textAlign: 'center', padding: '80px 16px' }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>😕</div>
      <h2>Job not found</h2>
      <Link to="/jobs" style={{ color: 'var(--md-sys-color-primary)' }}>Back to jobs</Link>
    </PageContainer>
  )

  const salary = job.salaryMin || job.salaryMax
    ? `${job.salaryCurrency ?? 'USD'} ${job.salaryMin ? job.salaryMin.toLocaleString() : ''}${job.salaryMin && job.salaryMax ? ' – ' : ''}${job.salaryMax ? job.salaryMax.toLocaleString() : ''}/${job.salaryPeriod ?? 'year'}`
    : null

  return (
    <PageContainer>
      {/* Breadcrumb */}
      <nav style={{ marginBottom: 24, fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>
        <Link to="/" style={{ color: 'var(--md-sys-color-primary)' }}>Home</Link>
        {' › '}
        <Link to="/jobs" style={{ color: 'var(--md-sys-color-primary)' }}>Jobs</Link>
        {' › '}
        <span>{job.title}</span>
      </nav>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 320px', gap: 24, alignItems: 'start' }}>
        {/* Main */}
        <div style={{ minWidth: 0 }}>
          {/* Header card */}
          <Card style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              {job.employer?.companyLogo ? (
                <img src={job.employer.companyLogo} alt={job.companyName} style={{ width: 64, height: 64, borderRadius: 'var(--md-sys-shape-corner-small)', objectFit: 'cover' }} />
              ) : (
                <div style={{ width: 64, height: 64, borderRadius: 'var(--md-sys-shape-corner-small)', background: 'var(--md-sys-color-primary-container)', color: 'var(--md-sys-color-on-primary-container)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, fontWeight: 700, flexShrink: 0 }}>
                  {job.companyName?.[0]?.toUpperCase()}
                </div>
              )}
              <div style={{ flex: 1 }}>
                <h1 style={{ margin: '0 0 4px', fontSize: 'var(--md-sys-typescale-headline-medium-size)', fontWeight: 600 }}>{job.title}</h1>
                <p style={{ margin: '0 0 8px', fontSize: 'var(--md-sys-typescale-title-medium-size)', color: 'var(--md-sys-color-primary)', fontWeight: 500 }}>{job.companyName}</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                  <InfoChip icon="📍">{job.location}</InfoChip>
                  {job.remote && <InfoChip icon="🌐">Remote</InfoChip>}
                  <StatusBadge status={job.type} />
                  <InfoChip icon="⭐">{job.experienceLevel} level</InfoChip>
                  <InfoChip icon="📂">{job.category}</InfoChip>
                  {salary && <InfoChip icon="💰">{salary}</InfoChip>}
                </div>
              </div>
            </div>

            {job.applicationDeadline && (
              <p style={{ margin: '16px 0 0', fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>
                Apply by: <strong>{new Date(job.applicationDeadline).toLocaleDateString()}</strong>
              </p>
            )}

            {job.views != null && (
              <p style={{ margin: '4px 0 0', fontSize: 'var(--md-sys-typescale-label-small-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>
                {job.views} views · {job.applicationCount ?? 0} applications
              </p>
            )}
          </Card>

          {/* Description */}
          <Card style={{ marginBottom: 16 }}>
            <h2 style={{ margin: '0 0 16px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Job description</h2>
            <div style={{ color: 'var(--md-sys-color-on-surface)', lineHeight: 1.7, whiteSpace: 'pre-wrap', fontSize: 'var(--md-sys-typescale-body-large-size)' }}>
              {job.description}
            </div>
          </Card>

          {job.requirements?.length > 0 && (
            <Card style={{ marginBottom: 16 }}>
              <h2 style={{ margin: '0 0 16px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Requirements</h2>
              <ul style={{ margin: 0, padding: '0 0 0 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {job.requirements.map((r: string, i: number) => <li key={i} style={{ lineHeight: 1.6 }}>{r}</li>)}
              </ul>
            </Card>
          )}

          {job.responsibilities?.length > 0 && (
            <Card style={{ marginBottom: 16 }}>
              <h2 style={{ margin: '0 0 16px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Responsibilities</h2>
              <ul style={{ margin: 0, padding: '0 0 0 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {job.responsibilities.map((r: string, i: number) => <li key={i} style={{ lineHeight: 1.6 }}>{r}</li>)}
              </ul>
            </Card>
          )}

          {job.skills?.length > 0 && (
            <Card>
              <h2 style={{ margin: '0 0 16px', fontSize: 'var(--md-sys-typescale-title-large-size)' }}>Skills</h2>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {job.skills.map((s: string) => (
                  <span key={s} style={{ padding: '6px 14px', borderRadius: 'var(--md-sys-shape-corner-full)', background: 'var(--md-sys-color-secondary-container)', color: 'var(--md-sys-color-on-secondary-container)', fontSize: 'var(--md-sys-typescale-label-large-size)', fontWeight: 500 }}>
                    {s}
                  </span>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Apply card */}
          <Card>
            {applySuccess ? (
              <Alert type="success">
                <strong>Application submitted!</strong> You'll receive a confirmation email. Track it in your dashboard.
              </Alert>
            ) : user?.role === 'candidate' ? (
              <>
                {!showForm ? (
                  <Button onClick={() => setShowForm(true)} style={{ width: '100%' }}>
                    Apply now
                  </Button>
                ) : (
                  <form onSubmit={handleApply} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <h3 style={{ margin: 0, fontSize: 'var(--md-sys-typescale-title-medium-size)' }}>Submit application</h3>
                    {applyError && <Alert type="error">{applyError}</Alert>}
                    <Textarea
                      label="Cover letter"
                      required
                      value={coverLetter}
                      onChange={e => setCoverLetter(e.target.value)}
                      rows={6}
                      placeholder="Why are you a great fit for this role?"
                    />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <label style={{ fontSize: 'var(--md-sys-typescale-label-medium-size)', fontWeight: 500, color: 'var(--md-sys-color-on-surface-variant)' }}>
                        Resume (PDF, DOC, DOCX — max 5MB) *
                      </label>
                      <input
                        type="file"
                        accept=".pdf,.doc,.docx"
                        onChange={e => setResume(e.target.files?.[0] ?? null)}
                        required
                        style={{ padding: '10px 0', fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-surface)' }}
                      />
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <Button type="submit" loading={applying} style={{ flex: 1 }}>Submit</Button>
                      <Button type="button" variant="outlined" onClick={() => setShowForm(false)}>Cancel</Button>
                    </div>
                  </form>
                )}
              </>
            ) : user?.role === 'employer' ? (
              <p style={{ margin: 0, color: 'var(--md-sys-color-on-surface-variant)', fontSize: 'var(--md-sys-typescale-body-medium-size)' }}>
                You're signed in as an employer.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <p style={{ margin: 0, color: 'var(--md-sys-color-on-surface-variant)', fontSize: 'var(--md-sys-typescale-body-medium-size)' }}>
                  Sign in to apply for this position.
                </p>
                <Link to="/auth/login" style={{ display: 'block' }}>
                  <Button style={{ width: '100%' }}>Sign in to apply</Button>
                </Link>
                <Link to="/auth/register" search={{ role: 'candidate' }} style={{ display: 'block' }}>
                  <Button variant="outlined" style={{ width: '100%' }}>Create account</Button>
                </Link>
              </div>
            )}
          </Card>

          {/* Company info */}
          {job.employer && (
            <Card>
              <h3 style={{ margin: '0 0 16px', fontSize: 'var(--md-sys-typescale-title-medium-size)' }}>About the company</h3>
              <p style={{ margin: '0 0 8px', fontWeight: 600 }}>{job.companyName}</p>
              {job.employer.industry && <InfoChip icon="🏭">{job.employer.industry}</InfoChip>}
              {job.employer.companySize && <InfoChip icon="👥">{job.employer.companySize} employees</InfoChip>}
              {job.employer.companyDescription && (
                <p style={{ margin: '12px 0 0', fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-surface-variant)', lineHeight: 1.6 }}>
                  {job.employer.companyDescription}
                </p>
              )}
              {job.employer.companyWebsite && (
                <a
                  href={job.employer.companyWebsite}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ display: 'inline-block', marginTop: 12, color: 'var(--md-sys-color-primary)', fontSize: 'var(--md-sys-typescale-label-large-size)' }}
                >
                  Visit website →
                </a>
              )}
            </Card>
          )}

          <Button variant="outlined" onClick={() => router.history.back()}>
            ← Back
          </Button>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          div[style*="grid-template-columns: minmax(0,1fr) 320px"] {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </PageContainer>
  )
}

function InfoChip({ icon, children }: { icon?: string; children: React.ReactNode }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 10px', borderRadius: 'var(--md-sys-shape-corner-full)', border: '1px solid var(--md-sys-color-outline-variant)', fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-surface-variant)', background: 'var(--md-sys-color-surface-container)' }}>
      {icon && <span>{icon}</span>}
      {children}
    </span>
  )
}

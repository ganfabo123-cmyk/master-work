import { createFileRoute, Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { api } from '#/lib/api'
import { JobCard } from '#/components/JobCard'
import { Spinner, PageContainer } from '#/components/ui'

export const Route = createFileRoute('/')({ component: Home })

const JOB_CATEGORIES = [
  { label: 'Engineering', icon: '⚙️' },
  { label: 'Design', icon: '🎨' },
  { label: 'Marketing', icon: '📣' },
  { label: 'Sales', icon: '💼' },
  { label: 'Finance', icon: '💰' },
  { label: 'Healthcare', icon: '🏥' },
  { label: 'Education', icon: '📚' },
  { label: 'Data Science', icon: '📊' },
]

const STATS = [
  { value: '10,000+', label: 'Active Jobs' },
  { value: '5,000+', label: 'Companies' },
  { value: '50,000+', label: 'Candidates' },
]

function Home() {
  const [featuredJobs, setFeaturedJobs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    api.getFeaturedJobs()
      .then((d: any) => setFeaturedJobs(d.jobs))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      {/* Hero */}
      <section
        style={{
          background: 'linear-gradient(135deg, var(--md-sys-color-primary) 0%, #0d3b9e 100%)',
          color: 'var(--md-sys-color-on-primary)',
          padding: '72px 16px',
          textAlign: 'center',
        }}
      >
        <div style={{ maxWidth: 720, margin: '0 auto' }}>
          <h1
            style={{
              fontSize: 'clamp(2rem, 5vw, var(--md-sys-typescale-display-medium-size))',
              fontWeight: 700,
              lineHeight: 1.15,
              margin: '0 0 16px',
            }}
          >
            Find the job that fits your life
          </h1>
          <p
            style={{
              fontSize: 'var(--md-sys-typescale-title-medium-size)',
              opacity: 0.88,
              margin: '0 0 40px',
              maxWidth: 560,
              marginInline: 'auto',
            }}
          >
            Search thousands of openings from companies that care about what you bring to the table.
          </p>

          {/* Search bar */}
          <form
            onSubmit={e => {
              e.preventDefault()
              if (search.trim()) window.location.href = `/jobs?q=${encodeURIComponent(search)}`
            }}
            style={{
              display: 'flex',
              gap: 0,
              maxWidth: 640,
              marginInline: 'auto',
              borderRadius: 'var(--md-sys-shape-corner-extra-large)',
              overflow: 'hidden',
              boxShadow: '0 4px 24px rgba(0,0,0,0.2)',
            }}
          >
            <input
              type="text"
              placeholder="Job title, keyword, or company..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                flex: 1,
                padding: '18px 24px',
                border: 'none',
                outline: 'none',
                fontSize: 'var(--md-sys-typescale-body-large-size)',
                background: 'var(--md-sys-color-surface-container-lowest)',
                color: 'var(--md-sys-color-on-surface)',
                minWidth: 0,
              }}
              aria-label="Search jobs"
            />
            <button
              type="submit"
              style={{
                padding: '18px 32px',
                background: 'var(--md-sys-color-primary-container)',
                color: 'var(--md-sys-color-on-primary-container)',
                border: 'none',
                cursor: 'pointer',
                fontWeight: 700,
                fontSize: 'var(--md-sys-typescale-label-large-size)',
                whiteSpace: 'nowrap',
              }}
            >
              Search
            </button>
          </form>

          <p style={{ marginTop: 16, opacity: 0.7, fontSize: 'var(--md-sys-typescale-body-medium-size)' }}>
            Popular: React Developer, Product Designer, Data Analyst
          </p>
        </div>
      </section>

      {/* Stats */}
      <section style={{ background: 'var(--md-sys-color-surface-container-low)', borderBottom: '1px solid var(--md-sys-color-outline-variant)' }}>
        <div
          style={{
            maxWidth: 900,
            margin: '0 auto',
            padding: '32px 16px',
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            textAlign: 'center',
            gap: 16,
          }}
        >
          {STATS.map(s => (
            <div key={s.label}>
              <p style={{ margin: 0, fontSize: 'clamp(1.5rem, 3vw, 2rem)', fontWeight: 800, color: 'var(--md-sys-color-primary)' }}>{s.value}</p>
              <p style={{ margin: '4px 0 0', fontSize: 'var(--md-sys-typescale-body-medium-size)', color: 'var(--md-sys-color-on-surface-variant)' }}>{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      <PageContainer>
        {/* Categories */}
        <section style={{ marginBottom: 56 }}>
          <h2 style={{ fontSize: 'var(--md-sys-typescale-headline-medium-size)', fontWeight: 600, margin: '0 0 24px' }}>
            Browse by category
          </h2>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
              gap: 12,
            }}
          >
            {JOB_CATEGORIES.map(cat => (
              <Link
                key={cat.label}
                to="/jobs"
                search={{ category: cat.label }}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 8,
                  padding: '20px 12px',
                  borderRadius: 'var(--md-sys-shape-corner-medium)',
                  border: '1px solid var(--md-sys-color-outline-variant)',
                  background: 'var(--md-sys-color-surface-container-low)',
                  textDecoration: 'none',
                  color: 'var(--md-sys-color-on-surface)',
                  transition: 'background 150ms, border-color 150ms',
                  textAlign: 'center',
                }}
                onMouseEnter={e => {
                  const el = e.currentTarget as HTMLElement
                  el.style.background = 'var(--md-sys-color-primary-container)'
                  el.style.borderColor = 'var(--md-sys-color-primary)'
                }}
                onMouseLeave={e => {
                  const el = e.currentTarget as HTMLElement
                  el.style.background = 'var(--md-sys-color-surface-container-low)'
                  el.style.borderColor = 'var(--md-sys-color-outline-variant)'
                }}
              >
                <span style={{ fontSize: 28 }}>{cat.icon}</span>
                <span style={{ fontSize: 'var(--md-sys-typescale-label-medium-size)', fontWeight: 500 }}>{cat.label}</span>
              </Link>
            ))}
          </div>
        </section>

        {/* Featured Jobs */}
        <section>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <h2 style={{ fontSize: 'var(--md-sys-typescale-headline-medium-size)', fontWeight: 600, margin: 0 }}>
              Featured jobs
            </h2>
            <Link
              to="/jobs"
              style={{
                color: 'var(--md-sys-color-primary)',
                fontWeight: 500,
                fontSize: 'var(--md-sys-typescale-label-large-size)',
              }}
            >
              View all →
            </Link>
          </div>

          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
              <Spinner size={40} color="var(--md-sys-color-primary)" />
            </div>
          ) : featuredJobs.length === 0 ? (
            <EmptyState
              icon="💼"
              title="No featured jobs yet"
              description="Check back soon or browse all available positions."
              action={<Link to="/jobs" style={{ color: 'var(--md-sys-color-primary)' }}>Browse all jobs</Link>}
            />
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
              {featuredJobs.map(job => <JobCard key={job._id} job={job} />)}
            </div>
          )}
        </section>

        {/* CTA */}
        <section
          style={{
            marginTop: 64,
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 16,
          }}
        >
          <div style={{ background: 'var(--md-sys-color-primary-container)', borderRadius: 'var(--md-sys-shape-corner-extra-large)', padding: '40px 32px' }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 'var(--md-sys-typescale-title-large-size)', color: 'var(--md-sys-color-on-primary-container)' }}>
              Looking for work?
            </h3>
            <p style={{ margin: '0 0 24px', color: 'var(--md-sys-color-on-primary-container)', opacity: 0.8 }}>
              Create a free profile, upload your resume, and start applying to thousands of roles today.
            </p>
            <Link
              to="/auth/register"
              search={{ role: 'candidate' }}
              style={{
                display: 'inline-block',
                padding: '12px 24px',
                background: 'var(--md-sys-color-primary)',
                color: 'var(--md-sys-color-on-primary)',
                borderRadius: 'var(--md-sys-shape-corner-full)',
                fontWeight: 600,
                textDecoration: 'none',
                fontSize: 'var(--md-sys-typescale-label-large-size)',
              }}
            >
              Create candidate profile
            </Link>
          </div>

          <div style={{ background: 'var(--md-sys-color-secondary-container)', borderRadius: 'var(--md-sys-shape-corner-extra-large)', padding: '40px 32px' }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 'var(--md-sys-typescale-title-large-size)', color: 'var(--md-sys-color-on-secondary-container)' }}>
              Hiring?
            </h3>
            <p style={{ margin: '0 0 24px', color: 'var(--md-sys-color-on-secondary-container)', opacity: 0.8 }}>
              Post your openings and reach a large pool of qualified candidates quickly.
            </p>
            <Link
              to="/auth/register"
              search={{ role: 'employer' }}
              style={{
                display: 'inline-block',
                padding: '12px 24px',
                background: 'var(--md-sys-color-secondary)',
                color: 'var(--md-sys-color-on-secondary)',
                borderRadius: 'var(--md-sys-shape-corner-full)',
                fontWeight: 600,
                textDecoration: 'none',
                fontSize: 'var(--md-sys-typescale-label-large-size)',
              }}
            >
              Post a job
            </Link>
          </div>
        </section>
      </PageContainer>
    </div>
  )
}

function EmptyState({ icon, title, description, action }: { icon: string; title: string; description: string; action?: React.ReactNode }) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 16px' }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>{icon}</div>
      <h3 style={{ margin: '0 0 8px', fontSize: 'var(--md-sys-typescale-title-medium-size)' }}>{title}</h3>
      <p style={{ margin: '0 0 16px', color: 'var(--md-sys-color-on-surface-variant)' }}>{description}</p>
      {action}
    </div>
  )
}

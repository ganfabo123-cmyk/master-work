import { createFileRoute, Link } from '@tanstack/react-router'
import { useEffect, useState, useRef } from 'react'
import { api } from '#/lib/api'
import { JobCard } from '#/components/JobCard'
import { Spinner, PageContainer, Button } from '#/components/ui'

interface SearchParams {
  q?: string
  location?: string
  type?: string
  category?: string
  experienceLevel?: string
  remote?: string
  page?: string
}

export const Route = createFileRoute('/jobs/')({
  validateSearch: (s: Record<string, string>): SearchParams => s,
  component: JobsPage,
})

const JOB_TYPES = ['full-time', 'part-time', 'contract', 'internship', 'freelance']
const EXP_LEVELS = ['entry', 'mid', 'senior', 'lead', 'executive']
const CATEGORIES = ['Engineering', 'Design', 'Marketing', 'Sales', 'Finance', 'Healthcare', 'Education', 'Data Science', 'Product', 'Operations', 'Legal', 'HR']

function JobsPage() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()

  const [jobs, setJobs] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)

  const [q, setQ] = useState(search.q ?? '')
  const [location, setLocation] = useState(search.location ?? '')
  const [type, setType] = useState(search.type ?? '')
  const [category, setCategory] = useState(search.category ?? '')
  const [expLevel, setExpLevel] = useState(search.experienceLevel ?? '')
  const [remote, setRemote] = useState(search.remote ?? '')
  const [page, setPage] = useState(Number(search.page ?? 1))
  const [filtersOpen, setFiltersOpen] = useState(false)

  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    const params: Record<string, string> = { page: String(page), limit: '12' }
    if (q) params.q = q
    if (location) params.location = location
    if (type) params.type = type
    if (category) params.category = category
    if (expLevel) params.experienceLevel = expLevel
    if (remote) params.remote = remote

    setLoading(true)
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      api.getJobs(params)
        .then((d: any) => { setJobs(d.jobs); setTotal(d.total); setPages(d.pages) })
        .catch(() => {})
        .finally(() => setLoading(false))
    }, 300)
  }, [q, location, type, category, expLevel, remote, page])

  function clearFilters() {
    setQ(''); setLocation(''); setType(''); setCategory(''); setExpLevel(''); setRemote(''); setPage(1)
  }

  const hasFilters = !!(q || location || type || category || expLevel || remote)

  return (
    <PageContainer style={{ padding: '24px 16px' }}>
      {/* Top search bar */}
      <div
        style={{
          display: 'flex',
          gap: 8,
          marginBottom: 24,
          background: 'var(--md-sys-color-surface-container-low)',
          border: '1px solid var(--md-sys-color-outline-variant)',
          borderRadius: 'var(--md-sys-shape-corner-extra-large)',
          padding: '8px 8px 8px 20px',
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <input
          type="text"
          placeholder="Search job title, skills, or company..."
          value={q}
          onChange={e => { setQ(e.target.value); setPage(1) }}
          style={{
            flex: 1,
            minWidth: 200,
            border: 'none',
            outline: 'none',
            background: 'transparent',
            fontSize: 'var(--md-sys-typescale-body-large-size)',
            color: 'var(--md-sys-color-on-surface)',
          }}
          aria-label="Search jobs"
        />
        <input
          type="text"
          placeholder="Location..."
          value={location}
          onChange={e => { setLocation(e.target.value); setPage(1) }}
          style={{
            width: 160,
            border: 'none',
            outline: 'none',
            background: 'transparent',
            fontSize: 'var(--md-sys-typescale-body-large-size)',
            color: 'var(--md-sys-color-on-surface)',
            borderLeft: '1px solid var(--md-sys-color-outline-variant)',
            paddingLeft: 12,
          }}
          aria-label="Filter by location"
        />
        <button
          onClick={() => setFiltersOpen(!filtersOpen)}
          style={{
            padding: '10px 20px',
            borderRadius: 'var(--md-sys-shape-corner-extra-large)',
            border: filtersOpen ? '2px solid var(--md-sys-color-primary)' : '1px solid var(--md-sys-color-outline)',
            background: filtersOpen ? 'var(--md-sys-color-primary-container)' : 'transparent',
            color: filtersOpen ? 'var(--md-sys-color-on-primary-container)' : 'var(--md-sys-color-on-surface)',
            cursor: 'pointer',
            fontWeight: 500,
            fontSize: 'var(--md-sys-typescale-label-large-size)',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M4.25 5.61C6.27 8.2 10 13 10 13v6c0 .55.45 1 1 1h2c.55 0 1-.45 1-1v-6s3.72-4.8 5.74-7.39A1 1 0 0 0 18.95 4H5.04a1 1 0 0 0-.79 1.61z" />
          </svg>
          Filters {hasFilters && `(${[type,category,expLevel,remote].filter(Boolean).length})`}
        </button>
      </div>

      {/* Filter panel */}
      {filtersOpen && (
        <div
          style={{
            background: 'var(--md-sys-color-surface-container)',
            border: '1px solid var(--md-sys-color-outline-variant)',
            borderRadius: 'var(--md-sys-shape-corner-medium)',
            padding: 20,
            marginBottom: 24,
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 16,
          }}
        >
          <FilterSelect label="Job type" value={type} onChange={v => { setType(v); setPage(1) }}
            options={JOB_TYPES} />
          <FilterSelect label="Category" value={category} onChange={v => { setCategory(v); setPage(1) }}
            options={CATEGORIES} />
          <FilterSelect label="Experience" value={expLevel} onChange={v => { setExpLevel(v); setPage(1) }}
            options={EXP_LEVELS} />
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 'var(--md-sys-typescale-body-large-size)' }}>
            <input
              type="checkbox"
              checked={remote === 'true'}
              onChange={e => { setRemote(e.target.checked ? 'true' : ''); setPage(1) }}
              style={{ width: 18, height: 18, accentColor: 'var(--md-sys-color-primary)' }}
            />
            Remote only
          </label>
          {hasFilters && (
            <button onClick={clearFilters} style={{ padding: '10px', borderRadius: 'var(--md-sys-shape-corner-small)', border: 'none', background: 'var(--md-sys-color-error-container)', color: 'var(--md-sys-color-on-error-container)', cursor: 'pointer', fontWeight: 500 }}>
              Clear filters
            </button>
          )}
        </div>
      )}

      {/* Results header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <p style={{ margin: 0, color: 'var(--md-sys-color-on-surface-variant)', fontSize: 'var(--md-sys-typescale-body-medium-size)' }}>
          {loading ? 'Searching…' : `${total.toLocaleString()} job${total !== 1 ? 's' : ''} found`}
        </p>
        {hasFilters && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {[q && { label: `"${q}"`, clear: () => setQ('') }, type && { label: type, clear: () => setType('') }, category && { label: category, clear: () => setCategory('') }, expLevel && { label: expLevel, clear: () => setExpLevel('') }, remote && { label: 'Remote', clear: () => setRemote('') }]
              .filter(Boolean)
              .map((f: any, i) => (
                <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 10px', borderRadius: 'var(--md-sys-shape-corner-full)', background: 'var(--md-sys-color-secondary-container)', color: 'var(--md-sys-color-on-secondary-container)', fontSize: 'var(--md-sys-typescale-label-medium-size)' }}>
                  {f.label}
                  <button onClick={f.clear} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', padding: 0, lineHeight: 1 }}>×</button>
                </span>
              ))}
          </div>
        )}
      </div>

      {/* Grid */}
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 64 }}>
          <Spinner size={40} color="var(--md-sys-color-primary)" />
        </div>
      ) : jobs.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '64px 16px' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔍</div>
          <h3 style={{ margin: '0 0 8px' }}>No jobs found</h3>
          <p style={{ color: 'var(--md-sys-color-on-surface-variant)', marginBottom: 24 }}>Try adjusting your search or filters.</p>
          <Button onClick={clearFilters} variant="tonal">Clear all filters</Button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
          {jobs.map(job => <JobCard key={job._id} job={job} />)}
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && !loading && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 40, flexWrap: 'wrap' }}>
          <Button variant="outlined" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
            ← Prev
          </Button>
          {Array.from({ length: Math.min(7, pages) }, (_, i) => {
            const pg = i + 1
            return (
              <button
                key={pg}
                onClick={() => setPage(pg)}
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 'var(--md-sys-shape-corner-full)',
                  border: 'none',
                  background: pg === page ? 'var(--md-sys-color-primary)' : 'var(--md-sys-color-surface-container)',
                  color: pg === page ? 'var(--md-sys-color-on-primary)' : 'var(--md-sys-color-on-surface)',
                  fontWeight: pg === page ? 700 : 400,
                  cursor: 'pointer',
                  fontSize: 'var(--md-sys-typescale-body-large-size)',
                }}
              >
                {pg}
              </button>
            )
          })}
          <Button variant="outlined" onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}>
            Next →
          </Button>
        </div>
      )}
    </PageContainer>
  )
}

function FilterSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 'var(--md-sys-typescale-label-medium-size)', fontWeight: 500, color: 'var(--md-sys-color-on-surface-variant)' }}>{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        style={{ padding: '10px 12px', borderRadius: 'var(--md-sys-shape-corner-small)', border: '1px solid var(--md-sys-color-outline)', background: 'var(--md-sys-color-surface-container-lowest)', color: 'var(--md-sys-color-on-surface)', fontSize: 'var(--md-sys-typescale-body-medium-size)', cursor: 'pointer' }}
      >
        <option value="">All {label}s</option>
        {options.map(o => <option key={o} value={o}>{o.charAt(0).toUpperCase() + o.slice(1)}</option>)}
      </select>
    </div>
  )
}

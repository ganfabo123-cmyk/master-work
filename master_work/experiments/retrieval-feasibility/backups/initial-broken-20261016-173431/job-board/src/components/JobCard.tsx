import { Link } from '@tanstack/react-router'

interface Job {
  _id: string
  title: string
  companyName: string
  companyLogo?: string
  location: string
  type: string
  remote: boolean
  salaryMin?: number
  salaryMax?: number
  salaryCurrency?: string
  salaryPeriod?: string
  experienceLevel: string
  category: string
  featured: boolean
  createdAt: string
  skills?: string[]
}

const TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  'full-time': { bg: 'var(--md-sys-color-primary-container)', text: 'var(--md-sys-color-on-primary-container)' },
  'part-time': { bg: 'var(--md-sys-color-secondary-container)', text: 'var(--md-sys-color-on-secondary-container)' },
  contract: { bg: 'var(--md-sys-color-tertiary-container)', text: 'var(--md-sys-color-on-tertiary-container)' },
  internship: { bg: 'var(--md-sys-color-surface-container-high)', text: 'var(--md-sys-color-on-surface)' },
  freelance: { bg: 'var(--md-sys-color-surface-container-highest)', text: 'var(--md-sys-color-on-surface)' },
}

function formatSalary(min?: number, max?: number, currency = 'USD', period = 'yearly') {
  if (!min && !max) return null
  const fmt = (n: number) =>
    n >= 1000 ? `${(n / 1000).toFixed(0)}k` : String(n)
  const range = min && max ? `${fmt(min)}–${fmt(max)}` : min ? `${fmt(min)}+` : `up to ${fmt(max!)}`
  const periodLabel = period === 'yearly' ? '/yr' : period === 'monthly' ? '/mo' : '/hr'
  return `${currency} ${range}${periodLabel}`
}

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  return `${Math.floor(days / 30)}mo ago`
}

export function JobCard({ job }: { job: Job }) {
  const typeStyle = TYPE_COLORS[job.type] ?? TYPE_COLORS['full-time']
  const salary = formatSalary(job.salaryMin, job.salaryMax, job.salaryCurrency, job.salaryPeriod)

  return (
    <Link
      to="/jobs/$id"
      params={{ id: job._id }}
      style={{ textDecoration: 'none', display: 'block' }}
    >
      <article
        style={{
          background: 'var(--md-sys-color-surface-container-low)',
          border: job.featured
            ? '2px solid var(--md-sys-color-primary)'
            : '1px solid var(--md-sys-color-outline-variant)',
          borderRadius: 'var(--md-sys-shape-corner-medium)',
          padding: '20px',
          transition: 'box-shadow 200ms var(--md-sys-motion-easing-standard), transform 200ms var(--md-sys-motion-easing-standard)',
          cursor: 'pointer',
          position: 'relative',
        }}
        onMouseEnter={e => {
          const el = e.currentTarget as HTMLElement
          el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)'
          el.style.transform = 'translateY(-2px)'
        }}
        onMouseLeave={e => {
          const el = e.currentTarget as HTMLElement
          el.style.boxShadow = ''
          el.style.transform = ''
        }}
      >
        {job.featured && (
          <span
            style={{
              position: 'absolute',
              top: 12,
              right: 12,
              background: 'var(--md-sys-color-primary)',
              color: 'var(--md-sys-color-on-primary)',
              fontSize: 'var(--md-sys-typescale-label-small-size)',
              fontWeight: 600,
              padding: '2px 8px',
              borderRadius: 'var(--md-sys-shape-corner-full)',
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
            }}
          >
            Featured
          </span>
        )}

        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          {job.companyLogo ? (
            <img
              src={job.companyLogo}
              alt={job.companyName}
              style={{ width: 48, height: 48, borderRadius: 'var(--md-sys-shape-corner-small)', objectFit: 'cover', flexShrink: 0 }}
            />
          ) : (
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 'var(--md-sys-shape-corner-small)',
                background: 'var(--md-sys-color-primary-container)',
                color: 'var(--md-sys-color-on-primary-container)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 20,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              {job.companyName[0]?.toUpperCase()}
            </div>
          )}

          <div style={{ flex: 1, minWidth: 0 }}>
            <h3
              style={{
                margin: 0,
                fontSize: 'var(--md-sys-typescale-title-medium-size)',
                fontWeight: 'var(--md-sys-typescale-title-medium-weight)',
                color: 'var(--md-sys-color-on-surface)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {job.title}
            </h3>
            <p
              style={{
                margin: '2px 0 0',
                fontSize: 'var(--md-sys-typescale-body-medium-size)',
                color: 'var(--md-sys-color-on-surface-variant)',
              }}
            >
              {job.companyName}
            </p>
          </div>
        </div>

        <div style={{ marginTop: 12, display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <Chip label={job.location} icon="📍" />
          {job.remote && <Chip label="Remote" icon="🌐" />}
          <span
            style={{
              padding: '2px 10px',
              borderRadius: 'var(--md-sys-shape-corner-full)',
              background: typeStyle.bg,
              color: typeStyle.text,
              fontSize: 'var(--md-sys-typescale-label-medium-size)',
              fontWeight: 600,
              textTransform: 'capitalize',
            }}
          >
            {job.type}
          </span>
          <Chip label={job.experienceLevel} />
        </div>

        {salary && (
          <p
            style={{
              margin: '10px 0 0',
              fontSize: 'var(--md-sys-typescale-title-small-size)',
              fontWeight: 600,
              color: 'var(--md-sys-color-primary)',
            }}
          >
            {salary}
          </p>
        )}

        {job.skills && job.skills.length > 0 && (
          <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {job.skills.slice(0, 4).map(s => (
              <span
                key={s}
                style={{
                  padding: '2px 8px',
                  borderRadius: 'var(--md-sys-shape-corner-extra-small)',
                  background: 'var(--md-sys-color-surface-container)',
                  color: 'var(--md-sys-color-on-surface-variant)',
                  fontSize: 'var(--md-sys-typescale-label-small-size)',
                  border: '1px solid var(--md-sys-color-outline-variant)',
                }}
              >
                {s}
              </span>
            ))}
            {job.skills.length > 4 && (
              <span style={{ fontSize: 'var(--md-sys-typescale-label-small-size)', color: 'var(--md-sys-color-on-surface-variant)', alignSelf: 'center' }}>
                +{job.skills.length - 4}
              </span>
            )}
          </div>
        )}

        <p
          style={{
            margin: '10px 0 0',
            fontSize: 'var(--md-sys-typescale-label-small-size)',
            color: 'var(--md-sys-color-on-surface-variant)',
          }}
        >
          {timeAgo(job.createdAt)}
        </p>
      </article>
    </Link>
  )
}

function Chip({ label, icon }: { label: string; icon?: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 10px',
        borderRadius: 'var(--md-sys-shape-corner-full)',
        border: '1px solid var(--md-sys-color-outline-variant)',
        fontSize: 'var(--md-sys-typescale-label-medium-size)',
        color: 'var(--md-sys-color-on-surface-variant)',
        background: 'var(--md-sys-color-surface-container)',
      }}
    >
      {icon && <span>{icon}</span>}
      {label}
    </span>
  )
}

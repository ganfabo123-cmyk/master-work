import { CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from 'react'

// ── MD3 Button ──────────────────────────────────────────────

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'filled' | 'tonal' | 'outlined' | 'text'
  children: ReactNode
  loading?: boolean
}

export function Button({ variant = 'filled', children, loading, style, disabled, ...props }: ButtonProps) {
  const base: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: '10px 24px',
    borderRadius: 'var(--md-sys-shape-corner-full)',
    fontSize: 'var(--md-sys-typescale-label-large-size)',
    fontWeight: 'var(--md-sys-typescale-label-large-weight)',
    lineHeight: 'var(--md-sys-typescale-label-large-line-height)',
    letterSpacing: '0.00625rem',
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    transition: 'opacity 150ms, background 150ms',
    border: 'none',
    outline: 'none',
    opacity: disabled || loading ? 0.38 : 1,
    whiteSpace: 'nowrap',
    position: 'relative',
  }

  const variants: Record<string, CSSProperties> = {
    filled: {
      background: 'var(--md-sys-color-primary)',
      color: 'var(--md-sys-color-on-primary)',
    },
    tonal: {
      background: 'var(--md-sys-color-secondary-container)',
      color: 'var(--md-sys-color-on-secondary-container)',
    },
    outlined: {
      background: 'transparent',
      color: 'var(--md-sys-color-primary)',
      border: '1px solid var(--md-sys-color-outline)',
    },
    text: {
      background: 'transparent',
      color: 'var(--md-sys-color-primary)',
      padding: '10px 12px',
    },
  }

  return (
    <button {...props} disabled={disabled || loading} style={{ ...base, ...variants[variant], ...style }}>
      {loading ? <Spinner size={16} /> : children}
    </button>
  )
}

// ── MD3 Text Field ──────────────────────────────────────────

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
  helperText?: string
}

export function TextField({ label, error, helperText, id, style, ...props }: TextFieldProps) {
  const inputId = id ?? `field-${label.toLowerCase().replace(/\s+/g, '-')}`
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, ...style as any }}>
      <label
        htmlFor={inputId}
        style={{
          fontSize: 'var(--md-sys-typescale-label-medium-size)',
          fontWeight: 'var(--md-sys-typescale-label-medium-weight)',
          color: error ? 'var(--md-sys-color-error)' : 'var(--md-sys-color-on-surface-variant)',
        }}
      >
        {label}{props.required && ' *'}
      </label>
      <input
        {...props}
        id={inputId}
        style={{
          padding: '12px 16px',
          borderRadius: 'var(--md-sys-shape-corner-small)',
          border: `1px solid ${error ? 'var(--md-sys-color-error)' : 'var(--md-sys-color-outline)'}`,
          background: 'var(--md-sys-color-surface-container-lowest)',
          color: 'var(--md-sys-color-on-surface)',
          fontSize: 'var(--md-sys-typescale-body-large-size)',
          outline: 'none',
          width: '100%',
          transition: 'border-color 150ms',
        }}
        onFocus={e => { e.currentTarget.style.borderColor = error ? 'var(--md-sys-color-error)' : 'var(--md-sys-color-primary)'; e.currentTarget.style.borderWidth = '2px' }}
        onBlur={e => { e.currentTarget.style.borderColor = error ? 'var(--md-sys-color-error)' : 'var(--md-sys-color-outline)'; e.currentTarget.style.borderWidth = '1px' }}
      />
      {(error || helperText) && (
        <span style={{ fontSize: 'var(--md-sys-typescale-label-small-size)', color: error ? 'var(--md-sys-color-error)' : 'var(--md-sys-color-on-surface-variant)' }}>
          {error ?? helperText}
        </span>
      )}
    </div>
  )
}

// ── MD3 Textarea ────────────────────────────────────────────

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
  error?: string
}

export function Textarea({ label, error, id, ...props }: TextareaProps) {
  const inputId = id ?? `field-${label.toLowerCase().replace(/\s+/g, '-')}`
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label
        htmlFor={inputId}
        style={{ fontSize: 'var(--md-sys-typescale-label-medium-size)', fontWeight: 500, color: error ? 'var(--md-sys-color-error)' : 'var(--md-sys-color-on-surface-variant)' }}
      >
        {label}{props.required && ' *'}
      </label>
      <textarea
        {...props}
        id={inputId}
        style={{
          padding: '12px 16px',
          borderRadius: 'var(--md-sys-shape-corner-small)',
          border: `1px solid ${error ? 'var(--md-sys-color-error)' : 'var(--md-sys-color-outline)'}`,
          background: 'var(--md-sys-color-surface-container-lowest)',
          color: 'var(--md-sys-color-on-surface)',
          fontSize: 'var(--md-sys-typescale-body-large-size)',
          outline: 'none',
          width: '100%',
          resize: 'vertical',
          fontFamily: 'inherit',
          minHeight: 100,
        }}
        onFocus={e => { e.currentTarget.style.borderColor = 'var(--md-sys-color-primary)'; e.currentTarget.style.borderWidth = '2px' }}
        onBlur={e => { e.currentTarget.style.borderColor = error ? 'var(--md-sys-color-error)' : 'var(--md-sys-color-outline)'; e.currentTarget.style.borderWidth = '1px' }}
      />
      {error && <span style={{ fontSize: 'var(--md-sys-typescale-label-small-size)', color: 'var(--md-sys-color-error)' }}>{error}</span>}
    </div>
  )
}

// ── MD3 Select ──────────────────────────────────────────────

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  error?: string
  options: { value: string; label: string }[]
}

export function Select({ label, error, options, id, ...props }: SelectProps) {
  const inputId = id ?? `select-${label.toLowerCase().replace(/\s+/g, '-')}`
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label htmlFor={inputId} style={{ fontSize: 'var(--md-sys-typescale-label-medium-size)', fontWeight: 500, color: 'var(--md-sys-color-on-surface-variant)' }}>
        {label}{props.required && ' *'}
      </label>
      <select
        {...props}
        id={inputId}
        style={{
          padding: '12px 16px',
          borderRadius: 'var(--md-sys-shape-corner-small)',
          border: `1px solid ${error ? 'var(--md-sys-color-error)' : 'var(--md-sys-color-outline)'}`,
          background: 'var(--md-sys-color-surface-container-lowest)',
          color: 'var(--md-sys-color-on-surface)',
          fontSize: 'var(--md-sys-typescale-body-large-size)',
          outline: 'none',
          width: '100%',
          cursor: 'pointer',
        }}
      >
        <option value="">Select {label}</option>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      {error && <span style={{ fontSize: 'var(--md-sys-typescale-label-small-size)', color: 'var(--md-sys-color-error)' }}>{error}</span>}
    </div>
  )
}

// ── MD3 Card ─────────────────────────────────────────────────

export function Card({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div
      style={{
        background: 'var(--md-sys-color-surface-container-low)',
        border: '1px solid var(--md-sys-color-outline-variant)',
        borderRadius: 'var(--md-sys-shape-corner-medium)',
        padding: 24,
        ...style,
      }}
    >
      {children}
    </div>
  )
}

// ── Spinner ──────────────────────────────────────────────────

export function Spinner({ size = 24, color }: { size?: number; color?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      style={{ animation: 'spin 0.75s linear infinite' }}
      aria-label="Loading"
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <circle cx="12" cy="12" r="10" stroke={color ?? 'currentColor'} strokeWidth="3" strokeOpacity="0.2" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke={color ?? 'currentColor'} strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

// ── Alert ────────────────────────────────────────────────────

export function Alert({ type = 'error', children }: { type?: 'error' | 'success'; children: ReactNode }) {
  const colors = {
    error: { bg: 'var(--md-sys-color-error-container)', text: 'var(--md-sys-color-on-error-container)', border: 'var(--md-sys-color-error)' },
    success: { bg: 'var(--md-sys-color-primary-container)', text: 'var(--md-sys-color-on-primary-container)', border: 'var(--md-sys-color-primary)' },
  }
  const c = colors[type]
  return (
    <div style={{ padding: '12px 16px', borderRadius: 'var(--md-sys-shape-corner-small)', background: c.bg, color: c.text, borderLeft: `4px solid ${c.border}`, fontSize: 'var(--md-sys-typescale-body-medium-size)' }}>
      {children}
    </div>
  )
}

// ── Status Badge ────────────────────────────────────────────

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  pending: { bg: 'var(--md-sys-color-surface-container-high)', text: 'var(--md-sys-color-on-surface-variant)' },
  reviewing: { bg: 'var(--md-sys-color-secondary-container)', text: 'var(--md-sys-color-on-secondary-container)' },
  shortlisted: { bg: 'var(--md-sys-color-tertiary-container)', text: 'var(--md-sys-color-on-tertiary-container)' },
  rejected: { bg: 'var(--md-sys-color-error-container)', text: 'var(--md-sys-color-on-error-container)' },
  hired: { bg: 'var(--md-sys-color-primary-container)', text: 'var(--md-sys-color-on-primary-container)' },
  active: { bg: 'var(--md-sys-color-primary-container)', text: 'var(--md-sys-color-on-primary-container)' },
  closed: { bg: 'var(--md-sys-color-error-container)', text: 'var(--md-sys-color-on-error-container)' },
  draft: { bg: 'var(--md-sys-color-surface-container-highest)', text: 'var(--md-sys-color-on-surface-variant)' },
}

export function StatusBadge({ status }: { status: string }) {
  const c = STATUS_COLORS[status] ?? STATUS_COLORS.pending
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 10px',
      borderRadius: 'var(--md-sys-shape-corner-full)',
      background: c.bg,
      color: c.text,
      fontSize: 'var(--md-sys-typescale-label-medium-size)',
      fontWeight: 600,
      textTransform: 'capitalize',
    }}>
      {status}
    </span>
  )
}

// ── Page layout wrapper ──────────────────────────────────────

export function PageContainer({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '32px 16px', ...style }}>
      {children}
    </div>
  )
}

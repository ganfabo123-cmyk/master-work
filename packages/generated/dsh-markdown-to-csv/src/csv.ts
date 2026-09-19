/**
 * RFC 4180 CSV serialization and download-filename sanitization.
 */

/** The header row plus every data row, one record per CRLF-terminated line. */
export function toCsv(columns: string[], rows: readonly (readonly string[])[]): string {
  const records = [columns, ...rows].map(row => row.map(escapeField).join(','))
  return `${records.join('\r\n')}\r\n`
}

/** The Excel-friendly body served over the download route: BOM + CRLF CSV. */
export function toCsvBody(csv: string): string {
  return `\uFEFF${csv}`
}

function escapeField(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value
}

/**
 * Reduce a user-supplied filename to a safe basename for the
 * Content-Disposition header: strip path separators, control characters, and
 * header-hazardous punctuation, then ensure a `.csv` extension.
 * @param value - The raw filename (may be empty or unsafe).
 * @param fallback - The name used when nothing safe remains.
 * @returns A safe `.csv` basename.
 */
export function sanitizeFilename(value: string, fallback = 'table.csv'): string {
  const cleaned = value
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, '')
    .trim()
  const base = cleaned.length === 0 ? fallback : cleaned
  return base.toLowerCase().endsWith('.csv') ? base : `${base}.csv`
}

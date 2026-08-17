/**
 * Fact-memory records, per-cwd file-path derivation, and Markdown serialization.
 *
 * Fact memory stores stable human/context facts (for example "the user's name
 * is gan") keyed to one absolute working directory. Unlike experience memory,
 * facts are not retrieved on demand: the fact system-prompt section injects
 * every fact for the current cwd automatically.
 *
 * @module @deepseek-ai/dsh-memory/fact
 */

import { createHash } from 'node:crypto'
import { join } from 'node:path'

/** One durable, cwd-scoped fact: a stable key mapped to a stable value. */
export interface FactMemory {
  /** Stable identity of the fact, for example `"user name"`. Keys are trimmed, lowercased, and unique within a cwd. */
  readonly key: string
  /** The fact value, for example `"gan"`. */
  readonly value: string
  /** One Harness-generated ISO timestamp for the fact writer batch. */
  readonly recordedAt: string
}

/**
 * Normalize a model-authored fact key into its durable and lookup form.
 * @param key - raw model-authored or caller-supplied key.
 * @returns trimmed, lowercased value.
 */
export function normalizeFactKey(key: string): string {
  return key.trim().toLowerCase()
}

/**
 * The facts file name for one absolute cwd: a short SHA-256 digest of the path.
 * The digest keeps the host path out of the filename and maps each absolute
 * cwd to one stable, collision-resistant, cross-platform-safe file.
 * @param cwd - absolute session working directory.
 * @returns stable `.md` filename under the facts directory.
 */
export function factFileNameFor(cwd: string): string {
  const digest = createHash('sha256').update(cwd, 'utf8').digest('hex').slice(0, 16)
  return `${digest}.md`
}

/**
 * Resolve the per-cwd facts file inside a facts directory.
 * @param factsDir - absolute directory owning every cwd-scoped fact file.
 * @param cwd - absolute session working directory.
 * @returns the source-of-truth fact file for this cwd.
 */
export function factFileFor(factsDir: string, cwd: string): string {
  return join(factsDir, factFileNameFor(cwd))
}

const RECORD_HEADING = /^#\s+(.+?)\s*$/u

/**
 * Parse a complete per-cwd facts document, rejecting non-canonical records.
 * @param text - UTF-8 Markdown source.
 * @returns parsed facts in file order, with duplicate keys collapsed to the last occurrence.
 */
export function parseFacts(text: string): FactMemory[] {
  if (text.trim().length === 0) return []
  const lines = text.replace(/\r\n/gu, '\n').split('\n')
  const starts: number[] = []
  for (const [index, line] of lines.entries()) {
    if (RECORD_HEADING.test(line)) starts.push(index)
    else if (/^#(?:\s|$)/u.test(line)) throw new Error(`facts file contains an invalid level-one heading at line ${String(index + 1)}`)
  }
  if (starts.length === 0 || starts[0] !== 0) throw new Error('facts file must contain only canonical fact records')

  const facts = new Map<string, FactMemory>()
  for (const [recordIndex, start] of starts.entries()) {
    const end = starts[recordIndex + 1] ?? lines.length
    const key = (RECORD_HEADING.exec(lines[start] ?? '')?.[1] ?? '').trim().toLowerCase()
    if (key.length === 0) throw new Error('facts record has an empty key')

    const block = lines.slice(start + 1, end)
    while (block[0]?.trim() === '') block.shift()
    const value = parseMetadata(block.shift(), 'Value')
    const recordedAt = parseMetadata(block.shift(), 'Recorded At')
    while (block[0]?.trim() === '') block.shift()
    if (block.length > 0) throw new Error(`facts record "${key}" contains unexpected content after its metadata`)
    if (value.length === 0) throw new Error(`facts record "${key}" has an empty value`)
    facts.set(key, { key, value, recordedAt })
  }
  return [...facts.values()]
}

/**
 * Serialize facts with level-one headings as the only record boundaries.
 * @param facts - durable facts in file order.
 * @returns canonical UTF-8 Markdown text.
 */
export function serializeFacts(facts: readonly FactMemory[]): string {
  if (facts.length === 0) return ''
  return facts.map(fact => [
    `# ${fact.key}`,
    '',
    `Value: ${fact.value}`,
    `Recorded At: ${fact.recordedAt}`,
    '',
  ].join('\n')).join('\n\n') + '\n'
}

function parseMetadata(line: string | undefined, name: string): string {
  const prefix = `${name}:`
  if (line === undefined || !line.startsWith(prefix)) throw new Error(`facts record is missing ${name} metadata`)
  return line.slice(prefix.length).trim()
}

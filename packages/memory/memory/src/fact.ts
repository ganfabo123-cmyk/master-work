/**
 * Fact-memory records, per-cwd file-path derivation, and JSON serialization.
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

/** One durable, cwd-scoped fact: a stable title mapped to a stable body. */
export interface FactMemory {
  /** Stable identity of the fact, for example `"user name"`. Titles are trimmed, lowercased, and unique within a cwd. */
  readonly title: string
  /** The fact body, for example `"gan"`. */
  readonly body: string
}

/**
 * Normalize a model-authored fact title into its durable and lookup form.
 * @param title - raw model-authored or caller-supplied title.
 * @returns trimmed, lowercased value.
 */
export function normalizeFactTitle(title: string): string {
  return title.trim().toLowerCase()
}

/**
 * The facts file name for one absolute cwd: a short SHA-256 digest of the path.
 * The digest keeps the host path out of the filename and maps each absolute
 * cwd to one stable, collision-resistant, cross-platform-safe file.
 * @param cwd - absolute session working directory.
 * @returns stable `.json` filename under the facts directory.
 */
export function factFileNameFor(cwd: string): string {
  const digest = createHash('sha256').update(cwd, 'utf8').digest('hex').slice(0, 16)
  return `${digest}.json`
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

/**
 * Parse a complete per-cwd facts document from JSON format.
 * @param text - UTF-8 JSON source.
 * @returns parsed facts in file order.
 * @throws {SyntaxError} if JSON is invalid.
 * @throws {Error} if structure is malformed.
 */
export function parseFactsJson(text: string): FactMemory[] {
  if (text.trim().length === 0) return []
  const data = JSON.parse(text)
  if (!Array.isArray(data)) throw new Error('facts JSON must be an array')
  const facts: FactMemory[] = []
  for (const item of data) {
    if (typeof item !== 'object' || item === null) throw new Error('facts array item must be an object')
    const { title, body } = item as Record<string, unknown>
    if (typeof title !== 'string' || typeof body !== 'string') throw new Error('facts item must have string title and body')
    const normalizedTitle = normalizeFactTitle(title)
    if (normalizedTitle.length === 0) throw new Error('facts record has an empty title')
    if (body.length === 0) throw new Error(`facts record "${normalizedTitle}" has an empty body`)
    facts.push({ title: normalizedTitle, body })
  }
  return facts
}

/**
 * Serialize facts to JSON format.
 * @param facts - durable facts in file order.
 * @returns canonical UTF-8 JSON text.
 */
export function serializeFactsJson(facts: readonly FactMemory[]): string {
  return JSON.stringify(facts, null, 2)
}

/**
 * Parse and serialize the canonical flat Markdown experience store.
 *
 * @module @deepseek-ai/dsh-memory/store/markdown
 */

import { memoryIdNumber, type ExperienceMemory, type MemoryOutcome } from '../memory.ts'

const RECORD_HEADING = /^#\s+(.+?)\s+\{(memory-\d+)\}\s*$/u
const ANY_H1 = /^#(?:\s|$)/mu
const OUTCOMES = new Set<MemoryOutcome>(['success', 'failure', 'mixed', 'unknown'])

/**
 * Parse a complete `memory.md` document, rejecting non-canonical record boundaries.
 * @param text - UTF-8 Markdown source.
 * @returns parsed experience records in file order.
 */
export function parseMemoryMarkdown(text: string): ExperienceMemory[] {
  if (text.trim().length === 0) return []
  const lines = text.replace(/\r\n/gu, '\n').split('\n')
  const starts: number[] = []
  for (const [index, line] of lines.entries()) {
    if (RECORD_HEADING.test(line)) starts.push(index)
    else if (/^#(?:\s|$)/u.test(line)) throw new Error(`memory.md contains an invalid level-one heading at line ${String(index + 1)}`)
  }
  if (starts.length === 0 || starts[0] !== 0) throw new Error('memory.md must contain only canonical experience records')

  const records: ExperienceMemory[] = []
  const ids = new Set<string>()
  for (const [recordIndex, start] of starts.entries()) {
    const end = starts[recordIndex + 1] ?? lines.length
    const heading = RECORD_HEADING.exec(lines[start] ?? '')
    if (heading?.[1] === undefined || heading[2] === undefined) throw new Error('invalid memory record heading')
    const id = heading[2]
    if (ids.has(id)) throw new Error(`memory.md contains duplicate id "${id}"`)
    ids.add(id)

    const block = lines.slice(start + 1, end)
    while (block[0]?.trim() === '') block.shift()
    const keywords = parseMetadata(block.shift(), 'Keywords').split(',').map(value => value.trim()).filter(Boolean)
    const recordedAt = parseMetadata(block.shift(), 'Recorded At')
    const outcomeText = parseMetadata(block.shift(), 'Outcome')
    if (!OUTCOMES.has(outcomeText as MemoryOutcome)) throw new Error(`memory.md contains invalid outcome "${outcomeText}"`)
    while (block[0]?.trim() === '') block.shift()
    while (block.at(-1)?.trim() === '') block.pop()
    const body = block.join('\n')
    if (body.trim().length === 0) throw new Error(`memory.md experience "${id}" has an empty body`)
    if (ANY_H1.test(body)) throw new Error(`memory.md experience "${id}" contains a level-one heading`)
    records.push({ id, title: heading[1].trim(), keywords, recordedAt, outcome: outcomeText as MemoryOutcome, body })
  }
  return records
}

/**
 * Serialize experiences with level-one headings as the only record boundaries.
 * @param memories - durable experiences in file order.
 * @returns canonical UTF-8 Markdown text.
 */
export function serializeMemoryMarkdown(memories: readonly ExperienceMemory[]): string {
  if (memories.length === 0) return ''
  return memories.map(memory => [
    `# ${memory.title} {${memory.id}}`,
    '',
    `Keywords: ${memory.keywords.join(', ')}`,
    `Recorded At: ${memory.recordedAt}`,
    `Outcome: ${memory.outcome}`,
    '',
    memory.body.trim(),
  ].join('\n')).join('\n\n') + '\n'
}

/**
 * Return the greatest numeric id in a parsed store.
 * @param memories - parsed durable experiences.
 * @returns greatest `memory-N` numeric suffix, or zero for an empty store.
 */
export function maxMemoryId(memories: readonly ExperienceMemory[]): number {
  return memories.reduce((maximum, memory) => Math.max(maximum, memoryIdNumber(memory.id)), 0)
}

function parseMetadata(line: string | undefined, name: string): string {
  const prefix = `${name}:`
  if (line === undefined || !line.startsWith(prefix)) throw new Error(`memory.md record is missing ${name} metadata`)
  const value = line.slice(prefix.length).trim()
  if (value.length === 0 && name !== 'Keywords') throw new Error(`memory.md record has empty ${name} metadata`)
  return value
}

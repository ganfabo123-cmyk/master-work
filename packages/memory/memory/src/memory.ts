/**
 * Experience-memory records and shared keyword normalization.
 *
 * @module @deepseek-ai/dsh-memory/memory
 */

/** Stable identity prefix for every stored experience. */
export const MEMORY_ID_PREFIX = 'memory'

/** The result of the task attempt captured by an experience. */
export type MemoryOutcome = 'success' | 'failure' | 'mixed' | 'unknown'

/** One durable, independently reusable task experience. */
export interface ExperienceMemory {
  readonly id: string
  readonly title: string
  readonly keywords: readonly string[]
  readonly recordedAt: string
  readonly outcome: MemoryOutcome
  readonly body: string
}

/** Model-authored fields accepted before operational metadata is assigned. */
export interface NewExperienceMemory {
  readonly title: string
  readonly keywords: readonly string[]
  readonly outcome?: MemoryOutcome
  readonly body: string
}

/** Lightweight document exposed to retrieval implementations. */
export interface MemorySearchDocument {
  readonly id: string
  readonly title: string
  readonly keywords: readonly string[]
  readonly outcome: MemoryOutcome
  readonly position: number
}

/**
 * Normalize model-authored keywords into their durable and query form.
 * @param keywords - raw model-authored or stored keyword values.
 * @returns trimmed, lowercase, non-empty values without duplicates.
 */
export function normalizeKeywords(keywords: readonly string[]): string[] {
  const normalized = keywords.map(keyword => keyword.trim().toLowerCase()).filter(keyword => keyword.length > 0)
  return [...new Set(normalized)]
}

/**
 * Extract the monotonic numeric suffix from a valid memory id.
 * @param id - candidate `memory-N` identity.
 * @returns the numeric suffix, or zero for an invalid identity.
 */
export function memoryIdNumber(id: string): number {
  const match = /^memory-(\d+)$/u.exec(id)
  return match?.[1] === undefined ? 0 : Number(match[1])
}

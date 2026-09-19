/**
 * Memory plugin persistence configuration.
 *
 * @module @deepseek-ai/dsh-memory/config
 */

import z from '@deepseek-ai/schemastery'
import { dshHomePath } from '@deepseek-ai/dsh-home-paths'

/** Default directory owning block-scoped experience-memory files. */
export const DEFAULT_MEMORY_DIR = dshHomePath('memory')

/** Legacy global experience file migrated into the default memory directory. */
export const DEFAULT_LEGACY_MEMORY_FILE = dshHomePath('memory.md')

/** Default directory owning every cwd-scoped fact file under the shared DSH home. */
export const DEFAULT_FACTS_DIR = dshHomePath('memory-facts')

/** Default cap on facts injected per cwd; the cheapest non-tunable bound. */
export const DEFAULT_MAX_FACTS = 100

const MAX_FACTS_MAX = 100_000

/** Plugin config for `@deepseek-ai/dsh-memory`. */
export interface Config {
  /** Absolute directory owning block-scoped experience stores. */
  memoryDir?: string
  /** Absolute directory owning per-cwd fact files (auto-injected long-term memory). */
  factsDir?: string
  /** Maximum facts injected into the system prompt per cwd. */
  maxFacts?: number
}

/** Runtime schema for loader validation and defaults. */
export const Config: z<Config> = z.object({
  memoryDir: z.string().default(DEFAULT_MEMORY_DIR),
  factsDir: z.string().default(DEFAULT_FACTS_DIR),
  maxFacts: z.number().step(1).min(1).max(MAX_FACTS_MAX).default(DEFAULT_MAX_FACTS),
})

/**
 * Validate and default plugin configuration.
 * @param config - Loader-provided plugin configuration.
 * @returns the validated persistence paths and fact budget.
 */
export function resolveConfig(config: Config): ResolvedConfig {
  const memoryDir = config.memoryDir ?? DEFAULT_MEMORY_DIR
  if (memoryDir.trim().length === 0) throw new TypeError('dsh-memory: memoryDir must not be blank')
  const factsDir = config.factsDir ?? DEFAULT_FACTS_DIR
  if (factsDir.trim().length === 0) throw new TypeError('dsh-memory: factsDir must not be blank')
  const maxFacts = config.maxFacts ?? DEFAULT_MAX_FACTS
  if (!Number.isSafeInteger(maxFacts) || maxFacts < 1) throw new TypeError('dsh-memory: maxFacts must be a positive safe integer')
  return { memoryDir, factsDir, maxFacts }
}

/** Resolved config after defaulting and validation. */
export interface ResolvedConfig {
  readonly memoryDir: string
  readonly factsDir: string
  readonly maxFacts: number
}

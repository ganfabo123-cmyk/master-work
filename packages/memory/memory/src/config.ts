/**
 * Memory plugin persistence configuration.
 *
 * @module @deepseek-ai/dsh-memory/config
 */

import z from '@deepseek-ai/schemastery'
import { dshHomePath } from '@deepseek-ai/dsh-home-paths'

/** Default global experience-memory file under the shared DSH home. */
export const DEFAULT_MEMORY_FILE = dshHomePath('memory.md')

/** Default directory owning every cwd-scoped fact file under the shared DSH home. */
export const DEFAULT_FACTS_DIR = dshHomePath('memory-facts')

/** Default cap on facts injected per cwd; the cheapest non-tunable bound. */
export const DEFAULT_MAX_FACTS = 100

const MAX_FACTS_MAX = 100_000

/** Plugin config for `@deepseek-ai/dsh-memory`. */
export interface Config {
  /** Absolute host path to the process-shared experience store. */
  memoryFile?: string
  /** Absolute directory owning per-cwd fact files (auto-injected long-term memory). */
  factsDir?: string
  /** Maximum facts injected into the system prompt per cwd. */
  maxFacts?: number
}

/** Runtime schema for loader validation and defaults. */
export const Config: z<Config> = z.object({
  memoryFile: z.string().default(DEFAULT_MEMORY_FILE),
  factsDir: z.string().default(DEFAULT_FACTS_DIR),
  maxFacts: z.number().step(1).min(1).max(MAX_FACTS_MAX).default(DEFAULT_MAX_FACTS),
})

/**
 * Validate and default plugin configuration.
 * @param config - Loader-provided plugin configuration.
 * @returns the validated persistence paths and fact budget.
 */
export function resolveConfig(config: Config): ResolvedConfig {
  const memoryFile = config.memoryFile ?? DEFAULT_MEMORY_FILE
  if (memoryFile.trim().length === 0) throw new TypeError('dsh-memory: memoryFile must not be blank')
  const factsDir = config.factsDir ?? DEFAULT_FACTS_DIR
  if (factsDir.trim().length === 0) throw new TypeError('dsh-memory: factsDir must not be blank')
  const maxFacts = config.maxFacts ?? DEFAULT_MAX_FACTS
  if (!Number.isSafeInteger(maxFacts) || maxFacts < 1) throw new TypeError('dsh-memory: maxFacts must be a positive safe integer')
  return { memoryFile, factsDir, maxFacts }
}

/** Resolved config after defaulting and validation. */
export interface ResolvedConfig {
  readonly memoryFile: string
  readonly factsDir: string
  readonly maxFacts: number
}

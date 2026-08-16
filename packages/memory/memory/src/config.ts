/**
 * Memory plugin persistence configuration.
 *
 * @module @deepseek-ai/dsh-memory/config
 */

import z from '@deepseek-ai/schemastery'
import { dshHomePath } from '@deepseek-ai/dsh-home-paths'

/** Default global experience-memory file under the shared DSH home. */
export const DEFAULT_MEMORY_FILE = dshHomePath('memory.md')

/** Plugin config for `@deepseek-ai/dsh-memory`. */
export interface Config {
  /** Absolute host path to the process-shared experience store. */
  memoryFile?: string
}

/** Runtime schema for loader validation and defaults. */
export const Config: z<Config> = z.object({
  memoryFile: z.string().default(DEFAULT_MEMORY_FILE),
})

/**
 * Validate and default plugin configuration.
 * @param config - Loader-provided plugin configuration.
 * @returns the validated persistence path.
 */
export function resolveConfig(config: Config): ResolvedConfig {
  const memoryFile = config.memoryFile ?? DEFAULT_MEMORY_FILE
  if (memoryFile.trim().length === 0) throw new TypeError('dsh-memory: memoryFile must not be blank')
  return { memoryFile }
}

/** Resolved config after defaulting and validation. */
export interface ResolvedConfig {
  readonly memoryFile: string
}

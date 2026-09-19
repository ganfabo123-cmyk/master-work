import z from '@deepseek-ai/schemastery'

export interface Config {
  /** How long a generated download link stays valid, in seconds. */
  downloadTtlSeconds?: number
  /** Cap on concurrently stored downloads before oldest-first eviction. */
  maxPendingDownloads?: number
}

export const Config: z<Partial<Config>, Config> = z.object({
  downloadTtlSeconds: z.natural().max(Number.MAX_SAFE_INTEGER).default(3600),
  maxPendingDownloads: z.natural().max(Number.MAX_SAFE_INTEGER).default(128),
})

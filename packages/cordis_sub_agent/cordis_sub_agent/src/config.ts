import z from '@deepseek-ai/schemastery'

export interface Config {
  repoRoot: string
  engineeringTypecheckCommand?: string
  engineeringBuildCommand?: string
  engineeringTestCommand?: string
  engineeringDocSyncCommand?: string
  engineeringTimeoutMs?: number
  acceptanceProvider: string
  acceptanceModel: string

  acceptanceMaxTokens?: number
}

export const Config: z<Config> = z.object({
  repoRoot: z.string()
    .default('.'),

  engineeringTypecheckCommand: z.string(),
  engineeringBuildCommand: z.string(),
  engineeringTestCommand: z.string(),
  engineeringDocSyncCommand: z.string(),
  engineeringTimeoutMs: z.number().min(1),

  acceptanceProvider: z.string()
    .default('opencode'),

  acceptanceModel: z.string()
    .default('deepseek-v4-flash'),

  acceptanceMaxTokens: z.number()
    .min(1),
})

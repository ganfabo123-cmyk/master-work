import z from '@deepseek-ai/schemastery'

export interface Config {
  repoRoot: string
  workspaceRoot: string
  developmentProvider: string

  acceptanceCommand: string
  acceptanceProvider: string
  acceptanceModel: string

  acceptanceMaxTokens?: number
}

export const Config: z<Config> = z.object({
  repoRoot: z.string()
    .default('.'),

  workspaceRoot: z.string()
    .default('./.cordis/worktrees'),

  developmentProvider: z.string()
    .default('spawn'),

  acceptanceCommand: z.string()
    .default('dsh'),

  acceptanceProvider: z.string()
    .default('deepseek-official'),

  acceptanceModel: z.string()
    .default('deepseek-v4-flash'),

  acceptanceMaxTokens: z.number()
    .min(1),
})

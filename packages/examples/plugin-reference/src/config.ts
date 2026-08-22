import z from '@deepseek-ai/schemastery'

export interface Config {
  enabled: boolean
  storagePath: string
  maxNotes: number
}

export const Config: z<Partial<Config>, Config> = z.object({
  enabled: z.boolean().default(true),
  storagePath: z.string().default('./.dsh/reference-notes.json'),
  maxNotes: z.number().min(1).step(1).default(100),
})

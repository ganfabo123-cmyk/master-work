import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import type { Config } from './config.js'
import type { ReferenceNote, ReferenceNoteInput } from './types.js'

export class ReferenceNoteService {
  constructor(private readonly config: Config) {}

  async add(input: ReferenceNoteInput): Promise<ReferenceNote> {
    const notes = await this.load()
    if (notes.length >= this.config.maxNotes) {
      throw new Error(`reference note limit reached: maxNotes=${this.config.maxNotes}`)
    }
    const note: ReferenceNote = {
      id: `note-${Date.now()}-${notes.length + 1}`,
      ...input,
      createdAt: new Date().toISOString(),
    }
    notes.push(note)
    await this.save(notes)
    return note
  }

  async list(tag?: string, limit?: number): Promise<ReferenceNote[]> {
    const notes = await this.load()
    const filtered = tag === undefined ? notes : notes.filter(note => note.tags.includes(tag))
    return limit === undefined ? filtered : filtered.slice(0, limit)
  }

  private async load(): Promise<ReferenceNote[]> {
    try {
      const raw = await readFile(this.config.storagePath, 'utf8')
      const value: unknown = JSON.parse(raw)
      if (!Array.isArray(value)) throw new Error('storage must contain an array')
      return value as ReferenceNote[]
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
      throw new Error(`unable to read reference notes: ${errorMessage(error)}`)
    }
  }

  private async save(notes: ReferenceNote[]): Promise<void> {
    await mkdir(dirname(this.config.storagePath), { recursive: true })
    await writeFile(this.config.storagePath, `${JSON.stringify(notes, null, 2)}\n`, 'utf8')
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

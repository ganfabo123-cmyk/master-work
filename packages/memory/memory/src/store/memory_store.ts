/**
 * Durable append-only memory storage over one host-owned Markdown file.
 *
 * @module @deepseek-ai/dsh-memory/store/memory-store
 */

import { readFile, stat } from 'node:fs/promises'
import { writeFileAtomic } from '@deepseek-ai/dsh-atomic-write'
import type { ExperienceMemory, MemorySearchDocument } from '../memory.ts'
import { maxMemoryId, parseMemoryMarkdown, serializeMemoryMarkdown } from './markdown.ts'

/** Read operations required by retrieval implementations. */
export interface MemorySearchSource {
  /** Return lightweight documents in durable record order. */
  listDocuments(signal?: AbortSignal): Promise<MemorySearchDocument[]>
}

/** Markdown-backed source of truth for experience memories. */
export class MemoryStore implements MemorySearchSource {
  private writeTail: Promise<void> = Promise.resolve()

  constructor(private readonly memoryFile: string) {}

  /**
   * Read every record from the current source-of-truth file.
   * @param signal - operation cancellation.
   * @returns durable experiences in file order.
   */
  async list(signal?: AbortSignal): Promise<ExperienceMemory[]> {
    signal?.throwIfAborted()
    try {
      const info = await stat(this.memoryFile)
      if (!info.isFile()) return []
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
      throw error
    }
    return parseMemoryMarkdown(await readFile(this.memoryFile, { encoding: 'utf8', signal }))
  }

  /**
   * Append records with ids allocated inside one process-wide serialized write operation.
   * @param entries - validated durable fields without ids.
   * @param signal - operation cancellation.
   * @returns appended experiences with assigned ids.
   */
  append(
    entries: readonly Omit<ExperienceMemory, 'id'>[],
    signal?: AbortSignal,
  ): Promise<ExperienceMemory[]> {
    const operation = this.writeTail.then(async () => {
      signal?.throwIfAborted()
      const memories = await this.list(signal)
      let nextId = maxMemoryId(memories) + 1
      const appended = entries.map(entry => ({ ...entry, id: `memory-${String(nextId++)}` }))
      await writeFileAtomic(this.memoryFile, serializeMemoryMarkdown([...memories, ...appended]), { mode: 0o600, dirMode: 0o700 })
      return appended
    })
    this.writeTail = operation.then(() => undefined, () => undefined)
    return operation
  }

  /**
   * Read one complete experience by stable id.
   * @param id - stable `memory-N` identity.
   * @param signal - operation cancellation.
   * @returns the complete experience, or `undefined` when absent.
   */
  async get(id: string, signal?: AbortSignal): Promise<ExperienceMemory | undefined> {
    return (await this.list(signal)).find(memory => memory.id === id)
  }

  /** Return the lightweight retrieval projection of the current file. */
  async listDocuments(signal?: AbortSignal): Promise<MemorySearchDocument[]> {
    return (await this.list(signal)).map((memory, position) => ({
      id: memory.id,
      title: memory.title,
      keywords: memory.keywords,
      outcome: memory.outcome,
      position,
    }))
  }
}

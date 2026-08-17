/**
 * Durable cwd-scoped fact storage over per-cwd Markdown files.
 *
 * Each absolute cwd owns one fact file under the shared facts directory. Writes
 * are serialized per cwd with process-wide tails so concurrent remember/forget
 * calls on the same cwd never lose a fact or tear a file.
 *
 * @module @deepseek-ai/dsh-memory/store/fact-store
 */

import { mkdir, readFile, rm, stat } from 'node:fs/promises'
import { dirname } from 'node:path'
import { writeFileAtomic } from '@deepseek-ai/dsh-atomic-write'
import type { FactMemory } from '../fact.ts'
import { factFileFor, parseFacts, serializeFacts } from '../fact.ts'

/** Read operations required by fact consumers and the injection renderer. */
export interface FactSource {
  /**
   * Read every fact for one cwd in file order.
   * @param cwd - absolute session working directory.
   * @param signal - operation cancellation.
   */
  list(cwd: string, signal?: AbortSignal): Promise<FactMemory[]>
}

/**
 * Markdown-backed source of truth for cwd-scoped facts.
 *
 * The active file is derived per cwd rather than fixed at construction because
 * the session cwd is only known at request time.
 */
export class FactStore implements FactSource {
  private readonly writeTails = new Map<string, Promise<void>>()

  constructor(private readonly factsDir: string) {}

  /**
   * Read every fact for one cwd from its source-of-truth file.
   * @param cwd - absolute session working directory.
   * @param signal - operation cancellation.
   * @returns durable facts in file order.
   */
  async list(cwd: string, signal?: AbortSignal): Promise<FactMemory[]> {
    signal?.throwIfAborted()
    const file = factFileFor(this.factsDir, cwd)
    try {
      const info = await stat(file)
      if (!info.isFile()) return []
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return []
      throw error
    }
    return parseFacts(await readFile(file, { encoding: 'utf8', signal }))
  }

  /**
   * Set one fact for a cwd, upserting by key, then persist the file.
   * @param cwd - absolute session working directory.
   * @param fact - the fact to persist (key/value/recordedAt).
   * @param signal - operation cancellation.
   */
  async set(cwd: string, fact: FactMemory, signal?: AbortSignal): Promise<void> {
    await this.mutate(cwd, (facts) => {
      const next = facts.filter(existing => existing.key !== fact.key)
      next.push(fact)
      return next
    }, signal)
  }

  /**
   * Remove one fact by key for a cwd and persist the result.
   * @param cwd - absolute session working directory.
   * @param key - the normalized key to remove.
   * @param signal - operation cancellation.
   * @returns whether a fact with that key was present and removed.
   */
  async remove(cwd: string, key: string, signal?: AbortSignal): Promise<boolean> {
    let removed = false
    await this.mutate(cwd, (facts) => {
      const remaining = facts.filter(existing => existing.key !== key)
      removed = remaining.length !== facts.length
      return remaining
    }, signal)
    return removed
  }

  /**
   * Serialize one update to a cwd's fact file inside its write tail.
   * @param cwd - absolute session working directory.
   * @param update - pure transform of the current facts into the next committed set.
   * @param signal - operation cancellation.
   */
  private async mutate(
    cwd: string,
    update: (facts: FactMemory[]) => FactMemory[],
    signal?: AbortSignal,
  ): Promise<void> {
    const previous = this.writeTails.get(cwd) ?? Promise.resolve()
    const operation = previous.then(async () => {
      signal?.throwIfAborted()
      const file = factFileFor(this.factsDir, cwd)
      await mkdir(dirname(file), { recursive: true, mode: 0o700 })
      const next = update(await this.list(cwd, signal))
      if (next.length === 0) {
        await rm(file, { force: true })
      } else {
        await writeFileAtomic(file, serializeFacts(next), { mode: 0o600, dirMode: 0o700 })
      }
    })
    const tail = operation.then(() => undefined, () => undefined)
    this.writeTails.set(cwd, tail)
    await operation
    if (this.writeTails.get(cwd) === tail) this.writeTails.delete(cwd)
  }
}

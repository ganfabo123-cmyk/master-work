import { describe, expect, it } from 'vitest'
import { mkdtemp, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { Config } from '../src/config.js'
import { ReferenceNoteService } from '../src/service.js'

describe('ReferenceNoteService', () => {
  it('persists, filters, and limits notes', async () => {
    const root = await mkdtemp(join(tmpdir(), 'dsh-plugin-reference-'))
    try {
      const service = new ReferenceNoteService({
        ...Config({}),
        storagePath: join(root, 'notes.json'),
      })
      await service.add({ title: 'First', content: 'one', tags: ['demo'] })
      await service.add({ title: 'Second', content: 'two', tags: ['other'] })
      await expect(service.list('demo', 1)).resolves.toHaveLength(1)
      await expect(service.list(undefined, 1)).resolves.toHaveLength(1)
    } finally {
      await rm(root, { recursive: true, force: true })
    }
  })

  it('treats a missing storage file as empty', async () => {
    const root = await mkdtemp(join(tmpdir(), 'dsh-plugin-reference-'))
    try {
      const service = new ReferenceNoteService({ ...Config({}), storagePath: join(root, 'missing.json') })
      await expect(service.list()).resolves.toEqual([])
    } finally {
      await rm(root, { recursive: true, force: true })
    }
  })
})

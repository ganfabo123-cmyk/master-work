import { afterEach, describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import * as Memory from '@deepseek-ai/dsh-memory'

const contexts: Context[] = []
const roots: string[] = []

afterEach(async () => {
  for (const ctx of contexts.splice(0)) await ctx.fiber.dispose()
  for (const root of roots.splice(0)) await rm(root, { recursive: true, force: true })
})

describe('memory plugin lifecycle', () => {
  it('removes all tools, service, and prompt guidance when its fiber unloads', async () => {
    const root = await mkdtemp(join(tmpdir(), 'dsh-memory-lifecycle-'))
    roots.push(root)
    const ctx = new Context()
    contexts.push(ctx)
    await ctx.plugin(SystemPrompt)
    await ctx.plugin(ToolRuntime)
    const fiber = await ctx.plugin(Memory, { memoryDir: join(root, 'memory') })

    expect(ctx.get('memory')).toBeDefined()
    expect(['memory_search', 'memory_get', 'memory_list_blocks', 'memory_record'].every(name => ctx.tools.get(name) !== undefined)).toBe(true)
    expect((await ctx.systemPrompt.assemble()).sections.some(section => section.name === 'tool:memory')).toBe(true)

    await fiber.dispose()

    expect(ctx.get('memory')).toBeUndefined()
    expect(['memory_search', 'memory_get', 'memory_list_blocks', 'memory_record'].every(name => ctx.tools.get(name) === undefined)).toBe(true)
    expect((await ctx.systemPrompt.assemble()).sections.some(section => section.name === 'tool:memory')).toBe(false)
  })
})

import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { afterEach, describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import Loader from '@deepseek-ai/cordis-plugin-loader'
import Include from '@deepseek-ai/cordis-plugin-include'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import { CallId } from '@deepseek-ai/dsh-llm'
import * as Memory from '@deepseek-ai/dsh-memory'
import { UTF8_BODY } from './fixtures/utf8-experience.ts'

let root: string | undefined
let context: Context | undefined

afterEach(async () => {
  await context?.fiber.dispose()
  context = undefined
  if (root !== undefined) await rm(root, { recursive: true, force: true })
  root = undefined
})

describe('memory real Loader composition through cordis.yml', () => {
  it('assembles block-scoped keyword-memory guidance and three product tools', async () => {
    root = await mkdtemp(join(tmpdir(), 'dsh-memory-loader-'))
    const memoryDir = join(root, 'memory').replace(/\\/gu, '/')
    const configPath = join(root, 'cordis.yml')
    await writeFile(configPath, [
      "- name: '@deepseek-ai/dsh-system-prompt'",
      "- name: '@deepseek-ai/dsh-tools'",
      "- name: '@deepseek-ai/dsh-memory'",
      '  config:',
      `    memoryDir: '${memoryDir}'`,
      '',
    ].join('\n'))

    context = new Context()
    context.baseUrl = pathToFileURL(root).href + '/'
    await context.plugin(Loader)
    context.loader.builtins.include = Include
    const modules = new Map<string, unknown>([
      ['@deepseek-ai/dsh-system-prompt', SystemPrompt],
      ['@deepseek-ai/dsh-tools', ToolRuntime],
      ['@deepseek-ai/dsh-memory', Memory],
    ])
    context.loader.internal = {
      version: 'v2',
      async import(specifier: string) {
        if (!modules.has(specifier)) throw new Error(`unexpected Loader import: ${specifier}`)
        return modules.get(specifier)
      },
    } as unknown as NonNullable<typeof context.loader.internal>
    await context.loader.create({ name: 'cordis:include', config: { path: pathToFileURL(configPath).href } })
    await context.loader.await()

    const assembly = await context.systemPrompt.assemble()
    const guidance = assembly.sections.find(section => section.name === 'tool:memory')?.text ?? ''
    expect(guidance).toMatchInlineSnapshot('"Experience memory is separated into named blocks such as global, python, and dsh. Call memory_list_blocks when you need the current set of blocks, then choose the relevant block_name before every memory_search, memory_get, memory_list, or memory_record call. Generate several specific keywords, call memory_search within one block, judge candidates from their title, keywords, matched keywords, outcome, and current context, then call memory_get with the same block_name only for candidates worth reading. Use memory_list only when the complete contents of one block are needed. Search results are candidates only: presentation order does not guarantee relevance or correctness. Treat loaded memories as past evidence that may be stale, not as truth. Record only reusable lessons with memory_record; do not record routine errors or complete session history."')
    expect(guidance).not.toMatch(/tree|temporary inbox|human confirmation/iu)
    expect(['memory_search', 'memory_get', 'memory_record', 'memory_list_blocks'].map(name => context?.tools.get(name)?.name))
      .toEqual(['memory_search', 'memory_get', 'memory_record', 'memory_list_blocks'])
    for (const toolName of ['memory_search', 'memory_get', 'memory_record']) {
      expect(context.tools.schemas().find(schema => schema.name === toolName)?.parameters.required).toContain('block_name')
    }
    expect(context.tools.get('memory_children')).toBeUndefined()

    const signal = new AbortController().signal
    const blocks = await context.tools.execute({
      name: 'memory_list_blocks', arguments: {}, callId: CallId('loader-memory-list-blocks'), signal,
    })
    expect(textOf(blocks)).toBe('No experience memory blocks exist.')
    const recorded = await context.tools.execute({
      name: 'memory_record',
      arguments: { block_name: 'dsh', entries: [{ title: 'Loader UTF-8', keywords: ['encoding', 'typescript'], body: UTF8_BODY }] },
      callId: CallId('loader-memory-record'),
      signal,
    })
    expect(textOf(recorded)).toContain('memory-1')
    await expect(readFile(join(root, 'memory', 'dsh_memory.md'), 'utf8')).resolves.toContain('# Loader UTF-8 {memory-1}')
    const searched = await context.tools.execute({
      name: 'memory_search', arguments: { block_name: 'dsh', keywords: ['encoding'] }, callId: CallId('loader-memory-search'), signal,
    })
    expect(textOf(searched)).toContain('[memory-1]')
    expect(textOf(searched)).not.toContain('DeepSeek Harness 在 Windows')
    const loaded = await context.tools.execute({
      name: 'memory_get', arguments: { block_name: 'dsh', id: 'memory-1' }, callId: CallId('loader-memory-get'), signal,
    })
    expect(textOf(loaded)).toContain('DeepSeek Harness 在 Windows')
  })
})

function textOf(result: Awaited<ReturnType<Context['tools']['execute']>>): string {
  return result.content.map(block => block.type === 'text' ? block.text : '').join('\n')
}

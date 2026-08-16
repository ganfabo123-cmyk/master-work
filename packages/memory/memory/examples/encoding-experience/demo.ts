import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { Context } from '@deepseek-ai/cordis'
import Loader from '@deepseek-ai/cordis-plugin-loader'
import Include from '@deepseek-ai/cordis-plugin-include'
import { CallId } from '@deepseek-ai/dsh-llm'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import * as Memory from '@deepseek-ai/dsh-memory'

const directory = dirname(fileURLToPath(import.meta.url))
const runtimeDirectory = await mkdtemp(join(tmpdir(), 'dsh-memory-demo-'))
const context = new Context()
context.baseUrl = pathToFileURL(runtimeDirectory).href + '/'
await context.plugin(Loader)
context.loader.builtins.include = Include
context.loader.internal = {
  version: 'v2',
  async import(specifier: string) {
    const modules = new Map<string, unknown>([
      ['@deepseek-ai/dsh-system-prompt', SystemPrompt],
      ['@deepseek-ai/dsh-tools', ToolRuntime],
      ['@deepseek-ai/dsh-memory', Memory],
    ])
    if (!modules.has(specifier)) throw new Error(`unexpected Loader import: ${specifier}`)
    return modules.get(specifier)
  },
} as NonNullable<typeof context.loader.internal>

try {
  const memoryPath = join(runtimeDirectory, 'memory.md')
  await writeFile(memoryPath, await readFile(join(directory, 'memory.md'), 'utf8'))
  const config = (await readFile(join(directory, 'cordis.yml'), 'utf8')).replace("'./memory.md'", `'${memoryPath.replace(/\\/gu, '/')}'`)
  const runtimeConfig = join(runtimeDirectory, 'cordis.yml')
  await writeFile(runtimeConfig, config)
  await context.loader.create({ name: 'cordis:include', config: { path: pathToFileURL(runtimeConfig).href } })
  await context.loader.await()

  const signal = new AbortController().signal
  const search = await context.tools.execute({
    name: 'memory_search',
    arguments: { keywords: ['deepseek-harness', 'encoding', 'typescript'] },
    callId: CallId('memory-demo-search'),
    signal,
  })
  console.log('$ memory_search(deepseek-harness, encoding, typescript)')
  console.log(textOf(search))

  const get = await context.tools.execute({
    name: 'memory_get', arguments: { id: 'memory-17' }, callId: CallId('memory-demo-get'), signal,
  })
  console.log('\n$ memory_get(memory-17)')
  console.log(textOf(get))
} finally {
  await context.fiber.dispose()
  await rm(runtimeDirectory, { recursive: true, force: true })
}

function textOf(result: Awaited<ReturnType<Context['tools']['execute']>>): string {
  return result.content.map(block => block.type === 'text' ? block.text : '').join('\n')
}

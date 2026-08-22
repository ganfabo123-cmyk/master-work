import { access, appendFile, mkdtemp, writeFile } from 'node:fs/promises'
import { isAbsolute, join, resolve } from 'node:path'
import { tmpdir } from 'node:os'
import { createInterface } from 'node:readline/promises'
import { stdin as input, stdout as output } from 'node:process'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { loadLayeredEnv } from '@deepseek-ai/dsh-app-boot'
import type { DshInvocation } from './args.ts'

interface HarnessNotification {
  method: string
  params: Record<string, unknown>
}

interface AcceptanceRuntime {
  start(input: {
    taskId: string
    patchPath: string
    repoRoot: string
    provider: string
    model: string
  }): Promise<{ id: string; childSessionId?: string; cwd: string }>
  send(input: {
    acceptanceId: string
    actor: 'user'
    message: string
    onNotification?: (notification: HarnessNotification) => void
  }): Promise<{ response: string }>
  stop(id: string, status: 'stopped' | 'failed'): Promise<unknown>
}

async function createAcceptanceRuntime(): Promise<AcceptanceRuntime> {
  // Keep the CLI launcher independent from the sub-agent package's source tree.
  // The built package is loaded at runtime after the sub-agent build gate.
  const modulePath = fileURLToPath(
    new URL('../../../packages/cordis_sub_agent/cordis_sub_agent/lib/acceptance.js', import.meta.url),
  )
  const module = await import(pathToFileURL(modulePath).href) as {
    AcceptanceService: new () => AcceptanceRuntime
  }
  return new module.AcceptanceService()
}

export async function runAcceptance(invocation: DshInvocation): Promise<void> {
  if (invocation.mode !== 'acceptance') throw new Error('dsh: invalid acceptance invocation')

  // Match web/headless: provider credentials in the project and DSH-home
  // .env layers must be materialized before the child inherits process.env.
  loadLayeredEnv('dsh')

  const logDirectory = await mkdtemp(join(tmpdir(), 'dsh-acceptance-cli-'))
  const logPath = join(logDirectory, 'events.jsonl')
  const log = async (type: string, data: unknown): Promise<void> => {
    await appendFile(logPath, `${JSON.stringify({
      timestamp: new Date().toISOString(),
      type,
      data,
    }, (_key, value: unknown) => typeof value === 'bigint' ? String(value) : value)}\n`, 'utf8')
  }

  await writeFile(logPath, '', 'utf8')
  output.write(`Temporary diagnostic log: ${logPath}\n`)

  const repoRoot = resolve(invocation.repoRoot ?? process.cwd())
  const patchPath = isAbsolute(invocation.patch)
    ? invocation.patch
    : resolve(repoRoot, invocation.patch)
  await access(patchPath)
  await log('launch', {
    argv: process.argv.slice(2),
    repoRoot,
    patchPath,
    provider: invocation.provider ?? 'opencode-go',
    model: invocation.model ?? 'deepseek-v4-flash',
    cwd: process.cwd(),
    environment: Object.fromEntries(
      Object.keys(process.env).sort().map(name => [name, {
        present: process.env[name] !== undefined,
        length: process.env[name]?.length ?? 0,
      }]),
    ),
  })

  const acceptance = await createAcceptanceRuntime()
  const session = await acceptance.start({
    taskId: `cli-${Date.now()}`,
    patchPath,
    repoRoot,
    provider: invocation.provider ?? 'opencode-go',
    model: invocation.model ?? 'deepseek-v4-flash',
  })
  await log('started', session)

  output.write([
    `Acceptance started: ${session.id}`,
    `Child session: ${session.childSessionId ?? '(none)'}`,
    `cwd: ${session.cwd}`,
    'Enter messages; use /exit to stop.',
    '> ',
  ].join('\n'))

  const rl = createInterface({ input, output, terminal: true })
  try {
    while (true) {
      const message = (await rl.question('')).trim()
      if (message === '/exit' || message === '/quit') break
      if (message.length === 0) continue
      await log('input', {
        acceptanceId: session.id,
        childSessionId: session.childSessionId,
        message,
      })
      const result = await acceptance.send({
        acceptanceId: session.id,
        actor: 'user',
        message,
        onNotification: notification => {
          void log('notification', notification)
        },
      })
      await log('response', result)
      output.write(`\n${result.response}\n> `)
    }
    const stopped = await acceptance.stop(session.id, 'stopped')
    await log('stopped', stopped)
    output.write(`\nTemporary diagnostic log: ${logPath}\n`)
  } catch (error) {
    await log('error', error instanceof Error
      ? { name: error.name, message: error.message, stack: error.stack }
      : error)
    await acceptance.stop(session.id, 'failed').catch(() => undefined)
    output.write(`\nTemporary diagnostic log: ${logPath}\n`)
    throw error
  } finally {
    rl.close()
  }
}

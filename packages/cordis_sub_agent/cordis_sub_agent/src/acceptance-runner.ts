#!/usr/bin/env node

/**
 * Package-owned JSON-RPC acceptance host.
 *
 * The web profile owns the runtime capabilities. The caller-owned patch is
 * applied as the final overlay, so acceptance does not maintain a second,
 * incomplete list of plugin dependencies.
 */

import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import {
  boot,
  loadLayeredEnv,
  loadOverlayPatches,
} from '@deepseek-ai/dsh-app-boot'
import { DSH_LAUNCH_ENVIRONMENT_KEY } from '@deepseek-ai/dsh-launch-environment'

const NAME = 'dsh-cordis-sub-agent-acceptance'
const configPath = requiredPath(process.argv[2], 'config')
const overlayPath = requiredPath(process.argv[3], 'patch')
const webPort = requiredPort(process.argv[4])
const repoRoot = resolve(process.cwd())
const installAnchor = resolve(
  repoRoot,
  'packages',
  'examples',
  'jsonrpc-demo',
  'package.json',
)

if (!existsSync(installAnchor)) {
  throw new Error(`${NAME}: cannot find dsh installation manifest: ${installAnchor}`)
}

const environment = loadLayeredEnv('dsh', repoRoot)
const userOverlay = loadOverlayPatches(NAME, overlayPath)

const webServer = resolve(
  repoRoot,
  'packages',
  'host',
  'webserver',
  'lib',
  'index.js',
)

if (!existsSync(webServer)) {
  throw new Error(`${NAME}: cannot find built web server: ${webServer}`)
}

const patches = [
  {
    insert: [
      {
        id: 'acceptance-webserver',
        name: pathToFileURL(webServer).href,
        config: {
          host: '127.0.0.1',
          port: webPort,
        },
      },
    ],
  },
  ...userOverlay,
]

let rootContext: Awaited<ReturnType<typeof boot>> | undefined
let exiting = false

function disposeAndExit(code: number): void {
  if (exiting) return
  exiting = true
  process.exitCode = code
  void rootContext?.fiber.dispose()
}

async function main(): Promise<void> {
  rootContext = await boot(
    NAME,
    configPath,
    patches,
    (ctx) => {
      ctx.provide(DSH_LAUNCH_ENVIRONMENT_KEY, environment)
    },
    pathToFileURL(installAnchor).href,
  )

  process.stdin.on('end', () => disposeAndExit(0))
  process.on('SIGTERM', () => disposeAndExit(0))
  process.on('SIGINT', () => disposeAndExit(130))
}

try {
  await main()
} catch (error) {
  process.stderr.write(`${NAME}: ${formatError(error)}\n`)
  process.exit(1)
}

function requiredPath(value: string | undefined, label: string): string {
  if (value === undefined || value.trim() === '') {
    throw new Error(`${NAME}: missing ${label} path argument`)
  }
  return resolve(value)
}

function requiredPort(value: string | undefined): number {
  if (value === undefined || !/^\d+$/.test(value)) {
    throw new Error(`${NAME}: missing or invalid web port argument`)
  }
  const port = Number(value)
  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new Error(`${NAME}: web port is outside 1..65535: ${value}`)
  }
  return port
}

function formatError(error: unknown): string {
  if (error instanceof AggregateError) {
    return [
      error.stack ?? error.message,
      ...error.errors.map(formatError),
    ].join('\n')
  }
  if (error instanceof Error) {
    const own = error.stack ?? error.message
    return error.cause === undefined
      ? own
      : `${own}\nCaused by: ${formatError(error.cause)}`
  }
  return String(error)
}

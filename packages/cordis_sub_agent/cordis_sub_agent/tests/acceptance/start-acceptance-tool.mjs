#!/usr/bin/env node

import assert from 'node:assert/strict'
import { createServer } from 'node:net'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { Context } from '@deepseek-ai/cordis'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import SystemPrompt from '../../../../core/system-prompt/lib/index.js'

import { AcceptanceService } from '../../lib/services/acceptance-service.js'
import { sendAcceptanceMessageTool } from '../../lib/tools/send-acceptance-message.js'
import { startAcceptanceTool } from '../../lib/tools/start-acceptance.js'
import { stopAcceptanceTool } from '../../lib/tools/stop-acceptance.js'

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const repoRoot = resolve(packageRoot, '../../..')
const patch = resolve(repoRoot, 'packages/generated/dsh-markdown-to-csv/cordis.yml')
const provider = process.env.ACCEPTANCE_PROVIDER ?? 'opencode-go'
const model = process.env.ACCEPTANCE_MODEL ?? 'deepseek-v4-flash'
const nonce = `acceptance-${Date.now()}`

await verifyRealMultiTurnAndPortFallback()
await verifyStartupTimeoutInterruptsChild()
console.log('PASS: start_acceptance multi-turn, plugin discovery, port fallback, and timeout interruption')

async function verifyRealMultiTurnAndPortFallback() {
  const occupied = createServer()
  await listen(occupied, 3079)

  const service = new AcceptanceService()
  const harness = await toolHarness(service)
  let acceptanceId

  try {
    const started = await execute(harness.ctx, 'start_acceptance', { patch })
    acceptanceId = started.acceptance_id
    assert.equal(started.web_port, 3078, '3079 is occupied, so acceptance must use 3078')

    const first = await execute(harness.ctx, 'send_acceptance_message', {
      acceptance_id: acceptanceId,
      actor: 'user',
      message: `Remember the exact nonce ${nonce}. Tell me whether you have a Markdown-table-to-CSV tool; if yes, reply with only the nonce and its exact tool name. Do not call the tool.`,
    })
    assert.match(first.response, new RegExp(escapeRegExp(nonce), 'i'))
    assert.match(first.response, /markdown_to_csv/i)

    const second = await execute(harness.ctx, 'send_acceptance_message', {
      acceptance_id: acceptanceId,
      actor: 'user',
      message: 'What were the nonce and exact Markdown-to-CSV tool name from the previous turn? Reply with only those two values and do not call the tool.',
    })
    assert.match(second.response, new RegExp(escapeRegExp(nonce), 'i'))
    assert.match(second.response, /markdown_to_csv/i)

    await execute(harness.ctx, 'stop_acceptance', { acceptance_id: acceptanceId })
    acceptanceId = undefined
  } finally {
    if (acceptanceId !== undefined) {
      await service.stop(acceptanceId).catch(() => {})
    }
    await harness.dispose()
    await close(occupied)
  }
}

async function verifyStartupTimeoutInterruptsChild() {
  const runtimeBin = resolve(packageRoot, 'tests/acceptance/hanging-acceptance-runner.mjs')
  const service = new AcceptanceService({
    runtimeBin,
    startupTimeoutMs: 60_000,
    startingWebPort: 3067,
  })
  const harness = await toolHarness(service)
  const startedAt = Date.now()

  try {
    const result = await harness.ctx.tools.execute({
      name: 'start_acceptance',
      arguments: { patch },
      callId: 'acceptance-timeout',
      signal: new AbortController().signal,
    })
    const elapsed = Date.now() - startedAt
    assert.equal(result.isError, true, 'hanging initialize must fail')
    assert.ok(elapsed >= 59_000 && elapsed < 75_000, `timeout elapsed ${elapsed}ms, expected about 60000ms`)
    assert.match(textOf(result), /initialize timed out after 60000ms/i)

    const probe = createServer()
    try {
      await listen(probe, 3067)
    } finally {
      await close(probe)
    }
  } finally {
    await harness.dispose()
  }
}

async function toolHarness(service) {
  const ctx = new Context()
  await ctx.plugin(SystemPrompt)
  await ctx.plugin(ToolRuntime)
  const disposers = [
    ctx.tools.register(startAcceptanceTool(service, { repoRoot, provider, model })),
    ctx.tools.register(sendAcceptanceMessageTool(service)),
    ctx.tools.register(stopAcceptanceTool(service)),
  ]
  return {
    ctx,
    async dispose() {
      for (const dispose of disposers.reverse()) dispose()
      await service.dispose()
      await ctx.fiber.dispose()
    },
  }
}

async function execute(ctx, name, arguments_) {
  const result = await ctx.tools.execute({
    name,
    arguments: arguments_,
    callId: `${name}-${Date.now()}`,
    signal: new AbortController().signal,
  })
  assert.equal(result.isError, false, `${name} failed: ${textOf(result)}`)
  assert.notEqual(result.value, undefined, `${name} returned no canonical value`)
  return result.value
}

function textOf(result) {
  return result.content.map(block => block.type === 'text' ? block.text : '').join('\n')
}

function listen(server, port) {
  return new Promise((resolvePromise, reject) => {
    server.once('error', reject)
    server.listen(port, '127.0.0.1', resolvePromise)
  })
}

function close(server) {
  return new Promise((resolvePromise, reject) => {
    server.close(error => error === undefined ? resolvePromise() : reject(error))
  })
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

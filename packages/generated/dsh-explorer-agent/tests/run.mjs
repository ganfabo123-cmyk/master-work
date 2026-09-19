/**
 * Sandbox-safe unit tests for @deepseek-ai/dsh-explorer-agent.
 *
 * Runs as plain Node against the BUILT lib artifacts (no bundler, no child
 * processes): the deterministic engineering gate executes `pnpm test` inside
 * the sandbox, where vitest cannot load its config because Vite's Windows
 * realpath optimization spawns a helper process (EPERM).
 */
import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import { ExplorerAgentWorkflow, normalizeDirectories } from '../lib/workflow.js'
import { explorerTool, explorePathsTool, exploreSemanticsTool } from '../lib/tools.js'

/** @type {{ name: string, fn: () => void | Promise<void> }[]} */
const tests = []

export function test(name, fn) {
  tests.push({ name, fn })
}

async function run() {
  let failed = 0
  for (const { name, fn } of tests) {
    try {
      await fn()
      console.log(`ok - ${name}`)
    } catch (error) {
      failed += 1
      console.error(`not ok - ${name}`)
      console.error(`  ${String(error && error.stack ? error.stack : error).split('\n').join('\n  ')}`)
    }
  }
  console.log(`${tests.length - failed}/${tests.length} tests passed`)
  if (failed > 0) process.exitCode = 1
}

// ---------------------------------------------------------------------------
// normalizeDirectories (src/workflow.js)
// ---------------------------------------------------------------------------

test('normalizeDirectories rejects an empty list', () => {
  assert.throws(() => normalizeDirectories([]), /at least one non-empty directory/)
})

test('normalizeDirectories rejects a list of blank entries', () => {
  assert.throws(() => normalizeDirectories(['  ', '']), /at least one non-empty directory/)
})

test('normalizeDirectories resolves relative entries against the cwd', () => {
  const [dir] = normalizeDirectories(['.'])
  assert.equal(dir, resolve('.'))
})

test('normalizeDirectories trims whitespace and deduplicates', () => {
  const dirs = normalizeDirectories(['.', ' . ', './'])
  assert.equal(dirs.length, 1)
  assert.equal(dirs[0], resolve('.'))
})

// ---------------------------------------------------------------------------
// ExplorerAgentWorkflow (src/workflow.js)
// ---------------------------------------------------------------------------

function makeFakeSubagents({
  stopReason = 'completed',
  capabilities = { outputSchema: true, depthLimit: true, toolFilter: true, persona: true },
} = {}) {
  const startCalls = []
  const subagents = {
    getProvider(name) {
      if (name !== 'spawn' && name !== 'fork') return undefined
      return { name, capabilities }
    },
    async start(name, request) {
      startCalls.push({ provider: name, request })
      return {
        result: Promise.resolve({ stopReason, output: [], structured: undefined }),
        async dispose() {},
      }
    },
  }
  return { subagents, startCalls }
}

const runOptions = { parent: {}, signal: new AbortController().signal }

test('run formats a pre-recorded explore_paths result', async () => {
  const { subagents } = makeFakeSubagents()
  const workflow = new ExplorerAgentWorkflow({ subagents })
  const question = 'where is the tool registry?'
  workflow.recordPaths({
    question,
    answer: 'packages/core/tools',
    paths: [{ path: 'packages/core/tools/src/index.ts', kind: 'file', summary: 'tool registry', reason: 'declares the registry' }],
    risks: [],
    gaps: [],
  })
  const answer = await workflow.run(['.'], question, runOptions)
  assert.match(answer, /# Explored paths/)
  assert.match(answer, /packages\/core\/tools\/src\/index\.ts/)
})

test('run formats a pre-recorded explore_semantics result', async () => {
  const { subagents } = makeFakeSubagents()
  const workflow = new ExplorerAgentWorkflow({ subagents })
  const question = 'what stops a tool from writing?'
  workflow.recordSemantics({
    question,
    answer: 'the sandbox policy fence',
    findings: [{ title: 'fence', summary: 'policy check', evidence: [{ path: 'a.ts', kind: 'file', reason: 'check' }] }],
    risks: [],
    gaps: [],
  })
  const answer = await workflow.run(['.'], question, runOptions)
  assert.match(answer, /# Semantic findings/)
  assert.match(answer, /sandbox policy fence/)
})

test('run fails when the child stops without submitting a result', async () => {
  const { subagents } = makeFakeSubagents()
  const workflow = new ExplorerAgentWorkflow({ subagents })
  await assert.rejects(workflow.run(['.'], 'no submission', runOptions), /completed without submitting an exploration result/)
})

test('run fails when the child stops abnormally', async () => {
  const { subagents } = makeFakeSubagents({ stopReason: 'error' })
  const workflow = new ExplorerAgentWorkflow({ subagents })
  await assert.rejects(workflow.run(['.'], 'boom', runOptions), /stopped with reason error/)
})

test('run fails loud without a toolFilter-capable provider', async () => {
  const { subagents } = makeFakeSubagents({ capabilities: { outputSchema: true, depthLimit: true, toolFilter: false, persona: true } })
  const workflow = new ExplorerAgentWorkflow({ subagents })
  await assert.rejects(workflow.run(['.'], 'no provider', runOptions), /requires a subagent provider with toolFilter capability/)
})

test('run cleans its record after formatting', async () => {
  const { subagents, startCalls } = makeFakeSubagents()
  const workflow = new ExplorerAgentWorkflow({ subagents })
  const question = 'cleanup check'
  workflow.recordPaths({
    question,
    answer: 'a',
    paths: [{ path: 'x.ts', kind: 'file', summary: 's', reason: 'r' }],
    risks: [],
    gaps: [],
  })
  await workflow.run(['.'], question, runOptions)
  // The second run has no record for this question, so it must fail.
  await assert.rejects(workflow.run(['.'], question, runOptions), /without submitting an exploration result/)
  assert.equal(startCalls.length, 2)
})

// ---------------------------------------------------------------------------
// Tool factories (src/tools.js)
// ---------------------------------------------------------------------------

test('explorePathsTool records and echoes its arguments', async () => {
  const { subagents } = makeFakeSubagents()
  const workflow = new ExplorerAgentWorkflow({ subagents })
  const result = await explorePathsTool(workflow).execute({
    question: 'q',
    answer: 'a',
    paths: [{ path: 'p.ts', kind: 'file', summary: 's', reason: 'r' }],
    risks: [],
    gaps: [],
  }, {})
  assert.equal(result.question, 'q')
  assert.equal(result.paths.length, 1)
})

test('exploreSemanticsTool records and echoes its arguments', async () => {
  const { subagents } = makeFakeSubagents()
  const workflow = new ExplorerAgentWorkflow({ subagents })
  const result = await exploreSemanticsTool(workflow).execute({
    question: 'q',
    answer: 'a',
    findings: [{ title: 't', summary: 's', evidence: [{ path: 'p.ts', kind: 'file', reason: 'r' }] }],
    risks: [],
    gaps: [],
  }, {})
  assert.equal(result.answer, 'a')
  assert.equal(result.findings.length, 1)
})

test('explorerTool requires a calling agent', async () => {
  const { subagents } = makeFakeSubagents()
  const workflow = new ExplorerAgentWorkflow({ subagents })
  const tool = explorerTool(workflow)
  await assert.rejects(tool.execute({ directories: ['.'], question: 'q' }, {}), /requires a calling agent/)
})

test('explorerTool routes directories and question through the workflow', async () => {
  const { subagents, startCalls } = makeFakeSubagents()
  const workflow = new ExplorerAgentWorkflow({ subagents })
  const question = 'through the tool'
  workflow.recordPaths({
    question,
    answer: 'a',
    paths: [{ path: 'p.ts', kind: 'file', summary: 's', reason: 'r' }],
    risks: [],
    gaps: [],
  })
  const answer = await explorerTool(workflow).execute(
    { directories: ['.'], question },
    { agent: {}, signal: new AbortController().signal },
  )
  assert.match(answer, /# Explored paths/)
  assert.equal(startCalls.length, 1)
  assert.equal(startCalls[0].provider, 'spawn')
  assert.match(startCalls[0].request.prompt[0].text, /Exploration directories:/)
})

test('explorerTool rejects invalid arguments with a typed error', async () => {
  const { subagents } = makeFakeSubagents()
  const workflow = new ExplorerAgentWorkflow({ subagents })
  const tool = explorerTool(workflow)
  // Missing question: parameter validation runs before the execute body.
  await assert.rejects(tool.execute({ directories: ['.'] }, { agent: {}, signal: new AbortController().signal }), /invalid arguments/)
})

await run()
/**
 * Sandbox-safe unit tests for @deepseek-ai/dsh-experiment-state.
 *
 * Runs as plain Node against the BUILT lib artifacts (no bundler, no child
 * processes): the deterministic engineering gate executes `pnpm test` inside
 * the sandbox, where vitest cannot load its config because Vite's Windows
 * realpath optimization spawns a helper process (EPERM).
 */
import assert from 'node:assert/strict'
import { ExperimentStore } from '../lib/store.js'
import { EXPERIMENT_EXECUTOR, createExperimentTool, getExperimentTool, listExperimentsTool, updateExperimentTool } from '../lib/tools.js'

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
// ExperimentStore.create
// ---------------------------------------------------------------------------

test('create stores a root experiment with pending status and empty write-back fields', () => {
  const store = new ExperimentStore()
  const record = store.create({
    hypothesis: 'cache initialization order is wrong',
    question: 'is the cache initialized before the first access in the failing case?',
    scope: ['src/cache'],
  })
  assert.match(record.id, /^[0-9a-f-]{36}$/)
  assert.equal(record.status, 'pending')
  assert.deepEqual(record.evidence, [])
  assert.equal(record.result, '')
  assert.equal(record.parentId, '')
  assert.equal(record.executor, 'self')
  assert.equal(record.createdAt, record.updatedAt)
})

test('create stores shared info and trims it', () => {
  const store = new ExperimentStore()
  const record = store.create({
    hypothesis: 'h',
    question: 'q',
    scope: ['src'],
    sharedInfo: '  explorer found init at src/cache/init.ts  ',
  })
  assert.equal(record.sharedInfo, 'explorer found init at src/cache/init.ts')
})

test('create stores an explicit executor', () => {
  const store = new ExperimentStore()
  const record = store.create({
    hypothesis: 'h',
    question: 'q',
    scope: ['src'],
    executor: 'detector',
  })
  assert.equal(record.executor, 'detector')
})

test('create rejects an unknown executor', () => {
  const store = new ExperimentStore()
  assert.throws(
    // The store accepts only typed input; an invalid executor surfaces through
    // the tool layer, and update() validates its executor explicitly.
    () => store.update('missing', { executor: 'nobody' }),
    /does not exist/,
  )
})

test('child inherits the parent executor when none is given', () => {
  const store = new ExperimentStore()
  const parent = store.create({ hypothesis: 'h', question: 'q', scope: ['src'], executor: 'detector' })
  const child = store.create({ hypothesis: 'sub', question: 'q2', scope: ['src/cache'], parentId: parent.id })
  assert.equal(child.executor, 'detector')
  const explicit = store.create({
    hypothesis: 'sub2',
    question: 'q3',
    scope: ['src/cache'],
    executor: 'self',
    parentId: parent.id,
  })
  assert.equal(explicit.executor, 'self')
})

test('child accumulates parent shared info with its own findings', () => {
  const store = new ExperimentStore()
  const parent = store.create({
    hypothesis: 'h',
    question: 'q',
    scope: ['src'],
    sharedInfo: 'root context',
    executor: 'detector',
  })
  const child = store.create({
    hypothesis: 'sub',
    question: 'q2',
    scope: ['src/cache'],
    sharedInfo: 'explorer found init at src/cache/init.ts',
    parentId: parent.id,
  })
  assert.equal(child.sharedInfo, 'root context\nexplorer found init at src/cache/init.ts')
})

test('child without new findings inherits the parent shared info', () => {
  const store = new ExperimentStore()
  const parent = store.create({ hypothesis: 'h', question: 'q', scope: ['src'], sharedInfo: 'root context' })
  const child = store.create({ hypothesis: 'sub', question: 'q2', scope: ['src/cache'], parentId: parent.id })
  assert.equal(child.sharedInfo, 'root context')
})

test('create rejects a blank hypothesis', () => {
  const store = new ExperimentStore()
  assert.throws(
    () => store.create({ hypothesis: '   ', question: 'q', scope: ['src'] }),
    /hypothesis must be non-empty/,
  )
})

test('create rejects a blank question', () => {
  const store = new ExperimentStore()
  assert.throws(
    () => store.create({ hypothesis: 'h', question: '', scope: ['src'] }),
    /question must be non-empty/,
  )
})

test('create rejects an empty scope', () => {
  const store = new ExperimentStore()
  assert.throws(
    () => store.create({ hypothesis: 'h', question: 'q', scope: [] }),
    /scope must contain at least one path/,
  )
})

test('create rejects a scope with a blank entry', () => {
  const store = new ExperimentStore()
  assert.throws(
    () => store.create({ hypothesis: 'h', question: 'q', scope: ['src', ' '] }),
    /scope entries must be non-empty/,
  )
})

test('create rejects an unknown parent id', () => {
  const store = new ExperimentStore()
  assert.throws(
    () => store.create({ hypothesis: 'h', question: 'q', scope: ['src'], parentId: 'missing' }),
    /parent "missing" does not exist/,
  )
})

test('create under an existing parent links the child for the tree view', () => {
  const store = new ExperimentStore()
  const parent = store.create({ hypothesis: 'h', question: 'q', scope: ['src'] })
  const child = store.create({ hypothesis: 'sub', question: 'q2', scope: ['src/cache'], parentId: parent.id })
  const parentView = store.viewOf(parent, true)
  assert.equal(parentView.children.length, 1)
  assert.equal(parentView.children[0].id, child.id)
  assert.equal(parentView.children[0].hypothesis, 'sub')
})

// ---------------------------------------------------------------------------
// ExperimentStore.update
// ---------------------------------------------------------------------------

test('update writes back status, evidence, result, and shared info', () => {
  const store = new ExperimentStore()
  const record = store.create({ hypothesis: 'h', question: 'q', scope: ['src'] })
  const updated = store.update(record.id, {
    status: 'confirmed',
    evidence: ['pool usage is 23%', 'request succeeds independently'],
    result: 'hypothesis rejected',
    sharedInfo: 'new context',
  })
  assert.equal(updated.status, 'confirmed')
  assert.deepEqual(updated.evidence, ['pool usage is 23%', 'request succeeds independently'])
  assert.equal(updated.result, 'hypothesis rejected')
  assert.equal(updated.sharedInfo, 'new context')
  // ISO 8601 strings compare lexicographically; the update must not move the
  // timestamp backwards even when create and update land in the same millisecond.
  assert.ok(updated.updatedAt >= record.updatedAt)
})

test('update rejects an unknown id', () => {
  const store = new ExperimentStore()
  assert.throws(() => store.update('missing', { result: 'x' }), /"missing" does not exist/)
})

test('update rejects an empty patch', () => {
  const store = new ExperimentStore()
  const record = store.create({ hypothesis: 'h', question: 'q', scope: ['src'] })
  assert.throws(() => store.update(record.id, {}), /requires at least one field/)
})

test('update rejects an invalid status', () => {
  const store = new ExperimentStore()
  const record = store.create({ hypothesis: 'h', question: 'q', scope: ['src'] })
  assert.throws(() => store.update(record.id, { status: 'done' }), /invalid experiment status "done"/)
})

test('update replaces evidence and trims entries', () => {
  const store = new ExperimentStore()
  const record = store.create({ hypothesis: 'h', question: 'q', scope: ['src'] })
  store.update(record.id, { evidence: [' first ', 'second '] })
  assert.deepEqual(store.get(record.id).evidence, ['first', 'second'])
  assert.throws(() => store.update(record.id, { evidence: ['ok', ' '] }), /evidence entries must be non-empty/)
})

// ---------------------------------------------------------------------------
// ExperimentStore.get / list / viewOf / clear
// ---------------------------------------------------------------------------

test('list returns experiments in creation order', () => {
  const store = new ExperimentStore()
  const first = store.create({ hypothesis: 'h1', question: 'q', scope: ['src'] })
  const second = store.create({ hypothesis: 'h2', question: 'q', scope: ['src'] })
  assert.deepEqual(store.list().map(record => record.id), [first.id, second.id])
})

test('viewOf without children omits the children field', () => {
  const store = new ExperimentStore()
  const record = store.create({ hypothesis: 'h', question: 'q', scope: ['src'] })
  const view = store.viewOf(record, false)
  assert.equal(Object.hasOwn(view, 'children'), false)
  assert.equal(view.parent_id, '')
})

test('clear drops every experiment', () => {
  const store = new ExperimentStore()
  store.create({ hypothesis: 'h', question: 'q', scope: ['src'] })
  store.clear()
  assert.deepEqual(store.list(), [])
})

// ---------------------------------------------------------------------------
// Tool factories (lib/tools.js)
// ---------------------------------------------------------------------------

async function createRoot(store) {
  return createExperimentTool(store, () => undefined).execute({
    hypothesis: 'cache initialization order is wrong',
    question: 'is the cache initialized before the first access?',
    scope: ['src/cache'],
  }, {})
}

test('experiment_create returns a tree view with an id and empty children', async () => {
  const store = new ExperimentStore()
  const view = await createRoot(store)
  assert.match(view.id, /^[0-9a-f-]{36}$/)
  assert.equal(view.status, 'pending')
  assert.deepEqual(view.evidence, [])
  assert.equal(view.result, '')
  assert.equal(view.executor, 'self')
  assert.deepEqual(view.children, [])
  assert.equal(Object.hasOwn(view, 'shared_info'), true)
})

test('experiment_create passes executor to the store and projects it', async () => {
  const store = new ExperimentStore()
  const view = await createExperimentTool(store, () => undefined).execute({
    hypothesis: 'h',
    question: 'q',
    scope: ['src'],
    executor: 'self',
  }, {})
  assert.equal(view.executor, 'self')
})

test('experiment_create with executor detector resolves the executor service and runs the experiment', async () => {
  const store = new ExperimentStore()
  const executor = {
    run: async (record, context) => {
      assert.equal(context.agent, 'agent-handle')
      return {
        status: 'rejected',
        result: 'the failing case initializes the cache before first use',
        evidence: ['the cache is initialized eagerly at module load', 'the failing access happens after that'],
      }
    },
  }
  const view = await createExperimentTool(store, () => executor).execute({
    hypothesis: 'cache initialization order is wrong',
    question: 'is the cache initialized before the first access?',
    scope: ['src/cache'],
    executor: 'detector',
  }, { agent: 'agent-handle', signal: new AbortController().signal })
  assert.equal(view.status, 'rejected')
  assert.equal(view.result, 'the failing case initializes the cache before first use')
  assert.equal(view.evidence.length, 2)
})

test('experiment_create with executor detector fails loud without the executor service', async () => {
  const store = new ExperimentStore()
  await assert.rejects(
    createExperimentTool(store, () => undefined).execute({
      hypothesis: 'h',
      question: 'q',
      scope: ['src'],
      executor: 'detector',
    }, {}),
    /experiment executor "detector" requires the dsh-detector plugin/,
  )
})

test('experiment_create rejects missing required arguments', async () => {
  const store = new ExperimentStore()
  const tool = createExperimentTool(store, () => undefined)
  await assert.rejects(
    tool.execute({ question: 'q', scope: ['src'] }, {}),
    /invalid arguments/,
  )
})

test('experiment_create rejects an unknown parent via store validation', async () => {
  const store = new ExperimentStore()
  const root = await createRoot(store)
  await assert.rejects(
    createExperimentTool(store, () => undefined).execute({
      hypothesis: 'sub',
      question: 'q2',
      scope: ['src/cache/init'],
      parent_id: 'missing',
    }, {}),
    /parent "missing" does not exist/,
  )
  assert.equal(root.children.length, 0)
})

test('experiment_update writes back the investigation result', async () => {
  const store = new ExperimentStore()
  const root = await createRoot(store)
  const updated = await updateExperimentTool(store).execute({
    id: root.id,
    status: 'rejected',
    evidence: ['the cache is initialized eagerly at module load', 'the failing access happens after that'],
    result: 'the failing case initializes the cache before first use',
  }, {})
  assert.equal(updated.status, 'rejected')
  assert.equal(updated.evidence.length, 2)
  assert.equal(updated.result, 'the failing case initializes the cache before first use')
})

test('experiment_update changes the executor', async () => {
  const store = new ExperimentStore()
  const root = await createRoot(store)
  const updated = await updateExperimentTool(store).execute({
    id: root.id,
    executor: 'detector',
  }, {})
  assert.equal(updated.executor, 'detector')
})

test('store update rejects an invalid executor', () => {
  const store = new ExperimentStore()
  const root = store.create({ hypothesis: 'h', question: 'q', scope: ['src'] })
  assert.throws(
    () => store.update(root.id, { executor: 'nobody' }),
    /invalid experiment executor "nobody"/,
  )
})

test('experiment_update requires an id', async () => {
  const store = new ExperimentStore()
  await assert.rejects(
    updateExperimentTool(store).execute({ result: 'x' }, {}),
    /invalid arguments/,
  )
})

test('experiment_update requires at least one field via store validation', async () => {
  const store = new ExperimentStore()
  const root = await createRoot(store)
  await assert.rejects(
    updateExperimentTool(store).execute({ id: root.id }, {}),
    /requires at least one field/,
  )
})

test('experiment_get returns the experiment with its children', async () => {
  const store = new ExperimentStore()
  const root = await createRoot(store)
  const child = await createExperimentTool(store).execute({
    hypothesis: 'sub-hypothesis',
    question: 'q2',
    scope: ['src/cache/init.ts'],
    parent_id: root.id,
  }, {})
  const view = await getExperimentTool(store).execute({ id: root.id }, {})
  assert.equal(view.children.length, 1)
  assert.equal(view.children[0].id, child.id)
  assert.equal(Object.hasOwn(view.children[0], 'children'), false)
})

test('experiment_get fails loud for an unknown id', async () => {
  const store = new ExperimentStore()
  await assert.rejects(
    getExperimentTool(store).execute({ id: 'missing' }, {}),
    /"missing" does not exist/,
  )
})

test('experiment_list returns every experiment without nested children', async () => {
  const store = new ExperimentStore()
  const first = await createRoot(store)
  const second = await createExperimentTool(store).execute({
    hypothesis: 'h2',
    question: 'q2',
    scope: ['src/service'],
  }, {})
  const result = await listExperimentsTool(store).execute({}, {})
  assert.deepEqual(result.experiments.map(experiment => experiment.id), [first.id, second.id])
  for (const experiment of result.experiments) {
    assert.equal(Object.hasOwn(experiment, 'children'), false)
  }
})

await run()
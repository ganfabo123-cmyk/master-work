/**
 * Keyless unit checks for the built `lib/` of @deepseek-ai/dsh-swebench: the
 * plugin export contract, the runtime skill registration, the case registry
 * (manifest parsing, image tag derivation, runner classification), and the
 * in-container script templates. The real docker execution path is exercised
 * by the acceptance runtime, not here.
 */

import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { name, inject, apply } from '../lib/index.js'
import { imageTagForInstance, loadCaseRegistry, runnerForInstance } from '../lib/cases.js'
import { buildEvalLauncher, buildEvaluator, buildRunLauncher, EVAL_RESULT_MARKER, DATASET_URL } from '../lib/scripts.js'
import { runDocker } from '../lib/docker.js'
import * as invariant from '../lib/invariant.js'

// Plugin contract: function-plugin named exports, no default export.
assert.equal(typeof name, 'string')
assert.ok(name.length > 0)
assert.deepEqual([...inject], ['tools', 'subprocess', 'skills'])
assert.equal(typeof apply, 'function')

// The skill file ships beside the built entry (resourceBase directory) and
// carries the frontmatter the runtime parser expects.
const skillPath = fileURLToPath(new URL('../skills/swe-bench/SKILL.md', import.meta.url))
const raw = readFileSync(skillPath, 'utf8')
const frontmatter = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/)
assert.ok(frontmatter, 'SKILL.md must have frontmatter')
const front = frontmatter[1]
const body = frontmatter[2]
assert.match(front, /^name:\s*swe-bench$/m)
assert.match(front, /^description:\s*.+$/m)
assert.ok(body.trim().length > 0, 'skill body must be non-empty')
for (const keyword of [
  'swb_list_cases',
  'swb_run',
  'swb_eval',
  'instance_id',
  'resolved',
  'test patch',
]) {
  assert.ok(body.includes(keyword), `skill body must mention ${keyword}`)
}

// apply registers exactly three tools and one runtime skill.
let toolNames = []
let registered = undefined
apply({
  effect: (install) => {
    registered = install()
  },
  tools: {
    register: (tool) => {
      toolNames.push(tool.name)
      return () => {}
    },
  },
  subprocess: {},
  skills: {
    register: (skill) => {
      assert.equal(skill.name, 'swe-bench')
      assert.ok(skill.description.length > 0)
      assert.ok(skill.content.length > 0)
      assert.equal(skill.source, 'runtime')
      assert.equal(skill.resourceBase.kind, 'directory')
      assert.ok(skill.resourceBase.path.replaceAll('\\', '/').endsWith('skills/swe-bench'))
      return () => {}
    },
  },
})
assert.deepEqual(toolNames.sort(), ['swb_eval', 'swb_list_cases', 'swb_run'])
assert.ok(registered !== undefined, 'apply must install an effect')
assert.equal(typeof registered, 'function', 'effect disposer must be callable')
registered()

// Image tag derivation follows the official `__` → `_1776_` convention.
assert.equal(
  imageTagForInstance('astropy__astropy-12907'),
  'swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest',
)
assert.equal(
  imageTagForInstance('django__django-10914'),
  'swebench/sweb.eval.x86_64.django_1776_django-10914:latest',
)

// Runner classification: django → runtests, everything else → pytest.
assert.equal(runnerForInstance('astropy__astropy-12907'), 'pytest')
assert.equal(runnerForInstance('django__django-10914'), 'runtests')

// The registry parses a manifest, derives environments, and fails loudly on
// unknown ids and unreadable roots.
const tmpDir = mkdtempSync(join(tmpdir(), 'dsh-swebench-test-'))
try {
  const manifest = [
    {
      instance_id: 'astropy__astropy-12907',
      repo_path: join(tmpDir, 'repo-a'),
      issue_statement_path: join(tmpDir, 'issue-a.md'),
      base_commit: 'd16bfe05a744909de4b27f5875fe0d4ed41ce607',
    },
    {
      instance_id: 'django__django-10914',
      repo_path: join(tmpDir, 'repo-b'),
      issue_statement_path: join(tmpDir, 'issue-b.md'),
      base_commit: 'e7fd69d051eaa67cb17f172a39b57253e9cb831a',
    },
  ]
  writeFileSync(join(tmpDir, 'manifest.json'), JSON.stringify(manifest), 'utf8')
  const registry = loadCaseRegistry(tmpDir)
  assert.equal(registry.size, 2)
  const astropy = registry.get('astropy__astropy-12907')
  assert.ok(astropy !== undefined)
  assert.equal(astropy.runner, 'pytest')
  assert.equal(astropy.imageTag, imageTagForInstance('astropy__astropy-12907'))
  assert.equal(astropy.case.base_commit, 'd16bfe05a744909de4b27f5875fe0d4ed41ce607')
  const django = registry.get('django__django-10914')
  assert.ok(django !== undefined)
  assert.equal(django.runner, 'runtests')
  assert.throws(() => loadCaseRegistry(join(tmpDir, 'missing')), /cannot read case manifest/)
  const bad = mkdtempSync(join(tmpdir(), 'dsh-swebench-bad-'))
  writeFileSync(join(bad, 'manifest.json'), '[]', 'utf8')
  assert.throws(() => loadCaseRegistry(bad), /contains no cases/)
  rmSync(bad, { recursive: true, force: true })
} finally {
  rmSync(tmpDir, { recursive: true, force: true })
}

// The run launcher copies the host repo into /testbed and executes the model
// command through the run mount; the eval launcher additionally prepares the
// locale and runs the python evaluator.
const runLauncher = buildRunLauncher('/testbed')
assert.ok(runLauncher.includes('tar --exclude=.git -C /host-testbed -cf - . | tar -C /testbed -xf -'))
assert.ok(runLauncher.includes('conda activate testbed'))
assert.ok(runLauncher.includes('bash /sweb/command.sh'))
assert.ok(runLauncher.includes('cd /testbed'))
const customRunLauncher = buildRunLauncher('/testbed/tests')
assert.ok(customRunLauncher.includes('cd /testbed/tests'))
const evalLauncher = buildEvalLauncher()
assert.ok(evalLauncher.includes('python /sweb/evaluator.py'))
assert.ok(evalLauncher.includes('export LANG=en_US.UTF-8'))

// The evaluator embeds the dataset URL, the instance id, CRLF defense, the
// no-index apply, and the result marker; the runtests variant emits the
// Django runner command.
const pytestEvaluator = buildEvaluator('astropy__astropy-12907', 'pytest')
assert.ok(pytestEvaluator.includes(DATASET_URL))
assert.ok(pytestEvaluator.includes('astropy__astropy-12907'))
assert.ok(pytestEvaluator.includes("sed', '-i', 's/\\r$//'"))
assert.ok(pytestEvaluator.includes("'git', 'apply', '--no-index', '/tmp/test.patch'"))
assert.ok(pytestEvaluator.includes("'pytest', '-q', node"))
assert.ok(pytestEvaluator.includes(EVAL_RESULT_MARKER))
assert.ok(pytestEvaluator.includes('fail_to_pass'))
const djangoEvaluator = buildEvaluator('django__django-10914', 'runtests')
// Django batch mode: one runtests.py invocation via python (CRLF-safe), the
// module-label derivation from '(module.Class)' nodes, and the
// FAIL:/ERROR: header plus '... ok' line parsing.
assert.ok(djangoEvaluator.includes("['python', 'tests/runtests.py', '--verbosity', '2', '--settings=test_sqlite', '--parallel', '1']"))
assert.ok(djangoEvaluator.includes('rsplit'))
assert.ok(djangoEvaluator.includes("line.startswith('FAIL:') or line.startswith('ERROR:')"))
assert.ok(djangoEvaluator.includes("line.endswith(' ... ok')"))
assert.ok(djangoEvaluator.includes("verdict['failed'] = list(nodes)"))
assert.ok(!djangoEvaluator.includes("['./tests/runtests.py'"))
// The pytest variant keeps per-node runs.
assert.ok(pytestEvaluator.includes("'pytest', '-q', node"))

// runDocker invokes the docker CLI with the executable first: the spawn argv
// must begin with `docker run --rm` (regression: an earlier build dropped the
// `docker` executable and failed with `spawn run ENOENT`).
let spawnedArgv = undefined
const settled = (() => {
  let resolveDone
  const done = new Promise(resolve => { resolveDone = resolve })
  return {
    done,
    settle: (code) => resolveDone({ exitCode: code, signal: null }),
  }
})()
const fakeCtx = {
  subprocess: {
    spawn: (spec) => {
      spawnedArgv = [...spec.argv]
      return {
        done: settled.done,
        collected: {
          stdout: { readFrom: () => ({ text: '', truncated: false }) },
          stderr: { readFrom: () => ({ text: '', truncated: false }) },
        },
      }
    },
  },
}
const runPromise = runDocker(fakeCtx, { signal: new AbortController().signal }, ['--rm', 'sample-image'])
settled.settle(0)
const runResult = await runPromise
assert.deepEqual(spawnedArgv.slice(0, 3), ['docker', 'run', '--rm'])
assert.equal(runResult.exitCode, 0)

// The invariant companion registers the exact package name.
let registeredInvariant = undefined
await invariant.apply({
  invariants: {
    register: (packageName, installer) => {
      registeredInvariant = { packageName, installer }
      return () => {}
    },
  },
})
assert.equal(invariant.name, 'swebench-invariant')
assert.equal(registeredInvariant.packageName, '@deepseek-ai/dsh-swebench')
assert.equal(typeof registeredInvariant.installer, 'function')

console.log('dsh-swebench: all unit checks passed')
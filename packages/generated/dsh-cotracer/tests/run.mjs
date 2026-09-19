/**
 * Keyless unit checks for the built `lib/` of @deepseek-ai/dsh-cotracer:
 * the plugin export contract and the runtime skill registration (frontmatter
 * parsing, body loading, and registration shape). The real orchestrated trace
 * path is exercised by the acceptance runtime, not here.
 */

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { name, inject, apply } from '../lib/index.js'
import * as invariant from '../lib/invariant.js'

// Plugin contract: function-plugin named exports, no default export.
assert.equal(typeof name, 'string')
assert.ok(name.length > 0)
assert.deepEqual([...inject], ['skills'])
assert.equal(typeof apply, 'function')

// The skill file ships beside the built entry (resourceBase directory) and
// carries the frontmatter the runtime parser expects.
const skillPath = fileURLToPath(new URL('../skills/dsh-cotracer/SKILL.md', import.meta.url))
const raw = readFileSync(skillPath, 'utf8')
const frontmatter = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/)
assert.ok(frontmatter, 'SKILL.md must have frontmatter')
const front = frontmatter[1]
const body = frontmatter[2]
assert.match(front, /^name:\s*cotracer-trace$/m)
assert.match(front, /^description:\s*.+$/m)
assert.ok(body.trim().length > 0, 'skill body must be non-empty')

// The skill body describes the full trace loop and the executor choice.
for (const keyword of [
  'ask_user_question',
  'explorer',
  'experiment_create',
  'executor',
  'detector',
  'self',
  'experiment_update',
  'experiment_get',
  'experiment_list',
  'shared_info',
  'root cause',
]) {
  assert.ok(body.includes(keyword), `skill body must mention ${keyword}`)
}

// apply registers exactly one runtime skill with the parsed metadata.
let registered = undefined
apply({
  effect: (install) => {
    registered = install()
  },
  skills: {
    register: (skill) => {
      assert.equal(skill.name, 'cotracer-trace')
      assert.ok(skill.description.length > 0)
      assert.ok(skill.content.length > 0)
      assert.equal(skill.source, 'runtime')
      assert.equal(skill.resourceBase.kind, 'directory')
      assert.ok(skill.resourceBase.path.replaceAll('\\', '/').endsWith('skills/dsh-cotracer'))
      return () => {}
    },
  },
})
assert.ok(registered !== undefined, 'apply must install an effect')
assert.equal(typeof registered, 'function', 'effect disposer must be callable')
registered()

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
assert.equal(invariant.name, 'cotracer-invariant')
assert.equal(registeredInvariant.packageName, '@deepseek-ai/dsh-cotracer')
assert.equal(typeof registeredInvariant.installer, 'function')

console.log('dsh-cotracer: all unit checks passed')
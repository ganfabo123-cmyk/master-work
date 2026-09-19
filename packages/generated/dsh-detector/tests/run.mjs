/**
 * Keyless unit checks for the built `lib/` of @deepseek-ai/dsh-detector:
 * the plugin export contract, the registered persona section content, the
 * registered delegate_experiment tool schema, and the experimentExecutor
 * service registration. The real recursive execution path is exercised by the
 * acceptance runtime, not here.
 */

import assert from 'node:assert/strict'
import { name, inject, Config, apply, DELEGATE_TOOL, DETECTOR_PERSONA_TEXT } from '../lib/index.js'
import * as invariant from '../lib/invariant.js'

/** Shared service key; must match @deepseek-ai/dsh-experiment-state's export. */
const EXPERIMENT_EXECUTOR = 'experimentExecutor'

/** Run `apply` against a mock context that records registrations. */
function applyToMock(config = { provider: 'spawn', maxDepth: 3, persona: true }) {
  const sections = []
  const tools = []
  const services = []
  let cleanup = undefined
  const ctx = {
    effect: (install) => {
      cleanup = install()
    },
    provide: (serviceName, value) => {
      services.push({ serviceName, value })
      return () => {}
    },
    systemPrompt: {
      section: (section) => {
        sections.push(section)
        return () => {}
      },
    },
    tools: {
      register: (definition) => {
        tools.push(definition)
        return () => {}
      },
    },
  }
  apply(ctx, config)
  return { sections, tools, services, dispose: () => cleanup() }
}

// Plugin contract: function-plugin named exports, no default export.
assert.equal(typeof name, 'string')
assert.ok(name.length > 0)
assert.deepEqual([...inject], ['tools', 'subagents', 'systemPrompt'])
assert.equal(typeof Config, 'function')
assert.equal(typeof apply, 'function')
assert.equal(DELEGATE_TOOL, 'delegate_experiment')

// The persona section registers as the order-0 persona slot and carries the
// experiment-structure contract the Detector works from.
const { sections, tools, services, dispose } = applyToMock()
assert.equal(sections.length, 1)
const section = sections[0]
assert.equal(section.name, 'detector:persona')
assert.equal(section.order, 0)
for (const keyword of [
  'experiment_id',
  'hypothesis',
  'question',
  'scope',
  'shared_info',
  'executor',
  'explorer',
  'experiment_update',
  'experiment_create',
  'structured_output',
  'confirmed',
  'rejected',
  'completed',
]) {
  assert.ok(section.text.includes(keyword), `persona must mention ${keyword}`)
}

// The delegate_experiment tool carries the experiment fields as parameters and
// the structured conclusion as its canonical output.
assert.equal(tools.length, 1)
const tool = tools[0]
// defineTool compiles the parameter DSL into a standard JSON Schema object,
// so the fields live under `parameters.properties` and required fields are a
// root-level name array.
assert.equal(tool.name, 'delegate_experiment')
assert.ok(tool.description.includes('sub-experiment'))
assert.equal(tool.parameters.type, 'object')
for (const field of ['experiment_id', 'hypothesis', 'question', 'scope', 'shared_info']) {
  assert.ok(field in tool.parameters.properties, `tool parameters must include ${field}`)
}
assert.ok(tool.parameters.required.includes('question'))
assert.ok(tool.parameters.required.includes('scope'))
const outputProperties = tool.output.schema.properties
for (const field of ['experiment_id', 'status', 'conclusion', 'evidence']) {
  assert.ok(field in outputProperties, `tool output must include ${field}`)
}
assert.deepEqual(outputProperties.status.enum, ['confirmed', 'rejected', 'completed'])

// The experimentExecutor service registers under the shared service key with a
// run() that writes a valid conclusion shape.
assert.equal(services.length, 1)
assert.equal(services[0].serviceName, EXPERIMENT_EXECUTOR)
assert.equal(typeof services[0].value.run, 'function')

// Disposal is effect owned and runs without throwing.
dispose()

// persona: false keeps the main agent's identity: no persona section, but the
// tool and the executor service still register.
const noPersona = applyToMock({ provider: 'spawn', maxDepth: 3, persona: false })
assert.equal(noPersona.sections.length, 0)
assert.equal(noPersona.tools.length, 1)
assert.equal(noPersona.services.length, 1)

// A recursion cap that is not a non-negative safe integer fails at load.
assert.throws(
  () => applyToMock({ provider: 'spawn', maxDepth: -1, persona: true }),
  /maxDepth must be a non-negative safe integer/,
)

// The exported persona text matches the section text.
assert.equal(DETECTOR_PERSONA_TEXT, section.text)

// The invariant companion registers the exact package name.
let registered = undefined
await invariant.apply({
  invariants: {
    register: (packageName, installer) => {
      registered = { packageName, installer }
      return () => {}
    },
  },
})
assert.equal(invariant.name, 'detector-invariant')
assert.equal(registered.packageName, '@deepseek-ai/dsh-detector')
assert.equal(typeof registered.installer, 'function')

console.log('dsh-detector: all unit checks passed')
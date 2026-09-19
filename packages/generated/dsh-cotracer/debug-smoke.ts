/**
 * Debug smoke: boot the base composition (agent-spine + llm) with the
 * acceptance overlay applied EXACTLY like the acceptance child: the overlay
 * carries cotracer, explorer-agent, experiment-state, detector (persona off),
 * the subagent seam, and the fs tool suite. Asserts the registered tool
 * surface (explorer, experiment_*, delegate_experiment), the cotracer skill,
 * and the experimentExecutor service. Not part of the shipped plugin.
 */
import { resolve } from 'node:path'
import { boot, loadOverlayPatches } from '@deepseek-ai/dsh-app-boot'
import { EXPERIMENT_EXECUTOR } from '@deepseek-ai/dsh-experiment-state'

const baseConfig = resolve('debug-composition-base.yml')
const patches = loadOverlayPatches('dsh-debug', resolve('cordis.acceptance.yml'))
const ctx = await boot('dsh-debug', baseConfig, patches)
try {
  const names = ctx.tools.schemas().map(schema => schema.name).sort()
  console.log('TOOLS:', names.join(', '))
  const required = [
    'explorer',
    'experiment_create',
    'experiment_update',
    'experiment_get',
    'experiment_list',
    'delegate_experiment',
    'read',
    'glob',
    'grep',
  ]
  for (const expected of required) {
    if (!names.includes(expected)) {
      console.log(`${expected} NOT registered`)
      process.exitCode = 1
    }
  }

  const spawn = ctx.subagents.getProvider('spawn')
  console.log('SPAWN PROVIDER:', spawn?.name, 'toolFilter:', spawn?.capabilities.toolFilter)
  if (spawn === undefined || !spawn.capabilities.toolFilter) {
    console.log('spawn provider with toolFilter NOT available')
    process.exitCode = 1
  }

  const executor = ctx.get(EXPERIMENT_EXECUTOR)
  console.log('EXPERIMENT EXECUTOR:', executor === undefined ? 'MISSING' : 'registered')
  if (executor === undefined || typeof executor.run !== 'function') {
    console.log('experimentExecutor service NOT available')
    process.exitCode = 1
  }

  const skills = await ctx.skills.get('cotracer-trace', { cwd: process.cwd() })
  console.log('SKILL cotracer-trace:', skills === undefined ? 'MISSING' : 'registered')
  if (skills === undefined) {
    console.log('cotracer-trace skill NOT registered')
    process.exitCode = 1
  }
} catch (error) {
  console.error('SMOKE FAILED:', error)
  process.exitCode = 1
} finally {
  await ctx.fiber.dispose()
  process.exit(0)
}

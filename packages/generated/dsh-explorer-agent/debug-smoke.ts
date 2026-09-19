/**
 * Debug smoke: boot the base composition (agent-spine + llm) with the
 * acceptance overlay applied EXACTLY like the acceptance child: the overlay
 * carries the plugin, the subagent seam, and the fs tool suites. Lists
 * registered tools and asserts the explorer surface plus a toolFilter-capable
 * subagent provider exist. Full end-to-end exploration needs a real session
 * agent (the `explorer` tool requires a calling agent), which acceptance
 * messaging provides. Not part of the shipped plugin.
 */
import { resolve } from 'node:path'
import { boot, loadOverlayPatches } from '@deepseek-ai/dsh-app-boot'

const baseConfig = resolve('debug-composition-base.yml')
const patches = loadOverlayPatches('dsh-debug', resolve('cordis.acceptance.yml'))
const ctx = await boot('dsh-debug', baseConfig, patches)
try {
  const names = ctx.tools.schemas().map(schema => schema.name).sort()
  console.log('TOOLS:', names.join(', '))
  const required = ['explorer', 'explore_paths', 'explore_semantics', 'read', 'glob', 'grep']
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
} catch (error) {
  console.error('SMOKE FAILED:', error)
  process.exitCode = 1
} finally {
  await ctx.fiber.dispose()
  process.exit(0)
}

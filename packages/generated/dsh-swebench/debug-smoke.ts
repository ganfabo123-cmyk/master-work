/**
 * Debug smoke: boot the base composition (agent-spine + llm) with the plugin
 * overlay applied EXACTLY like the acceptance child: the overlay carries the
 * `insert:` rows (subprocess service + fs tool chain + swebench plugin) as
 * direct file URLs. Lists registered tools, executes swb_list_cases against
 * the real docker daemon, then runs swb_run in one case container and
 * swb_eval against the same case. Requires a working local docker daemon with
 * the 10 eval images pulled. Not part of the shipped plugin.
 */
import { resolve } from 'node:path'
import { boot, loadOverlayPatches } from '@deepseek-ai/dsh-app-boot'

const baseConfig = resolve('debug-composition-base.yml')
const patches = loadOverlayPatches('dsh-debug', resolve('cordis.acceptance.yml'))
const ctx = await boot('dsh-debug', baseConfig, patches)
try {
  const names = ctx.tools.schemas().map(schema => schema.name).sort()
  console.log('TOOLS:', names.join(', '))
  for (const expected of ['swb_list_cases', 'swb_run', 'swb_eval']) {
    if (!names.includes(expected)) {
      console.log(`${expected} NOT registered`)
      process.exitCode = 1
    }
  }

  const signal = new AbortController().signal
  const list = await ctx.tools.execute({
    signal,
    callId: 'debug-list',
    name: 'swb_list_cases',
    arguments: {},
    agent: undefined,
  })
  const listText = list.content
    .filter(block => block.type === 'text')
    .map(block => block.text)
    .join('')
  console.log('LIST CASES:', listText)

  const run = await ctx.tools.execute({
    signal,
    callId: 'debug-run',
    name: 'swb_run',
    arguments: { instance_id: 'astropy__astropy-12907', command: 'python --version && pytest --version' },
    agent: undefined,
  })
  const runText = run.content
    .filter(block => block.type === 'text')
    .map(block => block.text)
    .join('')
  console.log('SWB_RUN:', runText)

  const evalResult = await ctx.tools.execute({
    signal,
    callId: 'debug-eval',
    name: 'swb_eval',
    arguments: { instance_id: 'astropy__astropy-12907' },
    agent: undefined,
  })
  const evalText = evalResult.content
    .filter(block => block.type === 'text')
    .map(block => block.text)
    .join('')
  console.log('SWB_EVAL:', evalText)
} catch (error) {
  console.error('SMOKE FAILED:', error)
  process.exitCode = 1
} finally {
  await ctx.fiber.dispose()
  process.exit(0)
}

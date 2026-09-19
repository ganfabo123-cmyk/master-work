/**
 * Debug smoke: boot the base composition (agent-spine + llm) with the plugin
 * overlay applied EXACTLY like `dsh web --patch <file>` / the acceptance child:
 * the overlay carries the `insert:` rows (plugin + web server) as direct file
 * URLs. Lists registered tools, executes markdown_to_csv, and fetches the
 * generated download URL. Not part of the shipped plugin.
 */
import { resolve } from 'node:path'
import { boot, loadOverlayPatches } from '@deepseek-ai/dsh-app-boot'

const baseConfig = resolve('debug-composition-base.yml')
const patches = loadOverlayPatches('dsh-debug', resolve('cordis.acceptance.yml'))
const ctx = await boot('dsh-debug', baseConfig, patches)
try {
  const names = ctx.tools.schemas().map(schema => schema.name).sort()
  console.log('TOOLS:', names.join(', '))
  if (!names.includes('markdown_to_csv')) {
    console.log('markdown_to_csv NOT registered')
    process.exitCode = 1
  } else {
    const result = await ctx.tools.execute({
      signal: new AbortController().signal,
      callId: 'debug-call',
      name: 'markdown_to_csv',
      arguments: { markdown: '| 名称 | 数量 |\n| 苹果 | 3 |\n| 香蕉 | 12 |' },
      agent: undefined,
    })
    const text = result.content
      .filter(block => block.type === 'text')
      .map(block => block.text)
      .join('')
    console.log('RESULT:', text)
    const urlMatch = text.match(/https?:\/\/[^\s]+/)
    if (urlMatch !== null) {
      const response = await fetch(urlMatch[0])
      console.log('FETCH STATUS:', response.status)
      const body = await response.text()
      console.log('FETCH BODY (first 60 chars):', JSON.stringify(body.slice(0, 60)))
    } else {
      console.log('NO URL FOUND IN RESULT')
      process.exitCode = 1
    }
  }
} catch (error) {
  console.error('SMOKE FAILED:', error)
  process.exitCode = 1
} finally {
  await ctx.fiber.dispose()
  process.exit(0)
}

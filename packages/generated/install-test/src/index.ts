import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'install-test'
export const inject = ['tools'] as const

export function apply(ctx: Context): void {
  ctx.effect(() => {
    const dispose = ctx.tools.register(defineTool({
      name: 'install_test',
      description: 'Return a deterministic result from the workspace install test plugin.',
      parameters: {},
      output: {
        schema: { type: 'string' },
        render: (_args, value) => [{ type: 'text', text: value }],
      },
      execute() {
        return Promise.resolve('install-test is available')
      },
    }))
    return () => dispose()
  }, 'install-test.tools')
}

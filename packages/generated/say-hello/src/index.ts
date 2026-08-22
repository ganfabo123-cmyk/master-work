import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'say-hello'
export const inject = ['tools'] as const

export function apply(ctx: Context): void {
  ctx.effect(() => {
    const dispose = ctx.tools.register(defineTool({
      name: 'say_hello',
      description: 'Greet someone by name and return the greeting text.',
      parameters: {
        name: { type: 'string', description: 'The name to greet. When omitted or blank, a generic greeting is returned.' },
      },
      output: {
        schema: { type: 'string' },
        render: (_args, value) => [{ type: 'text', text: value }],
      },
      execute(args) {
        const target = args.name?.trim()
        return Promise.resolve(target ? `Hello, ${target}!` : 'Hello!')
      },
    }))
    return () => dispose()
  }, 'say-hello.tools')
}
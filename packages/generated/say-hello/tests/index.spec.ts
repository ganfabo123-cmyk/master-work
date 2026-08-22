import { describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import ToolRuntime from '@deepseek-ai/dsh-tools'
import { CallId } from '@deepseek-ai/dsh-llm'
import { apply, inject, name } from '../src/index.js'

const signal = new AbortController().signal

async function mount(): Promise<{ ctx: Context; fiber: { dispose(): Promise<void> } }> {
  const ctx = new Context()
  await ctx.plugin(SystemPrompt, {})
  await ctx.plugin(ToolRuntime)
  const fiber = await ctx.plugin({ name, inject, apply })
  return { ctx, fiber }
}

async function run(ctx: Context, args: Record<string, unknown>): Promise<unknown> {
  const result = await ctx.tools.execute({
    signal,
    callId: CallId('say-hello-test'),
    name: 'say_hello',
    arguments: args,
  })
  const first = result.content[0]
  return first?.type === 'text' ? first.text : JSON.stringify(result.content)
}

describe('say-hello plugin', () => {
  it('registers the say_hello tool with an optional name parameter', async () => {
    const { ctx, fiber } = await mount()
    const sayHello = ctx.tools.schemas().find(schema => schema.name === 'say_hello')
    expect(sayHello).toBeDefined()
    const parameters = sayHello!.parameters as { properties?: Record<string, unknown>; required?: string[] }
    expect(parameters.properties?.name).toMatchObject({ type: 'string' })
    expect(parameters.required).toBeUndefined()
    await fiber.dispose()
  })

  it('greets a named person', async () => {
    const { ctx, fiber } = await mount()
    await expect(run(ctx, { name: 'Ada' })).resolves.toBe('Hello, Ada!')
    await fiber.dispose()
  })

  it('returns a generic greeting when name is omitted, empty, or blank', async () => {
    const { ctx, fiber } = await mount()
    await expect(run(ctx, {})).resolves.toBe('Hello!')
    await expect(run(ctx, { name: '' })).resolves.toBe('Hello!')
    await expect(run(ctx, { name: '   ' })).resolves.toBe('Hello!')
    await fiber.dispose()
  })

  it('unregisters the tool when the plugin fiber is disposed', async () => {
    const { ctx, fiber } = await mount()
    expect(ctx.tools.schemas().some(schema => schema.name === 'say_hello')).toBe(true)
    await fiber.dispose()
    expect(ctx.tools.schemas().some(schema => schema.name === 'say_hello')).toBe(false)
  })
})
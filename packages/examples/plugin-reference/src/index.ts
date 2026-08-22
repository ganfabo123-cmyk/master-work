import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue } from '@deepseek-ai/dsh-tools'
import { Config, type Config as PluginConfig } from './config.js'
import { ReferenceNoteService } from './service.js'

export const name = 'plugin-reference'
export const inject = ['tools'] as const
export { Config }
export type { PluginConfig }

export function apply(ctx: Context, config: PluginConfig): void {
  if (!config.enabled) return
  const service = new ReferenceNoteService(config)

  ctx.effect(() => {
    const disposers = [
      ctx.tools.register(defineTool({
        name: 'reference_echo',
        description: 'Echo a non-empty message and identify the reference plugin.',
        parameters: {
          message: { type: 'string', required: true, description: 'The message to echo.' },
        },
        output: {
          schema: {
            type: 'object',
            additionalProperties: false,
            properties: {
              plugin: { type: 'string', required: true },
              message: { type: 'string', required: true },
            },
          },
          render: (_args, value) => [{ type: 'text', text: `${value.plugin}: ${value.message}` }],
        },
        execute(args) {
          const message = args.message.trim()
          if (message.length === 0) throw new Error('message must be a non-empty string')
          return Promise.resolve({ plugin: name, message })
        },
      })),
      ctx.tools.register(defineTool({
        name: 'reference_note_add',
        description: 'Persist a note in the configured local JSON file.',
        parameters: {
          title: { type: 'string', required: true, description: 'A short non-empty title.' },
          content: { type: 'string', required: true, description: 'The note content.' },
          tags: { type: 'array', required: true, items: { type: 'string' }, description: 'Tags attached to the note.' },
        },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args) {
          const title = args.title.trim()
          if (title.length === 0) throw new Error('title must be a non-empty string')
          const content = args.content.trim()
          if (content.length === 0) throw new Error('content must be a non-empty string')
          const note = await service.add({ title, content, tags: args.tags.map(tag => tag.trim()).filter(Boolean) })
          return JSON.parse(JSON.stringify(note)) as Record<string, JsonValue>
        },
      })),
      ctx.tools.register(defineTool({
        name: 'reference_note_list',
        description: 'Read persisted notes, optionally filtered by tag and limited by count.',
        parameters: {
          tag: { type: 'string', description: 'Optional exact tag filter.' },
          limit: { type: 'integer', description: 'Optional positive maximum number of notes.' },
        },
        output: { schema: { type: 'object', additionalProperties: true }, render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }] },
        async execute(args) {
          if (args.limit !== undefined && args.limit < 1) throw new Error('limit must be a positive integer')
          const items = await service.list(args.tag?.trim() || undefined, args.limit)
          return JSON.parse(JSON.stringify({ items, count: items.length })) as Record<string, JsonValue>
        },
      })),
    ]
    return () => disposers.forEach(dispose => dispose())
  }, 'plugin-reference.tools')
}

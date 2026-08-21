import { defineTool } from '@deepseek-ai/dsh-tools'

import type {
  AcceptanceActor,
} from '../models/acceptance.js'

import type {
  AcceptanceService,
} from '../services/acceptance-service.js'


export function sendAcceptanceMessageTool(
  acceptanceService: AcceptanceService,
) {
  return defineTool({
    name: 'send_acceptance_message',

    description: [
      'Send one natural-language message to an existing real-host DSH acceptance session.',
      '',
      'The message is relayed directly to the child DSH session without prompt rewriting.',
      '',
      'For automated acceptance use actor="agent".',
      'For a message explicitly supplied by the user for human acceptance use actor="user".',
      '',
      'When actor="user", preserve the user-provided test input exactly. Do not rewrite, expand, clarify, or add tool hints.',
    ].join('\n'),

    parameters: {
      acceptance_id: {
        type: 'string',
        required: true,
        description:
          'The acceptance id returned by start_acceptance.',
      },

      actor: {
        type: 'string',
        required: true,
        enum: [
          'agent',
          'user',
        ],
        description:
          'Origin of this acceptance input.',
      },

      message: {
        type: 'string',
        required: true,
        description:
          'Raw natural-language input sent directly to the child DSH session.',
      },
    },

    output: {
      schema: {
        type: 'object',
        additionalProperties: false,

        properties: {
          acceptance_id: {
            type: 'string',
            required: true,
          },

          cwd: {
            type: 'string',
            required: true,
          },

          provider: {
            type: 'string',
            required: true,
          },

          model: {
            type: 'string',
            required: true,
          },

          actor: {
            type: 'string',
            required: true,
          },

          response: {
            type: 'string',
            required: true,
          },

          status: {
            type: 'string',
            required: true,
          },

          message_count: {
            type: 'integer',
            required: true,
          },
        },
      },

      render: (_args, value) => [
        {
          type: 'text',
          text: [
            `Acceptance: ${value.acceptance_id}`,
            `cwd: ${value.cwd}`,
            `Provider: ${value.provider}`,
            `Model: ${value.model}`,
            `Input actor: ${value.actor}`,
            `Status: ${value.status}`,
            `Interactions: ${value.message_count}`,
            '',
            'Child DSH response:',
            value.response,
          ].join('\n'),
        },
      ],
    },

    async execute(args, exec) {
      exec.signal.throwIfAborted()

      /*
       * args.message is intentionally passed directly
       * into AcceptanceService.
       *
       * Do NOT add:
       *
       * - extra system instructions
       * - tool hints
       * - acceptance explanations
       * - rewritten user intent
       */
      const result =
        await acceptanceService.send(
          {
            acceptanceId:
              args.acceptance_id,

            actor:
              args.actor as AcceptanceActor,

            message:
              args.message,
          },

          exec.signal,
        )

      return {
        acceptance_id:
          result.acceptance.id,

        cwd:
          result.acceptance.cwd,

        provider:
          result.acceptance.provider,

        model:
          result.acceptance.model,

        actor:
          args.actor,

        response:
          result.response,

        status:
          result.acceptance.status,

        message_count:
          result.acceptance.messages.length,
      }
    },
  })
}

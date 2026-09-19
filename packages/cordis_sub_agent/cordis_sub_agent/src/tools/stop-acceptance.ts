import { defineTool } from '@deepseek-ai/dsh-tools'

import type {
  AcceptanceService,
} from '../services/acceptance-service.js'


export function stopAcceptanceTool(
  acceptanceService: AcceptanceService,
) {
  return defineTool({
    name: 'stop_acceptance',

    description:
      'Stop the acceptance runtime identified by acceptance_id.',

    parameters: {
      acceptance_id: {
        type: 'string',
        required: true,
        description:
          'The acceptance id returned by start_acceptance.',
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

          acceptance_status: {
            type: 'string',
            required: true,
          },

          message: {
            type: 'string',
            required: true,
          },
        },
      },

      render: (_args, value) => [
        {
          type: 'text',
          text: [
            `Acceptance: ${value.acceptance_id}`,
            `Acceptance status: ${value.acceptance_status}`,
            '',
            value.message,
          ].join('\n'),
        },
      ],
    },

    async execute(args, exec) {
      exec.signal.throwIfAborted()

      const state =
        await acceptanceService.stop(
          args.acceptance_id,
        )

      return {
        acceptance_id:
          state.id,

        acceptance_status:
          state.status,

        message:
          'Acceptance runtime stopped.',
      }
    },
  })
}

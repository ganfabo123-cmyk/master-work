import { defineTool } from '@deepseek-ai/dsh-tools'
import { resolve } from 'node:path'

import type {
  AcceptanceService,
} from '../services/acceptance-service.js'

export interface StartAcceptanceToolOptions {
  repoRoot: string
  provider: string
  model: string
  maxTokens?: number
}


export function startAcceptanceTool(
  acceptanceService: AcceptanceService,
  options: StartAcceptanceToolOptions,
) {
  return defineTool({
    name: 'start_acceptance',

    description: [
      'Start real-host acceptance testing for a generated DeepSeek Harness plugin.',
      '',
      'The patch parameter is required and must identify the plugin to test.',
      '',
      'For patch, provide the Cordis patch file that selects the plugin to test.',
      '',
      'This launches a fresh isolated DSH runtime and returns an acceptance_id.',
      'Reuse that acceptance_id with send_acceptance_message and stop_acceptance.',
    ].join('\n'),

    parameters: {
      patch: {
        type: 'string',
        required: true,
        description:
          'A Cordis patch file selecting the plugin to test, for example packages/generated/say-hello/cordis.yml.',
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

          child_session_id: {
            type: 'string',
            required: true,
          },

          status: {
            type: 'string',
            required: true,
          },

          workspace_path: {
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

          plugin_entry_path: {
            type: 'string',
          },

          patch: {
            type: 'string',
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
            `Child session: ${value.child_session_id}`,
            `Status: ${value.status}`,
            `Workspace: ${value.workspace_path}`,
            `Child cwd: ${value.cwd}`,
            `Provider: ${value.provider}`,
            `Model: ${value.model}`,
            `Patch: ${value.patch}`,
            '',
            value.message,
          ].join('\n'),
        },
      ],
    },

    async execute(args, exec) {
      exec.signal.throwIfAborted()

      const patchPath = resolve(options.repoRoot, args.patch)
      const acceptance = await acceptanceService.start({
        taskId: `patch-${Date.now()}`,
        patchPath,
        repoRoot: options.repoRoot,
        provider: options.provider,
        model: options.model,
        ...(options.maxTokens !== undefined ? { maxTokens: options.maxTokens } : {}),
      })

      if (
        acceptance.childSessionId ===
        undefined
      ) {
        /*
         * 理论上 AcceptanceService.start()
         * 成功时一定有 childSessionId。
         *
         * 这里作为边界保护。
         */
        try {
          await acceptanceService.stop(
            acceptance.id,
            'failed',
          )
        } catch {
          // Preserve the original invariant failure.
        }

        throw new Error(
          'Acceptance runtime started without a child session id.',
        )
      }

      return {
        acceptance_id:
          acceptance.id,

        child_session_id:
          acceptance.childSessionId,

        status:
          acceptance.status,

        workspace_path:
          options.repoRoot,

        cwd:
          options.repoRoot,

        provider:
          options.provider,

        model:
          options.model,

        patch:
          patchPath,

        message: [
          'Cordis patch acceptance runtime started successfully.',
          `cwd: ${options.repoRoot}`,
          `provider: ${options.provider}`,
          `model: ${options.model}`,
          'The child DSH service is ready; send a message with send_acceptance_message.',
        ].join(' '),
      }
    },
  })
}


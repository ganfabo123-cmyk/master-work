import { defineTool } from '@deepseek-ai/dsh-tools'

import type {
  AcceptanceService,
} from '../services/acceptance-service.js'

import type {
  PluginMetadataTaskStore,
} from '../services/plugin-metadata-task-store.js'


export interface StartAcceptanceToolOptions {
  repoRoot: string
  provider: string
  model: string
  maxTokens?: number
}


export function startAcceptanceTool(
  acceptanceService: AcceptanceService,
  tasks: PluginMetadataTaskStore,
  options: StartAcceptanceToolOptions,
) {
  return defineTool({
    name: 'start_acceptance',

    description: [
      'Start real-host acceptance testing for a generated DeepSeek Harness plugin.',
      '',
      'Use this tool only after verify_development has recorded a successful engineering verification.',
      '',
      'The task_id must refer to an existing V3 metadata task with a successful engineering verification.',
      '',
      'The verified workspace path and plugin build artifact are loaded from the trusted V3 metadata task store.',
      'Do not provide or guess filesystem paths manually.',
      '',
      'This launches a fresh isolated DSH runtime and returns an acceptance_id.',
      'Reuse that acceptance_id with send_acceptance_message and stop_acceptance.',
    ].join('\n'),

    parameters: {
      task_id: {
        type: 'string',
        required: true,
        description:
          'The V3 task id returned by submit_plugin_metadata.',
      },

      plugin_config_json: {
        type: 'string',
        description:
          'Optional JSON object passed as the Cordis config of the plugin under test.',
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

          task_id: {
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
            `Task: ${value.task_id}`,
            `Child session: ${value.child_session_id}`,
            `Status: ${value.status}`,
            `Workspace: ${value.workspace_path}`,
            `Child cwd: ${value.cwd}`,
            `Provider: ${value.provider}`,
            `Model: ${value.model}`,
            `Plugin entry: ${value.plugin_entry_path}`,
            '',
            value.message,
          ].join('\n'),
        },
      ],
    },

    async execute(args, exec) {
      exec.signal.throwIfAborted()

      /*
       * 只相信 TaskStore 中由系统自己记录的状态。
       *
       * 不允许 Agent 再传 workspacePath /
       * pluginEntryPath。
       */
      const record =
        tasks.require(
          args.task_id,
        )

      /*
       * Engineering verification 是进入
       * Acceptance 的硬前置条件。
       */
      const verification = record.verification

      if (
        verification === undefined || !verification.success
      ) {
        throw new Error(
          `Plugin metadata task has no successful engineering verification result: ${args.task_id}`,
        )
      }

      /*
       * 防止同一个 task 同时启动多个 acceptance runtime。
       *
       * 第一版先保持 1 task -> 1 active acceptance。
       */
      if (
        record.acceptanceId !==
        undefined
      ) {
        throw new Error(
          [
            `Development task already has an active acceptance runtime: ${args.task_id}.`,
            `Acceptance id: ${record.acceptanceId}`,
          ].join(' '),
        )
      }

      let pluginConfig:
        | Record<string, unknown>
        | undefined

      if (
        args.plugin_config_json !==
        undefined
      ) {
        let parsed: unknown

        try {
          parsed =
            JSON.parse(
              args.plugin_config_json,
            )
        } catch (error) {
          throw new Error(
            `plugin_config_json is not valid JSON: ${errorMessage(error)}`,
          )
        }

        if (!isRecord(parsed)) {
          throw new Error(
            'plugin_config_json must contain a JSON object.',
          )
        }

        pluginConfig =
          parsed
      }

      /*
       * 关键：
       *
       * workspacePath 来自 task
       * pluginEntryPath 来自 verification
       *
       * 两者都不是模型重新提供的。
       */
      const acceptance =
        await acceptanceService.start({
          taskId:
            record.id,

          pluginEntryPath:
            verification.pluginEntryPath,

          repoRoot:
            options.repoRoot,

          provider:
            options.provider,

          model:
            options.model,

          ...(pluginConfig !== undefined
            ? {
              pluginConfig,
            }
            : {}),

          ...(options.maxTokens !== undefined
            ? {
              maxTokens:
                  options.maxTokens,
            }
            : {}),

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

      /*
       * 只有 AcceptanceService 真正启动成功之后，
       * 才把 acceptanceId 写入 TaskStore。
       */
      tasks.setAcceptanceId(
        record.id,
        acceptance.id,
      )
      return {
        acceptance_id:
          acceptance.id,

        task_id:
          record.id,

        child_session_id:
          acceptance.childSessionId,

        status:
          acceptance.status,

        workspace_path:
          record.pluginRoot,

        cwd:
          options.repoRoot,

        provider:
          options.provider,

        model:
          options.model,

        plugin_entry_path:
          verification.pluginEntryPath,

        message: [
          'Isolated DSH acceptance runtime started successfully.',
          `cwd: ${options.repoRoot}`,
          `provider: ${options.provider}`,
          `model: ${options.model}`,
          'The child DSH service is ready; send a message with send_acceptance_message.',
        ].join(' '),
      }
    },
  })
}


function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value)
  )
}


function errorMessage(
  error: unknown,
): string {
  return error instanceof Error
    ? error.message
    : String(error)
}

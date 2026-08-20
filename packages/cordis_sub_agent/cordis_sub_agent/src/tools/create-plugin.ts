import { randomUUID } from 'node:crypto'

import { defineTool } from '@deepseek-ai/dsh-tools'

import {
  parsePluginSpec,
} from '../models/plugin-spec.js'

import type {
  PluginDevelopmentService,
} from '../services/plugin-development-service.js'


export function createPluginTool(
  developmentService: PluginDevelopmentService,
  options?: {
    preferredProvider?: string
    buildCommand?: string
    testCommand?: string
    verificationTimeoutMs?: number
  },
) {
  return defineTool({
    name: 'create_plugin',

    description: [
      'Develop a DeepSeek Harness plugin from a user-confirmed PluginSpec.',
      '',
      'Use this tool only after the user has confirmed:',
      '1. the requirement analysis,',
      '2. the plugin input/output and interaction design,',
      '3. the final detailed requirement specification.',
      '',
      'This tool creates an isolated worktree and starts the Reader plus long-lived Coding Agent.',
      'A successful result means development has started, not that engineering or real-host acceptance passed.',
    ].join('\n'),

    parameters: {
      plugin_spec_json: {
        type: 'string',
        required: true,
        description:
          'JSON serialization of the final user-confirmed PluginSpec.',
      },
    },

    output: {
      schema: {
        type: 'object',
        additionalProperties: false,

        properties: {
          task_id: {
            type: 'string',
            required: true,
          },

          plugin_name: {
            type: 'string',
            required: true,
          },

          workspace_path: {
            type: 'string',
            required: true,
          },

          plugin_entry_path: {
            type: 'string',
          },

          status: {
            type: 'string',
            required: true,
          },

          build_exit_code: {
            type: 'integer',
          },

          test_exit_code: {
            type: 'integer',
          },

          next_step: {
            type: 'string',
            required: true,
          },
        },
      },

      render: (_args, value) => {
        const lines = [
          `Plugin development task: ${value.task_id}`,
          `Plugin: ${value.plugin_name}`,
          `Workspace: ${value.workspace_path}`,
          ...(value.plugin_entry_path !== undefined
            ? [`Build artifact: ${value.plugin_entry_path}`]
            : []),
          `Status: ${value.status}`,
        ]

        if (value.build_exit_code !== undefined) {
          lines.push(`Build exit code: ${value.build_exit_code}`)
        }

        if (
          value.test_exit_code !== undefined
        ) {
          lines.push(
            `Test exit code: ${value.test_exit_code}`,
          )
        }

        lines.push(
          '',
          value.next_step,
        )

        return [
          {
            type: 'text',
            text: lines.join('\n'),
          },
        ]
      },
    },

    async execute(
      args,
      exec,
    ) {
      /*
       * DevelopmentWorkflow 的 child agents
       * 必须挂在当前真实 calling Agent 下面。
       */
      const parent =
        exec.agent

      if (parent === undefined) {
        throw new Error(
          'create_plugin requires a calling agent.',
        )
      }

      exec.signal.throwIfAborted()

      /*
       * plugin_spec_json 来自模型输入。
       *
       * JSON.parse 只证明它是 JSON；
       * parsePluginSpec 才证明它符合我们的业务结构。
       */
      let rawSpec: unknown

      try {
        rawSpec =
          JSON.parse(
            args.plugin_spec_json,
          )
      } catch (error) {
        throw new Error(
          [
            'plugin_spec_json is not valid JSON.',
            errorMessage(error),
          ].join(' '),
        )
      }

      const spec =
        parsePluginSpec(
          rawSpec,
        )

      const taskId =
        randomUUID()

      const result =
        await developmentService.develop(
          {
            taskId,
            spec,
          },
          {
            parent,
            signal:
              exec.signal,

            ...(options?.preferredProvider !==
            undefined
              ? {
                preferredProvider:
                    options.preferredProvider,
              }
              : {}),

            ...(options?.buildCommand !==
            undefined
              ? {
                buildCommand:
                    options.buildCommand,
              }
              : {}),

            ...(options?.testCommand !==
            undefined
              ? {
                testCommand:
                    options.testCommand,
              }
              : {}),

            ...(options?.verificationTimeoutMs !==
            undefined
              ? {
                verificationTimeoutMs:
                    options.verificationTimeoutMs,
              }
              : {}),
          },
        )

      return {
        task_id:
          result.task.id,

        plugin_name:
          result.task.spec.name,

        workspace_path:
          result.task.workspacePath,

        ...(result.verification !== undefined
          ? { plugin_entry_path: result.verification.pluginEntryPath }
          : {}),

        status:
          result.task.status,

        ...(result.verification !== undefined
          ? { build_exit_code: result.verification.build.exitCode ?? -1 }
          : {}),

        ...(result.verification?.test !==
        undefined
          ? {
            test_exit_code:
                result.verification.test.exitCode ??
                -1,
          }
          : {}),

        next_step: [
          'A dedicated git worktree and a continuable Coding Agent were created.',
          'Use get_development_task for evidence and resume_development to continue the same Coding Agent.',
        ].join(' '),
      }
    },
  })
}


function errorMessage(
  error: unknown,
): string {
  return error instanceof Error
    ? error.message
    : String(error)
}

import { defineTool } from '@deepseek-ai/dsh-tools'

import type {
  AcceptanceService,
} from '../services/acceptance-service.js'

import type {
  DevelopmentTaskStore,
} from '../services/development-task-store.js'


const FINAL_ACCEPTANCE_STATUSES = [
  'passed',
  'failed',
  'stopped',
] as const

type FinalAcceptanceStatus =
  typeof FINAL_ACCEPTANCE_STATUSES[number]


export function stopAcceptanceTool(
  acceptanceService: AcceptanceService,
  tasks: DevelopmentTaskStore,
) {
  return defineTool({
    name: 'stop_acceptance',

    description: [
      'Stop an active real-host DSH acceptance runtime.',
      '',
      'Use final_status="passed" only after both:',
      '1. automated agent real-host acceptance has succeeded, and',
      '2. the user has supplied at least one real acceptance input that was sent unchanged to the child DSH session and completed successfully.',
      '',
      'Use final_status="failed" when acceptance exposed a real failure.',
      'Use final_status="stopped" when terminating the runtime without declaring success or failure.',
      '',
      'A passed acceptance that satisfies all required evidence marks the development task as completed.',
    ].join('\n'),

    parameters: {
      acceptance_id: {
        type: 'string',
        required: true,
        description:
          'The acceptance id returned by start_acceptance.',
      },

      final_status: {
        type: 'string',
        required: true,
        enum: FINAL_ACCEPTANCE_STATUSES,
        description:
            'Final state assigned to this acceptance runtime.',
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

          acceptance_status: {
            type: 'string',
            required: true,
          },

          task_status: {
            type: 'string',
            required: true,
          },

          message_count: {
            type: 'integer',
            required: true,
          },

          agent_message_count: {
            type: 'integer',
            required: true,
          },

          user_message_count: {
            type: 'integer',
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
            `Acceptance status: ${value.acceptance_status}`,
            `Task status: ${value.task_status}`,
            `Interactions: ${value.message_count}`,
            `Agent interactions: ${value.agent_message_count}`,
            `User interactions: ${value.user_message_count}`,
            '',
            value.message,
          ].join('\n'),
        },
      ],
    },

    async execute(args, exec) {
      exec.signal.throwIfAborted()

      /*
       * stop() 之前先读取 state。
       *
       * 因为 AcceptanceService.stop() 会把 runtime
       * 从自己的 runtime map 中移除。
       */
      const current =
        acceptanceService.get(
          args.acceptance_id,
        )

      const taskRecord =
        tasks.require(
          current.taskId,
        )

      /*
       * 防止某个 acceptance_id 被拿去关闭不属于当前
       * task active acceptance 的 runtime。
       */
      if (
        taskRecord.acceptanceId !==
        args.acceptance_id
      ) {
        throw new Error(
          [
            'Acceptance runtime does not match the active acceptance of its development task.',
            `Task: ${current.taskId}.`,
            `Expected: ${String(taskRecord.acceptanceId)}.`,
            `Received: ${args.acceptance_id}.`,
          ].join(' '),
        )
      }

      const finalStatus =
        args.final_status as FinalAcceptanceStatus

      /*
       * 在真正 shutdown 前先检查 pass 所需证据。
       *
       * completed === true 表示这一轮真实 DSH
       * interaction 正常完成。
       */
      const completedAgentMessages =
        current.messages.filter(
          message =>
            message.actor === 'agent' &&
            message.completed === true,
        )

      const completedUserMessages =
        current.messages.filter(
          message =>
            message.actor === 'user' &&
            message.completed === true,
        )

      /*
       * final_status="passed" 是一个强声明。
       *
       * 不满足 Definition of Done 时直接拒绝，
       * 而不是悄悄降级成 stopped。
       */
      if (finalStatus === 'passed') {
        if (
          completedAgentMessages.length === 0
        ) {
          throw new Error(
            [
              'Acceptance cannot be marked as passed.',
              'No completed agent-originated real-host acceptance interaction was recorded.',
            ].join(' '),
          )
        }

        if (
          completedUserMessages.length === 0
        ) {
          throw new Error(
            [
              'Acceptance cannot be marked as passed.',
              'No completed user-originated real-host acceptance interaction was recorded.',
            ].join(' '),
          )
        }
      }

      let state

      try {
        state =
          await acceptanceService.stop(
            args.acceptance_id,
            finalStatus,
          )
      } finally {
        /*
         * AcceptanceService.stop() 已经开始终止这个 runtime，
         * 因此无论 shutdown 最后是否抛异常，都不能继续让
         * TaskStore 把它当 active runtime。
         */
        tasks.clearAcceptanceId(
          current.taskId,
        )
      }

      /*
       * 更新 development task 生命周期。
       */
      if (
        state.status === 'passed'
      ) {
        taskRecord.task.status =
          'completed'

        delete taskRecord.task.error
      } else if (
        state.status === 'failed'
      ) {
        taskRecord.task.status =
          'failed'

        taskRecord.task.error =
          'Real-host acceptance failed.'
      } else {
        /*
         * stopped 不代表开发失败。
         *
         * Plugin 已经完成工程验证，
         * 只是 Acceptance 尚未得出最终结论，
         * 因此回到 accepting。
         */
        taskRecord.task.status =
          'accepting'
      }

      taskRecord.task.updatedAt =
        Date.now()

      return {
        acceptance_id:
          state.id,

        task_id:
          state.taskId,

        acceptance_status:
          state.status,

        task_status:
          taskRecord.task.status,

        message_count:
          state.messages.length,

        agent_message_count:
          completedAgentMessages.length,

        user_message_count:
          completedUserMessages.length,

        message:
          state.status === 'passed'
            ? [
              'Real-host acceptance passed.',
              'Both automated agent acceptance and user-originated acceptance evidence were recorded.',
              'The development task is now completed.',
            ].join(' ')
            : state.status === 'failed'
              ? [
                'Real-host acceptance failed.',
                'The development task has been marked as failed.',
              ].join(' ')
              : [
                'Acceptance runtime stopped without a final pass or failure.',
                'The development task remains in accepting status and may start another acceptance runtime.',
              ].join(' '),
      }
    },
  })
}

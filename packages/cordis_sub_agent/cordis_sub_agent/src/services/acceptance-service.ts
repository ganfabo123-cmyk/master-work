import { randomUUID } from 'node:crypto'
import { resolve } from 'node:path'

import {
  DeepSeekHarness,
  type HarnessSession,
  type RunResult,
} from '@deepseek-ai/dsh-sdk-client'

import type {
  AcceptanceActor,
  AcceptanceMessage,
  AcceptanceSession,
} from '../models/acceptance.js'

import {
  createAcceptanceComposition,
  type AcceptanceComposition,
} from './acceptance-composition.js'


export interface StartAcceptanceInput {
  taskId: string

  /**
   * Build 后真正加载的插件入口。
   * 例如：
   * D:/project/my-plugin/lib/index.js
   */
  pluginEntryPath: string

  /** The repository cwd used by the child runtime and its SDK session. */
  repoRoot: string

  /**
   * Child DSH 使用的 LLM provider。
   */
  provider: string

  /**
   * Child DSH 使用的 model。
   */
  model: string

  /**
   * 传给被测试插件的 Cordis config。
   */
  pluginConfig?: Record<string, unknown>

  maxTokens?: number
}


export interface SendAcceptanceInput {
  acceptanceId: string

  /**
   * 只用于记录消息来源。
   *
   * actor 不会改变真正发送给 child DSH 的内容。
   */
  actor: AcceptanceActor

  /**
   * 原始自然语言输入。
   *
   * Human Acceptance 时必须原样发送。
   */
  message: string
}


export interface AcceptanceSendResult {
  acceptance: AcceptanceSession
  response: string
  run: RunResult
}


interface AcceptanceRuntime {
  harness: DeepSeekHarness
  session: HarnessSession
  composition: AcceptanceComposition
  state: AcceptanceSession
}


export class AcceptanceService {
  private readonly runtimes = new Map<
    string,
    AcceptanceRuntime
  >()


  /**
   * 启动一个完全隔离的新 DSH runtime，
   * 并准备一个新的 acceptance session。
   *
   * 注意：
   * HarnessSession 是 lazy 的。
   * 真正的 server-side session 会在第一次 send() 时创建。
   */
  async start(
    input: StartAcceptanceInput,
  ): Promise<AcceptanceSession> {
    const acceptanceId = randomUUID()

    const childSessionId =
      `acceptance-${randomUUID().replaceAll('-', '')}`

    /*
     * 为本次验收创建独立的临时 Cordis composition。
     *
     * composition =
     * 官方 agent spine
     * +
     * 当前刚刚生成的插件。
     */
    const composition =
      await createAcceptanceComposition({
        pluginEntryPath:
          input.pluginEntryPath,

        ...(input.pluginConfig !== undefined
          ? {
            pluginConfig:
                input.pluginConfig,
          }
          : {}),
        provider: input.provider,
        apiKeyEnv: 'open_code_api',
      })

    const repoRoot = resolve(input.repoRoot)
    const runtimeBin = resolve(
      repoRoot,
      'packages',
      'examples',
      'jsonrpc-demo',
      'lib',
      'packaged-bin.js',
    )
    const harness = new DeepSeekHarness({
      launch: {
        command: process.execPath,

        /*
         * Child runtime 使用这份临时 cordis.yml。
         */
        args: [
          runtimeBin,
          composition.configPath,
        ],

        /*
         * 这里故意不是 composition.directory。
         *
         * Acceptance 应该站在真实插件 workspace 中运行。
         */
        cwd: repoRoot,
      },

      /*
       * initialize() 的 cwd。
       *
       * 也会成为 child session 的 workspace。
       */
      cwd: repoRoot,

      provider: input.provider,
      model: input.model,

      ...(input.maxTokens !== undefined
        ? {
          maxTokens:
              input.maxTokens,
        }
        : {}),
    })

    const state: AcceptanceSession = {
      id: acceptanceId,
      taskId: input.taskId,

      cwd: repoRoot,

      provider: input.provider,

      model: input.model,

      status: 'starting',

      childSessionId,

      messages: [],

      startedAt: Date.now(),
    }

    try {
      /*
       * 真正：
       *
       * spawn child process
       * → 建立 JSON-RPC transport
       * → initialize handshake
       */
      await harness.start()

      /*
       * 这里只创建 client-side HarnessSession handle。
       *
       * Server-side Agent/session 会在第一次 run() 时 lazy create。
       */
      const session =
        harness.session(childSessionId)

      state.status = 'running'

      this.runtimes.set(
        acceptanceId,
        {
          harness,
          session,
          composition,
          state,
        },
      )

      return state
    } catch (error) {
      state.status = 'failed'
      state.error = errorMessage(error)
      state.endedAt = Date.now()

      /*
       * startup 可能已经成功 spawn 了一部分 runtime，
       * 所以这里两边都尝试清理。
       */
      await Promise.allSettled([
        harness.close(),
        composition.dispose(),
      ])

      throw error
    }
  }


  /**
   * 向真实 child DSH session 发送一条消息。
   *
   * Human Acceptance 时 message 必须保持用户原始输入，
   * 这里不允许进行 prompt rewrite。
   */
  async send(
    input: SendAcceptanceInput,
    signal?: AbortSignal,
  ): Promise<AcceptanceSendResult> {
    const runtime =
      this.requireRuntime(
        input.acceptanceId,
      )

    if (
      runtime.state.status !==
      'running'
    ) {
      throw new Error(
        `Acceptance session is not running: ${input.acceptanceId}`,
      )
    }

    if (
      input.message.trim().length === 0
    ) {
      throw new Error(
        'Acceptance message must not be empty.',
      )
    }

    /*
     * 官方 SDK 当前没有 wire-level turn cancel。
     *
     * 所以这里只能在 run() 开始之前检查取消。
     */
    signal?.throwIfAborted()

    const record: AcceptanceMessage = {
      actor: input.actor,
      input: input.message,
      timestamp: Date.now(),
    }

    runtime.state.messages.push(record)

    try {
      /*
       * 这是 Acceptance 最关键的一行：
       *
       * 不改写
       * 不补提示词
       * 不提示调用哪个 tool
       *
       * 直接进入真实 DSH。
       */
      const result =
        await runtime.session.run(
          input.message,
        )

      record.output =
        result.finalResponse

      /*
       * 如果 AcceptanceMessage 已经加了 completed 字段，
       * 可以保留这一行。
       *
       * 如果你当前 acceptance.ts 没有 completed，
       * 就把这行删掉。
       */
      record.completed = true

      return {
        acceptance:
          runtime.state,

        response:
          result.finalResponse,

        run: result,
      }
    } catch (error) {
      const message =
        errorMessage(error)

      record.error = message
      record.completed = false

      runtime.state.status = 'failed'
      runtime.state.error = message

      throw error
    }
  }


  /**
   * 获取当前 Acceptance 状态。
   */
  get(
    acceptanceId: string,
  ): AcceptanceSession {
    return this.requireRuntime(
      acceptanceId,
    ).state
  }


  /**
   * 关闭一个 Acceptance Runtime。
   *
   * SDK 当前没有单独 close session API，
   * 所以 lifecycle boundary 是整个 DeepSeekHarness。
   */
  async stop(
    acceptanceId: string,

    finalStatus:
      | 'passed'
      | 'failed'
      | 'stopped' = 'stopped',
  ): Promise<AcceptanceSession> {
    const runtime =
      this.requireRuntime(
        acceptanceId,
      )

    /*
     * 先从 map 删除。
     *
     * 防止 shutdown 过程中还有新的 send() 进入。
     */
    this.runtimes.delete(
      acceptanceId,
    )

    try {
      await runtime.harness.close()
    } finally {
      try {
        await runtime.composition.dispose()
      } finally {
        runtime.state.status =
          finalStatus

        runtime.state.endedAt =
          Date.now()
      }
    }

    return runtime.state
  }


  /**
   * 插件整体卸载时关闭所有 Child DSH Runtime。
   */
  async dispose(): Promise<void> {
    const active =
      [...this.runtimes.values()]

    this.runtimes.clear()

    await Promise.allSettled(
      active.map(
        async (runtime) => {
          try {
            await runtime.harness.close()
          } finally {
            try {
              await runtime.composition.dispose()
            } finally {
              runtime.state.status =
                'stopped'

              runtime.state.endedAt =
                Date.now()
            }
          }
        },
      ),
    )
  }


  private requireRuntime(
    acceptanceId: string,
  ): AcceptanceRuntime {
    const runtime =
      this.runtimes.get(
        acceptanceId,
      )

    if (
      runtime === undefined
    ) {
      throw new Error(
        `Unknown acceptance session: ${acceptanceId}`,
      )
    }

    return runtime
  }
}


function errorMessage(
  error: unknown,
): string {
  return error instanceof Error
    ? error.message
    : String(error)
}

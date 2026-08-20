import type { Context } from '@deepseek-ai/cordis'

import type {} from '@deepseek-ai/dsh-fs'
import type {} from '@deepseek-ai/dsh-shell'

export interface EngineeringVerificationInput {
  workspacePath: string

  /**
   * 构建完成后预期的插件入口。
   *
   * 例如：
   * D:/xxx/plugin/lib/index.js
   */
  pluginEntryPath: string

  /**
   * 第一版默认 pnpm build。
   * 后面可以由 PluginSpec / package.json 检测逻辑决定。
   */
  buildCommand?: string

  /**
   * 可选测试命令。
   *
   * 第一版没有测试时可以不传。
   */
  testCommand?: string

  timeoutMs?: number
}

export interface CommandVerificationResult {
  command: string
  exitCode: number | null
  stdout: string
  stderr: string
  stdoutTruncated: boolean
  stderrTruncated: boolean
}

export interface EngineeringVerificationResult {
  success: true

  workspacePath: string
  pluginEntryPath: string

  build: CommandVerificationResult
  test?: CommandVerificationResult
}

export class EngineeringVerificationService {
  constructor(
    private readonly ctx: Context,
  ) {}

  async verify(
    input: EngineeringVerificationInput,
    signal?: AbortSignal,
  ): Promise<EngineeringVerificationResult> {
    signal?.throwIfAborted()

    const buildCommand =
      input.buildCommand ??
      'pnpm build'

    const build =
      await this.runCommand(
        buildCommand,
        input.workspacePath,
        input.timeoutMs,
        signal,
      )

    this.assertCommandSucceeded(
      'Build',
      build,
    )

    let test:
      | CommandVerificationResult
      | undefined

    if (input.testCommand !== undefined) {
      test = await this.runCommand(
        input.testCommand,
        input.workspacePath,
        input.timeoutMs,
        signal,
      )

      this.assertCommandSucceeded(
        'Test',
        test,
      )
    }

    /*
     * Build 命令成功不代表 artifact 一定存在。
     *
     * 所以必须再通过 fs 独立检查最终入口。
     */
    const entryTarget =
      await this.ctx.fs.resolve(
        input.pluginEntryPath,
        {
          ...(signal !== undefined
            ? { signal }
            : {}),
        },
      )

    const entryInfo =
      await this.ctx.fs.stat(
        entryTarget,
        signal,
      )

    if (entryInfo === undefined) {
      throw new Error(
        [
          'Engineering verification failed.',
          `Build artifact does not exist: ${input.pluginEntryPath}`,
        ].join(' '),
      )
    }

    return {
      success: true,
      workspacePath:
        input.workspacePath,
      pluginEntryPath:
        input.pluginEntryPath,
      build,
      ...(test !== undefined
        ? {
          test,
        }
        : {}),
    }
  }

  private async runCommand(
    command: string,
    workspacePath: string,
    timeoutMs?: number,
    signal?: AbortSignal,
  ): Promise<CommandVerificationResult> {
    const result =
      await this.ctx.shell.run(
        this.ctx.shell.resolve({
          command,
          workdir:
            workspacePath,

          ...(timeoutMs !== undefined
            ? {
              timeoutMs,
            }
            : {}),

          ...(signal !== undefined
            ? {
              signal,
            }
            : {}),
        }),
      )

    if (result.aborted) {
      throw new Error(
        `Command aborted: ${command}`,
      )
    }

    if (result.timedOut) {
      throw new Error(
        `Command timed out after ${result.timeoutMs}ms: ${command}`,
      )
    }

    return {
      command,
      exitCode:
        result.exitCode,
      stdout:
        result.stdout.text,
      stderr:
        result.stderr.text,
      stdoutTruncated:
        result.stdout.truncated,
      stderrTruncated:
        result.stderr.truncated,
    }
  }

  private assertCommandSucceeded(
    label: string,
    result: CommandVerificationResult,
  ): void {
    if (result.exitCode === 0) {
      return
    }

    throw new Error(
      [
        `${label} failed.`,
        `Command: ${result.command}`,
        `Exit code: ${String(result.exitCode)}`,
        '',
        'stdout:',
        result.stdout,
        '',
        'stderr:',
        result.stderr,
      ].join('\n'),
    )
  }
}

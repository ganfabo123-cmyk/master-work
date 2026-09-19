/**
 * @deepseek-ai/dsh-powershell — approved foreground PowerShell execution for
 * DSH plugins. Host plugins choose which model-facing tool exposes it; this
 * capability owns the permission, timeout, process, and result semantics.
 */

import { Context, Service } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue, ToolRunContext } from '@deepseek-ai/dsh-tools'
import type { ApprovalOutcome } from '@deepseek-ai/dsh-user-approval'
import type {} from '@deepseek-ai/dsh-user-approval'
import { createPowerShellExecutor, POWERSHELL_TIMEOUT_MS } from './executor.js'
import type { PowerShellRequest, PowerShellResult } from './executor.js'

export { createPowerShellExecutor, POWERSHELL_TIMEOUT_MS }
export type { PowerShellExecutor, PowerShellRequest, PowerShellResult } from './executor.js'
const MAX_TIMER_DELAY_MS = 2_147_483_647

interface PowerShellApproval {
  request(input: {
    agent: NonNullable<ToolRunContext['agent']>
    toolName: string
    callId: ToolRunContext['callId']
    reason: string
    signal: AbortSignal
  }): Promise<ApprovalOutcome>
}

declare module '@deepseek-ai/cordis' {
  interface Context {
    powershell: PowerShellService
  }
}

/** `ctx.powershell`: shared implementation behind host-specific PowerShell tools. */
export class PowerShellService extends Service {
  private readonly executor = createPowerShellExecutor()

  constructor(ctx: Context) {
    super(ctx, 'powershell')
  }

  /** Build the compatible user_powershell model tool for a host repository root. */
  createUserPowerShellTool(repositoryRoot: string) {
    return defineTool({
      name: 'user_powershell',
      description: 'Request user approval, then execute one foreground command through the user-started PowerShell bridge.',
      parameters: {
        command: { type: 'string', required: true, description: 'The exact PowerShell command to request.' },
        reason: { type: 'string', required: true, description: 'Why this command is needed and what it is expected to change.' },
        timeoutMs: { type: 'number', description: 'Command timeout in milliseconds. Defaults to 120000 (2 minutes).' },
      },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      execute: async (args, exec) => this.executeToolRequest(args, repositoryRoot, exec),
    })
  }

  async execute(request: PowerShellRequest, exec: ToolRunContext): Promise<PowerShellResult> {
    const approval = this.ctx.get('approval') as PowerShellApproval | undefined
    if (approval === undefined || exec.agent === undefined) {
      return unavailable('permission-unavailable', request, 'No user permission channel is available; the command was not executed.')
    }

    const outcome = await approval.request({
      agent: exec.agent,
      toolName: 'user_powershell',
      callId: exec.callId,
      reason: [
        '模型请求在用户 PowerShell 中执行命令。',
        `命令：${request.command}`,
        `模型 reason：${request.reason}`,
        `cwd：${request.cwd}`,
        `超时：${request.timeoutMs}ms`,
      ].join('\n'),
      signal: exec.signal,
    })
    if (outcome !== 'allowed-once') {
      return unavailable(
        outcome === 'unavailable' ? 'permission-unavailable' : 'permission-rejected',
        request,
        `User permission outcome: ${outcome}. The command was not executed.`,
      )
    }

    try {
      return { status: 'executed', ...request, ...await this.executor.execute(request, exec.signal) }
    } catch (error) {
      return unavailable('bridge-unavailable', request, error instanceof Error ? error.message : String(error))
    }
  }

  private async executeToolRequest(args: { command: string; reason: string; timeoutMs?: number }, repositoryRoot: string, exec: ToolRunContext): Promise<Record<string, JsonValue>> {
    const command = args.command.trim()
    const reason = args.reason.trim()
    const timeoutMs = args.timeoutMs ?? POWERSHELL_TIMEOUT_MS
    if (command.length === 0) throw new Error('command must be non-empty')
    if (reason.length === 0) throw new Error('reason must be non-empty')
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > MAX_TIMER_DELAY_MS) {
      throw new Error(`timeoutMs must be a positive number no greater than ${MAX_TIMER_DELAY_MS}`)
    }
    return JSON.parse(JSON.stringify(await this.execute({ command, reason, cwd: repositoryRoot, timeoutMs }, exec))) as Record<string, JsonValue>
  }
}

function unavailable(status: Exclude<PowerShellResult['status'], 'executed'>, request: PowerShellRequest, stderr: string): PowerShellResult {
  return { status, ...request, stdout: '', stderr, exitCode: null }
}

export const name = 'powershell'
export const inject = ['tools'] as const

export function apply(ctx: Context): void {
  ctx.plugin(PowerShellService)
}

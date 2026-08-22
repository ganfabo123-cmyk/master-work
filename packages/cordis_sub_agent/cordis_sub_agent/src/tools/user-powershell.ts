import { spawn } from 'node:child_process'
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue, ToolRunContext } from '@deepseek-ai/dsh-tools'
import type { ApprovalOutcome } from '@deepseek-ai/dsh-user-approval'
import type {} from '@deepseek-ai/dsh-user-approval'

export interface UserPowerShellRequest {
  command: string
  reason: string
  cwd: string
}

export interface UserPowerShellResult {
  status: 'executed' | 'permission-rejected' | 'permission-unavailable' | 'bridge-unavailable'
  command: string
  reason: string
  cwd: string
  stdout: string
  stderr: string
  exitCode: number | null
}

export interface UserPowerShellExecutor {
  execute(request: UserPowerShellRequest, signal: AbortSignal): Promise<Pick<UserPowerShellResult, 'stdout' | 'stderr' | 'exitCode'>>
}

export interface UserPowerShellApproval {
  request(input: {
    agent: NonNullable<ToolRunContext['agent']>
    toolName: string
    callId: ToolRunContext['callId']
    reason: string
    signal: AbortSignal
  }): Promise<ApprovalOutcome>
}

export async function executeUserPowerShellRequest(
  request: UserPowerShellRequest,
  exec: ToolRunContext,
  approval: UserPowerShellApproval | undefined,
  executor: UserPowerShellExecutor,
): Promise<UserPowerShellResult> {
  if (approval === undefined || exec.agent === undefined) {
    return {
      status: 'permission-unavailable',
      ...request,
      stdout: '',
      stderr: 'No user permission channel is available; the command was not executed.',
      exitCode: null,
    }
  }

  const approvalReason = [
    '模型请求在用户 PowerShell 中执行命令。',
    `命令：${request.command}`,
    `模型 reason：${request.reason}`,
    `cwd：${request.cwd}`,
  ].join('\n')

  const outcome = await approval.request({
    agent: exec.agent,
    toolName: 'user_powershell',
    callId: exec.callId,
    reason: approvalReason,
    signal: exec.signal,
  })

  if (outcome !== 'allowed-once') {
    return {
      status: outcome === 'unavailable' ? 'permission-unavailable' : 'permission-rejected',
      ...request,
      stdout: '',
      stderr: `User permission outcome: ${outcome}. The command was not executed.`,
      exitCode: null,
    }
  }

  try {
    const result = await executor.execute(request, exec.signal)
    return { status: 'executed', ...request, ...result }
  } catch (error) {
    return {
      status: 'bridge-unavailable',
      ...request,
      stdout: '',
      stderr: error instanceof Error ? error.message : String(error),
      exitCode: null,
    }
  }
}

export function createUserPowerShellExecutor(): UserPowerShellExecutor {
  return {
    async execute(request, signal) {
      if (signal.aborted) throw new Error('PowerShell command was aborted before it started')
      return await new Promise((resolve, reject) => {
        const child = spawn(
          'powershell.exe',
          ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', request.command],
          {
            cwd: request.cwd,
            env: { ...process.env },
            windowsHide: true,
            stdio: ['ignore', 'pipe', 'pipe'],
          },
        )
        let stdout = ''
        let stderr = ''
        let settled = false
        const timeout = setTimeout(() => {
          if (settled) return
          stderr += '\nPowerShell command timed out after 10 minutes.'
          child.kill()
        }, 10 * 60 * 1000)
        const abort = () => {
          if (!settled) child.kill()
        }
        signal.addEventListener('abort', abort, { once: true })
        child.stdout.on('data', chunk => { stdout += String(chunk) })
        child.stderr.on('data', chunk => { stderr += String(chunk) })
        child.once('error', error => {
          settled = true
          clearTimeout(timeout)
          signal.removeEventListener('abort', abort)
          reject(error)
        })
        child.once('close', exitCode => {
          settled = true
          clearTimeout(timeout)
          signal.removeEventListener('abort', abort)
          resolve({ stdout, stderr, exitCode })
        })
      })
    },
  }
}

export function userPowerShellTool(ctx: Context, repositoryRoot: string) {
  const executor = createUserPowerShellExecutor()
  return defineTool({
    name: 'user_powershell',
    description: 'Request user approval, then execute one foreground command through the user-started PowerShell bridge.',
    parameters: {
      command: { type: 'string', required: true, description: 'The exact PowerShell command to request.' },
      reason: { type: 'string', required: true, description: 'Why this command is needed and what it is expected to change.' },
    },
    output: {
      schema: { type: 'object', additionalProperties: true },
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
    },
    async execute(args, exec) {
      const command = args.command.trim()
      const reason = args.reason.trim()
      if (command.length === 0) throw new Error('command must be non-empty')
      if (reason.length === 0) throw new Error('reason must be non-empty')
      const result = await executeUserPowerShellRequest(
        { command, reason, cwd: repositoryRoot },
        exec,
        ctx.get('approval'),
        executor,
      )
      return JSON.parse(JSON.stringify(result)) as Record<string, JsonValue>
    },
  })
}

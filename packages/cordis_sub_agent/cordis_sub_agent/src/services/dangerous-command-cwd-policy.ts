import { resolve } from 'node:path'
import type { ToolExecution, ToolGuard } from '@deepseek-ai/dsh-tools'

const SHELL_TOOLS = new Set(['bash', 'pwsh'])
const IRREVERSIBLE_COMMANDS: Array<{ label: string; pattern: RegExp }> = [
  {
    label: '依赖安装或依赖树变更',
    pattern: /(?:^|[;&|])\s*(?:corepack\s+)?(?:pnpm(?:\.cmd)?|npm(?:\.cmd)?|yarn|bun(?:\.exe)?)\s+(?:install|i|add|remove|rm|uninstall|update|up|prune|rebuild|link|unlink|dedupe|publish)\b/i,
  },
  {
    label: '文件或目录删除、移动、覆盖',
    pattern: /(?:^|[;&|])\s*(?:rm|rmdir|del|erase|Remove-Item|Move-Item|move|Rename-Item|rename|shred)\b|(?:^|\s)(?:> |>> )/i,
  },
  {
    label: 'Git 工作区或历史破坏',
    pattern: /(?:^|[;&|])\s*git\s+(?:reset|clean|restore|checkout|rebase|commit|push|tag|branch\s+(?:-D|--delete))\b/i,
  },
  {
    label: '远程发布或推送',
    pattern: /(?:^|[;&|])\s*(?:docker\s+push|podman\s+push|twine\s+upload|git\s+push)\b/i,
  },
]

export interface DangerousCommandCwdCheckInput {
  toolName: string
  argumentsValue: unknown
  sessionCwd?: string
  repositoryRoot: string
  worktreeRoots: readonly string[]
}

export function dangerousCommandCwdReason(
  input: DangerousCommandCwdCheckInput,
): string | undefined {
  if (!SHELL_TOOLS.has(input.toolName)) return undefined

  const args = asRecord(input.argumentsValue)
  const command = typeof args.command === 'string' ? args.command : undefined
  if (command === undefined) return undefined

  const matched = IRREVERSIBLE_COMMANDS.find(item => item.pattern.test(command))
  if (matched === undefined) return undefined

  const dshRoot = resolve(input.repositoryRoot)

  return [
    'IRREVERSIBLE_COMMAND_REJECTED',
    `已阻止模型执行不可逆或高风险操作（${matched.label}）：${command}`,
    '模型不能代替用户执行此命令，也不能自行重试、后台重跑或改用另一个 shell 工具。',
    `请让用户在自己的 PowerShell 中，在当前正在运行 DSH 的项目根目录执行：${dshRoot}`,
    `用户可执行：Set-Location -LiteralPath "${dshRoot}"，然后运行上述命令。`,
    '本次命令尚未启动，依赖、文件、Git 历史或远程状态没有被本次调用修改。',
  ].join('\n')
}

export function createDangerousCommandGuard(repositoryRoot: string): ToolGuard {
  return (execution: Readonly<ToolExecution>) => {
    const sessionCwd = execution.agent?.session.header.cwd
    return dangerousCommandCwdReason({
      toolName: execution.name,
      argumentsValue: execution.arguments,
      ...(sessionCwd === undefined ? {} : { sessionCwd }),
      repositoryRoot,
      worktreeRoots: [],
    })
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null
    ? value as Record<string, unknown>
    : {}
}

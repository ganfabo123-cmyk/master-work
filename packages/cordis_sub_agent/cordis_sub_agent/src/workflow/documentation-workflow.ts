import type { Agent } from '@deepseek-ai/dsh-agent'
import type { ContentBlock } from '@deepseek-ai/dsh-llm'
import { relative } from 'node:path'
import type { Context } from '@deepseek-ai/cordis'
import type { DocumentationEvidence } from '../models/documentation-evidence.js'
import { DOCUMENTATION_ROLE, DOCUMENTATION_TOOLS } from './agent-roles.js'

export interface DocumentationWorkflowInput {
  requirementMetadata: unknown
  workspacePath: string
  repositoryPath: string
}

export interface DocumentationWorkflowOptions {
  parent: Agent
  signal: AbortSignal
  provider?: string
  pairingCommand?: string
  docSyncCommand?: string
}

export class DocumentationWorkflow {
  constructor(private readonly ctx: Context) {}

  async run(input: DocumentationWorkflowInput, options: DocumentationWorkflowOptions): Promise<DocumentationEvidence> {
    const before = await this.status(input.workspacePath, input.repositoryPath, options.signal)
    const provider = this.resolveProvider(options.provider)
    const run = await this.ctx.subagents.start(provider, {
      persona: DOCUMENTATION_ROLE,
      prompt: [{ type: 'text', text: [
        `Assigned pluginRoot (and cwd): ${input.workspacePath}`,
        `Submitted requirement metadata:\n${JSON.stringify(input.requirementMetadata, null, 2)}`,
        '',
        'Read the actual source, package manifest, tools, tests, build results, and repository documentation rules.',
        'Update only README.md, README.zh.md, and README.i18n.yaml inside pluginRoot.',
        'Do not edit business source, scripts, tests, package configuration, root configuration, or generated root documentation.',
        'Run the requested foreground documentation checks after writing. Report complete command output.',
      ].join('\n') }],
      parent: options.parent,
      signal: options.signal,
      toolFilter: { allow: DOCUMENTATION_TOOLS },
    })
    let output: ContentBlock[]
    try {
      const result = await run.result
      if (result.stopReason !== 'completed') throw new Error(`Documentation Agent stopped with reason ${result.stopReason}`)
      output = result.output
    } finally {
      await run.dispose()
    }

    const after = await this.status(input.workspacePath, input.repositoryPath, options.signal)
    const changedFiles = [...after].filter(file => !before.has(file))
    const allowed = new Set(['README.md', 'README.zh.md', 'README.i18n.yaml'])
    const outOfScopeFiles = changedFiles.filter(file => !allowed.has(file))
    const commands: string[] = []
    const pairPath = `${relative(input.repositoryPath, input.workspacePath).replaceAll('\\', '/')}/README.md`
    const pairing = await this.command(options.pairingCommand ?? `pnpm run verify-translation-pairing ${pairPath}`, input.repositoryPath, options.signal)
    commands.push(pairing.command)
    const docSync = options.docSyncCommand === undefined
      ? undefined
      : await this.command(options.docSyncCommand, input.repositoryPath, options.signal)
    if (docSync !== undefined) commands.push(docSync.command)
    const unresolved = [
      ...(outOfScopeFiles.length > 0 ? [`Documentation Agent changed out-of-scope files: ${outOfScopeFiles.join(', ')}`] : []),
      ...(pairing.exitCode === 0 ? [] : ['Translation pairing failed.']),
      ...(docSync === undefined || docSync.exitCode === 0 ? [] : ['Documentation check failed.']),
    ]
    const sourceFilesRead = JSON.stringify(output).match(/(?:[A-Za-z]:\\|\.\/|packages\/)[^\s`"]+/g) ?? []
    return { changedFiles, sourceFilesRead, commands, pairing, ...(docSync !== undefined ? { docSync } : {}), outOfScopeFiles, unresolved }
  }

  private async status(workspacePath: string, repositoryPath: string, signal: AbortSignal): Promise<Set<string>> {
    const result = await this.ctx.shell.run(this.ctx.shell.resolve({ command: 'git status --short --untracked-files=all', workdir: workspacePath, signal }))
    if (result.exitCode !== 0) throw new Error(`Unable to inspect documentation changes: ${result.stderr.text}`)
    const prefix = `${relative(repositoryPath, workspacePath).replaceAll('\\', '/')}/`
    return new Set(result.stdout.text.split(/\r?\n/).filter(Boolean).map((line) => {
      const file = line.slice(3).replace(/^"|"$/g, '').replaceAll('\\', '/')
      return file.startsWith(prefix) ? file.slice(prefix.length) : file
    }))
  }

  private async command(command: string, workdir: string, signal: AbortSignal) {
    const result = await this.ctx.shell.run(this.ctx.shell.resolve({ command, workdir, signal }))
    return {
      command,
      exitCode: result.exitCode,
      stdout: result.stdout.text,
      stderr: result.stderr.text,
      stdoutTruncated: result.stdout.truncated,
      stderrTruncated: result.stderr.truncated,
    }
  }

  private resolveProvider(preferred?: string): string {
    for (const name of [preferred, 'spawn', 'fork'].filter((value): value is string => value !== undefined)) {
      const provider = this.ctx.subagents.getProvider(name)
      if (provider?.capabilities.toolFilter) return name
    }
    throw new Error('Documentation workflow requires a subagent provider with toolFilter capability.')
  }
}

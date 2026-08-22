import type { Agent } from '@deepseek-ai/dsh-agent'
import type { ContentBlock } from '@deepseek-ai/dsh-llm'
import { relative } from 'node:path'
import type { Context } from '@deepseek-ai/cordis'
import type { DocumentationEvidence } from '../models/documentation-evidence.js'
import { TRANSLATE_README_ROLE, TRANSLATE_README_TOOLS } from './agent-roles.js'

export interface DocumentationWorkflowInput {
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
      label: 'translate_readme_agent',
      persona: TRANSLATE_README_ROLE,
      prompt: [{ type: 'text', text: [
        `Assigned pluginRoot (and cwd): ${input.workspacePath}`,
        `English README source: ${input.workspacePath}/README.md`,
        `Chinese README target: ${input.workspacePath}/README.zh.md`,
        '',
        'Read only README.md as the translation source.',
        'Write only README.zh.md as the Simplified Chinese translation.',
        'Do not edit README.md, README.i18n.yaml, business source, scripts, tests, package configuration, or repository-root files.',
        'Do not run commands. The parent document_development tool will generate README.i18n.yaml after this translation completes.',
      ].join('\n') }],
      parent: options.parent,
      signal: options.signal,
      toolFilter: { allow: TRANSLATE_README_TOOLS },
    })
    let output: ContentBlock[]
    try {
      const result = await run.result
      if (result.stopReason !== 'completed') throw new Error(`translate_readme_agent stopped with reason ${result.stopReason}`)
      output = result.output
    } finally {
      await run.dispose()
    }

    const afterTranslation = await this.status(input.workspacePath, input.repositoryPath, options.signal)
    const translatedFiles = [...afterTranslation].filter(file => !before.has(file))
    const translatorAllowed = new Set(['README.zh.md'])
    const outOfScopeFiles = translatedFiles.filter(file => !translatorAllowed.has(file))
    const commands: string[] = []
    const pairPath = `${relative(input.repositoryPath, input.workspacePath).replaceAll('\\', '/')}/README.md`
    const pairing = await this.command(options.pairingCommand ?? `pnpm run verify-translation-pairing --write ${pairPath}`, input.repositoryPath, options.signal)
    commands.push(pairing.command)
    const docSync = options.docSyncCommand === undefined
      ? undefined
      : await this.command(options.docSyncCommand, input.repositoryPath, options.signal)
    if (docSync !== undefined) commands.push(docSync.command)
    const after = await this.status(input.workspacePath, input.repositoryPath, options.signal)
    const changedFiles = [...after].filter(file => !before.has(file))
    const unresolved = [
      ...(outOfScopeFiles.length > 0 ? [`translate_readme_agent changed out-of-scope files: ${outOfScopeFiles.join(', ')}`] : []),
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
    throw new Error('translate_readme_agent requires a subagent provider with toolFilter capability.')
  }
}

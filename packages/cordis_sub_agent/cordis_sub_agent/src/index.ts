import type { Context } from '@deepseek-ai/cordis'

import {
  Config,
  type Config as PluginConfig,
} from './config.js'

import { readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import type {} from '@deepseek-ai/dsh-skill'

import {
  AcceptanceService,
} from './services/acceptance-service.js'

import {
  EngineeringVerificationService,
} from './services/engineering-verification-service.js'
import { DocumentationWorkflow } from './workflow/documentation-workflow.js'

import {
  createPluginTool,
} from './tools/create-plugin.js'

import {
  startAcceptanceTool,
} from './tools/start-acceptance.js'

import {
  sendAcceptanceMessageTool,
} from './tools/send-acceptance-message.js'

import {
  stopAcceptanceTool,
} from './tools/stop-acceptance.js'

import { getTaskStatusTool } from './tools/get-task-status.js'
import { discardDevelopmentTool } from './tools/discard-development.js'
import { verifyDevelopmentTool } from './tools/verify-development.js'
import { documentDevelopmentTool } from './tools/document-development.js'
import { ReaderConclusionStore, readerConclusionTool } from './tools/reader-conclusion.js'
import { submitPluginMetadataTool } from './tools/submit-plugin-metadata.js'
import { PluginMetadataTaskStore } from './services/plugin-metadata-task-store.js'
import { PluginMetadataReadWorkflow } from './workflow/plugin-metadata-read-workflow.js'


export const name =
  'cordis-sub-agent'


export const inject = [
  'fs',
  'shell',
  'subagents',
  'skills',
  'tools',
] as const


export { Config }

export function apply(
  ctx: Context,
  config: PluginConfig,
): void {
  const acceptance =
    new AcceptanceService()

  const verification =
    new EngineeringVerificationService(ctx)

  const documentation =
    new DocumentationWorkflow(ctx)

  const readerConclusions = new ReaderConclusionStore()

  const metadataTasks = new PluginMetadataTaskStore(
    join(resolve(config.repoRoot), 'packages', 'generated'),
  )

  const metadataReader =
    new PluginMetadataReadWorkflow(
      ctx,
      readerConclusions,
      resolve(config.repoRoot),
    )

  /*
   * Tool registrations.
   *
   * Register them inside one Cordis effect so all tool
   * registrations are removed automatically on unload/HMR.
   */
  ctx.effect(() => {
    const disposers = [
      ctx.tools.register(
        createPluginTool(metadataTasks, metadataReader),
      ),

      ctx.tools.register(
        startAcceptanceTool(
          acceptance,
          metadataTasks,
          {
            repoRoot:
              resolve(config.repoRoot),

            provider:
              config.acceptanceProvider,

            model:
              config.acceptanceModel,

            ...(config.acceptanceMaxTokens !== undefined
              ? {
                maxTokens:
                    config.acceptanceMaxTokens,
              }
              : {}),
          },
        ),
      ),

      ctx.tools.register(
        sendAcceptanceMessageTool(
          acceptance,
        ),
      ),

      ctx.tools.register(
        stopAcceptanceTool(
          acceptance,
          metadataTasks,
        ),
      ),

      ctx.tools.register(getTaskStatusTool(metadataTasks)),
      ctx.tools.register(discardDevelopmentTool(metadataTasks, acceptance)),
      ctx.tools.register(documentDevelopmentTool(
        metadataTasks,
        documentation,
        resolve(config.repoRoot),
      )),
      ctx.tools.register(verifyDevelopmentTool(
        metadataTasks,
        verification,
        {
          repositoryPath: resolve(config.repoRoot),
          ...(config.engineeringTypecheckCommand !== undefined ? { typecheckCommand: config.engineeringTypecheckCommand } : {}),
          ...(config.engineeringBuildCommand !== undefined ? { buildCommand: config.engineeringBuildCommand } : {}),
          ...(config.engineeringTestCommand !== undefined ? { testCommand: config.engineeringTestCommand } : {}),
          ...(config.engineeringDocSyncCommand !== undefined ? { docSyncCommand: config.engineeringDocSyncCommand } : {}),
          ...(config.engineeringTimeoutMs !== undefined ? { timeoutMs: config.engineeringTimeoutMs } : {}),
        },
      )),
      ctx.tools.register(readerConclusionTool(readerConclusions)),
      ctx.tools.register(submitPluginMetadataTool(metadataTasks)),
    ]

    return () => {
      for (const dispose of disposers) {
        dispose()
      }
    }
  }, 'cordis-sub-agent tools')

  /*
   * Skill registration.
   */
  const currentFile =
    fileURLToPath(import.meta.url)

  const currentDir =
    dirname(currentFile)

  const skillDir =
    join(
      currentDir,
      '../skills/dsh-plugin-development',
    )

  const skillPath =
    join(
      skillDir,
      'SKILL.md',
    )

  const rawSkill =
    readFileSync(
      skillPath,
      'utf8',
    )

  const parsedSkill =
    parseSkillMarkdown(
      rawSkill,
    )

  ctx.effect(() => {
    const disposeSkill =
      ctx.skills.register({
        name:
          parsedSkill.name,

        description:
          parsedSkill.description,

        content:
          parsedSkill.content,

        source:
          'runtime',

        resourceBase: {
          kind: 'directory',
          path: skillDir,
        },
      })

    return () => {
      disposeSkill()
    }
  }, 'cordis-sub-agent skill')

  /*
   * AcceptanceService owns child DSH subprocesses.
   *
   * Cordis unload/HMR must shut all of them down.
   */
  ctx.effect(
    () => async () => {
      await acceptance.dispose()
    },
    'cordis-sub-agent acceptance cleanup',
  )
}

interface ParsedSkill {
  name: string
  description: string
  content: string
}

function parseSkillMarkdown(
  raw: string,
): ParsedSkill {
  const match =
    raw.match(
      /^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/,
    )

  if (match === null) {
    throw new Error(
      'Invalid SKILL.md: missing YAML frontmatter.',
    )
  }

  const frontmatter =
    match[1]

  const body =
    match[2]

  if (
    frontmatter === undefined ||
    body === undefined
  ) {
    throw new Error(
      'Invalid SKILL.md: malformed frontmatter.',
    )
  }

  const content =
    body.trim()

  const name =
    frontmatter.match(
      /^name:\s*(.+)$/m,
    )?.[1]?.trim()

  const description =
    frontmatter.match(
      /^description:\s*(.+)$/m,
    )?.[1]?.trim()

  if (
    name === undefined ||
    name.length === 0
  ) {
    throw new Error(
      'Invalid SKILL.md: missing name.',
    )
  }

  if (
    description === undefined ||
    description.length === 0
  ) {
    throw new Error(
      'Invalid SKILL.md: missing description.',
    )
  }

  if (content.length === 0) {
    throw new Error(
      'Invalid SKILL.md: empty content.',
    )
  }

  return {
    name,
    description,
    content,
  }
}

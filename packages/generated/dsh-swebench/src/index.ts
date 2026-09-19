/**
 * @deepseek-ai/dsh-swebench — encapsulates the local SWE-bench Lite cases'
 * Docker runtime environments behind three high-level tools plus a workflow
 * skill, so a tracing agent (cotracer) works against the cases as if they
 * were a local execution environment: read/edit the host case repo with
 * ordinary fs tools, `swb_run` any command or model-written test script in
 * the real case environment, and `swb_eval` the official black-box
 * FAIL_TO_PASS / PASS_TO_PASS verdict. Docker specifics (image tags, bind
 * mounts, throwaway `--rm` containers, conda activation, `git apply
 * --no-index`, CRLF defense) are fully internal.
 * @module @deepseek-ai/dsh-swebench
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Context } from '@deepseek-ai/cordis'
import z from '@deepseek-ai/schemastery'
// Side-effect type imports: activate the `ctx.skills` and `ctx.subprocess`
// declaration merges.
import type {} from '@deepseek-ai/dsh-skill'
import type {} from '@deepseek-ai/dsh-subprocess'
import { loadCaseRegistry } from './cases.js'
import { evalTool, listCasesTool, runTool } from './tools.js'

export const name = 'swebench'
export const inject = ['tools', 'subprocess', 'skills'] as const

/** Plugin configuration. */
export interface Config {
  /**
   * Absolute path of the swe-bench-lite-10 root directory holding
   * `manifest.json`, `cases/`, and the per-case repos (default
   * `D:\PycharmProjects\CodeHarness\github_rep\swe-bench-lite-10`).
   */
  casesRoot: string
}

export const Config: z<Config> = z.object({
  casesRoot: z
    .string()
    .default('D:\\PycharmProjects\\CodeHarness\\github_rep\\swe-bench-lite-10'),
})

/** Frontmatter-parsed skill metadata (name/description/body). */
interface ParsedSkill {
  name: string
  description: string
  content: string
}

/** Parse SKILL.md frontmatter (name/description) followed by the markdown body. */
function parseSkillMarkdown(raw: string): ParsedSkill {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/)
  if (match === null) {
    throw new Error('Invalid SKILL.md: missing YAML frontmatter.')
  }
  const frontmatter = match[1]
  const body = match[2]
  if (frontmatter === undefined || body === undefined) {
    throw new Error('Invalid SKILL.md: malformed frontmatter.')
  }
  const content = body.trim()
  const skillName = frontmatter.match(/^name:\s*(.+)$/m)?.[1]?.trim()
  const description = frontmatter.match(/^description:\s*(.+)$/m)?.[1]?.trim()
  if (skillName === undefined || skillName.length === 0) {
    throw new Error('Invalid SKILL.md: missing name.')
  }
  if (description === undefined || description.length === 0) {
    throw new Error('Invalid SKILL.md: missing description.')
  }
  if (content.length === 0) {
    throw new Error('Invalid SKILL.md: empty content.')
  }
  return { name: skillName, description, content }
}

/**
 * Register the case registry factory, the three tools, and the swe-bench
 * workflow skill. The registry is rebuilt on every tool call (the manifest is
 * small and can change between calls), so a configuration fix or an updated
 * case set takes effect without a plugin reload.
 * @param ctx - Cordis context with tools, subprocess, and skills services.
 * @param config - plugin configuration.
 */
export function apply(ctx: Context, config: Config): void {
  const registry = () => loadCaseRegistry(config.casesRoot)
  const currentFile = fileURLToPath(import.meta.url)
  const currentDir = dirname(currentFile)
  const skillDir = join(currentDir, '../skills/swe-bench')
  const skillPath = join(skillDir, 'SKILL.md')
  const parsed = parseSkillMarkdown(readFileSync(skillPath, 'utf8'))

  ctx.effect(() => {
    const disposers = [
      ctx.tools.register(listCasesTool(ctx, registry)),
      ctx.tools.register(runTool(ctx, registry)),
      ctx.tools.register(evalTool(ctx, registry)),
      ctx.skills.register({
        name: parsed.name,
        description: parsed.description,
        content: parsed.content,
        source: 'runtime',
        resourceBase: { kind: 'directory', path: skillDir },
      }),
    ]
    return () => {
      for (const dispose of disposers) {
        dispose()
      }
    }
  }, 'swebench tools and skill')
}

/**
 * @deepseek-ai/dsh-cotracer — hypothesis-driven multi-agent debugging
 * (trace) orchestration. The plugin registers one skill (`cotracer-trace`)
 * that describes the full trace process, and its cordis.yml composition loads
 * the three infrastructure plugins beside it — `dsh-explorer-agent`
 * (read-only repo exploration), `dsh-experiment-state` (shared experiment
 * tree, with the `executor` parameter that can hand an experiment to a
 * Detector subagent automatically), and `dsh-detector` (the investigation
 * subagent plus the shared `experimentExecutor` service). The main agent runs
 * the skill with the composed tool set; the plugin itself owns no tools.
 * @module @deepseek-ai/dsh-cotracer
 */

import type { Context } from '@deepseek-ai/cordis'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
// Side-effect type imports: activate the `ctx.skills` declaration merge.
import type {} from '@deepseek-ai/dsh-skill'

export const name = 'cotracer'
export const inject = ['skills'] as const

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
 * Register the trace skill from this package's skills directory. The skill
 * directory travels beside the built entry, so resource-relative references
 * inside the skill resolve against it.
 * @param ctx - Cordis context with the skills service.
 */
export function apply(ctx: Context): void {
  const currentFile = fileURLToPath(import.meta.url)
  const currentDir = dirname(currentFile)
  const skillDir = join(currentDir, '../skills/dsh-cotracer')
  const skillPath = join(skillDir, 'SKILL.md')
  const parsed = parseSkillMarkdown(readFileSync(skillPath, 'utf8'))

  ctx.effect(() => {
    const dispose = ctx.skills.register({
      name: parsed.name,
      description: parsed.description,
      content: parsed.content,
      source: 'runtime',
      resourceBase: { kind: 'directory', path: skillDir },
    })
    return () => dispose()
  }, 'cotracer trace skill')
}

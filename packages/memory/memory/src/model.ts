/**
 * Model-facing experience templates and result formatting.
 *
 * @module @deepseek-ai/dsh-memory/model
 */

import type { FactMemory } from './fact.ts'
import type { ExperienceMemory } from './memory.ts'
import type { MemorySearchCandidate } from './service.ts'

/** Recommended structure for a reusable experience body. */
export const EXPERIENCE_BODY_TEMPLATE = `## Context

Describe the task and relevant environment.

## Problem

Describe the problem or unexpected behavior.

## Attempts

Describe attempted approaches and their outcomes.

## Resolution

Describe the adopted resolution when one exists.

## Lesson

State the transferable lesson for future tasks.`

/**
 * Render lightweight candidates without exposing internal ranking signals.
 * @param candidates - selected search candidates in presentation order.
 * @returns model-facing candidate metadata.
 */
export function formatSearchCandidates(candidates: readonly MemorySearchCandidate[]): string {
  if (candidates.length === 0) return 'No candidate memories matched the supplied keywords.'
  return candidates.map(candidate => [
    `[${candidate.id}]`,
    `title: ${candidate.title}`,
    `keywords: ${candidate.keywords.join(', ')}`,
    `matched keywords: ${candidate.matchedKeywords.join(', ')}`,
    `outcome: ${candidate.outcome}`,
  ].join('\n')).join('\n\n')
}

/**
 * Render one complete experience for model use.
 * @param memory - durable experience selected by id.
 * @returns model-facing metadata and complete body.
 */
export function formatExperience(memory: ExperienceMemory): string {
  return [
    `# ${memory.title} {${memory.id}}`,
    '',
    `Keywords: ${memory.keywords.join(', ')}`,
    `Recorded At: ${memory.recordedAt}`,
    `Outcome: ${memory.outcome}`,
    '',
    memory.body,
  ].join('\n')
}

/**
 * Render the injected per-cwd facts the model should treat as known context.
 * Facts are stable key/value pairs the user or the model deliberately saved for
 * this working directory; they are not retrieval candidates and are not stale
 * few-shot — each is asserted as a current fact for this cwd.
 * @param facts - durable cwd-scoped facts in file order.
 * @returns the injected system-prompt fact block, or `''` when there are none.
 */
export function formatFactSection(facts: readonly FactMemory[]): string {
  if (facts.length === 0) return ''
  const lines = facts.map(fact => `${fact.key}: ${fact.value}`)
  return 'Remembered facts for this working directory (saved by the user or the model; treat them as known, current facts unless contradicted by the user):\n' + lines.join('\n')
}

/**
 * Case registry of @deepseek-ai/dsh-swebench: loads the local
 * swe-bench-lite-10 manifest (`manifest.json`), derives the official eval
 * image tag from each instance id, and classifies the test runner (pytest for
 * Astropy, Django's runtests.py for Django). Pure data access — no Docker or
 * network I/O happens here, so every tool can use the registry.
 * @module @deepseek-ai/dsh-swebench/cases
 */

import { readFileSync } from 'node:fs'
import { join } from 'node:path'

/** One manifest entry for a local SWE-bench Lite case. */
export interface SwebenchCase {
  /** Dataset instance id, e.g. `astropy__astropy-12907`. */
  instance_id: string
  /** Absolute host path of the checked-out case repository (worktree). */
  repo_path: string
  /** Absolute host path of the issue statement markdown file. */
  issue_statement_path: string
  /** Base commit the case repository is checked out at. */
  base_commit: string
}

/** Test runner vocabulary of the official eval images. */
export type CaseRunner = 'pytest' | 'runtests'

/** One case plus its derived environment facts. */
export interface CaseEnvironment {
  case: SwebenchCase
  /** Full local eval image tag, e.g. `swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest`. */
  imageTag: string
  /** The repo's official test runner. */
  runner: CaseRunner
}

/** The fixed image-prefix protocol of the official SWE-bench eval images. */
export const IMAGE_PREFIX = 'swebench/sweb.eval.x86_64.'
/** The fixed image-tag suffix of the official SWE-bench eval images. */
export const IMAGE_SUFFIX = ':latest'

/**
 * Derive the official eval image tag from an instance id. The public tag
 * replaces the dataset `__` separator with `_1776_`
 * (`astropy__astropy-12907` → `swebench/sweb.eval.x86_64.astropy_1776_astropy-12907:latest`).
 * @param instanceId - dataset instance id.
 * @returns the full image tag.
 */
export function imageTagForInstance(instanceId: string): string {
  return `${IMAGE_PREFIX}${instanceId.replace('__', '_1776_')}${IMAGE_SUFFIX}`
}

/**
 * Classify the official test runner from the repo name in an instance id.
 * @param instanceId - dataset instance id (`<repo>__<repo>-<issue>`).
 * @returns the runner vocabulary.
 */
export function runnerForInstance(instanceId: string): CaseRunner {
  return instanceId.startsWith('django') ? 'runtests' : 'pytest'
}

/**
 * Load and index the case manifest under a cases root directory.
 * @param casesRoot - absolute path of the swe-bench-lite-10 root (holds
 *   `manifest.json`).
 * @returns the indexed case environments, keyed by instance id.
 * @throws when the manifest is unreadable or empty.
 */
export function loadCaseRegistry(casesRoot: string): Map<string, CaseEnvironment> {
  const manifestPath = join(casesRoot, 'manifest.json')
  let raw: string
  try {
    raw = readFileSync(manifestPath, 'utf8')
  } catch (error: unknown) {
    throw new Error(`swb: cannot read case manifest at ${manifestPath} (${error instanceof Error ? error.message : String(error)})`)
  }
  let entries: SwebenchCase[]
  try {
    // The benchmark manifest is written by PowerShell with `-Encoding UTF8`,
    // which emits a UTF-8 BOM; strip it so the parse never sees \uFEFF.
    const withoutBom = raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw
    entries = JSON.parse(withoutBom) as SwebenchCase[]
  } catch (error: unknown) {
    throw new Error(`swb: case manifest at ${manifestPath} is not valid JSON (${error instanceof Error ? error.message : String(error)})`)
  }
  if (!Array.isArray(entries) || entries.length === 0) {
    throw new Error(`swb: case manifest at ${manifestPath} contains no cases`)
  }
  const registry = new Map<string, CaseEnvironment>()
  for (const entry of entries) {
    if (typeof entry.instance_id !== 'string' || entry.instance_id.length === 0) {
      throw new Error(`swb: case manifest at ${manifestPath} has an entry without an instance_id`)
    }
    if (typeof entry.repo_path !== 'string' || entry.repo_path.length === 0) {
      throw new Error(`swb: case ${entry.instance_id} in ${manifestPath} has no repo_path`)
    }
    registry.set(entry.instance_id, {
      case: entry,
      imageTag: imageTagForInstance(entry.instance_id),
      runner: runnerForInstance(entry.instance_id),
    })
  }
  return registry
}

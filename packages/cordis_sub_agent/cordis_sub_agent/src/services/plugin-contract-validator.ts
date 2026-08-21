import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import type { ArtifactEvidence } from '../models/test-evidence.js'

export interface PluginContract {
  packageName: string
  buildCommand: string
  typecheckCommand: string
  testCommand?: string
}

export class PluginContractValidator {
  documentationChecks(workspacePath: string): { id: string; passed: boolean; evidence: string }[] {
    const checks = [
      ['readme-en', join(workspacePath, 'README.md'), 'README.md'],
      ['readme-zh', join(workspacePath, 'README.zh.md'), 'README.zh.md'],
      ['readme-i18n', join(workspacePath, 'README.i18n.yaml'), 'README.i18n.yaml'],
    ] as const
    const result: { id: string; passed: boolean; evidence: string }[] = checks.map(([id, path, label]) => ({
      id,
      passed: existsSync(path),
      evidence: existsSync(path) ? `${label} exists.` : `${label} does not exist.`,
    }))
    const readmePath = join(workspacePath, 'README.md')
    const english = existsSync(readmePath) ? readFileSync(readmePath, 'utf8') : ''
    const zhPath = join(workspacePath, 'README.zh.md')
    const chinese = existsSync(zhPath) ? readFileSync(zhPath, 'utf8') : ''
    const hasLimitations = english.includes('## Known Limitations and Deferred Work')
    result.push({ id: 'known-limitations', passed: hasLimitations, evidence: hasLimitations ? 'Known limitations section exists.' : 'Known limitations section is missing.' })
    const modelExperience = english.includes('## Model Experience') && (chinese.includes('## Model Experience') || chinese.includes('## 模型体验'))
    result.push({ id: 'model-experience', passed: modelExperience, evidence: modelExperience ? 'Model Experience sections exist.' : 'Model Experience sections are missing.' })
    result.push({ id: 'language-switchers', passed: english.includes('README.zh.md') && chinese.includes('README.md'), evidence: english.includes('README.zh.md') && chinese.includes('README.md') ? 'Language switchers exist.' : 'Language switchers are missing.' })
    return result
  }

  inspect(workspacePath: string, expectedPluginName: string): {
    contract?: PluginContract
    artifact: ArtifactEvidence
    checks: { id: string; passed: boolean; evidence: string }[]
  } {
    const packagePath = join(workspacePath, 'package.json')
    const entryPath = join(workspacePath, 'lib', 'index.js')
    const typesPath = join(workspacePath, 'lib', 'index.d.ts')
    const checks: { id: string; passed: boolean; evidence: string }[] = []
    const errors: string[] = []
    if (!existsSync(packagePath)) {
      errors.push('package.json does not exist')
      return { artifact: this.artifact(packagePath, entryPath, typesPath, expectedPluginName, errors), checks: [{ id: 'package-json', passed: false, evidence: errors.join('; ') }] }
    }

    let manifest: Record<string, unknown>
    try {
      manifest = JSON.parse(readFileSync(packagePath, 'utf8')) as Record<string, unknown>
    } catch (error) {
      errors.push(`package.json is invalid: ${errorMessage(error)}`)
      return { artifact: this.artifact(packagePath, entryPath, typesPath, expectedPluginName, errors), checks: [{ id: 'package-json', passed: false, evidence: errors.join('; ') }] }
    }

    const packageName = typeof manifest.name === 'string' ? manifest.name : ''
    const scripts = isRecord(manifest.scripts) ? manifest.scripts : {}
    const main = manifest.main
    const types = manifest.types
    const exports = isRecord(manifest.exports) ? manifest.exports['.'] : undefined
    const exportRecord = isRecord(exports) ? exports : {}
    const expected = [
      ['package-name', packageName === expectedPluginName, `package name: ${packageName || '(missing)'}`],
      ['build-script', typeof scripts.build === 'string', `build script: ${String(scripts.build ?? '(missing)')}`],
      ['main', main === 'lib/index.js', `main: ${String(main ?? '(missing)')}`],
      ['types', types === 'lib/index.d.ts', `types: ${String(types ?? '(missing)')}`],
      ['exports-default', exportRecord.default === './lib/index.js', `exports.default: ${String(exportRecord.default ?? '(missing)')}`],
      ['exports-types', exportRecord.types === './lib/index.d.ts', `exports.types: ${String(exportRecord.types ?? '(missing)')}`],
    ] as const
    for (const [id, passed, evidence] of expected) {
      checks.push({ id, passed, evidence })
      if (!passed) errors.push(evidence)
    }
    const artifact = this.artifact(packagePath, entryPath, typesPath, packageName, errors)
    const contract: PluginContract = {
      packageName,
      buildCommand: 'pnpm build',
      typecheckCommand: 'pnpm exec tsc -b --pretty false',
      ...(typeof scripts.test === 'string' ? { testCommand: 'pnpm test' } : {}),
    }
    return { contract, artifact, checks }
  }

  private artifact(packagePath: string, entryPath: string, typesPath: string, packageName: string, errors: string[]): ArtifactEvidence {
    const entryExists = existsSync(entryPath)
    const typesExists = existsSync(typesPath)
    if (!entryExists) errors.push(`missing artifact: ${entryPath}`)
    if (!typesExists) errors.push(`missing artifact: ${typesPath}`)
    return {
      packagePath,
      entryPath,
      typesPath,
      packageName,
      passed: errors.length === 0 && entryExists && typesExists,
      errors: [...errors],
    }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

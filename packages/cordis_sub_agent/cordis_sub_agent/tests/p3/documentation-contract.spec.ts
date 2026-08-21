import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { PluginContractValidator } from '../../src/services/plugin-contract-validator.js'

describe('P3 documentation contract', () => {
  it('keeps the plugin README triad and required model-facing sections valid', () => {
    const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
    expect(existsSync(resolve(packageRoot, 'README.md'))).toBe(true)
    const checks = new PluginContractValidator().documentationChecks(packageRoot)
    expect(checks).toEqual(expect.arrayContaining([
      expect.objectContaining({ id: 'readme-en', passed: true }),
      expect.objectContaining({ id: 'readme-zh', passed: true }),
      expect.objectContaining({ id: 'readme-i18n', passed: true }),
      expect.objectContaining({ id: 'model-experience', passed: true }),
      expect.objectContaining({ id: 'known-limitations', passed: true }),
      expect.objectContaining({ id: 'language-switchers', passed: true }),
    ]))
  })
})

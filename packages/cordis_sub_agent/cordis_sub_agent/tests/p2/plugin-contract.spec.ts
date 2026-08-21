import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { afterEach, describe, expect, it } from 'vitest'
import { PluginContractValidator } from '../../src/services/plugin-contract-validator.js'

const directories: string[] = []

afterEach(async () => {
  await Promise.all(directories.splice(0).map(directory => rm(directory, { recursive: true, force: true })))
})

describe('PluginContractValidator', () => {
  it('accepts the deterministic package and artifact contract', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'cordis-sub-agent-contract-'))
    directories.push(directory)
    await mkdir(join(directory, 'lib'))
    await writeFile(join(directory, 'package.json'), JSON.stringify({
      name: 'hello-plugin',
      scripts: { build: 'tsc -b' },
      main: 'lib/index.js',
      types: 'lib/index.d.ts',
      exports: { '.': { default: './lib/index.js', types: './lib/index.d.ts' } },
    }))
    await writeFile(join(directory, 'lib', 'index.js'), '')
    await writeFile(join(directory, 'lib', 'index.d.ts'), '')
    await writeFile(join(directory, 'README.md'), 'English | [中文](README.zh.md)\n\n## Model Experience\n\n### Entry\n\n#### What the model sees\n\nA tool.\n\n#### Token effect\n\nSmall.\n\n#### KV Cache effect\n\nStable.\n\n## Known Limitations and Deferred Work\n- One.\n')
    await writeFile(join(directory, 'README.zh.md'), '[English](README.md) | 中文\n\n## Model Experience\n\n### Entry\n\n#### What the model sees\n\n一个工具。\n\n#### Token effect\n\n较小。\n\n#### KV Cache effect\n\n稳定。\n\n## Known Limitations and Deferred Work\n- 一个。\n')
    await writeFile(join(directory, 'README.i18n.yaml'), '')

    const result = new PluginContractValidator().inspect(directory, 'hello-plugin')
    expect(result.artifact.passed).toBe(true)
    expect(result.checks.every(check => check.passed)).toBe(true)
    expect(new PluginContractValidator().documentationChecks(directory).every(check => check.passed)).toBe(true)
  })

  it('reports package contract mismatches', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'cordis-sub-agent-contract-'))
    directories.push(directory)
    await writeFile(join(directory, 'package.json'), JSON.stringify({ name: 'wrong-plugin' }))
    const result = new PluginContractValidator().inspect(directory, 'hello-plugin')
    expect(result.artifact.passed).toBe(false)
    expect(result.checks.some(check => check.id === 'package-name' && !check.passed)).toBe(true)
  })
})

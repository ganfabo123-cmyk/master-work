import { mkdir, mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { afterEach, describe, expect, it } from 'vitest'
import { createPluginScaffold } from '../../src/services/plugin-scaffold.js'
import { PluginMetadataTaskStore } from '../../src/services/plugin-metadata-task-store.js'

const directories: string[] = []

afterEach(async () => {
  await Promise.all(directories.splice(0).map(directory => rm(directory, { recursive: true, force: true })))
})

describe('createPluginScaffold', () => {
  it('creates the common plugin files with TODO placeholders', async () => {
    const root = await mkdtemp(join(tmpdir(), 'cordis-sub-agent-scaffold-'))
    directories.push(root)
    const pluginRoot = join(root, 'packages', 'generated', 'say-hello')
    await mkdir(pluginRoot, { recursive: true })

    const result = await createPluginScaffold(pluginRoot, {
      plugin_name: '@deepseek-ai/dsh-say-hello',
      plugin_description: 'Say hello.',
      input_schema: [],
      output_schema: [],
      brief_execution_flow: { blocks: [], arrows: [] },
      detailed_plugin_document: 'A greeting plugin.',
    })

    expect(result.files).toEqual([
      'package.json',
      'tsconfig.json',
      'src/index.ts',
      'src/invariant.ts',
      'README.md',
    ])
    expect(JSON.parse(await readFile(join(pluginRoot, 'package.json'), 'utf8'))).toEqual({
      _TODO: 'Replace this file with the plugin package manifest before verification.',
    })
    expect(await readFile(join(pluginRoot, 'tsconfig.json'), 'utf8')).toContain('TODO: replace this file')
    expect(await readFile(join(pluginRoot, 'src', 'index.ts'), 'utf8')).toContain('TODO: implement the plugin entry point')
    const invariant = await readFile(join(pluginRoot, 'src', 'invariant.ts'), 'utf8')
    expect(invariant).toContain('TODO: implement this package\'s runtime invariant companion')
    expect(invariant).toContain('No runtime invariant:')
    expect(await readFile(join(pluginRoot, 'README.md'), 'utf8')).toContain('## Model Experience')
    expect(await readFile(join(pluginRoot, 'README.md'), 'utf8')).toContain('## Known Limitations and Deferred Work')
  })

  it('creates the scaffold through the metadata task store', async () => {
    const root = await mkdtemp(join(tmpdir(), 'cordis-sub-agent-task-'))
    directories.push(root)
    const generatedRoot = join(root, 'packages', 'generated')
    await mkdir(generatedRoot, { recursive: true })
    const task = await new PluginMetadataTaskStore(generatedRoot).create('say-hello', {
      plugin_name: 'say-hello',
      plugin_description: 'Say hello.',
      input_schema: [],
      output_schema: [],
      brief_execution_flow: { blocks: [], arrows: [] },
      detailed_plugin_document: 'A greeting plugin.',
    })

    expect(await readFile(join(task.pluginRoot, 'package.json'), 'utf8')).toContain('_TODO')
    expect(await readFile(join(task.pluginRoot, 'src', 'index.ts'), 'utf8')).toContain('TODO: implement the plugin entry point')
  })
})

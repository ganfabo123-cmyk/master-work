import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import type { PluginMetadata } from './plugin-metadata-task-store.js'

export interface PluginScaffoldResult {
  files: string[]
}

/** Create the common files that a generated plugin needs before implementation. */
export async function createPluginScaffold(
  pluginRoot: string,
  metadata: PluginMetadata,
): Promise<PluginScaffoldResult> {
  await mkdir(join(pluginRoot, 'src'), { recursive: true })
  const files = new Map<string, string>()
  files.set('package.json', packageJson())
  files.set('tsconfig.json', tsconfigJson())
  files.set('src/index.ts', indexSource(metadata.plugin_name))
  files.set('src/invariant.ts', invariantSource(metadata.plugin_name))
  files.set('README.md', readmeSource(metadata.plugin_name, metadata.plugin_description))

  for (const [relativePath, content] of files) {
    await writeFile(join(pluginRoot, relativePath), content, 'utf8')
  }
  return { files: [...files.keys()] }
}

function packageJson(): string {
  return `${JSON.stringify({
    _TODO: 'Replace this file with the plugin package manifest before verification.',
  }, null, 2)}\n`
}

function tsconfigJson(): string {
  return `{
  // TODO: replace this file with the plugin's TypeScript configuration.
}\n`
}

function indexSource(pluginName: string): string {
  void pluginName
  return '// TODO: implement the plugin entry point and choose its actual export form.\n'
}

function invariantSource(pluginName: string): string {
  void pluginName
  return '// TODO: implement this package\'s runtime invariant companion.\n//\n+// This file is not the plugin entry point. It registers checks with\n+// @deepseek-ai/dsh-invariants for package-owned event streams, mutable data\n+// relationships, lifecycle cleanup, or other runtime invariants.\n+//\n+// If this plugin owns no such relationship, keep a valid empty installer and\n+// explain why with a comment containing: No runtime invariant:\n'
}

function readmeSource(pluginName: string, description: string): string {
  return `English | [中文](README.zh.md)\n\n# ${pluginName}\n\n${description}\n\n## Usage\n\n<!-- TODO: document installation and usage. -->\n\n## Model Experience\n\n### Plugin interaction\n\n#### What the model sees\n\n<!-- TODO: describe the exact model-visible inputs, tools, or prompt contribution. -->\n\n#### Token effect\n\n<!-- TODO: describe the token effect. -->\n\n#### KV Cache effect\n\n<!-- TODO: describe cache-prefix behavior. -->\n\n## Known Limitations and Deferred Work\n\n- TODO: document known limitations and deferred work.\n`
}

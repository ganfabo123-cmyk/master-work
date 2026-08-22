import {
  mkdtemp,
  rm,
  writeFile,
} from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

export interface AcceptanceCompositionInput {
  /** Optional built plugin entry for the legacy direct-plugin path. */
  pluginEntryPath?: string

  /**
   * 传给被测试插件的 Cordis config。
   */
  pluginConfig?: Record<string, unknown>

  /** Provider route used by the child JSON-RPC runtime. */
  provider: string

  /** Environment variable name containing the provider credential. */
  apiKeyEnv: string
}

export interface AcceptanceComposition {
  /**
   * 临时 acceptance composition 所在目录。
   */
  directory: string

  /**
   * 临时生成的 cordis.yml。
   */
  configPath: string

  /**
   * 删除临时 composition。
   */
  dispose(): Promise<void>
}

export async function createAcceptanceComposition(
  input: AcceptanceCompositionInput,
): Promise<AcceptanceComposition> {
  const directory =
    await mkdtemp(
      join(
        tmpdir(),
        'dsh-plugin-acceptance-',
      ),
    )

  const configPath =
    join(
      directory,
      'cordis.yml',
    )

  /*
   * 使用 file:// URL 加载 build artifact。
   *
   * pathToFileURL 同时正确处理 Windows / POSIX 路径。
   */
  const pluginUrl = input.pluginEntryPath === undefined
    ? undefined
    : pathToFileURL(input.pluginEntryPath).href

  const yaml = [
    /*
     * 官方预组装 Agent Runtime。
     *
     * Acceptance 不自己重新拼 llm / agent /
     * session / tools / loop 等基础组件。
     */
    '- id: agent-spine',
    '  name: \'@deepseek-ai/dsh-agent-spine-demo\'',
    '  config:',
    '    workspaceContext: false',
    '',

    ...(input.provider === 'deepseek-official'
      ? [
        '- id: llm-deepseek',
        "  name: '@deepseek-ai/dsh-llm-deepseek'",
      ]
      : [
        '- id: llm-pi-ai',
        "  name: '@deepseek-ai/dsh-llm-pi-ai'",
        '  config:',
        '    providers:',
        `      ${escapeYamlKey(input.provider)}:`,
        `        apiKeyEnv: ${escapeYamlString(input.apiKeyEnv)}`,
      ]),
    '',

    '- id: sdk-jsonrpc-server',
    "  name: '@deepseek-ai/dsh-sdk-jsonrpc-server'",
    '',

    ...(pluginUrl === undefined
      ? []
      : [
        /* Current plugin under test for the legacy direct-plugin path. */
        '- id: acceptance-plugin',
        `  name: '${escapeYamlString(pluginUrl)}'`,
      ]),

    ...renderConfig(
      input.pluginConfig ?? {},
    ),

    '',
  ].join('\n')

  try {
    await writeFile(
      configPath,
      yaml,
      'utf8',
    )
  } catch (error) {
    /*
     * 如果 composition 创建失败，
     * 不留下临时目录。
     */
    await rm(
      directory,
      {
        recursive: true,
        force: true,
      },
    )

    throw error
  }

  return {
    directory,
    configPath,

    async dispose(): Promise<void> {
      await rm(
        directory,
        {
          recursive: true,
          force: true,
        },
      )
    },
  }
}

function renderConfig(
  config: Record<string, unknown>,
): string[] {
  if (
    Object.keys(config).length === 0
  ) {
    return []
  }

  const serialized =
    JSON.stringify(config)

  if (serialized === undefined) {
    throw new Error(
      'Plugin config is not JSON-serializable.',
    )
  }

  /*
   * JSON 是合法 YAML flow-style value，
   * 第一版无需引入 YAML serializer。
   */
  return [
    `  config: ${serialized}`,
  ]
}

function escapeYamlString(
  value: string,
): string {
  /*
   * YAML single-quoted scalar 中，
   * 单引号通过两个单引号转义。
   */
  return value.replaceAll(
    '\'',
    '\'\'',
  )
}

function escapeYamlKey(value: string): string {
  if (/^[A-Za-z0-9_-]+$/.test(value)) return value
  return `'${escapeYamlString(value)}'`
}

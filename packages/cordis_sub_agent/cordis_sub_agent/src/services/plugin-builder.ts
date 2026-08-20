import type { Context } from '@deepseek-ai/cordis'

import type {
  DevelopmentArtifact,
} from '../models/development-task.js'

export interface PluginBuilderOptions {
  workspaceRoot: string
}

export interface WriteArtifactInput {
  path: string
  content: string
  description?: string
}

export class PluginBuilder {
  constructor(
    private readonly ctx: Context,
    private readonly options: PluginBuilderOptions,
  ) {}

  /**
   * 返回某个插件项目的根目录。
   *
   * 这里只负责路径组合，不访问文件系统。
   */
  getPluginRoot(pluginName: string): string {
    const root = this.options.workspaceRoot.replace(/[\\/]+$/, '')
    return `${root}/${pluginName}`
  }

  /**
   * 判断目标路径是否已经存在。
   */
  async exists(
    path: string,
    signal?: AbortSignal,
  ): Promise<boolean> {
    const target =
      await this.ctx.fs.resolve(
        path,
        {
          ...(signal !== undefined
            ? { signal }
            : {}),
        },
      )

    const info =
      await this.ctx.fs.stat(
        target,
        signal,
      )

    return info !== undefined
  }

  /**
   * 读取 UTF-8 文本文件。
   */
  async readText(
    path: string,
    signal?: AbortSignal,
  ): Promise<string> {
    const target =
      await this.ctx.fs.resolve(
        path,
        {
          ...(signal !== undefined
            ? { signal }
            : {}),
        },
      )

    return this.ctx.fs.readText(
      target,
      signal,
    )
  }

  /**
   * 写入一个文本 artifact。
   *
   * FileSystem seam 没有 mkdir。
   * 当前官方 local provider 会在 writeText 时自动创建父目录。
   */
  async writeArtifact(
    input: WriteArtifactInput,
    signal?: AbortSignal,
  ): Promise<DevelopmentArtifact> {
    const target =
      await this.ctx.fs.resolve(
        input.path,
        {
          ...(signal !== undefined
            ? { signal }
            : {}),
        },
      )

    await this.ctx.fs.writeText(
      target,
      input.content,
      undefined,
      signal,
    )

    return {
      path: target.displayPath,

      ...(input.description !== undefined
        ? {
          description:
              input.description,
        }
        : {}),
    }
  }
  /**
   * 批量写入生成文件。
   */
  async writeArtifacts(
    inputs: WriteArtifactInput[],
    signal?: AbortSignal,
  ): Promise<DevelopmentArtifact[]> {
    const artifacts: DevelopmentArtifact[] = []

    for (const input of inputs) {
      const artifact = await this.writeArtifact(input, signal)
      artifacts.push(artifact)
    }

    return artifacts
  }

  /**
   * 创建插件项目的最小基础骨架。
   *
   * 这里只创建完全确定性的工程文件。
   * 业务 src 代码由后续 Development Workflow / Agent 生成。
   */
  async createBaseProject(
    pluginName: string,
    signal?: AbortSignal,
  ): Promise<DevelopmentArtifact[]> {
    return this.createBaseProjectAt(
      this.getPluginRoot(pluginName),
      pluginName,
      signal,
    )
  }

  async createBaseProjectAt(
    pluginRoot: string,
    pluginName: string,
    signal?: AbortSignal,
  ): Promise<DevelopmentArtifact[]> {

    if (await this.exists(pluginRoot, signal)) {
      throw new Error(
        `Plugin workspace already exists: ${pluginRoot}`,
      )
    }

    return this.writeArtifacts(
      [
        {
          path: `${pluginRoot}/package.json`,
          content: JSON.stringify({
            name: pluginName,
            version: '0.1.0',
            type: 'module',
            scripts: { build: 'tsc -b' },
            main: 'lib/index.js',
            types: 'lib/index.d.ts',
            exports: {
              '.': {
                types: './lib/index.d.ts',
                default: './lib/index.js',
              },
            },
          }, null, 2) + '\n',
          description: 'Plugin package manifest',
        },
        {
          path: `${pluginRoot}/tsconfig.json`,
          content: JSON.stringify({
            compilerOptions: {
              rootDir: 'src',
              outDir: 'lib',
              declaration: true,
              module: 'NodeNext',
              moduleResolution: 'NodeNext',
              target: 'ES2022',
              strict: true,
              skipLibCheck: true,
            },
            include: ['src'],
          }, null, 2) + '\n',
          description: 'TypeScript project configuration',
        },
        {
          path: `${pluginRoot}/src/index.ts`,
          content: [
            `export const name = ${JSON.stringify(pluginName)}`,
            'export function apply(): void {}',
            '',
          ].join('\n'),
          description: 'Cordis plugin entry point',
        },
      ],
      signal,
    )
  }
}

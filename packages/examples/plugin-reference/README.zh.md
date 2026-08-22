# @deepseek-ai/dsh-plugin-reference

[English](README.md) | 中文

这是 DeepSeek Harness 普通插件生成流程使用的 canonical reference plugin。
它保持小型和本地化，用于让 Agent 先理解普通 Cordis 插件的结构，再调查任务特有
的 API 和依赖。
Agent 应先阅读 AGENT_GUIDE.md，了解文件职责、可复制和必须替换的内容以及边界；
本 README 是面向用户的概览。

## 覆盖内容

- apply(ctx, config) 和具名插件导出
- 带默认值的 Schemastery 配置 schema
- ctx.tools.register 和面向模型的参数 schema
- 从插件入口分离出的 service
- 本地 JSON 持久化和结构化错误
- 通过 ctx.effect 管理生命周期清理
- Cordis 与 DSH Tool 的 workspace:* 依赖
- TypeScript 声明、build 产物、测试和双语文档

## 配置

plugins:
  plugin-reference:
    enabled: true
    storagePath: ./.dsh/reference-notes.json
    maxNotes: 100

enabled 默认是 true；storagePath 默认是 ./.dsh/reference-notes.json；
maxNotes 默认是 100。

## Tools

### reference_echo

{ "message": "hello" }

返回去除首尾空格后的消息和插件名称。空消息会被拒绝。

### reference_note_add

{ "title": "Example", "content": "A note", "tags": ["demo"] }

把 note 持久化到配置指定的 JSON 文件。空标题、空内容以及达到 maxNotes 上限时
会返回明确错误。

### reference_note_list

{ "tag": "demo", "limit": 10 }

读取 notes，可按 tag 精确筛选并限制返回数量。存储文件不存在时视为空列表；JSON
损坏时返回明确错误。

## 开发

pnpm build
pnpm test

这个 package 是结构参考，不是业务实现。生成插件应复用其 package 结构、Tool、
service、配置、持久化和验收组织方式，再根据确认的 PluginSpec 替换具体内容。

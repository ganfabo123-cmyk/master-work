# Agent Note: Markdown long-term memory plugin

Status: implemented

[English](2026-08-15-markdown-long-term-memory.md) | 中文

## Problem

harness 及其会话需要一个能跨越任何单个会话、可查询且不淹没模型的持久长时记忆。需求是：一个以标题为索引的单一 Markdown 文件，经验按固定模板记录，读取从不返回整个文件——DFS 单层 `memory_children` 索引 + 按 id 的 `memory_get`。

## Decision

新增可选包 [`@deepseek-ai/dsh-memory`](../../../../packages/memory/memory)，挂载 `ctx.memory` 服务与三个面向模型的工具（`memory_children`、`memory_get`、`memory_record`）。正式记忆文件（默认 `$DSH_HOME/memory.md`）由进程共享，因此是**全局记忆**。每次正式树操作都重新加载这个由 Harness 自己拥有的宿主文件，因此被外部编辑过的文件是唯一真源；写入会原子替换序列化树，并以仅属主可访问的权限创建缺失的父目录或文件。工作区沙箱限制模型选择的文件系统目标，不限制这个由插件配置固定的持久化路径。

正式经验是"正文符合模板"的叶子标题，由稳定的 `memory-N` id 标识，标题在父级之下唯一（重复写入被拒绝）。`memory_children` 列出某一层的主题与经验，供 DFS 遍历；`memory_get` 按 id 返回单条正式经验。[`memory_record` 单独收集未分类记录](2026-08-15-temporary-memory-inbox.md)，所以记录不会修改正式树。

服务保留 `add(path, title, body)` 作为受信调用方与后续树管理工具使用的正式插入操作；面向模型的包尚未提供分类或插入 `memory.md` 的能力。

## Alternatives considered

- **改用后端（SQLite/JSON）存储而非 Markdown** — 拒绝：用户明确要可读、可手工编辑的 `memory.md` 及标题索引树。
- **读取时返回整个文件** — 拒绝：模型不应收到完整记忆；导航刻意一层一层（DFS），检索按 id。
- **仅靠标题、不用 id** — 拒绝：用户选了 `id + 标题去重`；即便标题在不同父级下重复，id 也能让检索无歧义。

## Consequences

- 会话可以记录并在后续跨会话检索长时经验；读取保持有界（一层或一条经验），绝不返回整个文件。
- 记忆当前为全局；按会话或按工作区的作用域被延后并记为已知限制，文件路径即未来的作用域键。
- 正式树读取与未分类记录保持为不同操作；临时收件箱决策负责记录确认与持久化规则。

# 经验记忆

[English](memory.md) | 中文

[`@deepseek-ai/dsh-memory`](../../packages/memory/memory) 拥有进程全局的 `ctx.memory` 服务及其追加式 Markdown 唯一事实源。它保存可复用的任务经验而不是 Session，先暴露轻量关键词候选，再按需读取完整正文，并且不把内部检索信号放入面向模型的结果。

源文件：[`packages/memory/memory/src/service.ts`](../../packages/memory/memory/src/service.ts)

## 记录

`ExperienceMemory` 包含稳定的 `memory-N` id、标题、规范化关键词、Harness 生成的 ISO 8601 时间、明确结果和 Markdown 正文。`NewExperienceMemory` 只包含模型编写的字段；Service 拥有 id 与时间，并把缺省结果设为 `unknown`。

只有 `# <title> {memory-N}` 能开始一条持久记录。正文拒绝一级标题，因此其中的 `##` 到 `######` Section 不会创建另一个 Record Boundary。

## 检索

`MemorySearchRequest` 提供关键词与可选 limit。V1 Retriever 使用规范化关键词精确交集筛选 Top-K，再按 id 升序返回 `MemorySearchCandidate`；候选包含匹配关键词，但不包含 Score 或正文。模型判断候选相关后，`memory_get` 才执行显式渐进加载。

## 持久化与并发

Store 在每次操作前重新加载事实源文件。进程内队列串行执行完整的重新加载、id 分配和原子替换，避免同一进程内不同 Session 产生重复 id 或丢失更新。不同进程不能并发写同一个文件。

## 公开使用与验证

该包的 [README](../../packages/memory/memory/README.md) 包含核心流程、真实 Windows UTF-8 案例、Store/Retriever 架构、可安装配置，以及可复现 Cordis Loader Demo 的真实输出。面向发布的测试覆盖 Markdown 边界、最大 ID 分配、外部修改重载、Batch 原子校验、并发写入、Retriever 契约、模型结果边界、Loader 装配、插件卸载清理和多语言 UTF-8 磁盘往返。

<!-- BEGIN GENERATED cordis-surface (gen-cordis-catalog.ts) — do not edit between markers -->

<a id="cordis-surface"></a>

## Cordis API

Generated from source by `scripts/gen-cordis-catalog.ts` (verified fresh by `pnpm run verify-cordis-catalog` in doc-sync; regenerate with `pnpm run gen-cordis-catalog`) — this section is byte-identical in both language sides of the page. Signature blocks use a `ts cordis-catalog` fence and keep the original source JSDoc; dispatch modes are defined in the [primer](../cordis-primer.md#dispatch-modes), and the framework-inherited `ctx` API lives in [cordis-api/inherited.md](../cordis-api/inherited.md).

<a id="ctxmemory--memoryservice"></a>

### `ctx.memory` — `MemoryService`

Process-global experience memory backed by the configured Markdown file.

```ts cordis-catalog
/**
 * Validate and append one or more experiences to the formal memory store.
 * Keywords are persisted in canonical form, omitted outcomes become
 * `unknown`, and one Harness-generated ISO timestamp applies to the batch.
 * @param entries - model-authored experience fields supplied for persistence.
 * @param signal - operation cancellation.
 * @returns durable experiences with assigned ids and timestamps.
 */
async record(entries: readonly NewExperienceMemory[], signal?: AbortSignal): Promise<ExperienceMemory[]>

/**
 * Select lightweight candidates. Internal ranking chooses Top-K only; the
 * returned order is stable id order and does not express relevance.
 * @param request - query keywords and optional candidate limit.
 * @param signal - operation cancellation.
 * @returns candidate metadata without bodies or ranking scores.
 */
async search(request: MemorySearchRequest, signal?: AbortSignal): Promise<MemorySearchCandidate[]>

/**
 * Read one complete experience by stable id.
 * @param id - stable `memory-N` identity.
 * @param signal - operation cancellation.
 * @returns the complete experience, or `undefined` when absent.
 */
get(id: string, signal?: AbortSignal): Promise<ExperienceMemory | undefined>
```

Source: [`packages/memory/memory/src/service.ts:49`](../../packages/memory/memory/src/service.ts)
<!-- END GENERATED cordis-surface -->

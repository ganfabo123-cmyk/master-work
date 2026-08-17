# 经验与事实记忆

[English](memory.md) | 中文

[`@deepseek-ai/dsh-memory`](../../packages/memory/memory) 拥有进程全局的 `ctx.memory` 服务及其 Markdown 事实源。它保存可复用的任务经验而不是 Session，先暴露轻量关键词候选，再按需读取完整正文，不把内部检索信号放入面向模型的结果，并且每次装配时把按 cwd 隔离的事实注入模型上下文。

源文件：[`packages/memory/memory/src/service.ts`](../../packages/memory/memory/src/service.ts)

## 记录

`ExperienceMemory` 包含稳定的 `memory-N` id、标题、规范化关键词、Harness 生成的 ISO 8601 时间、明确结果和 Markdown 正文。`NewExperienceMemory` 只包含模型编写的字段；Service 拥有 id 与时间，并把缺省结果设为 `unknown`。

只有 `# <title> {memory-N}` 能开始一条持久经验记录。正文拒绝一级标题，因此其中的 `##` 到 `######` Section 不会创建另一个 Record Boundary。

`FactMemory` 包含规范化键、值与 Harness 生成的 ISO 8601 时间。事实按绝对 cwd 存储：每个 cwd 对应事实目录下的一个 Markdown 文件，文件名是该路径的短 SHA-256 摘要；当前 cwd 的每条事实在每次装配时作为 system-prompt Section 注入。

## 检索

`MemorySearchRequest` 提供关键词与可选 limit。V1 Retriever 使用规范化关键词精确交集筛选 Top-K，再按 id 升序返回 `MemorySearchCandidate`；候选包含匹配关键词，但不包含 Score 或正文。模型判断候选相关后，`memory_get` 才执行显式渐进加载。

事实不参与检索：`rememberFact` 按规范化键对调用方 cwd 做 upsert，`forgetFact` 按键删除，`facts` 列出当前 cwd 的完整集合供注入渲染使用。

## 持久化与并发

Store 在每次操作前重新加载事实源文件。进程内队列串行执行完整的重新加载、id 分配和原子替换，避免同一进程内不同 Session 产生重复 id 或丢失更新。不同进程不能并发写同一个文件。

## 公开使用与验证

该包的 [README](../../packages/memory/memory/README.md) 包含核心流程、真实 Windows UTF-8 案例、Store/Retriever 架构、可安装配置，以及可复现 Cordis Loader Demo 的真实输出。面向发布的测试覆盖 Markdown 边界、最大 ID 分配、外部修改重载、Batch 原子校验、并发写入、Retriever 契约、模型结果边界、事实往返与按 cwd 隔离、注入渲染、Loader 装配、插件卸载清理和多语言 UTF-8 磁盘往返。

<!-- BEGIN GENERATED cordis-surface (gen-cordis-catalog.ts) — do not edit between markers -->

<a id="cordis-surface"></a>

## Cordis API

Generated from source by `scripts/gen-cordis-catalog.ts` (verified fresh by `pnpm run verify-cordis-catalog` in doc-sync; regenerate with `pnpm run gen-cordis-catalog`) — this section is byte-identical in both language sides of the page. Signature blocks use a `ts cordis-catalog` fence and keep the original source JSDoc; dispatch modes are defined in the [primer](../cordis-primer.md#dispatch-modes), and the framework-inherited `ctx` API lives in [cordis-api/inherited.md](../cordis-api/inherited.md).

<a id="ctxmemory--memoryservice"></a>

### `ctx.memory` — `MemoryService`

Process-global memory service backed by the configured experience file and per-cwd fact files.

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

/**
 * Read every fact for one cwd in file order.
 * @param cwd - absolute session working directory.
 * @param signal - operation cancellation.
 * @returns durable cwd-scoped facts.
 */
facts(cwd: string, signal?: AbortSignal): Promise<FactMemory[]>

/**
 * Upsert one fact for a cwd, normalizing the key and assigning a timestamp.
 * @param cwd - absolute session working directory.
 * @param input - the key/value to persist; the key is trimmed and lowercased.
 * @param signal - operation cancellation.
 * @returns the durable fact assigned a Harness-generated ISO timestamp.
 */
async rememberFact(cwd: string, input: { key: string; value: string }, signal?: AbortSignal): Promise<FactMemory>

/**
 * Remove one fact by normalized key for a cwd.
 * @param cwd - absolute session working directory.
 * @param key - the fact key to remove; trimmed and lowercased before lookup.
 * @param signal - operation cancellation.
 * @returns whether a fact with that key was removed.
 */
forgetFact(cwd: string, key: string, signal?: AbortSignal): Promise<boolean>

/**
 * The configured cap on facts injected per cwd.
 * @returns the effective fact count budget for the injected section.
 */
factBudget(): number
```

Source: [`packages/memory/memory/src/service.ts:54`](../../packages/memory/memory/src/service.ts)
<!-- END GENERATED cordis-surface -->

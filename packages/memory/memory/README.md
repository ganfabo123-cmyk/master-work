# dsh-memory

English | [中文](README.zh.md)

**Session stores what happened. Experience Memory stores what is worth reusing.**

`@deepseek-ai/dsh-memory` is an append-only experience-memory plugin for DeepSeek Harness. It distils reusable successes and failures into independent Markdown records instead of storing conversations or reconstructing complete sessions. It also provides cwd-scoped fact memory: stable facts about the user or workspace that are injected automatically into the model context on every turn.

![Experience Memory core flow](assets/memory-flow.svg)

The model searches lightweight candidate metadata, explicitly loads only a useful experience, and records a new lesson only when the current task produced something reusable.

## See it work

This transcript is produced by the repository's [real Cordis Loader demo](examples/encoding-experience/demo.ts), using the same plugin, tools, prompt registration, parser, and retriever as production.

![Real Loader demo: memory_search followed by memory_get](assets/demo-terminal.svg)

From the repository root:

```powershell
pnpm exec tsx packages/memory/memory/examples/encoding-experience/demo.ts
```

The complete example includes a real [`cordis.yml`](examples/encoding-experience/cordis.yml) and seeded [`memory.md`](examples/encoding-experience/memory.md).

## Why Experience Memory?

| System | Stores | Best for | Main trade-off |
|---|---|---|---|
| Session history/search | Complete interactions and events | Audit, replay, recovery | Large and noisy as a reusable prompt |
| Generic RAG memory | Retrieved chunks from broad corpora | Finding potentially relevant information | A chunk is not necessarily a verified lesson |
| Experience Memory | Distilled success/failure records | Reusing proven debugging and task lessons | Requires deliberate experience capture |

Experience Memory complements session storage. Session data remains the full historical evidence; `memory.md` contains compact lessons selected for future reuse.

## A real UTF-8 debugging case

The plugin was motivated by a recurring Windows encoding failure: writing Chinese TypeScript or Markdown through an implicit default encoding corrupted the source. A failed approach and its successful UTF-8 resolution became one reusable experience.

![A real UTF-8 debugging experience reused by a later task](assets/encoding-case.svg)

The durable record is ordinary Markdown:

```markdown
# Windows 中文源码写入必须显式使用 UTF-8 {memory-17}

Keywords: deepseek-harness, windows, encoding, filesystem, typescript
Recorded At: 2026-08-16T02:34:23.123Z
Outcome: success

## Problem

依赖 PowerShell 默认编码写回文件后，中文内容发生乱码。

## Resolution

读写包含非 ASCII 内容的文件时显式使用 UTF-8，并通过磁盘重新加载验证内容。

## Lesson

跨平台文本修改必须控制源文件编码，并用真实多语言内容做 round-trip 回归。
```

A later task searches without loading every body:

```text
[memory-17]
title: Windows 中文源码写入必须显式使用 UTF-8
keywords: deepseek-harness, windows, encoding, filesystem, typescript
matched keywords: deepseek-harness, encoding, typescript
outcome: success
```

Only `memory_get("memory-17")` adds the complete experience to model context.

## Install and configure

Add the package to a DeepSeek Harness workspace:

```powershell
pnpm add @deepseek-ai/dsh-memory
```

Load the plugin after the system-prompt and tool services:

```yaml
- name: '@deepseek-ai/dsh-system-prompt'
- name: '@deepseek-ai/dsh-tools'
- name: '@deepseek-ai/dsh-memory'
  config:
    memoryFile: 'C:/Users/you/.dsh/memory.md'
```

`memoryFile` defaults to `$DSH_HOME/memory.md`. The host owns this path; the model cannot choose a workspace file. The parent directory and file are created on the first successful `memory_record` call.

Fact memory is stored per absolute cwd under `factsDir` (defaults to `$DSH_HOME/memory-facts`), one Markdown file per cwd whose name is a short SHA-256 digest of the absolute path. `maxFacts` caps how many facts are injected into the system prompt per cwd (default `100`).

## Fact memory (per-cwd long-term memory)

Unlike experience memory, facts are never searched: `fact_remember` and `fact_forget` manage a title/body store scoped to the absolute session working directory, and every fact for the current cwd is injected into the system prompt on each assembly.

```text
user says "我叫 gan" or asks to remember the name
  → fact_remember({ title: 'user name', body: 'gan' })
  → persisted to <factsDir>/<sha256(cwd)>.md
  → injected every turn as "## 1. user name" plus body content for this cwd only
```

- Isolation is by absolute cwd: a fact saved in `D:/project-a` is never visible in `D:/project-b`, or in the same path spelled with a different casing or separator.
- Titles are trimmed and lowercased; `fact_remember` upserts, so a later body for the same title replaces the earlier one.
- The injected block tells the model to treat the facts as known, current facts unless the user contradicts them, and to remember stable personal or project facts proactively and forget corrected or revoked ones on request.
- Injection is a dynamic `system-prompt/assemble` contribution, so facts appear on every turn and update immediately after a `fact_remember` or `fact_forget` call without a restart.

## Model-facing tools

### `memory_search`

Accepts specific keywords and an optional limit. It returns `id`, `title`, canonical keywords, matched keywords, and outcome. It never returns the body or an internal ranking score.

### `memory_get`

Loads one complete record by stable `memory-N` id. A missing id returns an explicit model-readable message.

### `memory_record`

Validates and directly persists the fields supplied by the model Tool Call. The Harness generates the id and ISO 8601 `recordedAt`; omitted outcomes become `unknown`. There is currently no human-confirmation step.

```text
model Tool Call
  → validate title, keywords, body, outcome
  → normalize keywords
  → serialize the write
  → reload memory.md and allocate max(memory-N) + 1
  → atomic replace
```

Blank titles, bodies, or keyword lists are rejected. Bodies may contain `##` through `######` headings, but a level-one heading is forbidden because only `# <title> {memory-N}` defines a record boundary.

### `fact_remember`

Saves one title/body fact for the current session cwd. A blank title or body is rejected; the title is trimmed and lowercased before persistence.

### `fact_forget`

Removes one saved fact by title for the current session cwd. A missing title returns an explicit model-readable message instead of failing.

## Architecture

![Experience Memory architecture](assets/architecture.svg)

`MemoryStore` owns the Markdown source of truth. `MemoryRetriever` owns candidate selection. The V1 `KeywordRetriever` performs exact normalized keyword intersection and linear scanning.

Its internal matched-keyword count selects Top-K only. Selected candidates are then presented in ascending `memory-N` order, so presentation order is not a relevance claim. Model-facing output never exposes `score`, `rankingScore`, or `similarity`.

`MemoryRetriever` receives a `MemorySearchSource`. Future BM25, vector, or hybrid providers may maintain derived indexes without changing the Store, Service, or model tools. Those providers are extension points, not V1 features.

`FactStore` owns the per-cwd fact files; `FactSource` is its read-only projection used by the system-prompt injection. `MemoryService` exposes both stores and is the sole entry point for the tools.

## Durability and concurrency

- `memory.md` is reloaded for every read and inside every append operation, so external edits remain visible.
- Writes use atomic replacement with owner-only file and directory permissions.
- A process-local serialized queue covers reload, id allocation, and write. Concurrent sessions in one process cannot duplicate ids or lose an append.
- Multiple processes writing the same file concurrently are not supported.
- Each cwd's fact file has its own serialized write queue, so concurrent `fact_remember` calls on one cwd cannot lose a fact, and a `fact_forget` that empties the store removes the file.

## Verification

The release-focused suite covers:

- empty, single, multiple, malformed, and nested-heading Markdown records;
- maximum-id allocation, missing-file creation, external reload, and atomic batch rejection;
- three concurrent appends without duplicate ids or lost content;
- exact keyword matching, canonical normalization, zero-match behavior, limit, and Top-K/presentation separation;
- tool output contracts, including no body or score leakage from search;
- fact round-trip, concurrent remember, per-cwd isolation, and injected-section rendering;
- real Cordis Loader assembly and complete `record → search → get` tool execution;
- plugin unload cleanup for tools, service, and system-prompt section;
- multilingual UTF-8 round-trip with 中文, English, 日本語, emoji, Markdown, code spans, and a Chinese Windows path.

Run it with:

```powershell
pnpm exec vitest run packages/memory/memory/tests
pnpm exec tsc -p packages/memory/memory/tsconfig.json --noEmit
```

Coverage percentage is diagnostic rather than the release definition; product contracts and reproducible integration behavior are the acceptance criteria.

## Model Experience

### Experience and fact interaction

#### What the model sees

The model sees the `memory_search`, `memory_get`, `memory_record`, `fact_remember`, and `fact_forget` tool schemas. The guidance tells it to generate several specific search keywords, treat results as candidates rather than truth, explicitly load only worthwhile records, and record reusable lessons rather than routine errors or complete session history. Injected per-cwd facts arrive as known context, while `fact_remember` and `fact_forget` update that cwd-scoped context.

#### Token effect

Tool schemas and fixed guidance remain prefix-stable while plugin visibility is unchanged. Search cost grows with lightweight selected metadata; complete body tokens enter context only through explicit `memory_get` calls. Injected facts add at most `maxFacts` short `title + body` records per cwd per turn.

#### KV Cache effect

An unchanged tool view and unchanged fact set preserve the request prefix. Calling `memory_get` or changing cwd facts appends data-dependent context after that stable prefix; it does not claim a fixed token saving.

## Known Limitations and Deferred Work

- Experience memory is process-global and exact-keyword only; there is no project-root scope, BM25, embedding, vector, reranking, or hybrid retrieval. Fact memory is cwd-scoped only — it does not follow a project to its subdirectories.
- There is no automatic session mining, migration, deletion, merge, semantic deduplication, contradiction handling, or decay.
- The write queue protects one process only.
- Fact titles are case-insensitive by design (trimmed and lowercased), so `User Name` and `user name` are the same fact.
- Performance benchmarking and large-corpus retrieval evaluation are deferred until real usage invalidates the current linear-scan assumption.

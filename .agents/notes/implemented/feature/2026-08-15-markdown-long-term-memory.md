# Agent Note: Markdown long-term memory plugin

Status: implemented

English | [中文](2026-08-15-markdown-long-term-memory.zh.md)

## Problem

A harness and its sessions needed a durable long-term memory that outlives any single session and is queryable without flooding the model. The requirement was a single Markdown file indexed by headings, with experiences recorded from a fixed template, and reads that never return the whole file — a DFS one-level `memory_children` index plus an id `memory_get`.

## Decision

A new opt-in package [`@deepseek-ai/dsh-memory`](../../../../packages/memory/memory) mounts a `ctx.memory` service and three model-facing tools (`memory_children`, `memory_get`, `memory_record`). The formal memory file (`$DSH_HOME/memory.md` by default) is shared process-wide, so it is a **global memory**. Every formal-tree operation reloads this Harness-owned host file, so an externally edited file is the source of truth; a write atomically replaces the serialized tree and creates an absent parent directory or file with owner-only permissions. The workspace sandbox confines model-selected filesystem targets, not this fixed plugin-configured persistence path.

Formal experiences are leaf headings whose body is the template, identified by a stable `memory-N` id and a title that is unique under its parent (a duplicate write is rejected). `memory_children` lists one level of topics and experiences for DFS traversal; `memory_get` returns one formal experience by id. [`memory_record` collects unclassified records separately](2026-08-15-temporary-memory-inbox.md), so recording does not mutate the formal tree.

The service retains `add(path, title, body)` as the formal insertion operation for trusted callers and later tree-management tools; the model-facing package does not yet expose classification or insertion into `memory.md`.

## Alternatives considered

- **Store memory in a backend (SQLite/JSON) instead of Markdown** — rejected because the user explicitly wanted a human-readable, hand-editable `memory.md` and heading-indexed tree.
- **Return the whole file on read** — rejected: the model must not receive the full memory; navigation is deliberately one level at a time (DFS) and retrieval is by id.
- **Rely on titles alone, no ids** — rejected: the user chose `id + 标题去重`; ids make retrieval unambiguous even where titles repeat across parents.

## Consequences

- A session can record and later retrieve long-term experience across sessions; reads stay bounded (one level or one experience), never the whole file.
- The memory is global today; per-session or per-workspace scoping is deferred and documented as a known limitation, with the file path as the future scope key.
- Formal-tree reads and unclassified recording remain separate operations; the temporary inbox decision owns recording consent and persistence.

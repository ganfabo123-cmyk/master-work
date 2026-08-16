# Agent Note: Keyword experience memory

Status: implemented

English | [中文](2026-08-16-keyword-experience-memory.zh.md)

## Problem

Long-term memory must recall reusable task experience without loading complete sessions or forcing one experience into a single topic-tree path. A temporary inbox and later tree classification add a second source of persistence work without improving recall after classification is removed.

## Decision

`@deepseek-ai/dsh-memory` stores flat, append-only experience records in the global `memory.md`. Each `memory-N` record contains a title, canonical keywords, a Harness-generated ISO 8601 timestamp, an explicit outcome, and a Markdown body. A level-one `# <title> {memory-N}` heading is the only record boundary; bodies reject level-one headings.

`memory_record` validates and appends the model-authored Tool Call fields directly to the formal store without a human-confirmation step. A process-local serialized queue covers reload, monotonic id allocation, and atomic replacement, preventing duplicate ids and lost updates between sessions in one process. The file does not support concurrent writers from different processes.

The open-source readiness pass adds a reproducible real-Loader encoding demo, three explanatory diagrams plus a verified terminal capture, and release-focused coverage for Store boundaries, UTF-8 disk round-trips, Retriever contracts, tool result boundaries, Loader composition, concurrent writes, and unload cleanup.

`memory_search` progressively discloses id, title, canonical keywords, matched keywords, and outcome. `KeywordRetriever` uses matched-keyword count only to select and truncate Top-K; selected candidates are presented in ascending id order, and neither score nor rank semantics cross the model-facing API. `memory_get` loads a complete selected experience. The model judges relevance and treats loaded memories as possibly stale historical evidence.

The `MemoryRetriever` interface receives a `MemorySearchSource`. Exact keyword retrieval scans documents in V1; a later BM25, vector, or hybrid implementation may own a derived index without changing the store, service, or tools. `memory.md` remains the source of truth.

## Alternatives considered

**Retain the heading tree and temporary inbox.** One parent path cannot represent the several technology, environment, component, and symptom dimensions that may recall an experience. Removing classification also removes the temporary record's distinct lifecycle.

**Expose internal retrieval scores or preserve relevance order.** Keyword counts, BM25 scores, and vector similarities are selection signals rather than confidence or correctness. Numeric scores and ranked presentation encourage the model to delegate its final relevance judgment to an approximate signal.

**Allocate ids before entering the write queue.** Atomic replacement prevents partial files but not two readers from allocating the same id or overwriting one another. Allocation belongs inside the serialized reload-to-write operation.

## Consequences

The plugin has three stable model operations: record, search, and get. Search remains lightweight, storage and retrieval evolve independently, and concurrent sessions in one process retain every append. The design gives up tree navigation, temporary promotion, compatibility with the retired Markdown format, cross-process write safety, semantic retrieval, deletion, merge, and automatic contradiction handling.

Package tests cover Markdown boundaries, canonical keywords, hidden ranking signals, Top-K presentation order, direct recording, malformed old storage, and concurrent append. A real Loader composition test pins the assembled prompt and tool set.

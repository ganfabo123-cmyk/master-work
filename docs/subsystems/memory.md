# Experience Memory

English | [中文](memory.zh.md)

[`@deepseek-ai/dsh-memory`](../../packages/memory/memory) owns the process-global `ctx.memory` service and its append-only Markdown source of truth. It stores reusable task experiences rather than sessions, exposes lightweight keyword candidates before complete bodies, and keeps internal retrieval signals out of the model-facing result.

Source: [`packages/memory/memory/src/service.ts`](../../packages/memory/memory/src/service.ts)

## Records

`ExperienceMemory` carries a stable `memory-N` id, title, canonical keywords, Harness-generated ISO 8601 timestamp, explicit outcome, and Markdown body. `NewExperienceMemory` contains only model-authored fields; the service owns ids and timestamps and defaults an omitted outcome to `unknown`.

Only `# <title> {memory-N}` starts a durable record. Bodies reject level-one headings so their `##` through `######` sections cannot create another record boundary.

## Retrieval

`MemorySearchRequest` supplies keywords and an optional limit. The V1 retriever uses exact normalized keyword intersection to select Top-K, then returns `MemorySearchCandidate` values in ascending id order with matched keywords but no score or body. `memory_get` performs the explicit progressive load after the model judges a candidate relevant.

## Durability and concurrency

The Store reloads the authoritative file before each operation. A process-local queue serializes the complete reload, id allocation, and atomic replacement operation, preventing duplicate ids and lost updates between sessions in one process. Different processes must not write the same file concurrently.

## Public usage and verification

The package [README](../../packages/memory/memory/README.md) includes the core flow, the real Windows UTF-8 case, the Store/Retriever architecture, installable configuration, and output captured from a reproducible Cordis Loader demo. Release-focused tests cover Markdown boundaries, maximum-id allocation, external reload, atomic batch validation, concurrent writes, Retriever contracts, model-facing result boundaries, Loader assembly, plugin unload cleanup, and multilingual UTF-8 disk round-trips.

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

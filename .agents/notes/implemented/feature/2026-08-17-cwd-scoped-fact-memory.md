# Agent Note: Cwd-scoped fact memory

Status: implemented

English | [中文](2026-08-17-cwd-scoped-fact-memory.zh.md)

## Problem

The [keyword experience memory](../architecture/2026-08-16-keyword-experience-memory.md) plugin recalls reusable task lessons on demand, but it has no place for stable facts about the user or a workspace — a name, a preference, a project convention — that the agent should simply already know. Facts are not recall-shaped: they are small, current, and wanted in every turn, not retrieved by keyword on some later occasion. Without them the model re-asks for the same user identity or project constraint in every session.

## Decision

`@deepseek-ai/dsh-memory` adds cwd-scoped fact memory alongside experience memory. A `FactMemory` record is a normalized key, a value, and a Harness-generated ISO 8601 timestamp. Facts are stored per absolute cwd: each cwd maps to one Markdown file under the configured `factsDir` (default `$DSH_HOME/memory-facts`), whose name is a 16-hex SHA-256 digest of the absolute path, so no host path leaks into the filename and each cwd is isolated from every other.

`MemoryService.rememberFact` trims and lowercases the key and upserts by it; `forgetFact` removes by normalized key and reports whether anything was removed; `facts` lists the current cwd's full set. The model-facing tools are `fact_remember` and `fact_forget`, both scoped to `exec.agent.session.header.cwd` and failing loud without a session cwd. Every assembly injects the current cwd's facts as a system-prompt section through a `system-prompt/assemble` waterfall contribution that reads `assembly.variables.cwd` — the cwd variable the agent loop registers — so facts appear on every turn and update immediately after a remember or forget, with no restart. `maxFacts` (default 100) caps the injected count per cwd.

The fact files use the same durability rules as the experience store: atomic replacement with owner-only permissions, and a process-local per-cwd serialized write queue so concurrent remembers cannot lose a fact; a forget that empties a store removes the file.

## Alternatives considered

- **Reuse the experience record / keyword retrieval for facts** — rejected: facts must be present in every turn, not selectively recalled; injecting them through the retrieval path would make them invisible until the model guesses the right keywords.
- **Store facts in the single global `memory.md` with a scope tag** — rejected: the experience file is append-only and keyword-indexed; mixing upsert-by-key facts into it would couple two very different write and read patterns and leave no hard cwd isolation.
- **Inject through a fixed static system-prompt section** — rejected: a static section cannot know the current cwd or the live fact set; the `system-prompt/assemble` waterfall reevaluates per turn, so injection stays current without plugin reconfiguration.

## Consequences

The plugin now serves two memory kinds: on-demand experience recall and always-on cwd-scoped facts. Facts are cheap (a few short `key: value` lines per turn, capped by `maxFacts`) and immediately reflected in the very next assembly. The cost is a second persistence format and a second write queue, both homogeneous with the existing store; fact keys are case-insensitive by design (normalized lowercase), and isolation is strictly by absolute cwd — a fact saved in `D:/a` is invisible in `D:/b` or in a differently-spelled equivalent path.

Package tests cover fact round-trips, per-cwd isolation, concurrent remembers, tool execution without a session cwd, and injected-section rendering.
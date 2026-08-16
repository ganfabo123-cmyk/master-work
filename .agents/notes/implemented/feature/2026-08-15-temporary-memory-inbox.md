# Agent Note: Temporary memory inbox

Status: implemented

English | [中文](2026-08-15-temporary-memory-inbox.zh.md)

## Problem

New experiences cannot always be classified into the formal memory tree when they are recorded. Requiring the model to inspect and choose a tree path during recording mixes capture with curation and can place an experience under an unsuitable heading.

## Decision

`memory_record` captures unclassified experiences in `$DSH_HOME/temp_memory.md` by default and never changes the formal `$DSH_HOME/memory.md` tree. Recording requires no preceding `memory_children` call and accepts no tree path.

Each entry has a title, a `recordedAt` value in `YYYY-MM-DD HH:mm` form, and one complete body. The body follows the established experience template and carries the event date, optional confirmed event time, outcome evidence, concrete approach, and causal reflection. `recordedAt` identifies when the record was created; it does not invent an event time.

The tool asks the human to confirm or edit each complete body through `userQuestions`, declining blank answers. Approved records receive `temp-memory-N` ids and are atomically stored with their creation time. Formal `memory-N` ids remain independent.

Classification, merging, insertion into the formal tree, and removal from the temporary inbox belong to later management tools. The service retains formal-tree insertion for trusted callers, but `memory_record` only captures temporary records.

## Alternatives considered

- **Let `memory_record` choose a formal path after reading the tree** — rejected because capture time does not guarantee enough context to choose a durable taxonomy, and the read-before-write requirement couples two separate tasks.
- **Keep action, outcome, and reflection as separate tool fields** — rejected because those fragments duplicated the human-visible template and constrained edits; one complete body is the confirmed record.
- **Reuse `memory-N` ids in both files** — rejected because independently allocated ids would collide when later management tools insert temporary records into the formal tree.

## Consequences

- Recording is independent of formal-tree navigation and cannot accidentally create a formal branch.
- The temporary file becomes an explicit curation queue with record-time metadata and a separate id namespace.
- No model-facing operation currently lists, classifies, inserts, merges, or removes temporary records; those capabilities remain unavailable until management tools define their complete lifecycle.
- This behavior change has source type-check and documentation validation but no updated unit coverage because the current task explicitly excludes test changes.

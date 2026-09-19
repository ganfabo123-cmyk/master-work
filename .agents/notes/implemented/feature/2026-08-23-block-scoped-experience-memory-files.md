# Agent Note: Block-scoped experience memory files

Status: implemented

English | [中文](2026-08-23-block-scoped-experience-memory-files.zh.md)

## Problem

A single experience file gives every retrieval operation the same candidate corpus. Keywords express relevance but do not let a model select a bounded technology or project memory collection, and a globally unique `memory-N` couples otherwise unrelated experience collections.

## Decision

Experience memory is divided into named file blocks under `memoryDir`, which defaults to `$DSH_HOME/memory`. A validated `block_name` maps to `<block_name>_memory.md`; normalization trims and lowercases the value, and validation permits 1–64 ASCII letters, digits, underscores, or hyphens so model input cannot select a path outside the configured directory.

`memory_search`, `memory_get`, and `memory_record` require `block_name`. `MemoryService` caches one `MemoryStore` per normalized block, so each file retains the original Markdown record format, independent `memory-N` allocation, atomic replacement, external-edit reload behavior, and process-local serialized writes. The retriever receives the already selected store and remains unaware of blocks.

With the default configuration, first access to the `global` block renames `$DSH_HOME/memory.md` to `$DSH_HOME/memory/global_memory.md` without rewriting its content. The operation rejects a conflicting target rather than merging or overwriting it.

## Alternatives considered

**Block metadata in one file.** This preserves global ids but leaves storage and write ownership global, while the requested unit is a complete original-format memory file.

**One configurable path per block.** This permits arbitrary placement but expands configuration and path authority beyond the current need for named files in one host-owned directory.

**Cross-block and whole-block read tools.** These operations weaken the selected-block retrieval flow and have no current consumer, so the plugin exposes only the existing search, get, and record operations with an added block name.

## Consequences

The stable identity of an experience is the pair `(block_name, memory-N)`, and separate blocks may each contain `memory-1`. Models must choose a block for every experience operation. Blocks are namespaces rather than access control: a model with the tools may name any valid block. Multi-process writes to the same block file remain unsupported.

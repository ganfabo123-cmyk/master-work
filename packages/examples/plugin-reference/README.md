# @deepseek-ai/dsh-plugin-reference

English | [中文](README.zh.md)

This is the canonical ordinary-plugin reference for DeepSeek Harness plugin
generation. It is intentionally small and local: read it to learn the shape of
a normal Cordis plugin before investigating task-specific APIs and dependencies.
Agents should read AGENT_GUIDE.md first for the file map, copy/replace rules,
and boundaries; this README is the user-facing overview.

## What it demonstrates

- apply(ctx, config) and named plugin exports
- a Schemastery configuration schema with defaults
- ctx.tools.register and model-facing parameter schemas
- a small service separated from the plugin entry point
- local JSON persistence and structured errors
- lifecycle cleanup through ctx.effect
- workspace:* Cordis and DSH tool dependencies
- TypeScript declarations, build output, tests, and bilingual documentation

## Configuration

plugins:
  plugin-reference:
    enabled: true
    storagePath: ./.dsh/reference-notes.json
    maxNotes: 100

enabled defaults to true; storagePath defaults to
./.dsh/reference-notes.json; maxNotes defaults to 100.

## Tools

### reference_echo

{ "message": "hello" }

Returns the trimmed message and the plugin name. An empty message is rejected.

### reference_note_add

{ "title": "Example", "content": "A note", "tags": ["demo"] }

Persists a note to the configured JSON file. Empty title/content and a full
maxNotes store are rejected.

### reference_note_list

{ "tag": "demo", "limit": 10 }

Reads notes, optionally filters by exact tag, and limits the result. A missing
storage file behaves as an empty list; malformed JSON returns an explicit error.

## Development

pnpm build
pnpm test

Use this package as a structural reference, not as a business implementation.
Generated plugins should copy the package shape and replace the tools, service,
configuration, persistence, and acceptance behavior with the confirmed
PluginSpec.

# Agent Guide: dsh-plugin-reference

This file is the agent-facing guide for the canonical ordinary DeepSeek Harness
plugin reference. Read it together with README.md and the actual src/ files.
The source is authoritative when this guide and implementation differ.

## Reading order

1. Read package.json to learn the package name, exports, workspace dependencies,
   scripts, and generated declaration paths.
2. Read tsconfig.json to learn the repository project-reference and output
   conventions.
3. Read src/index.ts for the Cordis plugin entry point, inject list, config
   forwarding, Tool registration, and disposal.
4. Read src/config.ts for the configuration schema and defaults.
5. Read src/service.ts and src/types.ts for the service/data boundary and local
   persistence behavior.
6. Read README.md and README.zh.md for the user-facing contract.
7. Read tests/ for the style of isolated local verification.

## File-to-responsibility map

| File | Responsibility |
|---|---|
| package.json | Package metadata, exports, workspace dependencies, and commands |
| tsconfig.json | TypeScript project settings and output |
| src/index.ts | Named plugin exports, apply, injection, Tool schemas, lifecycle |
| src/config.ts | Runtime configuration interface and Schemastery defaults |
| src/service.ts | Business operations and file persistence |
| src/types.ts | Domain data types |
| tests/ | Focused behavior tests using temporary storage |
| README.md | English user-facing contract |
| README.zh.md | Chinese user-facing contract |
| README.i18n.yaml | README pairing hashes |

## Patterns to copy

Copy the structural patterns:

- named exports for name, inject, Config, and apply
- a small Config schema with safe defaults
- a service class for business logic
- Tool definitions with explicit parameter schemas
- structured JSON-compatible Tool results
- validation before calling the service
- ctx.effect for registration cleanup
- temporary directories in tests
- README bilingual pairing

## Patterns to replace

Do not copy these values as business requirements:

- plugin name and package name
- tool names and descriptions
- note domain types and JSON file format
- storagePath and maxNotes
- echo/note behavior
- acceptance examples
- dependency list that is unrelated to the new PluginSpec

Replace them with the confirmed PluginSpec and with APIs verified in the
current repository.

## Contract boundaries

The plugin entry point should compose the runtime:

apply(ctx, config)
→ create service
→ register model-facing tools
→ return lifecycle cleanup

The service should own domain behavior and persistence:

Tool arguments
→ validate and normalize
→ service operation
→ JSON-compatible result or explicit error

Do not put business persistence or domain rules in module-level side effects.
Do not assume a Tool return type is serializable unless it is composed only of
JSON-compatible values.

## What this example does not prove

This package does not cover every DSH API. In particular, do not infer its
patterns for ACP, JSON-RPC entry points, agent spine composition, sessions,
goals, shell execution, sandbox policies, or external services. For those
requirements, inspect the relevant official package under packages/examples/
and the actual dependency source.

The example also does not decide the correct dependency set for a new plugin.
Investigate each required dependency and use the version/range convention of
the current repository.

## Main Agent invariants

- Keep the generated plugin inside its registered pluginRoot.
- Preserve the package name and exports contract.
- Add only dependencies required by the confirmed PluginSpec.
- Keep finite build, typecheck, and test commands in the foreground.
- Test filesystem behavior with temporary paths.
- Update both README files when documentation changes.
- Update README.i18n.yaml after both README files are synchronized.
- Do not change root configuration during ordinary plugin development.

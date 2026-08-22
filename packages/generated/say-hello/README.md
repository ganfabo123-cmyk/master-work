# say-hello

English | [中文](README.zh.md)

A minimal DeepSeek Harness plugin that registers one model-callable tool, `say_hello`, with the [`ToolRuntime`](../../core/tools/README.md) registry through `defineTool`. The tool takes an optional `name` and returns a plain-text greeting; the plugin is purely in-memory, with no persistence and no external services.

## Tool: `say_hello`

The package is a named-export function plugin (`name` / `inject` / `apply`, no default export): `inject: ['tools']` declares the tools service, and `apply` registers the tool inside `ctx.effect`, so the registration is disposed with the plugin fiber.

- Parameter `name` (optional `string`): the person to greet. `execute` trims the value; an omitted, empty, or blank `name` returns `Hello!`, and every other value returns `Hello, <name>!` (for example, `' Ada '` greets `Ada`).
- Output: the canonical value is the plain greeting string (`output.schema` is `{ type: 'string' }`), rendered to the model as a single `text` block.
- Lifecycle: the tool unregisters when the plugin fiber is disposed; the unit tests cover that removal along with the two greeting behaviors.

## Composition

`@deepseek-ai/cordis` and `@deepseek-ai/dsh-tools` are peer dependencies, and `lib/index.js` is the plugin entry (`main`). Build with `pnpm run build`, then mount the package in a harness profile composition alongside those runtimes — for example, a [profile bundle](../../bundle/README.md) whose patch mounts this package. In a session, ask the model to call the tool:

- "Use the say_hello tool." → the model receives `Hello!`
- "Use the say_hello tool with name Ada." → the model receives `Hello, Ada!`

## Model Experience

### say_hello tool

#### What the model sees

The model sees the `say_hello` function definition — description `Greet someone by name and return the greeting text.` — with one optional `string` parameter `name`. The definition flows into prompt assembly through `ctx.tools`, and each call comes back as the plain greeting string.

#### Token effect

Fixed per-request cost of one function definition while the tool is visible; the greeting result is data-dependent text.

#### KV Cache effect

Prefix-stable while the tool definition and its visibility are unchanged; plugin lifecycle or scoped restrictions may invalidate reuse from this definition.

### Tool result

#### What the model sees

Each call returns exactly the plain string `Hello!` when `name` is omitted, empty, or blank, and `Hello, <name>!` otherwise; `name` is trimmed before use, so surrounding whitespace never reaches the greeting.

#### Token effect

Result text is data-dependent and resent until compaction.

#### KV Cache effect

Append-only; newly visible result content follows the reusable request prefix and does not invalidate existing KV-cache entries.

## Known Limitations and Deferred Work

- **No configuration surface** — the plugin exports no `Config`, so the tool name and greeting wording are fixed in source; a deployment that needs different wording must edit this plugin rather than configure it.
- **Plain-text output only** — `say_hello` returns a single string; consumers that need structured data (for example, the greeted name separate from the greeting) must parse the text.
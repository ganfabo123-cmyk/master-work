# @deepseek-ai/dsh-tool-cross-session-search

English | [中文](README.zh.md)

User-approved model tools that search prior session history **across every workspace** through `ctx.sessionQuery`. Unlike `@deepseek-ai/dsh-tool-session-query`, whose cross-session reads are authorized only for the caller's own workspace (`cwd` equality), this opt-in package reaches sessions created in other working directories. Reaching them is a sensitive operation, so every call first passes a per-call user-approval gate through `ctx.approval`: the composed answerers must grant `'allowed-once'` before any session-query interaction, and each gate emits a durable `approval/asked` + `approval/decided` audit pair onto the caller's session log.

The package registers one read-only tool, `cross_session_search`. It is not mounted by shipped host compositions.

## Configuration

| Key | Default | Meaning |
|---|---:|---|
| `maxSearchResults` | `20` | Maximum cross-workspace hits returned by one call, enforced in the service layer |

## Authorization and audit

`cross_session_search` is the single code path into cross-workspace search, and it is gated before any provider contact. The tool calls `ctx.approval.request()` with the invocation's `callId` and a reason naming the query; it then enforces the returned outcome:

- `allowed-once` — the search proceeds for this call only.
- `rejected` — the tool fails closed with a model-safe message; no session-query interaction happens.
- `cancelled` — the tool fails closed; no hit is fetched.
- `unavailable` — no composed answerer could answer; the tool fails closed.

The model cannot decide or forge the approval range: the answerer chain, not the tool, selects the outcome, and a deployment policy of `never` under `@deepseek-ai/dsh-user-approval` rejects every gate deterministically. Because grants are one-shot (`allowed-once`), the package keeps no cross-call authorization cache, and no workspace scope is ever derived from model arguments.

## Search semantics

A call never adds a `cwd` clause to the session filter, so the live-preferred logical corpus spans every workspace. The package reuses `ctx.sessionQuery.searchSessions` and `ctx.sessionQuery.readTitleSnapshots`; it creates no secondary store and copies no database. Results are cursor-free: the tool pages internally through provider cursors without exposing them, and returns each hit's folded title, owning workspace, availability, and strongest-match excerpt so the model can reason about cross-workspace context without a second lookup. The deployment `maxSearchResults` cap is enforced in the service layer regardless of any provider limit.

## Model Experience

### System prompt

#### What the model sees

The model receives one fixed cross-workspace guidance section while the plugin is mounted.

##### Cross-workspace search guidance

```markdown
Use session_cross_search to find relevant work across prior sessions in ANY workspace. Each call asks the user for approval before searching. Results are cursor-free and bounded. The search reaches sessions created in other working directories only after the user approves this call.
```

#### Token effect

One fixed concise section is present on each request while the plugin is mounted.

#### KV Cache effect

Prefix-stable while the plugin and guidance text are unchanged.

### Tool schemas

#### What the model sees

The model sees the generated [`cross_session_search` schema](../../../docs/tool-catalog.md#deepseek-aidsh-tool-cross-session-search). It exposes query text and optional creation/parent filters, and deliberately omits cursors, page sizes, workspace paths, and any model-controlled result limit.

#### Token effect

One fixed read-only schema is sent on each request while the tool is visible.

#### KV Cache effect

Prefix-stable while tool visibility and definition are unchanged.

### Tool results

#### What the model sees

Each approved successful call emits one plain-text block listing the bounded hits with title, workspace, availability, and excerpt. Each denied call emits one error block naming the closed outcome.

#### Token effect

Results are data-dependent and remain in logged tool history until compaction; `maxSearchResults` bounds the hit count.

#### KV Cache effect

Append-only result text follows the reusable request prefix and does not invalidate earlier cache entries.

## Known Limitations and Deferred Work

- Workspace identity is the exact `cwd` string stored on each session header, so symlink-equivalent paths and a session created without a `cwd` are treated as their own workspaces.
- The gate is evaluated per call; there is no persistent cross-call authorization, so a long multi-step workflow re-approves each search.
- The full-text backend is the deployment's mounted `ctx.sessionQuery` provider; a deployment that disables search (`openAt: never`) fails search calls even after approval, while exact reads remain available.

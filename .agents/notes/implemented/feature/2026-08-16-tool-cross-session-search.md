# Agent Note: Cross-workspace session search — per-call user-approval gate

Status: implemented

English | [中文](2026-08-16-tool-cross-session-search.zh.md)

## Problem

The harness can already search *prior* sessions in the caller's own workspace: `@deepseek-ai/dsh-tool-session-query` registers `session_search` over `ctx.sessionQuery`, and the workspace-access module authorizes a target only when its `cwd` exactly equals the caller's `cwd` — a session with a different or absent `cwd` is invisible. A maintainer or model frequently needs to look up work done in *other* working directories of the same harness home (a later project's sessions, related work under another checkout) to answer "did I already solve this elsewhere?". No model-facing capability reached those records. Reaching them is a sensitive operation — another workspace's sessions can contain unrelated or private history — so the boundary must be a decision the user makes, not something the model grants itself. The existing workspace-scoped tool derives its authorization purely from session headers (same `cwd`), which is exactly the wrong credential for cross-workspace access.

## Decision

Add a new opt-in model-facing Consumer, `@deepseek-ai/dsh-tool-cross-session-search` in `packages/session-query/tool-cross-session-search`, that searches the live-preferred logical session corpus across **every** workspace through the same `ctx.sessionQuery` service. It reuses the existing provider and its cursor-free `searchSessions`/`readTitleSnapshots`; it creates no secondary store and copies no database. Unlike the workspace-scoped sibling, it never adds a `cwd` clause to the session filter, so the search scope is the whole corpus.

### The per-call user-approval gate is the single entry

`cross_session_search` is the only code path into cross-workspace search, and it is gated before any provider contact. Each call invokes `ctx.approval.request({ agent, toolName, callId, reason, signal })` and enforces the returned outcome:

- `allowed-once` — the search proceeds for this call only.
- `rejected`, `cancelled`, or `unavailable` — the tool fails closed with a model-safe `SESSION_CROSS_SEARCH_DENIED` error and no session-query interaction happens.

The gate is the composed approval answerer chain, not the tool, that selects the outcome, so the model cannot decide or forge the approval range: a deployment policy of `never` under `@deepseek-ai/dsh-user-approval` rejects every gate deterministically, and because grants are one-shot the package keeps **no** cross-call authorization cache and derives no workspace scope from model arguments. Every gate appends the durable `approval/asked` + `approval/decided` audit pair to the caller's session log, satisfying the harness rule that anything a model sees is reconstructable from the log. The tool execution signal forwards through the gate exactly as the workspace-scoped sibling forwards it through authorization, so cancellation races resolve as a closed `'cancelled'` outcome.

### Result boundary

The deployment `maxSearchResults` config (default `20`, schemastery `Config`) is enforced in the service layer `enforceCap` regardless of any provider page limit, so a misbehaving provider cannot return more hits than the cap. Results are plain text: each hit's folded title, owning workspace (`cwd`), availability, and strongest-match excerpt, so the model can reason about cross-workspace context without a second lookup.

### Consumption posture

The package is opt-in and not mounted by shipped base/web/headless bundles, mirroring `tool-session-query`. It depends only on the `ctx.sessionQuery` interface and the approval seam; it does not import the SQLite implementation, and it does not touch `agent-loop`, `tools`, or `session-query` itself. Full-text search additionally requires the deployment to enable the provider's content index (`openAt`); with search disabled the provider already fails loudly via `SESSION_QUERY_SEARCH_DISABLED`, and the approval gate still runs first.

## Testing

- **Unit** — the package test drives the real `ctx.tools.execute` against a fake `SessionQueryEngine` and a real `ApprovalService`, covering: schema shape (no `cwd`/`cursor`/`limit`), the pure `presentCall`, HMR-safety disposal, the audit pair landing on the caller session, each closed outcome (`rejected`, `cancelled`, `unavailable`) feeding `SESSION_CROSS_SEARCH_DENIED` with zero provider interaction, the approval-request-throws path yielding `SESSION_CROSS_SEARCH_APPROVAL_FAILED`, the missing-agent path yielding `SESSION_CROSS_SEARCH_MISSING_AGENT`, omission of any `cwd` filter, parent/root filter handling, and the service-layer cap.
- **Real SQLite composition** — a real `SessionStore` + JSONL persistence + `SqliteSessionQueryEngine` + `ApprovalService` boots the plugin and searches persisted sessions in other `cwd`s: granted search returns cross-workspace hits; a rejected gate returns none and leaks no session id or path; a missing approval service fails loudly; the configured cap is enforced across workspaces; and the audit pair is recorded on the caller session.

## Alternatives considered

### Broadening `tool-session-query` to cross-workspace

Reusing the existing package and relaxing its workspace authorization by adding an approval branch. Rejected: that package's README and the workspace-access module guarantee same-`cwd` authority as an invariant, its batch authorization (`authorizeSessionIds`) is built around `cwd` equality, and relaxing it would weaken the security posture of the shipped workspace-scoped tools and force a migration of their tests. A separate consumer keeps the safe default intact and makes the cross-workspace capability an explicit opt-in.

### Persistent cross-workspace authorization cache

Storing a grant so later calls skip the gate. Rejected: it widens the attack surface, contradicts the harness's fail-closed approval stance, and cannot be "logged" as a single audit event once it spans calls. Per-call `allowed-once` is the minimal, auditable boundary the task demands.

### A new capability seam (new Service Definition/provider)

Building a distinct service/provider for cross-workspace search. Rejected: this is a Consumer of the existing `ctx.sessionQuery` seam, not a new seam; adding a service would duplicate the query interface and violate the "one internal caller" inverse-smell rule (packages/AGENTS.md).

## Consequences

A model can search prior sessions from any workspace of the harness home, but only after an explicit, audited, per-call user approval; the operation is opt-in, cursor-free, bounded by a configurable cap, and reuses the single trusted query provider. The cost is a per-call prompt for the user, which is the deliberate price of a sensitive cross-boundary read. The workspace-scoped sibling remains unchanged and continues to offer same-`cwd` search without prompting.

## Related

- [Model-facing session-query tools](2026-07-24-model-facing-session-query-tools.md) — the workspace-scoped sibling and the search-to-trace/read workflow.
- [SQLite session-query provider](2026-07-10-sqlite-session-query-provider.md) — the underlying `ctx.sessionQuery` service.

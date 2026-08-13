# Blueprint contract

Replace section 7 of `APP_DESIGN.md` with all tables below.

## State schema

| Field | Type | Initial value/source | Updated by transition | Persisted reason |
|---|---|---|---|---|

State must include `task_id`, `session_id`, current phase/progress, facts needed for future decisions, consumed Action IDs, and terminal result.

## Phase contracts

| Phase ID | Selected Agent IDs | Observation view IDs | Available Action IDs | Collection condition | Resolution | Transition | Next phase |
|---|---|---|---|---|---|---|---|

Every phase must have a deterministic next step. An automatic phase has no selected Agent and must be handled by a declared deterministic hook rather than an invented LLM actor.

## Observation projections

| View ID | Agent IDs | Included State/info IDs | Excluded private info | Available Action IDs |
|---|---|---|---|---|

## Action schemas

| Action ID | Tool name | Actor IDs | JSON-like parameters | Available when | Validation failures and reasons | Payload fields |
|---|---|---|---|---|---|---|

## Transition rules

| Transition ID | From phase | Collected Actions | State updates | Consumed IDs | To phase |
|---|---|---|---|---|---|

## Event and ROOM projection

Replace section 8 with:

| Event ID/type | Trigger | Complete content | Room key | Recipients | Private | Release time |
|---|---|---|---|---|---|---|

Do not replace full business content with status text such as "submitted" or "completed".

## Recovery

State the safe persistence boundary after each successful transition, resources needed to rebuild Agents/ROOM/contexts, and expected resumed phase.

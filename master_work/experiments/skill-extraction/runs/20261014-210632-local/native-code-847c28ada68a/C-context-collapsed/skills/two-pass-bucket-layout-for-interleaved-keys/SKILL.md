---
name: two-pass-bucket-layout-for-interleaved-keys
description: Use when a hash/index structure stores per-key runs of item positions in one shared flat array and lookups return wrong items after new keys appear between items of an older key. Helps the agent replace a single-pass append layout (which silently corrupts bucket ranges when input keys interleave) with a classify-then-layout two-pass build, and verify with an index dump plus the query test suite. Requires a way to dump bucket start/count/slot contents and a test suite covering interleaved key orders. Do not use when input items are already grouped by key, or when the wrong-results cause has not been confirmed by dumping the bucket layout.
---
# Build Per-Key Contiguous Slot Arrays with a Two-Pass Layout

## Goal
Fix a hash/index structure whose per-key runs live in one shared flat slot array and whose lookups silently return the wrong entries once input keys interleave, by replacing the single-pass append layout with a classify-then-layout two-pass build, then prove correctness with an index dump and the query test suite.

## Scope
### In scope
- Symptom: ground-key lookups return items belonging to other keys, and queries yield 0 or wrong solutions while the same data unindexed works.
- Structures: bucket table with per-bucket `start`/`count` into a shared `slots[]` array, built while streaming items in input order.
- The failure mode where a bucket's `start` is recorded when the bucket is first created, but its later items are appended after other buckets' items, breaking the assumed contiguity.
- Two-pass remedy: pass 1 classifies items into per-bucket temporary lists; pass 2 writes bucket offsets and copies the lists contiguously.
- Verification: dump bucket start/count/slots with each slot's decoded key, plus the pre-existing query test suites.

### Out of scope
- Choosing hash functions, resizing policies, or bucket counts.
- Cases where input is already grouped by key (single-pass append is correct there) — do not refactor without reproduced corruption.
- Logic bugs in the query/backtracking layer that remain after the index layout is proven correct.

## Inputs
1. **Failing query/observation** — type: test output; source: query suite; required: yes; constraint: a query that should return ≥1 solution returns 0, or wrong clauses are tried; default: 无.
2. **Index build function** — type: source; source: e.g. `db_build_index` with per-bucket `idx_start`/`idx_count` and shared `idx_clause_slots[]`; required: yes; default: 无.
3. **Bucket dump harness** — type: small debug program or temporary instrumentation; source: written during diagnosis; required: yes; constraint: must print each bucket's kind/start/count and, for each slot, the position and decoded head/key; default: 无.
4. **Input order of items** — type: data/code; source: the asserted clauses or records; required: yes; constraint: must show whether same-key items are interleaved with other keys (e.g. `path(a,b). path(b,c). path(a,c).`); default: 无.
5. **Test suite covering mixed orders** — type: project tests; required: yes; constraint: should include interleaved keys and mixed variable/ground entries; default: the project's existing suites.

## Outputs
### Artifacts
- Rewritten index-build function in the existing source file (two passes, optional static per-bucket temporary accumulators sized by the bucket capacity constant).
- Optional retained debug dump helper.
- Unchanged public API (`build`/`range-query` signatures) and unchanged query code.

### Success criteria
- The dumped layout shows each bucket's slots contiguous and containing only its own key (start ranges non-overlapping, ascending).
- The previously 0-solution query returns its expected solution count; all indexing tests pass (observed: `13/13 tests passed`), and the whole suite returns to full pass (observed: `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`).

### Failure criteria
- Dump still shows a bucket's slot range covering another bucket's items.
- Any previously passing suite regresses (ordering semantics broken — the query-time merge must still return clauses in ascending clause order).

## Preconditions
- A reproducible failing case exists whose input demonstrably interleaves keys; if you cannot reproduce wrong lookups, stop — the single-pass layout may be fine for your data.
- You can instrument the structure to print bucket offsets and slot contents (the diagnosis in this trajectory came from that dump, not from reading the code alone).
- The bucket count and per-bucket capacity are statically bounded, so per-bucket temporaries of `INDEX_MAX_BUCKETS × INDEX_MAX_INDEXED`-scale exist or can be made `static` in a non-reentrant builder.
- The query path's expected ordering (clause order) is known, because the fix must preserve it during the ground-bucket + catch-all merge.
- If any of these is missing, stop and gather them before editing.

## Procedure
### Step 1: Reproduce and capture the wrong-lookup observation
- Actions: run the smallest query that fails (observed: `reachable(a,c)` over `path(a,b). path(b,c). path(a,c).` returned 0 solutions); record expected vs actual.
- Inputs: failing test or REPL query.
- Outputs: a one-command reproduction.
- Cautions: make sure the same data works with the index disabled/larger coverage before blaming the layout.
- Preserve: the failing input unchanged for the post-fix comparison.
- Next: go to Step 2.

### Step 2: Dump the built index and decode every slot
- Actions: write a short harness that loads the data, prints each bucket (`kind`, `start`, `count`), and for each slot prints the stored position plus the decoded key of the item at that position.
- Inputs: index struct fields; item decoder.
- Outputs: a layout dump.
- Cautions: decode through the actual item store — printing raw positions hides the corruption.
- Next: go to Step 3.

### Step 3: Test the contiguity invariant on the dump
- Actions: for each bucket verify that slots `[start, start+count)` all decode to that bucket's key and that bucket ranges do not overlap; check against the observed failure (bucket 0 counted 2 slots while its second slot decoded to a different key, and bucket 1's `start` overlapped it).
- Outputs: confirmed "single-pass layout broke contiguity because keys interleaved" — or a clean dump, in which case stop and look elsewhere.
- Cautions: interleaved keys (`a, b, a`) are required to trigger this; grouped input can pass even with a buggy builder.
- Next: only on a broken dump, go to Step 4.

### Step 4: Rewrite the builder as classify-then-layout
- Actions: pass 1 — iterate items in order, classify each into a per-bucket temporary list (ground keys) or the variable/catch-all list, creating buckets as needed but never touching the shared slot array; pass 2 — for each bucket set `start = current_offset`, `count = temp_count`, and append its temp list to the shared array, advancing the offset; keep overflow behavior (capacity exceeded → treat item as catch-all) unchanged.
- Inputs: existing builder, capacity constants.
- Outputs: two-pass builder (per-bucket temporaries may be function-local `static` given bounded capacity and a non-reentrant builder — a separate, documented trade-off).
- Cautions: do not reorder items within a bucket — clause/insertion order must survive, since the query-time merge depends on ascending positions.
- Preserve: function signature, capacity fallbacks, catch-all semantics.
- Next: go to Step 5.

### Step 5: Re-dump, then run the suites
- Actions: rebuild, re-run the Step 2 harness and confirm the contiguity invariant; run the index-focused suite and the full suite.
- Outputs: clean dump + suite tallies.
- Cautions: if a query-level failure persists with a clean dump, the defect is in the query/backtracking path — report it separately instead of reopening the layout fix.
- Next: stop when all suites pass; document the two-pass decision in the project plan/changelog.

## Decision Rules
### When same-key items are interleaved with other keys in input order
Assume the single-pass shared-array layout is unsafe; a bucket's slots are only contiguous if the builder never appends another bucket's items between them.

### When the dump shows a bucket range covering foreign keys
Replace the build with two passes (classify into per-bucket temporaries, then lay out); do not patch offsets with special cases.

### When the dump is clean but the query still fails
Stop treating this as a layout problem; investigate the query/backtracking path (the trajectory separately rewrote a backtrack loop before the index dump pinpointed the layout bug).

### When bucket or slot capacity is exceeded
Keep the existing graceful fallback (overflow items go to the catch-all/variable bucket so they are always tried) — correctness may degrade to a full scan but must never drop clauses.

### When input is provably grouped by key and no corruption reproduces
Leave the single-pass builder alone; a two-pass rewrite without reproduced corruption is unverified refactoring.

## Invariants
- Public API and callers are untouched: only the internals of the index-build function change.
- Within each bucket, items keep their original input (clause) order; the query-time merge of ground bucket + catch-all in ascending item position must still be valid.
- No item is ever dropped: capacity overflows continue to route to the always-tried catch-all list.
- Catch-all (variable-first-arg) items remain guaranteed-tried for every query, including ground keys absent from the table.
- The layout invariant is checked by an actual dump, not asserted from code reading.
- Full test suite must match or exceed its pre-fix pass count before the fix is reported.

## Common Failures
### Failure: bucket start recorded at creation time, items appended later
- Symptoms: a bucket's `count` spans positions written after other buckets' entries; dump shows bucket 0 slot[1] decoding to a different key while bucket 1 starts at an overlapping offset.
- Causes: single-pass design assuming same-key items are contiguous in input.
- Recovery: two-pass classify-then-layout so offsets are assigned only after all classification is done.

### Failure: fixing the index did not make the test pass
- Symptoms: after the two-pass rewrite, one query test still fails.
- Causes: an independent bug (in this trajectory the backtrack loop was rewritten around the same window) or stale binary.
- Recovery: rebuild/rerun, re-dump the index to confirm the layout is clean, then debug the query path with its own instrumentation; do not attribute the residual failure to the index.

### Failure: layout fixed but clause ordering changed
- Symptoms: solutions come back in a different order or a "second solution" test regresses.
- Causes: pass 2 re-sorted slots or rebuilt the catch-all list out of order.
- Recovery: preserve item order inside both temporaries and keep the ascending-position merge at query time; rerun the ordering-sensitive tests.

### Failure: temporaries themselves blow the stack
- Symptoms: the rewritten builder crashes with 0xC00000FD because `BucketTemp tmp[N]` was made a local.
- Causes: per-bucket temporaries sized in the tens of KB–MB placed on the call stack.
- Recovery: make the temporaries function-local `static` in the non-reentrant builder (as done here) or otherwise off-stack, then re-run; see the companion stack-overflow skill.

## Verification
Observable checks:

1. Re-run the dump harness: every bucket's `[start, start+count)` slots decode to that bucket's own key, ranges are non-overlapping and ascending — the pre-fix dump instead showed bucket 0 containing a foreign key (`slot[1]=pos1 head=path(b,c)`) with `Total solutions: 0`.
2. The previously failing query returns its expected solution count (the `reachable(a,c)` case expects 1).
3. Index-focused suite passes completely: `13/13 tests passed`.
4. Ordering-sensitive query suite passes: `22/22 tests passed` (includes "backtracking finds second solution after first fails").
5. Full suite back to green: `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`.
6. Negative check: a query on an unseen key still returns only catch-all/variable clauses, and arity-0 predicates still bypass indexing (both covered by the index suite).

## Examples
### Example 1: Interleaved first-argument values in a Prolog clause store
- Input: clauses asserted as `path(a, b). path(b, c). path(a, c).` and query `?- reachable(a, c).` via `reachable(X, Y) :- path(X, Y).`; the single-pass index reported `path/2: count=3 buckets=2` with bucket 0 holding `slot[0]=pos0 head=path(a,b)` and `slot[1]=pos1 head=path(b,c)`, and the harness printed `Total solutions: 0`.
- Procedure: Step 2 dump → Step 3 contiguity check fails (bucket 0's second slot decodes to key `b`; bucket 1's `start=1` overlaps bucket 0's range) → Step 4 two-pass rewrite of the builder (classify into per-bucket temps, then assign offsets in pass 2) → Step 5 re-dump and run suites.
- Expected result: bucket ranges clean, query returns 1 solution; suites `22/22 tests passed`, `13/13 tests passed`, and finally `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`.
- Parameterized values: bucket capacity 64, indexed slots 256, catch-all slots 64; substitute your own key field and capacities.

### Example 2: Mixed variable/ground keys with the same builder
- Input: program containing both `f(X) :- true.` (variable first argument) and `f(a).` (ground), queried with ground and variable arguments.
- Procedure: same two-pass builder — variable-first-arg items are classified into the catch-all list during pass 1; at query time the ground bucket is merged with the catch-all in ascending position order.
- Expected result: ground query returns the matching ground clause plus catch-all clauses; variable query returns everything (index suite cases "mixed var/ground clauses resolve correctly" and "variable query still returns all solutions" pass).
- Parameterized values: catch-all capacity 64; overflow items degrade to catch-all rather than being dropped.

## Evidence
problem:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 234, source_part_index: 0, quote: "    slot[1]=pos1 head=path(b,c)", supports: the instrumented dump showing bucket 0's second slot holding a foreign key (wrong layout), the concrete reproduction of the corruption.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 234, source_part_index: 0, quote: "Total solutions: 0", supports: the user-visible symptom (query expected 1 solution) produced by the corrupted index.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 236, source_part_index: 0, quote: "The issue: **buckets don't stay contiguous** when multiple buckets interleave.", supports: the root-cause conclusion that single-pass append breaks contiguity for interleaved keys.

action:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 242, source_part_index: 0, quote: "so we cannot build the flat slot array in a single forward", supports: the explicit rationale recorded in the replacement builder comment for abandoning the single-pass layout.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 242, source_part_index: 0, quote: "    /* Pass 2: lay out buckets contiguously in idx_clause_slots[] */", supports: the second pass that assigns offsets only after classification, the core of the fix.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 372, source_part_index: 0, quote: "pass 2 lays the buckets out contiguously in idx_clause_slots[].", supports: the project's own changelog documenting the two-pass algorithm as the delivered fix.

verification:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 261, source_part_index: 0, quote: "22/22 tests passed", supports: the solver/index-integration suite (previously 21/22 with the failing query, then 0-solution repro) passing after the two-pass rewrite and relink.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 279, source_part_index: 0, quote: "13/13 tests passed", supports: the dedicated index suite (bucket classification, ground/unknown/variable queries, mixed var/ground, integer-vs-atom separation) passing with the new builder.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 333, source_part_index: 0, quote: "=== FINAL RESULT: 10/10 suites passed, 0 failed ===", supports: whole-suite confirmation that the index rewrite preserved every other behavior.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 206, source_part_index: 0, quote: "exit: -1073741571", supports: caveat that an unrelated stack-overflow crash coexisted and had to be fixed separately before the index suite itself could verify (fixes are not attributable to one cause).

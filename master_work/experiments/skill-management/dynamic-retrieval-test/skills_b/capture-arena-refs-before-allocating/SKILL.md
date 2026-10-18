---
name: capture-arena-refs-before-allocating
description: Use when a unit test fails an equality assertion of the form deref(x) == ctx.atom("name") even though unification is correct, because the helper call allocates a fresh term and returns a new arena index on every invocation. Helps the agent capture references once before mutation so assertions compare stable identity or walk state. Requires the failing assertion lines from test output and edit access to the test file. Do not use when the compared helper returns an interned or otherwise stable identifier, or when deref itself is under suspicion.
triggers:
  - "EXPECT_EQ(ctx.deref"
  - "ctx.deref(x) == ctx.atom("
---
# Write stable assertions over arena-allocated term references

## Goal
Fix unit tests whose equality assertions fail because an allocating helper is called on both sides of the comparison, by capturing the arena-allocated reference once and asserting on stable identity or walk state instead.

## Scope
### In scope
- Failing assertions of the form `EXPECT_EQ(ctx.deref(x), ctx.atom("name"))` where the second helper call allocates a new arena term, producing a different reference index than the one bound earlier.
- Capturing the reference into a local before any binding or undo, and asserting post-undo state through the variable walk result (`var_walk(...).tag == TERM_UNBOUND`) rather than reference identity.

### Out of scope
- Cases where the compared value comes from an interned table with stable ids (atom ids), which are unaffected.
- Bugs inside `deref`, `unify`, or `trail_undo` themselves; in the traced session the trail implementation was read and found correct before the test was changed.
- Fixtures or storage-layout changes (covered by the separate stack-overflow skill).

## Inputs
- **Failing assertion lines** — type: tool result text from the test run. Source: framework failure output. Required: yes. Constraint: assertions comparing `deref(...)` against a freshly created reference such as `ctx.atom("name")`. Default: 无.
- **Test file with the fixture** — type: file path. Source: project tree (trajectory: `tests/test_unifier.cpp`). Required: yes. Constraint: fixture exposes allocating helpers (`ctx.atom`, `ctx.integer`, `ctx.var`, `ctx.compound`). Default: 无.
- **Allocation behaviour of the helpers** — type: code behaviour. Source: fixture implementation; each helper appends a new term to the arena and returns its fresh `TermRef`. Required: yes (understanding). Constraint: only references returned by such helpers are affected; interned atom ids are stable. Default: 无.
- **Walk-state API for post-undo checks** — type: function. Source: engine headers (trajectory: `var_walk(&vars, var_id)` returning a `WalkResult` with `tag`). Required: yes. Constraint: needed to assert unbound state after `trail_undo`. Default: 无.

## Outputs
### Artifacts
- Test file with references captured before mutation: e.g. `TermRef alice = ctx.atom("alice");` taken before `unify`/`mark`/`undo`, then assertions comparing against that captured reference.
- Post-undo assertions expressed through walk state (`var_walk(&vars, var_id).tag == TERM_UNBOUND`) instead of reference equality against a newly built term.

### Success criteria
- The previously failing assertions pass and the whole suite reports all tests passing (trajectory: `18/18 tests passed` in the unifier suite after the change).

### Failure criteria
- A failing assertion still constructs a reference inside the comparison; or the suite passes only because the assertion was deleted; or the engine code was changed to satisfy a wrong test (not permitted by this skill).

## Preconditions
- The failing assertion compares a value obtained earlier against the result of a helper that appends a new term to an arena on every call (fresh index each time).
- The engine behaviour under test is believed correct: check the engine code (trajectory: `trail_undo` was read and confirmed to reset both tag and value before the test was declared wrong).
- A walk/deref API exists to observe binding state without allocating (trajectory: `var_walk` returning `WalkResult` with `tag` and `root_id`).
- Edit access to the test file only; engine sources must not be modified to make a wrong test pass.
If the compared helper returns a stable interned id (e.g. atom id lookup), this skill does not apply.

## Procedure
### Step 1: Read the failing assertions and classify
- actions: List the failing assertion lines; check whether either side of each comparison calls a helper that allocates a new term (trajectory: `ctx.deref(x) == ctx.atom("alice")` and `ctx.deref(x) == ctx.atom("before")`).
- inputs: test failure output.
- outputs: set of assertions that compare against freshly allocated references.
- cautions: assertions that captured the reference earlier (`TermRef alice = ctx.atom("alice"); ... EXPECT_EQ(dr, alice);`) passed in the same run — use them as the model.
- next condition: assertions classified as identity comparisons against fresh allocations.

### Step 2: Check the engine implementation before blaming it
- actions: Read the relevant engine function (trajectory: `trail_undo` in `engine/unifier.cpp`) and confirm it restores the expected state.
- inputs: engine source.
- outputs: confirmation that the implementation resets both tag and value, so the test expectation is what is wrong.
- cautions: do not modify engine code to satisfy an assertion built on unstable references.
- next condition: test-side fix justified.

### Step 3: Capture references before mutation
- actions: Hoist the allocating call above the operation being tested: `TermRef alice = ctx.atom("alice");` then `ctx.unify(x, alice); EXPECT_EQ(ctx.deref(x), alice);`.
- inputs: failing tests.
- outputs: assertions compare stable identity.
- cautions: keep the semantic intent — a reference created after a binding/undo must not be used to check that earlier binding.
- next condition: identity assertions fixed.

### Step 4: Express post-undo checks as walk state
- actions: After `trail_undo`, assert unbound state through the variable walk (`var_walk(&vars, var_id).tag == TERM_UNBOUND`) rather than comparing references, since the binding itself is gone.
- inputs: undo-related tests.
- outputs: assertions that remain valid regardless of later allocations.
- cautions: obtain `var_id` from the term node before undoing.
- next condition: rebuild and run the suite.

### Step 5: Rebuild and run the suite
- actions: Compile the test file and run the binary; confirm the previously failing assertions now pass and no new failures appear.
- inputs: build and run commands.
- outputs: full suite summary (trajectory: `18/18 tests passed`).
- cautions: run the whole suite, not just the edited tests, to catch cross-test effects.
- next condition: stop when the suite passes; otherwise re-read the assertions for remaining fresh-allocation comparisons.

## Decision Rules
### When an equality assertion fails between a dereffed value and a freshly constructed term reference
The constructing helper allocates on every call, so the two references can never be compared. Capture the reference once, before the operation under test, and compare against the captured value.

### When the assertion checks state after trail undo
Undo removes the binding, so compare walk state (`var_walk(...).tag == TERM_UNBOUND`) instead of reference identity; a reference built after undo is a different arena entry.

### When the engine code looks suspicious but the test compares fresh allocations
Verify the engine function by reading it (it reset both tag and value in the traced session), then fix the test. Never change engine code to satisfy an assertion built on unstable references.

## Invariants
- Do not modify engine code to make a test built on unstable references pass.
- Do not delete the failing assertion; restructure it to capture the reference or assert walk state.
- References used in comparisons must be created before the operation whose effect is being checked.
- Interned identifiers (atom ids) keep their stable-identity semantics; only arena-allocated references need capture.
- Do not claim the suite passes based on a partial rerun; run the whole suite after the edit.

## Common Failures
### Failure: assertion still fails after capturing one side
symptoms: the comparison still mismatches.
causes: the captured reference was taken after an operation that allocated more terms, or the test compares against a reference obtained inside a helper that allocates each call.
recovery: move the capture to the first point after the term is created, before any unify/mark/undo.

### Failure: mistakenly "fixing" the engine
symptoms: engine sources edited to make the assertion pass.
causes: assuming the engine is wrong because the assertion reads plausible.
recovery: revert engine changes; read the engine function first (the trace's `trail_undo` was verified correct), then fix the test.

### Failure: passing test hides a broken assertion
symptoms: suite green because the assertion was deleted or replaced with a trivially true one.
cautions: the goal is an equivalent but stable check (identity of the captured ref, or walk state after undo).
recovery: restore an assertion with real semantic content.

## Verification
- Rebuild and run the suite containing the edited tests; the previously failing assertion lines must no longer appear in the failure output.
- Confirm the suite summary reports all tests passing (observed after the fix: `18/18 tests passed` in the unifier suite).
- Review the edited assertions to confirm each comparison uses a captured reference or walk state, and none constructs a term inside the comparison.
- Run neighbouring suites to confirm no cross-test effects were introduced.

## Examples
### Example 1: capture the atom reference before unify and undo
input: The unifier suite fails two tests: `FAIL  D:\Epilog\tests\test_unifier.cpp:203  ctx.deref(x) == ctx.atom("alice")` and a similar failure at line 222 comparing against `ctx.atom("before")`, although `unify` and `trail_undo` (read in `engine/unifier.cpp`) behave correctly.
procedure: Step 1 classify both assertions as comparisons against freshly allocated references; Step 2 verify the engine's undo resets tag and value; Step 3 rewrite the tests to capture the reference first — `TermRef alice = ctx.atom("alice"); ... ctx.unify(x, alice); EXPECT_EQ(ctx.deref(x), alice); ctx.undo(mark);` — and assert post-undo unbound state via `var_walk(&ctx.vars, t->data.var.var_id).tag == TERM_UNBOUND`; Step 5 rebuild and rerun the suite.
expected result: the two failures disappear and the suite reports `18/18 tests passed`, with engine sources unchanged.
parameterized values: variable names, atom spellings, suite name, engine headers consulted.

## Evidence
- problem — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1048, source_part_index: 0, quote: `FAIL  D:\Epilog\tests\test_unifier.cpp:203  ctx.deref(x) == ctx.atom("alice")`, supports: the trail tests failed because the assertion constructed a fresh arena reference inside the comparison, so it could never equal the earlier-bound reference.
- problem — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1071, source_part_index: 0, quote: `e->tag              = TERM_UNBOUND;`, supports: reading `trail_undo` in `engine/unifier.cpp` confirmed the engine resets the binding correctly, so the test expectation was at fault.
- action — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1077, source_part_index: 0, quote: `TermRef  alice = ctx.atom("alice"); /* capture ref before any undo */`, supports: the fix captures the reference once before unify/mark/undo and compares against the captured value, with walk-state checks after undo.
- verification — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1191, source_part_index: 0, quote: `18/18 tests passed`, supports: after this test-only change the unifier suite passes completely, with engine sources untouched.

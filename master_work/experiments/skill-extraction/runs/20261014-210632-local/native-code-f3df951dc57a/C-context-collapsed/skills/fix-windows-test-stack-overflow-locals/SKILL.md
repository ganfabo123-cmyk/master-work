---
name: fix-windows-test-stack-overflow-locals
description: Use when a Windows test binary compiles and links but prints nothing and exits with code -1073741571. Helps the agent size the test harness locals, move MB-scale fixed-size structs to static storage with per-test re-initialisation, and remove by-value copies of large structs so the tests actually run. Requires the test source, struct size estimates, and a rebuild/run cycle. Do not use when the binary fails to link (use resolve-lnk1105-locked-output) or when tests print failures and exit 1.
---
# Fix Windows Test Binaries That Exit Silently with -1073741571

## Goal
Make a Windows test binary that currently exits silently with code -1073741571 actually execute its tests, by removing MB-scale fixed-size struct allocations from the function stack and proving it with a green run.

## Scope
### In scope
- Confirming the silent-crash signature: no test output plus exit code -1073741571 on a binary that compiled and linked.
- Estimating the size of the test harness's per-test locals (arena/table/registry members) and comparing them against the Windows default 1 MB stack.
- Converting MB-scale harness state to static storage (class static members or function-local `static`) while keeping explicit re-initialisation per test.
- Removing accidental by-value copies of large structs produced by value-returning helpers.
- Rebuilding and re-running the affected binary and then the full suite.

### Out of scope
- File-lock/link problems such as `LNK1105` (handle those first with resolve-lnk1105-locked-output).
- Test assertion changes, test removal, or test-framework rewrites.
- Production engine code restructuring.
- Crashes that occur after tests start printing PASS lines, and assertion failures with exit code 1.
- Unverified causes: static-initialisation order and framework-registry corruption were speculated about in the trajectory but never confirmed.

## Inputs
- **Crash observation** — record — tool result of running the binary — required — empty output plus `exit: -1073741571` for the target binary, while sibling suites print PASS lines — default: 无.
- **Test source file** — file — repository — required — the failing `tests/test_*.cpp` (or equivalent harness) and the context struct it instantiates per test — default: 无.
- **Struct size estimates** — numbers — derived from headers/field arithmetic — required — e.g. `AtomTable` ~1 MB, `Database` ~1.6 MB, combined context ≈3.4 MB — default: computed by field arithmetic or `sizeof` when a build is available.
- **Stack budget** — constant — environment — required — Windows default thread stack of 1 MB that the harness must fit into — default: 1 MB.
- **Existing static pattern** — file — repository — optional — an already-static sibling harness whose storage pattern can be copied — default: 无.
- **Rebuild/run command** — string — build system — required — the command that recompiles one test binary and runs it — default: the project's existing test build command.

## Outputs
### Artifacts
- Edited test source in place — same file path — C++ source containing static-storage harness members and reference (not value) bindings — format: source file.
- Rebuilt test binary — existing build path — format: PE `.exe`.
- Run log with per-suite pass counts and the final suite summary — session log — format: plain text.

### Success criteria
- The previously silent binary exits 0 and prints its per-test PASS lines (observed `13/13 tests passed`, `17/17 tests passed`).
- The full suite run ends with all suites passing (observed `=== FINAL RESULT: 10/10 suites passed, 0 failed`).
- The diff touches only storage duration in test sources; assertions and test names are unchanged.

### Failure criteria
- The binary still exits -1073741571 after the static-storage and reference edits.
- No local larger than about 1 MB is found in the harness (cause unconfirmed — stop and re-diagnose instead of guessing).
- The test file no longer compiles after the edit.

## Preconditions
- The host is Windows with the default 1 MB thread stack, and the target binary already compiles and links (if linking fails, resolve that first with resolve-lnk1105-locked-output).
- The observed symptom is exactly: no test output printed and process exit code -1073741571 (decodes to 0xC00000FD, STATUS_STACK_OVERFLOW).
- The test source for the failing binary is readable and editable, and the rebuild/run command for that single binary is known.
- At least one struct instantiated per test can be sized (by `sizeof` or field arithmetic) so the 1 MB budget can be checked.
- If the binary prints PASS/FAIL lines and exits 1, stop: that is an assertion failure, not this problem.
- If no harness local approaches 1 MB, stop and report that the cause is unconfirmed rather than applying speculative fixes.

## Procedure
### Step 1: Confirm the silent-crash signature
- Actions: run the binary; record the exit code; confirm that no PASS lines were printed; compare with sibling suites that print results normally in the same run.
- Inputs: run output for the failing binary and for a healthy sibling.
- Outputs: confirmation of "silent exit -1073741571"; failing binary name.
- Cautions: an empty run can also mean the binary was never produced — check the link step's result first (a lock shows `LNK1105`, not a silent exit).
- Preserve: nothing is edited in this step.
- Next condition: signature confirmed → Step 2; a link error is present → handle the lock first.

### Step 2: Size the harness locals against the 1 MB budget
- Actions: enumerate everything instantiated per test in the harness (atom tables, clause databases, term arenas, variable registries, solver stacks); compute approximate sizes from field counts or `sizeof`; sum them for one test's frame.
- Inputs: test source and headers.
- Outputs: list of stack-resident objects with sizes and a total compared to 1 MB.
- Cautions: the trajectory estimated sizes by field arithmetic (≈3.4 MB context, ~1 MB table, ~1.6 MB database) without `sizeof` — keep estimates labelled as estimates.
- Preserve: analysis only, no edits.
- Next condition: at least one object ≥ ~1 MB or a total near/over 1 MB → Step 3; nothing close → stop and report the cause as unconfirmed.

### Step 3: Move MB-scale state to static storage
- Actions: convert the harness's per-test members to static storage — class static members or function-local `static` objects — and keep an explicit re-initialisation call at the start of each test (constructor or `*_init` helper) so every test starts from clean state.
- Inputs: harness source from Step 2.
- Outputs: edited harness with static members plus per-test re-init.
- Cautions: without re-initialisation, static state leaks between tests and produces false passes/failures.
- Preserve: test names, assertions, ordering, and the helper's re-init semantics.
- Next condition: compiles → Step 5 (continue to Step 4 if copies remain).

### Step 4: Remove accidental by-value copies of large structs
- Actions: search the harness for assignments, arguments, or returns that copy a big struct by value (observed `AtomTable t = make_table();`) and bind by reference instead (`AtomTable &t = make_table();`).
- Inputs: harness source.
- Outputs: value bindings replaced with reference bindings.
- Cautions: a helper returning a reference still copies if the receiving variable is declared by value — check the receiver, not just the helper.
- Preserve: the helper's behaviour (re-initialise on each call) stays intact.
- Next condition: compiles → Step 5.

### Step 5: Rebuild, run the target, then run the full suite
- Actions: rebuild the affected test binary only; run it and record exit code plus pass counts; then run the whole suite for a final summary; optionally re-run the target twice to confirm stable counts.
- Inputs: rebuild/run commands.
- Outputs: exit code 0, per-suite pass counts, suite summary.
- Cautions: sibling suites failing for unrelated reasons are out of scope — report them separately instead of folding them into this result.
- Preserve: no edits outside the test sources.
- Next condition: target exits 0 with pass counts → done; still -1073741571 → stop and re-diagnose, cause unconfirmed.

## Decision Rules
### When a linked test binary exits -1073741571 with no output
Treat it as a stack overflow (0xC00000FD) and measure the harness locals before touching the test framework, assertions, or production code.

### When the harness context combines several multi-MB fixed-size members
Give the whole context static storage (class statics or function-local `static`) and re-initialise every member per test; the trajectory's fix for an ≈3.4 MB context yielded 13/13 then 10/10 suites passing.

### When most members are static but one binding still copies a ~1 MB struct by value
Change the receiver to a reference (`AtomTable &t = make_table();`); after that single edit the atoms suite printed 17/17 tests passed.

### When a file lock had to be cleared before linking
Expect the relink to succeed while the crash remains: a run showed `performing full link` with no LNK1105 and still `exit: -1073741571`. Continue with this procedure; do not report the work as done on the basis of linking.

### When no harness local is anywhere near 1 MB
Stop and report the cause as unconfirmed. Speculative explanations (static-initialisation order, shared framework registry) appeared in the trajectory but were never verified, and the failing binary stayed unresolved there.

## Invariants
- Change storage duration only: test names, assertions, expected values, and test ordering stay byte-for-byte identical.
- Every piece of shared static state is re-initialised at the start of each test; no test may consume another test's state.
- Never disable, skip, or delete a failing test to obtain a green run.
- Do not modify production engine code from this skill; the observed fixes were confined to test sources.
- Do not report a suite as passing without a run showing exit 0 and printed pass counts.
- Do not attribute the crash to the test framework, static-initialisation order, or shared registries before measuring local sizes against the 1 MB budget; unverified causes are reported as unconfirmed.

## Common Failures
### Failure: Silent exit -1073741571 before any test output
- Symptoms: the suite header prints (e.g. `=== test_indexing ===`) followed by `exit: -1073741571` with zero PASS lines, while sibling suites in the same run print results normally.
- Causes: a multi-MB fixed-size test context (estimated ≈3.4 MB from AtomTable 1 MB + Database 1.6 MB + two TermArenas + two VarRegistries) allocated as a function-local, exceeding the 1 MB default Windows stack.
- Recovery: make the harness members static and re-initialise per test; the same suite then printed `13/13 tests passed` and the full run ended `10/10 suites passed, 0 failed`.

### Failure: One by-value copy inside an otherwise static harness
- Symptoms: the crash persists although most members are static; the offending statement assigns a ~1 MB struct from a value-returning helper (`AtomTable t = make_table();`).
- Causes: the receiver is declared by value, so the reference returned by the helper is copied onto the stack.
- Recovery: change the receiver to a reference (`AtomTable &t = make_table();`); the atoms suite subsequently printed `17/17 tests passed`.

### Failure: File lock cleared but crash remains
- Symptoms: after process kills the link reports `LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link` with no LNK1105, yet the run still ends `exit: -1073741571`.
- Causes: removing the lock only restores linking; the stack-overflow defect lives in the test source. In one session this crash was never resolved within the visible trajectory.
- Recovery: apply this procedure after linking works; never report the build as fixed on the strength of a successful link alone.

### Failure: Cause speculation without measurement
- Symptoms: repeated hypothesis changes (static-initialisation order, shared test-framework registry, shared static token lists) with no size check and no behavioural change in the failing binary.
- Causes: cause unconfirmed — the trajectory contains the reasoning but no verification for these hypotheses.
- Recovery: measure the harness locals against the 1 MB budget first; if nothing is near the limit, stop and report the cause as unconfirmed instead of continuing to speculate.

## Verification
- The binary that previously printed nothing now prints its per-test PASS lines and exits 0.
- The suite that exited -1073741571 reports its count, e.g. `13/13 tests passed` after the static-context change, or `17/17 tests passed` after the by-value copy was made a reference.
- The full suite run ends with an all-green summary such as `=== FINAL RESULT: 10/10 suites passed, 0 failed`.
- Re-running the affected binary twice yields identical counts, confirming per-test re-initialisation of the shared static state.
- The diff shows only storage-duration edits in test sources (`static` members, `&` bindings, re-init calls); assertions, test names, and expected values are unchanged.
- Healthy suites that passed before the edit still pass after it (no regression from shared static state).
- If any of these checks fail, the fix is not complete: re-open Step 2/Step 3 rather than reporting success.

## Examples
### Example 1: Multi-MB test context moved to static members
- Input: `test_indexing` compiles and links, then prints only its header and `exit: -1073741571`, while `test_stats` and `test_memo` in the same run print `10/10` and `11/11`.
- Procedure: Step 1 confirms the silent-crash signature; Step 2 sizes the context (`AtomTable` ≈1 MB, `Database` ≈1.6 MB, two `TermArena`s, two `VarRegistry`s → ≈3.4 MB, i.e. over the 1 MB default stack); Step 3 converts the context members to static storage with per-test re-initialisation; Step 5 rebuilds and runs the suite.
- Expected result: exit 0 with `13/13 tests passed`, and the full run ends `=== FINAL RESULT: 10/10 suites passed, 0 failed`.
- Parameterized values: context struct name, per-field sizes, suite name, build flags (`-std=<std> -Wall -Wextra -I<include> -g -O0`).

### Example 2: 1 MB struct copied by value inside a static helper
- Input: `test_atoms` prints nothing and exits -1073741571 even though its helper already keeps the table in a function-local `static`; the offending statement is `AtomTable t = make_table();`.
- Procedure: Step 4 changes the receiver to a reference (`AtomTable &t = make_table();`), Step 5 rebuilds that one binary and runs it, then runs the whole suite.
- Expected result: the atoms suite prints `17/17 tests passed` and the suite summary stays all-green.
- Parameterized values: struct type, helper name, per-suite pass counts.

### Example 3: Distinguishing a cleared lock from a fixed test
- Input: after killing test processes the link reports `LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link` with no LNK1105, but the run still ends `exit: -1073741571`.
- Procedure: record the link as resolved (Step 1 of the lock procedure), then start this procedure at Step 1 for the runtime crash.
- Expected result: the session reports two separate facts — lock cleared, test still crashing — and proceeds to size the harness instead of re-killing processes.
- Parameterized values: binary name, exit code, suite name.

## Evidence
- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 206, source_part_index: 0
  quote: `exit: -1073741571`
  supports: problem — `test_indexing` printed its header and nothing else while `test_stats`, `test_memo`, and `test_solver` in the same run printed pass counts.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 262, source_part_index: 0
  quote: `But the 3.4MB still exceeds the default Windows stack size (1MB).`
  supports: problem diagnosis — size analysis of the per-test context (AtomTable 1 MB + Database 1.6 MB + two TermArenas + two VarRegistries) against the 1 MB Windows stack budget.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 267, source_part_index: 0
  quote: `The \`IdxCtx\` struct members need to become static like in \`test_solver.cpp\`.`
  supports: action — move the multi-MB harness members to static storage, mirroring an existing static harness.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 282, source_part_index: 0
  quote: `13/13 tests passed`
  supports: verification — after the static-members edit the previously silent `test_indexing` suite compiled, ran, and passed every test.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 324, source_part_index: 0
  quote: `this copies the 1MB \`AtomTable\` by value onto the LOCAL stack! That's an immediate stack overflow.`
  supports: problem diagnosis — the single by-value binding that kept `test_atoms` crashing inside an otherwise static harness.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 325, source_part_index: 0
  quote: `AtomTable  &t  = make_table();`
  supports: action — the by-value receiver replaced with a reference binding.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 333, source_part_index: 0
  quote: `PASS  intern empty string is a valid atom`
  supports: verification — the atoms suite now prints its individual PASS lines in the final full run.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 333, source_part_index: 0
  quote: `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`
  supports: verification — full-suite green run after the static-storage and reference fixes.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 287, source_part_index: 0
  quote: `AtomTable is ~1 MB — too large for the default Windows stack.`
  supports: action — the harness pattern actually used: a single function-local `static` instance re-initialised per test.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 372, source_part_index: 0
  quote: `GoalStack, ChoiceStack, and RenameMap in solve() are now \`static\` locals to keep them out of the call stack (Windows default 1 MB limit).`
  supports: action — the same static-storage remedy was applied to large engine-side stacks, documented in the changelog written in this session.

- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1194, source_part_index: 0
  quote: `exit: -1073741571`
  supports: problem (recurrence) — in another session the same silent crash survived a successful relink (`performing full link`, no LNK1105 in the same result), showing that clearing locks and fixing the crash are independent.

- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1195, source_part_index: 0
  quote: `This is a static initialisation crash`
  supports: failure mode (unverified cause) — a speculative explanation recorded without measurement or a passing run; the binary stayed unresolved in the visible trajectory, so such hypotheses must not be reported as facts.

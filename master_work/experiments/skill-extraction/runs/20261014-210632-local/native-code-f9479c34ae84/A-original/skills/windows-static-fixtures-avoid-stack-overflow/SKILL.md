---
name: windows-static-fixtures-avoid-stack-overflow
description: Use when C++ test executables on Windows exit with -1073741571 and print no test output, indicating a startup stack overflow caused by multi-megabyte fixtures (AtomTable, TermArena, Database, TokenList) declared as locals or returned by value. Helps the agent relocate every large fixture to static storage, bind it by reference, and re-run the suite until each suite prints a pass count. Requires knowledge of each fixture's size, an editable test source tree, and a build-and-run script for all test binaries. Do not use when the binary fails to link or is locked by another process, or when individual assertions fail inside a suite that already runs.
---
# Move Multi-MB Test Fixtures to Static Storage on Windows

## Goal
Stop Windows test executables from crashing at startup (exit -1073741571, zero test output) by moving every multi-megabyte test fixture into static storage, so the suites run and print their pass counts.

## Scope
### In scope
- Test binaries that terminate with exit code `-1073741571` before printing any `PASS`/`FAIL` line.
- Fixtures sized in the megabytes used by the tests: atom table (~1 MB), term arenas (~4 MB), database (~4 MB), token lists (~128 KB), plus the contexts that embed them.
- Patterns: helper functions returning a function-local `static` object by reference, fixture structs whose large members are `static` and bound by reference in the constructor, and `static` locals replacing stack locals inside test bodies.
- Re-running the whole suite until each suite prints `N/N tests passed`.

### Out of scope
- Suites that fail to link or whose executable is locked (see recover-lnk1105-locked-test-binary).
- Individual assertions failing inside a suite that runs to completion (engine/test logic defects).
- Changing production code layout or raising the thread stack size — the trace never tried either.
- The final state of `test_atoms`: in the last visible run it still produced no output; its remaining cause is unconfirmed.

## Inputs
- **Per-suite exit codes and output**: string; source = tool results of the run script (e.g. `(exit -1073741571)` for every suite); required; a suite with an exit code but no test lines indicates startup failure; default: none.
- **Fixture inventory with sizes**: list of struct name → approximate size (`AtomTable` ~1 MB, `TermArena` ~4 MB, `Database` ~4 MB, `TokenList` ~128 KB); source = headers/`sizeof` reasoning in the trace; required to decide what must leave the stack; default: none.
- **Test sources**: `tests/test_*.cpp` and their fixture helpers; source = project; required; default: none.
- **Build-and-run script**: PowerShell loop compiling each test with the full source list and executing it; source = project; required for verification; default: none.
- **Platform**: Windows, default thread stack far smaller than the fixture sizes (trace: local `AtomTable` of ~1 MB overflows a default 1 MB stack); source = environment; required; default: none.

## Outputs
### Artifacts
- Test sources in which large fixtures live in static storage: helpers such as `static AtomTable &fresh_table() { static AtomTable t; atom_table_init(&t); return t; }` exposed via `#define make_table() fresh_table()`, fixture structs with `static` members plus reference members (e.g. `SolverCtx`), and `static` locals inside test bodies.
- A suite run in which every previously silent suite prints test lines.

### Success criteria
- No suite exits `-1073741571` with empty output; each suite prints `PASS`/`FAIL` lines and `N/N tests passed`.
- The harness prints a final tally covering all suites.

### Failure criteria
- Any suite still exits `-1073741571` with no output.
- A suite prints nothing at all in the summary (its crash or lock is unresolved).
- Fixtures remain reachable as by-value copies of multi-MB objects inside test functions.

## Preconditions
- The failing suites compile and link successfully first; if they do not, resolve the link problem first (LNK2019 or LNK1105 procedures).
- You can enumerate the fixture types and their sizes (from headers or `sizeof`); without sizes you cannot tell stack from non-stack causes.
- Edit access to all `tests/test_*.cpp` files, including helpers and fixture structs.
- A build-and-run script that executes every suite and echoes each exit code.
- The environment is Windows with default thread stacks (the observed exit code and stack-limit reasoning are Windows-specific); on other platforms stop and confirm the crash cause before applying this procedure.

## Procedure
### Step 1: Confirm a startup crash rather than test failures
Actions: run the suite script and inspect each suite's section: record exit code and whether any `PASS`/`FAIL` line was printed. Inputs: run output. Outputs: list of suites exiting `-1073741571` with empty output. Cautions: an empty section can also mean a link failure — check for `COMPILE ERROR` lines first and route those elsewhere. Preserve: nothing is edited yet. Next: proceed only for suites that link but print nothing.

### Step 2: Size every fixture that test code can put on the stack
Actions: list `AtomTable` (~1 MB), `TermArena` (~4 MB), `Database` (~4 MB), `TokenList` (~128 KB) and the contexts embedding them (e.g. `SolverCtx` with two `TermArena`s, ~8 MB); mark each use as local variable, by-value return, or by-value copy from a helper. Inputs: headers, test sources. Outputs: a checklist of stack-resident multi-MB objects. Cautions: one ~1 MB local is already enough to overflow a default 1 MB stack. Preserve: production sources. Next: Step 3.

### Step 3: Move fixtures to static storage
Actions: (a) replace value-returning helpers with static-backed ones — `static AtomTable &fresh_table()` plus `#define make_table() fresh_table()`; (b) give fixture structs `static` members and bind references in the constructor, e.g. `static AtomTable s_atoms; ... SolverCtx() : atoms(s_atoms), ... { atom_table_init(&atoms); db_init(&db); ... }`; (c) replace remaining large locals inside test bodies with `static` storage (`AtomTable &t = fresh_table();`). Inputs: test sources. Outputs: no multi-MB object reachable from a test function frame. Cautions: every constructor must still reinitialize the statics, because they are shared across tests. Preserve: test assertions and names. Next: Step 4.

### Step 4: Audit for by-value copies of the static fixtures
Actions: grep the helpers and their call sites; a call written `AtomTable t = make_table();` copies the whole ~1 MB object back onto the stack even though the helper is static — bind a reference instead: `AtomTable &t = make_table();`. Inputs: test sources. Outputs: all call sites use references. Cautions: this copy-vs-reference point was identified in the trace but the suite it targeted (`test_atoms`) never produced a passing run afterwards; treat it as a required check, not as a proven fix. Next: Step 5.

### Step 5: Rebuild and rerun every suite
Actions: re-run the full build-and-run script; compare per-suite exit codes and pass counts with the Step 1 baseline. Inputs: build script. Outputs: per-suite output and final tally. Cautions: suites that now run may expose ordinary assertion failures — report them separately from stack issues. Next: stop when no suite exits `-1073741571` with empty output.

## Decision Rules
### When a suite that links cleanly exits -1073741571 with no test lines
Treat it as a startup stack overflow: move that suite's multi-MB fixtures to static storage (Steps 2–3).

### When a helper must return a large fixture
Make it return a reference to a function-local static (`static AtomTable &fresh_table()`), never the object by value.

### When a fixture struct embeds several multi-MB members
Give the members `static` storage and bind them by reference in the constructor; reinitialize them in the constructor because all tests share them.

### When a call site initializes a fixture from a helper with `Type t = helper();`
Rewrite it as `Type &t = helper();` — the by-value form copies megabytes onto the stack (identified in the trace; the targeted suite's recovery was not captured, so re-verify after every change).

### When, after static conversion, a suite runs but individual assertions fail
This is no longer a stack problem: report the failing assertions separately and do not keep moving storage classes.

### When a suite still prints nothing after all fixture moves
Stop and collect new evidence (the trace ends with `test_atoms` still silent and a process-kill relink whose result was not captured); do not claim success for that suite.

## Invariants
- No multi-megabyte object may be created on a test-function stack frame: not as a local, not as a by-value return, not as a by-value copy of a helper result.
- Static fixtures are reinitialized in the fixture constructor/helper on every test that uses them; static storage never means "initialized once at program start and reused dirty".
- Test assertions, test names, and the runner are not modified to accommodate the storage change.
- Production sources and build flags stay untouched; only test code moves to static storage.
- Every change is followed by a full re-run of all suites; a single hand-built binary is not sufficient evidence.
- Report only suites that actually printed results; a silent suite stays reported as unresolved.

## Common Failures
### Failure: Static helper bound by value at the call site
Symptoms: suite still exits with no output although the helper returns a `static` reference. Causes: `AtomTable t = make_table();` copies the ~1 MB object into a stack local; the trace identified this copy explicitly. Recovery: rewrite every call site as `Type &t = helper();` and re-run — note the trace's last visible run still showed the targeted suite silent, so confirm with a fresh run.

### Failure: One test body keeps its own stack local
Symptoms: after converting helpers, a specific suite still crashes at startup. Causes: an overlooked `AtomTable t;` (or similar) declared directly inside a `TEST` body — observed while the suite kept crashing after the helper conversion. Recovery: grep the file for large types in test bodies and convert them to the static-backed helper.

### Failure: Suite runs but assertions fail after the move
Symptoms: the binary now prints test lines yet ends with failures such as `18/22 tests passed (4 FAILED)` in a suite that had been crashing before. Causes: ordinary test/engine defects that were previously masked by the crash; in the trace the root cause of those specific assertion failures was investigated but not confirmed. Recovery: stop stack work for that suite; diagnose assertions separately.

### Failure: Treating a locked binary's empty output as a stack overflow
Symptoms: a suite section is empty but the build printed `LNK1105 ... error code 1224`. Causes: the executable was never relinked because a process still holds it. Recovery: use recover-lnk1105-locked-test-binary instead.

## Verification
- Re-run the full build-and-run script and confirm no suite prints `(exit -1073741571)` (or exits `-1073741571`) with an empty section.
- Each suite that previously crashed now prints individual `PASS` lines and a `N/N tests passed` line (observed target state: suites reporting `22/22 tests passed`, `15/15 tests passed`, `18/18 tests passed`, `12/12 tests passed`, `17/17 tests passed`).
- The harness reaches its final tally line (e.g. `=== 6 PASSED, 1 FAILED ===`), proving every suite was executed rather than aborted.
- Search the test sources for remaining large types in value positions (`Type t = make_table();`, `Type t;` inside test bodies) and confirm none remain.
- Any suite still producing no output must be listed as unresolved with its last observed output, not counted as fixed.

## Examples
### Example 1: All suites crash before the first assertion
Input: run output where `test_atoms`, `test_terms`, `test_parser`, `test_unifier`, `test_solver` each print `(exit -1073741571)` and nothing else, while the project's fixtures are `AtomTable` ~1 MB, `TermArena` ~4 MB, `Database` ~4 MB, `TokenList` ~128 KB.
Procedure: Step 1 (classify as startup crash), Step 2 (size inventory), Step 3 (static-backed helpers and static fixture members), Step 5 (full rerun).
Expected result: the silent suites start printing test lines and pass counts; the final tally covers all suites (observed end state `=== 6 PASSED, 1 FAILED ===` with `test_atoms` still silent).
Parameterized values: exit code `-1073741571`, helper name `fresh_table()`, macro alias `make_table()`, fixture struct `SolverCtx`, output dir `build\tests`.

### Example 2: Fixture struct with six multi-MB members
Input: a `SolverCtx` holding `AtomTable`, `Database`, two `TermArena`s and two `VarRegistry`s as plain members, constructed as a test local (~12 MB).
Procedure: Step 3(b): declare `static AtomTable s_atoms; static Database s_db; static TermArena s_clause_arena; ...` and construct reference members bound to them, re-running every `*_init` in the constructor; then Step 5.
Expected result: constructing `SolverCtx` inside a test body no longer allocates megabytes, and multi-clause/multi-query tests execute (suite printed `22/22 tests passed`).
Parameterized values: member prefix `s_`, initializers `atom_table_init`, `db_init`, `term_arena_init`, `var_registry_init`.

### Example 3: Helper is static but the call site copies
Input: `static AtomTable &fresh_table()` exists, yet tests still write `AtomTable t = make_table();` and the suite exits silently.
Procedure: Step 4 — rewrite to `AtomTable &t = make_table();` everywhere, then Step 5 rerun.
Expected result: no megabyte copy on the stack; the suite must be re-run and only its actual output may be reported (the trace's final run for this suite was not captured).
Parameterized values: call sites count in `tests/test_atoms.cpp`, edit mode `replace_all`.

## Evidence
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 987; source_part_index: 0; quote: `(exit -1073741571)`; supports: problem — five suites linked but died before printing any test line (startup crash signature).
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 998; source_part_index: 0; quote: `when test functions declare it on the stack, several of them together overflow the default 1MB Windows thread stack`; supports: diagnosis (assistant judgement) tying the exit code to stack overflow by multi-MB fixtures.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1002; source_part_index: 0; quote: `AtomTable is ~1 MB — too large for the default Windows stack.`; supports: action — test helper replaced by a static instance re-initialised per test.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1036; source_part_index: 0; quote: `Large members (AtomTable ~1MB, TermArena ~4MB) live in static storage.`; supports: action — fixture struct converted to static members bound by reference.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1059; source_part_index: 0; quote: `AtomTable &t = fresh_table();`; supports: action — remaining stack local inside a test body replaced by a reference to the static fixture.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1203; source_part_index: 0; quote: `So \`AtomTable t = make_table()\` **copies** the ~1MB AtomTable onto the local stack.`; supports: diagnosis (assistant judgement) of why a suite kept crashing after the helper was made static; the matching edit is at source_index 1204 (`AtomTable &t = make_table();`) but no passing run for that suite was captured afterwards.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1191; source_part_index: 0; quote: `=== 6 PASSED, 1 FAILED ===`; supports: verification — after the static-storage conversion the previously silent `test_parser` (12/12), `test_solver` (22/22), `test_terms` (15/15), `test_unifier` (18/18) and `test_variables` (17/17) suites ran and printed counts; only `test_atoms` remained blocked (by a link lock in that run).
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1218; source_part_index: 0; quote: `=== 5/6 suites PASSED, 2 FAILED ===`; supports: boundary of verification — in the last captured full run `test_atoms` still printed nothing, so that suite is explicitly not claimed as fixed.

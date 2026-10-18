---
name: fix-test-stack-overflow-large-fixtures
description: Use when test binaries on Windows exit with -1073741571 (0xC00000FD, STATUS_STACK_OVERFLOW) before printing any test output while test fixtures hold large fixed-size arena or table structs by value. Helps the agent move that storage to static members and reference bindings so suites run inside the default 1 MB thread stack. Requires test run output showing the negative exit code and access to the test sources. Do not use when suites print their assertions and fail them, or when a fixture-free minimal test also crashes.
---
# Keep multi-megabyte test fixtures off the default Windows stack

## Goal
Stop test binaries from crashing at startup with a stack overflow on Windows by moving the large fixed-size fixture storage of arena/table-based test harnesses off the thread stack, so every suite prints its results and exits with its real status.

## Scope
### In scope
- Test harness structs and helpers whose members are large fixed-size engine structs (atom table, term arena, variable registry, clause database) and which are declared as locals or returned by value, causing Windows thread-stack overflow at process start.
- Moving that storage to function-local `static` instances (helper pattern) or class `static` members bound by reference in the fixture constructor, and binding helper results by reference instead of by value.
- Confirming each suite prints results after the change.

### Out of scope
- Assertion failures that appear once the suites run (e.g. wrong test expectations, engine bugs).
- Production-code allocation strategy (the engine's no-heap design is unchanged; only test storage location changes).
- Linux/macOS stack sizes; the evidence is Windows default 1 MB stack behaviour.
- The final state of suites whose last rerun result is not visible in the trace (see Verification notes).

## Inputs
- **Test run output with negative exit codes** — type: tool result text. Source: running each test binary. Required: yes. Constraint: suites exiting `-1073741571` with no printed test lines. Default: 无.
- **Test fixture sources** — type: file paths. Source: `tests/test_*.cpp` and the shared framework header. Required: yes. Constraint: fixtures embed large fixed-size engine structs (atom table, term arena, variable registry, clause database). Default: 无.
- **Helper functions returning fixtures** — type: source snippets. Source: test files (trajectory: `make_table()`, `make_arena()`, `make_reg()`). Required: yes. Constraint: they return large structs by value today. Default: 无.
- **Fixture-free minimal test program** — type: source file. Source: generated during diagnosis. Required: no (used to confirm the framework itself runs). Constraint: uses the framework but no large fixtures. Default: 无.
- **Struct sizes** — type: integers. Source: not printed in the trace; the assistant estimated ~1 MB for the atom table and larger for the term arena without measuring. Required: no. Constraint: treat exact sizes as unverified; only the crash symptom and fix location matter. Default: 无.

## Outputs
### Artifacts
- Test files updated so large fixture storage lives in function-local `static` instances (helper functions returning a reference to a re-initialised static) or class `static` members bound by reference in the fixture constructor (trajectory: `ParseCtx`, `UnifyCtx`, `SolverCtx` gained `static` members plus reference fields; `make_table`/`make_arena`/`make_reg` became `fresh_*` functions returning references).
- By-value copies of large fixtures replaced with reference bindings where they remained (trajectory: `AtomTable t = make_table();` became `AtomTable &t = make_table();`).

### Success criteria
- Every suite that previously exited `-1073741571` with no output now prints its test list and a `N/N tests passed` summary (trajectory: `15/15 tests passed`, `17/17 tests passed`, `18/18 tests passed`, `22/22 tests passed` observed after the fix).
- No suite exits with `-1073741571`.

### Failure criteria
- A suite still exits `-1073741571` before printing anything; or suites newly fail assertions because static fixture state leaked between tests (a missing re-initialisation in the constructor).

## Preconditions
- The crashing suites exit with `-1073741571` and print no test output, indicating a crash before `main`'s test loop produces results (on Windows this is the stack-overflow status code).
- A fixture-free minimal program built with the same framework runs successfully, isolating the crash to fixture storage rather than the framework.
- Test fixtures or helpers place large fixed-size engine structs (arena/table/registry/database types) on the stack, either as locals, by-value members, or by-value helper returns.
- The platform uses the default thread stack (trajectory: Windows default 1 MB); if tests already run under an enlarged stack, this fix is unnecessary.
- Edit access to the test sources is available; production code is not to be changed for this purpose.
If a minimal fixture-free test also crashes at the same exit code, stop and investigate runtime/library causes instead.

## Procedure
### Step 1: Confirm crash-before-output
- actions: Run each failing test binary individually and record the exit code and any output.
- inputs: built test binaries.
- outputs: list of suites exiting `-1073741571` with no printed test lines (trajectory: test_atoms, test_terms, test_parser, test_unifier, test_solver all did).
- cautions: an empty output with exit 0 is not this failure; distinguish from suites that print results and fail assertions.
- next condition: all crashing suites share large fixture types.

### Step 2: Isolate the framework with a fixture-free minimal test
- actions: Build a tiny program that uses only the test framework (one trivial TEST) and run it.
- inputs: framework header; engine sources needed to link.
- outputs: evidence the framework itself runs (trajectory: `1/1 tests passed`).
- cautions: if the minimal test also crashes at the same code, stop — the cause is not fixture storage.
- next condition: framework OK, so the crash comes from fixture storage.

### Step 3: Move helper-returned fixtures to static storage
- actions: Convert helpers like `AtomTable make_table()` (return by value) into functions returning a reference to a function-local `static` instance that is re-initialised on each call (trajectory: `static AtomTable &fresh_table()` calling `atom_table_init`).
- inputs: test files with by-value helpers.
- outputs: helpers no longer place megabyte-sized objects on the caller's stack.
- cautions: keep per-call re-initialisation, otherwise state leaks between tests.
- next condition: helpers fixed; fixture structs next.

### Step 4: Move fixture-struct members to static storage with reference fields
- actions: In fixture structs (trajectory: `ParseCtx`, `UnifyCtx`, `SolverCtx`), declare the large members `static`, expose them as reference fields bound in the constructor, and call every `*_init` in the constructor. Define the static members once at file scope.
- inputs: fixture definitions.
- outputs: fixtures construct without stack allocation while keeping the same member syntax at call sites.
- cautions: each `*_init` must still run in the constructor because static storage persists across tests.
- next condition: rebuild and check remaining crashes.

### Step 5: Eliminate residual by-value copies
- actions: Grep the tests for local declarations that copy a fixture or large struct by value (e.g. `AtomTable t = make_table();`) and change them to reference bindings (`AtomTable &t = make_table();`).
- inputs: test sources.
- outputs: no megabyte copy is constructed on a test frame.
- cautions: this step's runtime verification in the traced session was incomplete (the final rerun of the affected suite is not visible in the trace); re-run that suite yourself before claiming success.
- next condition: rebuild all suites.

### Step 6: Run every suite and record results
- actions: Compile and run each `tests/test_*.cpp`; record `N/N tests passed` per suite and exit codes.
- inputs: full test list.
- outputs: suites printing results; any remaining assertion failures are separate problems.
- cautions: on Windows, a suite that is still running from a previous attempt locks its output file (LNK1105) — kill stale processes before relinking.
- next condition: stop when no suite exits `-1073741571`.

## Decision Rules
### When a test binary exits -1073741571 and prints nothing while a fixture-free minimal test passes
Move the large fixture storage off the stack: function-local statics behind reference-returning helpers, and class static members bound by reference in the fixture constructor.

### When a suite still crashes after the helpers became static
Search for remaining by-value copies of the large types in test bodies (declarations of the form `AtomTable t = make_table();`) and convert them to reference bindings. Note that in the traced session this final step was applied but its rerun of the affected suite is not visible in the trace, so re-verify it yourself.

### When a suite prints results but fails assertions after the storage change
That is no longer this failure mode; treat the assertion failures as separate problems (wrong expectations or engine bugs), and verify the fixture constructor still re-initialises every static member so state does not leak between tests.

## Invariants
- Do not modify production engine code or its no-heap design to solve a test-side storage problem.
- Do not weaken or delete tests to make the crash "pass"; only storage location changes.
- Every static fixture storage must be re-initialised in the fixture constructor or helper call, otherwise state leaks between tests.
- Do not claim success for a suite whose rerun output is missing; in the traced session the final rerun of one suite was not visible, so it must be re-verified before being reported as fixed.
- Do not confuse locked-output errors (LNK1105) with regressions; resolve process locks separately.
- Do not enlarge the stack (linker flags, `#pragma comment` stack tricks) as a substitute when the goal is portable test code — move the storage instead.

## Common Failures
### Failure: suite still crashes after converting the helpers
symptoms: the same negative exit code for a suite whose helpers now return static references.
causes: test bodies still copy the large struct by value (observed: `AtomTable t = make_table();` copying a static instance back onto the stack).
recovery: bind by reference (`AtomTable &t = make_table();`) everywhere; verified pattern in the trace, though the affected suite's final rerun is not visible there.

### Failure: suites newly fail with assertion errors after the storage move
symptoms: suites print results but report unexpected failures or cross-test contamination.
causes: static storage persists across tests and the fixture constructor did not re-initialise every member.
recovery: call all `*_init` functions in the constructor for each static member (the pattern used by the fixtures in the trace).

### Failure: relink reports LNK1105 cannot close file
symptoms: intermittent "COMPILE ERROR" with a file-lock message on some suites only.
causes: binaries from the previous run still executing.
recovery: kill the stale processes and rerun; observed in the trace and resolved by killing the test processes.

## Verification
- Rerun each previously crashing binary and record exit code plus output: no suite may exit `-1073741571`, and each must print its test list and `N/N tests passed` summary (observed after the fix: `15/15`, `17/17`, `18/18`, `22/22` for different suites).
- Run the fixture-free minimal program as a control; it must still pass.
- Grep the test sources for remaining by-value declarations of the large fixture types (`AtomTable t = make_table();`-style) and require zero matches.
- Run every suite in one pass and report per-suite results; kill lingering test processes first so no suite blocks the others' output files.
- For any suite whose rerun output is unavailable, report it as unverified rather than fixed.

## Examples
### Example 1: static-backed fixtures turn startup crashes into real test output
input: On Windows, five test binaries exit `-1073741571` printing nothing, while a fixture-free minimal test built with the same framework prints `1/1 tests passed`. Test fixtures embed large engine structs (`AtomTable`, `TermArena`, `VarRegistry`, `Database`) as members and helpers return them by value.
procedure: Step 3 replace `static AtomTable make_table()` (by-value return) with `static AtomTable &fresh_table()` initialising a function-local static per call; Step 4 give `ParseCtx`/`UnifyCtx`/`SolverCtx` class `static` members plus reference fields bound in constructors that call every `*_init`; Step 5 replace remaining `AtomTable t = make_table();` copies with `AtomTable &t = make_table();`; Step 6 rebuild and run all suites after killing stale processes.
expected result: suites that previously crashed now print results — e.g. `test_terms: 15/15 tests passed`, `test_unifier: 18/18 tests passed`, `test_solver: 22/22 tests passed` — and no suite exits `-1073741571`.
parameterized values: fixture struct types and sizes, helper names, per-suite source lists, output directory; the traced session's final rerun of one suite was not visible and must be re-verified.

## Evidence
- problem — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 987, source_part_index: 0, quote: `(exit -1073741571)`, supports: five test binaries crashed at startup (Windows stack-overflow status) with no test output.
- problem — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1053, source_part_index: 0, quote: `exit: -1073741571`, supports: after the first static-storage round, one suite still crashed — a residual by-value copy of the large fixture remained.
- action — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1002, source_part_index: 0, quote: `static AtomTable t;`, supports: the by-value helper was replaced by a function returning a reference to a re-initialised function-local static.
- action — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1014, source_part_index: 0, quote: `static AtomTable   s_atoms;`, supports: fixture structs (ParseCtx and later UnifyCtx/SolverCtx) moved their large members to class static storage bound by references.
- action — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1204, source_part_index: 0, quote: `AtomTable &t = make_table();`, supports: residual by-value copies of the static fixture were converted to reference bindings.
- verification — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1199, source_part_index: 0, quote: `1/1 tests passed`, supports: the fixture-free control program runs, isolating the crash to fixture storage.
- verification — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1048, source_part_index: 0, quote: `15/15 tests passed`, supports: a suite that previously exited -1073741571 now prints its full results after the storage move.
- verification — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1218, source_part_index: 0, quote: `test_terms: 15/15 tests passed`, supports: suites keep passing after the by-reference copy fix; the traced session's final rerun of the last affected suite is not visible in the trace and must be re-verified.

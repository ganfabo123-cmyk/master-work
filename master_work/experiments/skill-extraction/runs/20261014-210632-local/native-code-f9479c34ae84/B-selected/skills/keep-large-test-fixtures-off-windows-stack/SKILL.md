---
name: keep-large-test-fixtures-off-windows-stack
description: Use when C++ test binaries on Windows exit immediately with code -1073741571 (0xC00000FD stack overflow) before printing any test output, and tests construct multi-megabyte fixed-capacity structs (arenas, hash tables, databases). Helps the agent move fixtures to static storage via reference-returning helpers or static fixture members, and catch by-value copies that silently re-introduce the stack usage. Requires the ability to rebuild and rerun the test binaries. Do not use when the crash persists with all fixtures already in static storage or is a linker/loader error instead.
---
# Avoid Windows stack overflow from large fixed-size test fixtures

## Goal
Fix C++ test binaries that crash at startup on Windows (exit code -1073741571 / 0xC00000FD stack overflow) because test fixtures hold multi-megabyte fixed-capacity structs, so every test prints results instead of dying silently.

## Scope
### In scope
- Recognising the silent-startup-crash signature: test binary produces no output and exits with -1073741571 on Windows.
- Moving large fixture members (atom tables, term arenas, variable registries, clause databases of ~1–4 MB each) into static storage: helper functions returning `static T&`, fixture structs with `static` member storage plus reference members.
- Finding and eliminating by-value copies of those helpers (`T t = make()` copies megabytes back onto the stack).
- Rebuilding and rerunning each suite to confirm.

### Out of scope
- Diagnosing assertion failures inside tests that do run.
- Changing production code to shrink the structs.
- Enlarging the process stack (`editbin /STACK`) as a permanent fix — not used or verified in this trace.
- AddressSanitizer-based debugging: in this trace `-fsanitize=address` produced `-1073741515` (missing ASAN runtime DLL) and was abandoned.

## Inputs
- Exit codes of the test binaries (integers): required; e.g. -1073741571 indicates stack overflow; a negative code with no test output is the trigger.
- Test sources under `tests/` containing fixture structs or helper factories for the large types; required.
- Size knowledge of the fixture types (from headers, e.g. capacity constants like 4096 entries × ~256 bytes ≈ 1 MB per table, several MB per arena); required to judge what is "too large" for the default ~1 MB Windows thread stack.
- Build command for the test suite (`clang++ -std=c++23 -Iinclude -Itests ...`); required; no default.
- No defaults for any of the above.

## Outputs
### Artifacts
- Edited test files (`tests/test_*.cpp`) where large fixture state lives in `static` storage: `static T& fresh_x()` helpers returning a re-initialised static instance, and/or fixture structs with `static` member storage bound by reference members with out-of-class definitions.
- Rebuilt test binaries under `build/tests/`.

### Success criteria
- Suites that previously produced no output now print their PASS/FAIL lines and the `<passed>/<total> tests passed` summary with exit code 0 when all assertions pass.

### Failure criteria
- Any suite still exits -1073741571 (or any nonzero code) before printing any test line.
- A "fix" that only enlarges the stack, or that changes assertions to make the crash go away.

## Preconditions
- The crash signature is confirmed: running the binary prints nothing and the process exit code is -1073741571; a minimal test using only the framework runs fine (proving the framework itself is not the problem).
- You can identify which types are MB-scale (fixed-capacity arenas/tables declared at file or struct scope) by reading their headers.
- You can rebuild and rerun the suites on the same machine.
- If a suite's binary is locked by a lingering process (`LNK1105: cannot close file`), kill stale processes first so verification runs are trustworthy.

## Procedure
### Step 1: Confirm the crash is startup stack overflow, not an assertion
- Actions: Run the failing binary directly and print its exit code; build a minimal file that includes only the test framework with one trivial TEST and run it. If the minimal binary passes while the real suite prints nothing and exits -1073741571, the crash is stack overflow during test execution.
- Inputs: test binaries, framework.
- Outputs: confirmed diagnosis.
- Cautions: do not debug with ASAN unless its runtime is on PATH; in this trace the ASAN build itself failed with -1073741515 (missing DLL) and told nothing about the crash.
- Preserve: production code, test assertions.
- Next: proceed to Step 2.

### Step 2: Inventory stack-resident large objects
- Actions: grep the test files for declarations of the MB-scale types (`AtomTable t;`, `TermArena a;`, `VarRegistry r;`, fixture structs containing them by value, and factory helpers returning them by value). Compute rough sizes from the capacity constants.
- Inputs: `tests/*.cpp`, `include/*.hpp`.
- Outputs: list of every stack-resident large object.
- Cautions: a factory returning `T` by value still copies onto the caller's stack even if the factory itself uses a static.
- Preserve: the test logic inside each TEST body.
- Next: proceed to Step 3.

### Step 3: Move large state to static storage
- Actions: For simple helpers, replace `static T make()` with `static T& fresh()` that initialises and returns a function-local `static T`. For fixture structs holding several large members, add `static` member storage (with out-of-class definitions `T Cls::s_x = {};`) and make the struct hold references to it, re-running the *_init functions in the constructor.
- Inputs: test files from Step 2.
- Outputs: edited test files.
- Cautions: because the storage is shared, the fixture constructor must fully re-initialise every member per test; otherwise state leaks between tests and you will chase phantom "order-dependent" failures.
- Preserve: public member names used by tests (bind references with the same names so test bodies are untouched where possible).
- Next: proceed to Step 4.

### Step 4: Eliminate by-value copies of the helpers
- Actions: grep for `T x = make...()` / `T x = fresh...()` patterns and change them to references (`T &x = ...`). In this trace the remaining crashing suite still had `AtomTable t = make_table();` fourteen times; each copy put ~1 MB on the stack.
- Inputs: test files.
- Outputs: edited test files.
- Cautions: with the macro trick `#define make_table() fresh_table()` the copy is invisible to grep for the helper name — search for the type name assigned by value instead.
- Preserve: call sites' variable names.
- Next: rebuild all suites.

### Step 5: Verify every suite runs
- Actions: Rebuild each test binary (killing lingering test processes if the linker reports the output file cannot be closed), run each, and confirm PASS/FAIL lines and the summary appear; treat a locked binary as an environmental retry, not a failure.
- Inputs: build command, binaries.
- Outputs: per-suite pass counts.
- Cautions: in this trace one suite's final verification was cut short by a file lock; if that happens, rerun that suite alone before claiming success.
- Next: stop when every suite prints its full test list.

## Decision Rules
### When a test binary exits -1073741571 with zero output while a minimal framework-only test passes
The fixtures are overflowing the ~1 MB default Windows stack. Move all MB-scale fixture state to static storage (Step 3); do not investigate the assertions.

### When a suite passes in isolation but fails (or crashes) when run after others
Shared static fixture storage is being reused without full re-initialisation. Make every fixture constructor re-run all *_init functions over its static members before proceeding with other debugging.

### When a helper returns a large struct by value
Convert it to return a reference to function-local static storage and update call sites to bind references; a by-value binding re-copies the whole object onto the stack.

### When the linker reports LNK1105 cannot close the output file
A lingering test process holds the binary. Kill it and rerun; this is not a code defect.

## Invariants
- No MB-scale fixed-capacity struct is ever a stack local, a by-value return, or a by-value member of a per-test fixture.
- Static fixture storage is fully re-initialised in the fixture constructor for every test; no test relies on leftover state.
- Test assertions and production sources are unchanged by this fix.
- Success is claimed only after the affected binaries actually run and print their test summaries; exit codes are checked, not just compile success.
- The stack size is not increased as a substitute for the fix.

## Common Failures
### Failure: suite prints nothing and exits -1073741571
- Symptoms: `(exit -1073741571)` for several test binaries in the same run.
- Causes: ~1 MB `AtomTable` / multi-MB `TermArena` instances declared as locals or returned by value in test helpers; the default Windows thread stack is ~1 MB.
- Recovery: static storage via `static T&` helpers or static fixture members; then rebuild and rerun.

### Failure: fix applied to the helper but the suite still crashes
- Symptoms: after introducing `static T& fresh_table()`, the suite still exits -1073741571.
- Causes: test bodies still bind by value (`AtomTable t = make_table();` copies the object onto the stack), or some tests still declare the type locally.
- Recovery: change bindings to references (`AtomTable &t = make_table();`) and grep for remaining by-value declarations of the type.

### Failure: order-dependent assertion failures after moving to static storage
- Symptoms: tests pass alone but fail in sequence.
- Causes: the shared static members are not fully re-initialised between tests (only some *_init functions called).
- Recovery: call every member's init function in the fixture constructor; verify with a minimal two-test sequence before resuming normal debugging.

### Failure: ASAN build of the crashing suite fails to start with -1073741515
- Symptoms: `-1073741515` instead of the original crash code.
- Causes: ASAN runtime DLL not on PATH.
- Recovery: abandon ASAN for this diagnosis; use exit-code evidence plus the minimal-test comparison.

## Verification
- Each previously-crashing suite binary now prints its per-test PASS/FAIL lines and a `<passed>/<total> tests passed` summary, and its exit code is 0 when all assertions pass (in the trace, suites reached counts such as 22/22, 18/18, 15/15 after the change, versus blank output and -1073741571 before).
- Grep confirms no `T x = make_...()` / `T x = fresh_...()` by-value bindings of the large types remain in `tests/`.
- A minimal framework-only test still passes, isolating the fix to fixture storage.
- Running the full suite twice yields identical results, indicating shared static state is properly re-initialised.

## Examples
### Example 1: by-value factory helper replaced with static-backed reference helper
- Input: `static AtomTable make_table() { AtomTable t; atom_table_init(&t); return t; }` used by 16 tests; suite exits -1073741571 with no output.
- Procedure: Step 3 — replace with `static AtomTable &fresh_table() { static AtomTable t; atom_table_init(&t); return t; }` and `#define make_table() fresh_table()`; Step 4 — change bindings to `AtomTable &t = make_table();`.
- Expected result: the suite prints all PASS lines instead of crashing at startup.
- Parameterized values: type `AtomTable` (~1 MB, 4096 slots), helper name, macro alias.

### Example 2: fixture struct with six large members moved to static members
- Input: `struct SolverCtx { AtomTable atoms; Database db; TermArena clause_arena; ... SolverCtx() { atom_table_init(&atoms); db_init(&db); ... } };` — up to ~12 MB by value per test.
- Procedure: Step 3 — declare `static AtomTable s_atoms; static Database s_db; ...` inside the struct, define them out of class (`AtomTable SolverCtx::s_atoms = {};`), bind reference members in the constructor's initializer list, and keep all *_init calls in the constructor body.
- Expected result: the solver integration suite runs to completion (22/22 in the trace) with cross-test isolation preserved by the constructor re-initialisation.
- Parameterized values: member count, init functions (`atom_table_init`, `db_init`, `term_arena_init`, `var_registry_init`).

## Evidence
- problem — file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index 987, source_part_index 0, quote: "=== test_atoms ===\r\n(exit -1073741571)", supports: five test binaries died at startup with the Windows stack-overflow exit code and produced no test output.
- problem — same file_id, source_index 1053, source_part_index 0, quote: "Exit code 253\r\nexit: -1073741571", supports: re-running the atoms suite reproduced the same silent crash code.
- action — same file_id, source_index 1002, source_part_index 0, quote: "/* AtomTable is ~1 MB — too large for the default Windows stack.", supports: the fix's stated rationale and the move to a `static AtomTable &fresh_table()` helper in the same edit.
- action — same file_id, source_index 1036, source_part_index 0, quote: "    static AtomTable   s_atoms;\n    static Database    s_db;\n    static TermArena   s_clause_arena;", supports: the fixture-struct variant of the fix (static member storage with reference members) applied to the solver test context.
- action — same file_id, source_index 1204, source_part_index 0, quote: "    AtomTable &t = make_table();", supports: eliminating the by-value copy of the ~1 MB table that the static helper alone did not remove (replace_all edit over 14 call sites).
- verification — same file_id, source_index 1191, source_part_index 0, quote: "=== 6 PASSED, 1 FAILED ===", supports: after the static-storage changes, six suites (lexer 22/22, parser 12/12, solver 22/22, terms 15/15, unifier 18/18, variables 17/17) compiled, linked, ran and printed summaries, versus blank output and -1073741571 before; the remaining suite was a locked binary, not a crash.

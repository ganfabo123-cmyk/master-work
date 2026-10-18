---
name: fix-windows-stack-overflow-in-large-local-fixtures
description: Use when a Windows test executable prints no output (or partial output) and exits with -1073741571 (0xC00000FD) even though it linked successfully. Helps the agent identify large fixed-size structs allocated as local/by-value variables that blow the 1 MB default stack, move them to static storage or references, and re-run the suite to green. Requires a Windows test build (clang++/PowerShell) and the ability to edit test sources. Do not use for LNK1105/link failures or for assertion-level test failures that print FAIL lines.
triggers:
  - "-1073741571"
  - "0xC00000FD"
  - "STATUS_STACK_OVERFLOW"
---
# Fix Windows Test Binaries That Crash Silently with Exit -1073741571

## Goal
Make Windows test executables that crash before printing anything (observed exit `-1073741571`, i.e. `0xC00000FD` stack overflow) run to completion by relocating oversized fixed-size fixture structs off the call stack, verified by the suite printing its full pass counts.

## Scope
### In scope
- Windows test/CLI binaries that link successfully but terminate immediately with no output or exit code `-1073741571` (`0xC00000FD`, STATUS_STACK_OVERFLOW).
- Test fixtures and harness structs that embed large fixed-capacity tables (atom tables, clause databases, term arenas, registries) declared as local variables or returned/assigned by value.
- Moving such state to static storage (class static members or function-local `static`) or to references so it lives in BSS/heap rather than on the 1 MB default Windows thread stack.
- Re-running the affected suite(s) to confirm normal output and exit code 0.

### Out of scope
- Link failures (`LNK1105` and other linker errors) — handle the lock problem instead.
- Test assertion failures that print `FAIL` lines with a nonzero exit — those are logic defects.
- Production code stack-usage redesign beyond test fixtures (not observed/verified here).
- Increasing thread stack size via linker/`CreateThread` parameters (not observed in the trace; not a verified remedy).

## Inputs
- **Crash signature**: tool result showing the test binary producing no output (or truncated output) and `exit: -1073741571`; source = the run of the built `.exe`; required = yes; constraint = link must have succeeded (no `LNK1105`); default = 无.
- **Test source file**: the `.cpp`/`.c` defining the fixture context struct (e.g. `tests/test_indexing.cpp`, `tests/test_atoms.cpp`); source = identified from the test name in the crash output; required = yes; constraint = edit only test files; default = 无.
- **Fixture struct definition**: struct declaration whose members are large fixed-size tables (`AtomTable`, `Database`, `TermArena`, `VarRegistry`); source = reading the test file; required = yes; constraint = size must plausibly exceed the 1 MB Windows default stack; default = 无.
- **Existing pattern to copy**: a working test that already stores the same state in `static` members (e.g. `test_solver.cpp` with `static Database s_db`); source = project test code; required = no; constraint = reuse the project's established pattern rather than inventing a new one; default = 无.
- **Build/run command**: the command that compiles and runs the suite (PowerShell loop invoking `clang++ ... -o <exe>` then `& <exe>`); source = the failed run's tool call; required = yes; constraint = re-run unchanged after the edit; default = 无.
- **Expected counts**: per-suite pass totals (e.g. `13/13 tests passed`); source = earlier runs of the same suite where available; required = no; constraint = use the suite's own printed totals; default = 无.

## Outputs
### Artifacts
- **Edited test source** (e.g. `tests/test_indexing.cpp`) where the fixture's large members are `static` (class static members or function-local `static`) or held by reference instead of by value.
- **Rebuilt test executable** at its original output path.
- **Run log** showing the suite's full output and pass counts with exit code 0.

### Success criteria
- The suite prints its complete per-test output and a pass summary (e.g. `13/13 tests passed`) with exit `0`; no `-1073741571` appears.
- The whole test run reports all expected suites passing (observed: `FINAL RESULT: 10/10 suites passed, 0 failed`).
- No production source, build flags, or linker settings were changed to achieve this.

### Failure criteria
- The binary still exits `-1073741571` after the state was moved off the stack.
- The suite runs but reports `FAIL` assertions — a logic defect, report separately.
- The link fails with `LNK1105` — out of scope; switch to the lock-handling workflow.

## Preconditions
- The binary must link successfully first; if the run log contains `LNK1105`, stop and resolve the output-file lock before diagnosing crashes.
- The crash must be silent/abrupt: no test output at all, or output stopping before that suite's header, with exit `-1073741571`. If the suite prints `FAIL` lines, this skill does not apply.
- The host must be Windows (the `-1073741571` / 1 MB default stack behavior is Windows-specific), with the project's compiler (`clang++`) and shell (PowerShell) available for rebuild-and-rerun.
- The fixture struct and its member types must be readable and editable (test sources); confirm which struct the test instantiates as a local before editing.
- A prior or sibling run of the suite should exist (or be runnable) to establish the expected output/counts for comparison.

## Procedure
### Step 1: Confirm the silent-crash signature
- Actions: run the suite binary (or read the last run) and confirm: link succeeded, then the process exits `-1073741571` with no (or truncated) output.
- Inputs: run log for the suspect test executable.
- Outputs: confirmation of stack-overflow-style abrupt exit; note which suite header never printed.
- Cautions: PowerShell may swallow child output on crash — capture `$LASTEXITCODE` explicitly; a missing `.exe` or `LNK1105` means the wrong problem.
- Preserve: the existing binary/run command for before/after comparison.
- Next: proceed to Step 2 when exit is `-1073741571` and the link was clean.

### Step 2: Locate the oversized local fixture
- Actions: open the test source; find the per-test context struct instantiated as a local in each test case (e.g. `struct IdxCtx { AtomTable atoms; Database db; TermArena clause_arena; ... };`); estimate its size from member arrays (atom tables ~1 MB, clause databases with per-predicate indexes ~1.6 MB, arenas/registries hundreds of KB).
- Inputs: test source file; member type definitions if sizes are unclear.
- Outputs: the struct name, the members that dominate its size, and the local-instantiation sites.
- Cautions: a multi-MB struct created once per test case sequentially still overflows a 1 MB stack if it is a stack local; do not assume "only one at a time" is safe.
- Preserve: the struct's semantics (same members, same init sequence).
- Next: proceed to Step 3 when the local and its big members are identified.

### Step 3: Move the state off the call stack
- Actions: prefer the project's existing pattern — make the big members `static` (class static members defined at namespace scope, as an existing passing test already does with `static Database s_db`, or function-local `static`); if the value is produced by a function returning a large struct by value, change the use to a reference/pointer instead of a copy (e.g. `AtomTable &t = make_table();`).
- Inputs: fixture struct definition; existing static-member pattern in a passing sibling test.
- Outputs: edited test source.
- Cautions: static members are shared across all test cases in the binary — each test must still re-initialize state in its constructor/setup exactly as before, or earlier tests will pollute later ones; keep the edits inside test files.
- Preserve: member order, initialization calls, and test assertions unchanged.
- Next: rebuild and rerun (Step 4).

### Step 4: Rebuild the binary with the unchanged command and run it
- Actions: re-run the project's compile-and-link command for that suite (same flags, same `-o` path), then execute the binary and capture `$LASTEXITCODE`.
- Inputs: build/run command from Step 1.
- Outputs: fresh link log and full suite output.
- Cautions: if `LNK1105` appears now, the binary is locked by a prior run — kill/rename per the lock workflow, then retry; do not confuse it with the crash.
- Preserve: all compiler flags and the output path.
- Next: proceed to Verification when the suite prints output; iterate on Step 3 if the crash persists.

### Step 5: Run the whole test batch
- Actions: run every suite in the project's test loop to confirm no regression elsewhere after the fixture change.
- Inputs: full test loop command.
- Outputs: aggregate pass/fail summary across suites.
- Cautions: suites that previously crashed silently may now run and reveal real assertion failures — report those separately as logic issues.
- Preserve: test order and flags.
- Next: stop when all suites pass; otherwise triage each failure by type (crash vs FAIL).

## Decision Rules
### When the binary exits `-1073741571` with no output after a clean link
Treat as `0xC00000FD` stack overflow in process startup/first test; inspect the test fixture struct for large fixed-capacity locals rather than debugging assertions or the linker.

### When the fixture struct's members include multi-MB fixed tables instantiated as function locals
Make the members `static` (class static members or function-local `static`) so they are zero-initialized in BSS before `main`, and keep per-test `init` calls in the constructor/setup. Observed: a context struct with a ~1 MB atom table plus a ~1.6 MB database crashed as a local and passed after becoming static members.

### When a helper returns a large struct by value into a local
Change the call site to bind a reference (or pointer) instead of copying; observed fix: `AtomTable t = make_table()` → `AtomTable &t = make_table()` for a ~1 MB struct copied onto the stack.

### When a freshly linked binary under a new filename still crashes with the same exit code
The lock workaround is irrelevant to the crash — proceed with the stack fix; do not keep producing new filenames expecting different behavior.

### When the suite runs after the fix but prints `FAIL` lines
Stop the stack-overflow work; the crash is resolved and the remaining failures are assertion/logic defects to be handled separately (observed: unrelated solver backtracking failures surfaced once binaries ran).

### When the suspect state is a class static member already
Class statics with trivial default constructors live in BSS and do not consume stack — if a static-member test still crashes, look for a different large local (e.g. a by-value copy) instead of making more members static.

## Invariants
- Edit only test files (and only the fixture/storage declarations); do not change production sources, compiler flags, linker settings, or build scripts to work around a test stack overflow.
- Keep the fixture's member set, initialization order, and per-test reset behavior identical — only the storage duration/location changes.
- Do not weaken, skip, or delete tests to make the suite green; assertions must remain as-is.
- Do not report a suite as passing without its own printed pass counts and exit 0 from a run after the edit.
- Do not keep relinking under new filenames to dodge a crash — filename changes never alter stack usage.
- Distinguish the three failure classes (link lock LNK1105, stack-overflow crash `-1073741571`, assertion `FAIL`) and never claim one fixed another.
- Preserve the project's existing conventions (e.g. reuse the static-instance helper pattern already present in sibling tests) instead of introducing a new framework.

## Common Failures
### Failure: suite prints nothing and exits -1073741571
- Symptoms: `=== <suite> ===` header prints from the harness, then immediately `exit: -1073741571` (or the header itself never appears); no PASS/FAIL lines.
- Causes: a multi-MB fixed-size fixture struct instantiated as a function-local variable, or a by-value copy of such a struct, exceeding the 1 MB default Windows stack before the first assertion runs.
- Recovery: make the fixture members `static` (class statics or function-local `static`) or bind references instead of copies, rebuild with the same command, rerun.

### Failure: suite runs but a single test copies a large struct by value
- Symptoms: most tests print, but the process dies partway (or a specific test never reports) with the same crash code.
- Causes: one remaining `BigStruct t = make_table();`-style value copy among otherwise reference-based tests (observed at `test_atoms.cpp` line 108 while every other test used `&t`).
- Recovery: change that single copy to a reference (`AtomTable &t = make_table();`) and rerun.

### Failure: converted fixture makes later tests fail with wrong state
- Symptoms: after moving to `static`, some tests fail assertions that previously passed.
- Causes: static storage is shared across all test cases in the binary; missing per-test re-initialization lets earlier tests pollute later ones.
- Recovery: keep/restore the constructor or helper's `*_init(...)` calls on every test entry (the observed pattern re-initialized inside the static-instance helper on each call).

### Failure: relink reports LNK1105 instead of running
- Symptoms: after the source edit, the build fails with `LNK1105 ... error code 1224`.
- Causes: a previous run of the binary is still alive or its handle is held.
- Recovery: stop that process and relink (separate lock workflow), then rerun; do not attribute this to the stack fix.

### Failure: crash persists after making everything static
- Symptoms: exit is still `-1073741571` after the obvious fixtures were converted.
- Causes: another large local remains (deep call chain of large frames, large arrays in test bodies), or the cause is unconfirmed in the trace.
- Recovery: re-read the test and helper sources for any remaining by-value large types; if none is found, report the unresolved crash rather than guessing.

## Verification
All checks are read from a run performed after the edit (never from memory):
- The suite binary's run output includes its full list of PASS lines instead of ending silently; `$LASTEXITCODE` is `0`.
- The suite prints its own totals matching its test count (observed targets: `13/13 tests passed` for the indexing suite; `17/17 tests passed` for the atoms suite) with no `-1073741571` anywhere in the log.
- The aggregate test loop reports every suite passing (observed: `FINAL RESULT: 10/10 suites passed, 0 failed`).
- The changed file(s) contain only test-file edits: grep/read confirms the fixture is now `static` (or referenced) and no production/build file was modified.
- Re-running the same binary a second time yields the same counts (static-shared state is re-initialized correctly and the result is not a first-run artifact).
- Any suite that newly runs but prints `FAIL` is reported separately as a logic issue, not counted as this fix's success or failure.

## Examples
### Example 1: convert a per-test fixture struct to static members
- Input: `test_indexing` links cleanly but runs as `=== test_indexing ===` followed by `exit: -1073741571`; the fixture `struct IdxCtx` embeds `AtomTable atoms; Database db; TermArena clause_arena; VarRegistry clause_vars; TermArena query_arena; VarRegistry query_vars;` and is instantiated as a local in each test case; the database grew to ~1.6 MB after a per-predicate first-arg index was added (~2.1 KB per `PredEntry`, 512 predicates).
- Procedure: Step 1 signature confirmed → Step 2 size estimate of `IdxCtx` (~3.4 MB vs 1 MB stack) → Step 3 make the members `static` following the pattern already used by the passing `test_solver.cpp` (`static Database s_db;`) → Step 4 rebuild the binary with the same `clang++ ... -o build/tests/<name>.exe` command and run it.
- Expected result: the suite prints all PASS lines and `13/13 tests passed` with exit 0.
- Parameterized values: struct = `IdxCtx`; new members = `static`; suite totals = 13 tests.

### Example 2: fix a single by-value copy of a 1 MB struct
- Input: `test_atoms` exits `-1073741571` before printing anything; the file already uses a static helper (`static AtomTable &fresh_table() { static AtomTable t; atom_table_init(&t); return t; }`) with the comment `AtomTable is ~1 MB — too large for the default Windows stack`, but one test still reads `AtomTable   t  = make_table();`.
- Procedure: Step 2 find the outlier → Step 3 Edit changing it to `AtomTable  &t  = make_table();` → Step 4/5 rebuild and run the whole batch.
- Expected result: `=== test_atoms ===` prints `17/17 tests passed`, and the batch ends with `FINAL RESULT: 10/10 suites passed, 0 failed`.
- Parameterized values: struct = `AtomTable` (~1 MB); fix = value → reference in one test; suite totals = 17 tests across 10 suites.

### Example 3: separating a lock problem from the crash
- Input: while trying to relink a crashing suite, the build reports `LINK : fatal error LNK1105: cannot close file 'build\tests\test_indexing.exe'; error code 1224`.
- Procedure: resolve the lock first (kill/short wait, or relink to a fresh name such as `test_indexing2025.exe`), re-run, and observe that the fresh binary still exits `-1073741571` — confirming the crash is independent of the lock — then apply Steps 2–4.
- Expected result: lock handling produces a runnable binary; the stack fix produces a passing suite; the final report states both were addressed separately.
- Parameterized values: fresh name suffix = `2025`; crash code = `-1073741571`.

## Evidence
**Problem**
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 180, source_part_index 0 — quote: `=== test_indexing ===` — supports: the harness printed the suite header and then nothing (no PASS lines), the silent-crash symptom.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 206, source_part_index 0 — quote: `exit: -1073741571` — supports: the characteristic stack-overflow exit code of the crashed test binary (the same result shows other suites printing normally, proving the link was fine).
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 261, source_part_index 0 — quote: `exit: -1073741571` — supports: a freshly linked binary under a new filename still crashes, separating the crash from the file-lock problem.

**Action**
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 267, source_part_index 0 — quote: `The `IdxCtx` struct members need to become static like in `test_solver.cpp`. Let me rewrite `test_indexing.cpp` to use static members:` — supports: the chosen remedy (static members, copying the existing passing test's pattern).
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 264, source_part_index 0 — quote: `struct IdxCtx {` — supports: the fixture struct that embeds the large fixed-size tables (`AtomTable`, `Database`, `TermArena`, `VarRegistry` members follow on the next lines of the same Read result) and is instantiated as a local in each test.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 308, source_part_index 0 — quote: `tests\test_solver.cpp:18:    static Database    s_db;` — supports: the project's existing pattern of storing large fixtures in class statics.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 287, source_part_index 0 — quote: `/* AtomTable is ~1 MB — too large for the default Windows stack.` — supports: the size-vs-1 MB-stack diagnosis recorded in the fixed test source, alongside the `static AtomTable &fresh_table()` helper in the same result.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 324, source_part_index 0 — quote: `Line 108: `AtomTable t = make_table();` — this copies the 1MB `AtomTable` by value onto the LOCAL stack! That's an immediate stack overflow. This was pre-existing before my changes.` — supports: identifying a single by-value copy as the crash cause.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 325, source_part_index 0 — quote: `    AtomTable  &t  = make_table();` — supports: the value→reference edit applied to that line.

**Verification**
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 282, source_part_index 0 — quote: `13/13 tests passed` — supports: after converting `IdxCtx` to static members, the previously silent-crashing indexing suite ran to completion.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 333, source_part_index 0 — quote: `=== FINAL RESULT: 10/10 suites passed, 0 failed ===` — supports: the whole batch passes after the stack fixes; the same result contains `17/17 tests passed` for the formerly crashing `test_atoms` suite.

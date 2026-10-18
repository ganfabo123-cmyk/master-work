---
name: fix-c00000fd-large-structs-on-windows-stack
description: Use when a Windows C/C++ binary or test executable exits with -1073741571 / 0xC00000FD or prints no output at all. Helps the agent locate fixed-capacity structs (tables, arenas, stacks) that are local, static-member, or by-value-copied onto the default 1 MB thread stack, and move them to static storage without changing behavior. Requires the ability to read struct capacity constants and rebuild/rerun the failing binary. Do not use when the exit code is a different NTSTATUS, when the crash is a true deep-recursion bug in logic you must rewrite, or when the binary runs but individual assertions fail.
---
# Fix 0xC00000FD Stack Overflow from Large Fixed-Capacity Structs on Windows

## Goal
Diagnose a Windows test/binary that dies with exit code -1073741571 (0xC00000FD, STATUS_STACK_OVERFLOW) or exits silently with no output, find every fixed-capacity struct that exceeds the default 1 MB thread stack, relocate it to static storage (or pass by reference), and produce a rebuilt binary whose previously crashing test suites run to completion with their normal pass counts.

## Scope
### In scope
- Interpreting NTSTATUS 0xC00000FD / -1073741571 and "silent exit, no output" as stack overflow on Windows.
- Computing struct sizes from capacity constants (e.g. 4096 slots × ~260 bytes ≈ 1 MB tables, arena of 8192 nodes + arg pool, choice-point arrays of ~1300 bytes × 256).
- Three verified relocation patterns: function-local `static` working stacks in a non-reentrant routine; class-level `static` members exposed to tests as references; helper functions that return/produce a reference to a static instance instead of copying by value.
- Re-running the exact crashing binary (by full path) to confirm the fix.

### Out of scope
- Growing the thread stack (not attempted in this trajectory) or moving storage to the heap where a "no post-init malloc" rule forbids it.
- Genuine unbounded C-recursion bugs in the algorithm itself.
- Crashes with other exit codes (e.g. missing DLL -1073741515, linker errors), and test assertions that fail while the binary runs normally.

## Inputs
1. **Failing exit code / output** — type: tool result; source: run of the test binary; required: yes; constraint: must be -1073741571 / 0xC00000FD, or an empty stdout with a non-zero exit; default: 无.
2. **Struct definitions and their capacity constants** — type: source files read via Read/Grep; source: project headers (e.g. `AtomTable` with `ATOM_TABLE_CAPACITY 4096U`, `TermArena` with `TERM_ARENA_CAPACITY 8192U`, `ChoiceStack` with `CHOICE_STACK_CAPACITY 256U`); required: yes; constraint: need element size × count to estimate bytes; default: 无.
3. **Call sites that place these structs on the stack** — type: source; source: functions (`solve`), test fixtures (`IdxCtx`, `SolverCtx`), entry point (`main`), helper returns (`AtomTable t = make_table()`); required: yes; default: 无.
4. **Reentrancy facts** — type: code reading; source: whether the owning routine is called recursively or concurrently; required: yes; constraint: `static` relocation is only safe for non-reentrant code or code that re-initializes its state on entry; default: 无.
5. **Build + run commands** — type: project scripts (Makefile, PowerShell/clang++ invocations); source: repository; required: yes; default: the project's existing test target.

## Outputs
### Artifacts
- Edited source files where oversized locals became `static` locals, class `static` members (with reference accessors), or reference-returning helpers — same repository paths, no new files required.
- A rebuilt test binary executed by full path.

### Success criteria
- The previously crashing binary exits 0 and prints its normal per-test lines and `N/N tests passed`.
- A full suite run reports all suites passing (observed: `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`).
- No behavioral change: previously passing suites keep the same pass counts.

### Failure criteria
- Binary still exits -1073741571 or still prints nothing.
- A suite that used to pass now fails after the relocation.
- Fix required disabling tests or changing assertions instead of storage location.

## Preconditions
- The failing binary can be rebuilt and executed on the target Windows machine with the project's compiler (clang++ in this trajectory); if only the shell used cannot run `.exe` files, switch to PowerShell before concluding anything about a crash.
- You can read the struct definitions to compute `capacity × sizeof(element)` before editing; do not guess which struct is at fault without the arithmetic.
- The routine receiving `static` storage is non-reentrant, or explicitly re-initializes (e.g. `memset`) its statics on every entry — confirm this in the code first; otherwise stop and report that a heap/thread-stack solution is needed instead.
- If a crash produces no output at all, confirm the binary actually runs (full path) before assuming a static-initializer problem.
- If any of these cannot be confirmed, stop and report the missing precondition rather than applying a blind `static`.

## Procedure
### Step 1: Confirm the crash signature
- Actions: run the failing binary by full path and capture the exit code; decode -1073741571 as 0xC00000FD (stack overflow); note whether any output was produced.
- Inputs: binary path, shell that can execute `.exe`.
- Outputs: confirmed signature "exit -1073741571" or "silent non-zero exit".
- Cautions: an empty output block may also mean a locked/stale binary (`LNK1105 cannot close file`) — rebuild first; a missing runtime DLL yields -1073741515, which is a different problem.
- Preserve: the original binary name/path so the same binary can be re-run after the fix.
- Next: if the signature matches, go to Step 2; otherwise stop and pick the matching diagnosis.

### Step 2: Compute who owns the bytes
- Actions: read the capacity constants of every large fixed-size struct reachable from the crashing frame; multiply element size × capacity (e.g. `ChoicePoint ≈ 1300 B × 256 ≈ 332 KB`, `AtomTable ≈ 1 MB`, `IdxCtx ≈ 3.4 MB`); list every place one is created: function locals, test-fixture members, helper return-by-value, entry-point object.
- Inputs: headers and the crashing function/test fixture.
- Outputs: a ranked list of frames whose totals exceed ~1 MB.
- Cautions: sum nested members — a fixture with two arenas plus a database can exceed the limit even though each individual array looks small.
- Preserve: the struct definitions themselves (capacities stay unchanged).
- Next: go to Step 3 with the top offenders.

### Step 3: Relocate oversized storage off the call stack
- Actions (choose by situation):
  1. Non-reentrant worker: make its working stacks function-local `static` and `memset` them at entry (`static GoalStack gs; static ChoiceStack cs;`).
  2. Test fixture with many big members: move members to class-level `static` storage and hold references in the fixture; the constructor still runs the `*_init()` calls so each test gets fresh state.
  3. Helper that hands out a big object: return a reference to a function-local `static` instance (and make call sites bind with `&`, not `=`).
  4. Entry point: `static ReplState s;` in `main` instead of a stack object.
- Inputs: the ranked list from Step 2.
- Outputs: edited source at the same paths.
- Cautions: after making members `static`, grep for accidental by-value copies (`AtomTable t = make_table();` copies ~1 MB even though the helper returns a reference); re-verify every consumer still re-initializes state per test.
- Preserve: initialization order, public signatures, and all existing tests.
- Next: go to Step 4.

### Step 4: Rebuild and re-run the exact failing binary
- Actions: rebuild, execute the previously crashing binary by full path, then run the complete suite.
- Inputs: build script, test runner.
- Outputs: per-suite pass lines and the overall suite tally.
- Cautions: stale binaries and file locks produce misleading failures — if a suite shows no tests at all, rebuild it before interpreting.
- Next: go to Step 5.

### Step 5: Confirm no regression and document the decision
- Actions: compare pass counts with the pre-fix baseline; record in the project changelog/plan that the stacks were made `static` to stay under the Windows 1 MB default and that the routine is non-reentrant by design.
- Outputs: final tally plus the written rationale.
- Cautions: state the reentrancy assumption explicitly, since `static` storage makes the routine single-use across calls.
- Next: stop when every suite passes; otherwise return to Step 2 for any frame still over budget.

## Decision Rules
### When exit code is -1073741571 / 0xC00000FD
Treat as stack overflow; compute frame sizes before editing anything.

### When a test binary prints nothing at all
Run it by full path first; if it still dies before `main`, look for stack-sized objects created before/at startup (entry-point locals, huge return-by-value in the first executed helper), not for logic bugs.

### When the offending frame is a non-reentrant worker (solver loop)
Make its goal/choice/rename stacks function-local `static` and `memset` on entry; this was preferred over heap because the project forbids post-init malloc.

### When the offending frame is a test fixture used by many test cases
Move the big members to class `static` storage and expose them as references, keeping per-test `*_init()` calls in the constructor so state still resets between tests.

### When a helper returns a large struct by value
Change the call sites to bind a reference (`AtomTable &t = make_table();`); a value binding copies the whole table onto the stack even when the helper itself uses static storage.

### When only the entry point holds the object
Declare it `static` in `main`; nothing else needs to change.

### When the binary still overflows after relocation
Recompute the remaining locals (parser state, token buffers, clause structs) and repeat; do not enlarge capacities or delete tests to make the crash disappear.

## Invariants
- No capacity constants are reduced and no tests are skipped or weakened to avoid the overflow.
- No unrelated files, build flags, or configurations are modified; only storage duration/location of the oversized objects changes.
- Every relocated static buffer is still explicitly initialized (memset/`*_init`) at each entry point that uses it — no reliance on stale data from a previous call.
- The non-reentrancy assumption of each `static` is checked in code and stated; if reentrancy is required, this skill is not applied.
- Function signatures and observable behavior stay identical (callers only change `T x = helper()` to `T &x = helper()` where needed).
- The fix is only claimed after the previously crashing binary itself is re-run and its output observed; a clean compile alone is never reported as success.

## Common Failures
### Failure: suite shows an empty section instead of test output
- Symptoms: harness prints `--- test_indexing ---` with nothing after it, or exit -1073741571 with no lines.
- Causes: the binary crashed before `main` (stack overflow) — or, in one observed case, a stale/locked binary that failed to relink.
- Recovery: rebuild the binary, run it by full path, and only then attribute the silence to a stack overflow; the observed trajectory showed both causes in the same session.

### Failure: helper returns a reference but callers still copy
- Symptoms: after converting the helper to `static AtomTable &fresh_table()`, tests still crash.
- Causes: call sites written as `AtomTable t = make_table();` copy ~1 MB by value (the macro hides the reference).
- Recovery: grep every call site and change to `AtomTable &t = make_table();`; re-run until the binary passes.

### Failure: fixture made static, but tests now pollute each other
- Symptoms: suites that previously passed start failing in later test cases after the relocation.
- Causes: constructor no longer re-initializes the shared statics, or one test's state leaks into the next.
- Recovery: keep the `*_init()` calls in the fixture constructor (as the verified fix did) and re-run the full suite; if failures persist, the cause is elsewhere — do not attribute it to storage duration without evidence.

### Failure: fix appears to work but one suite still crashes
- Symptoms: overall tally like `9/10 suites passed, 1 failed` with one silent suite.
- Causes: a second offender remains (e.g. a test still declaring the big struct locally after the fixture was fixed).
- Recovery: repeat Step 2 arithmetic for the remaining suite's own locals; only the whole-suite run counts as verification.

## Verification
Observable checks (run after the edit; do not assume):

1. The previously crashing binary, invoked by full path, exits 0 and prints its per-test lines — e.g. the solver suite reported `22/22 tests passed` where it previously exited `-1073741571`.
2. Each formerly silent suite prints its own tally — the index suite printed `13/13 tests passed`, the atoms suite printed `17/17 tests passed` after its by-value copy was removed.
3. The whole-suite run reports zero failed suites — `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`.
4. Cross-check against the earlier baseline in the second session, which moved from `=== 2 suite(s) PASSED, 5 FAILED ===` toward `=== 6 PASSED, 1 FAILED ===` after the fixture relocations (the last suite there was still blocked by the by-value copy, so only partial credit until re-verified).
5. No suite's pass count dropped relative to pre-fix numbers (assertion-level regressions are out of scope and must be reported separately).
6. Grep confirms no remaining `T x = make_large_helper();` value bindings and no remaining multi-megabyte locals in the previously crashing frames.

## Examples
### Example 1: Solver working stacks blow the stack after an optimization
- Input: a solver whose choice point grew to `candidates[320]` uint32s (~1300 B) × `CHOICE_STACK_CAPACITY = 256` (~332 KB) as function locals; test run exits `-1073741571`.
- Procedure: Step 1 signature check → Step 2 arithmetic (`ChoiceStack ≈ 332 KB` plus goal stack and rename maps inside `solve()`) → Step 3.1 make them function-local `static` with `memset` at entry, justified by "solve() is non-reentrant by design" → Step 4 rebuild and rerun.
- Expected result: the solver suite runs to completion and prints `22/22 tests passed` instead of the crash exit.
- Parameterized values: choice capacity 256 × ~1300 B/entry; Windows default thread stack 1 MB.

### Example 2: Test fixture holds a 3.4 MB context as locals
- Input: an indexing test whose `IdxCtx` aggregates `AtomTable` (~1 MB) + `Database` (~1.6 MB with the embedded per-predicate index) + two `TermArena`s (~328 KB each) + two `VarRegistry`s; the suite exits `-1073741571` with no output.
- Procedure: Step 2 sums the members to ~3.4 MB → Step 3.2 converts members to class `static` storage with reference members while the constructor keeps calling `atom_table_init/db_init/term_arena_init/var_registry_init` → Step 4 reruns the suite by full path.
- Expected result: `13/13 tests passed`, exit 0.
- Parameterized values: fixture total ~3.4 MB vs 1 MB stack; adjust the member list to your own structs.

### Example 3: Helper hands out a 1 MB table and the caller copies it
- Input: `static AtomTable &fresh_table()` exists, yet the atoms suite still dies silently.
- Procedure: Step 2 finds call sites written `AtomTable t = make_table();`; Step 3.3 changes them to `AtomTable &t = make_table();` → Step 4 rerun.
- Expected result: `17/17 tests passed` for that suite, and the full run reaches `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`.
- Parameterized values: table capacity 4096 × ~260 B ≈ 1 MB; the same pattern applies to any ≥ few-hundred-KB struct returned by value.

### Example 4: Entry point allocates the whole runtime on the stack
- Input: program dies at startup; `ReplState` bundles `AtomTable` + `Database` + `TermArena` (megabytes) as a local in `main`.
- Procedure: Step 3.4 — `static ReplState s;  /* too large for the stack (~4 MB) */` — plus making the REPL's `TokenList`/`SolutionContext` per-query buffers `static` where they were ~128 KB locals.
- Expected result: binary starts, prints its banner, and the acceptance queries run (the trajectory's REPL acceptance run completed after this change).
- Parameterized values: runtime object size and per-query buffer sizes.

## Evidence
problem:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 184, source_part_index: 0, quote: "Exit code `-1073741571` = `0xC00000FD` = stack overflow.", supports: the crash signature being diagnosed in session 1 after the choice-point struct grew.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 187, source_part_index: 0, quote: "The real problem: `GoalStack` and `ChoiceStack` are local variables in `solve()` — that's where the stack overflow happens.", supports: locating oversized locals by size arithmetic (332 KB choice stack) rather than guessing.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 253, source_part_index: 0, quote: "test_indexing`, `test_solver`, and `test_atoms` all silently failed (exit with no output — stack overflow). They need to be run with full paths.", supports: the silent-exit symptom and the full-path run requirement.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 998, source_part_index: 0, quote: "The actual crash is a stack overflow from local `AtomTable` variables in test functions.", supports: the same failure mode independently identified in session 2 (~1 MB table in test locals).
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 324, source_part_index: 0, quote: "Line 108: `AtomTable t = make_table();` — this copies the 1MB `AtomTable` by value onto the LOCAL stack!", supports: the by-value copy as a distinct offender even after static helpers exist.

action:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 191, source_part_index: 0, quote: "/* Static to keep these large structures off the call stack.", supports: relocation of solver goal/choice stacks to function-local static storage with an explicit reentrancy rationale.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 268, source_part_index: 0, quote: "static AtomTable   s_atoms;", supports: the test-fixture pattern (class static members exposed as references) applied to the indexing fixture.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1002, source_part_index: 0, quote: "/* AtomTable is ~1 MB — too large for the default Windows stack.", supports: the reference-returning helper pattern (`fresh_table()` + macro) adopted in session 2.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1203, source_part_index: 0, quote: "So `AtomTable t = make_table()` **copies** the ~1MB AtomTable onto the local stack.", supports: the follow-up correction that call sites must bind references, not values.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-02, source_index: 271, source_part_index: 0, quote: "    static ReplState s;  /* too large for the stack (~4 MB) */", supports: the entry-point pattern (static runtime object in main).

verification:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 261, source_part_index: 0, quote: "22/22 tests passed", supports: the solver suite (previously crashing with -1073741571) runs to completion after the static-stack change.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 261, source_part_index: 0, quote: "exit: -1073741571", supports: shows the index suite was still crashing at that point, i.e. one fix did not cover all offenders (evidence the problem recurs per-frame).
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 279, source_part_index: 0, quote: "13/13 tests passed", supports: the fixture-static fix resolves the index suite crash.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 328, source_part_index: 0, quote: "17/17 tests passed", supports: the atoms suite passes after the by-value copy becomes a reference.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 333, source_part_index: 0, quote: "=== FINAL RESULT: 10/10 suites passed, 0 failed ===", supports: full-suite verification of all stack-overflow fixes together.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 984, source_part_index: 0, quote: "=== 2 suite(s) PASSED, 5 FAILED ===", supports: session-2 baseline before the fixture relocations.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1191, source_part_index: 0, quote: "=== 6 PASSED, 1 FAILED ===", supports: session-2 progress after static fixtures — and that its last suite stayed unverified for the by-value copy in this trajectory.

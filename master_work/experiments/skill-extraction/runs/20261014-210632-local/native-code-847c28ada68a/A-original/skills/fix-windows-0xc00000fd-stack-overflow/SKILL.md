---
name: fix-windows-0xc00000fd-stack-overflow
description: Use when a native C/C++ executable or test binary exits with 0xC00000FD / -1073741571 on Windows, usually with no output before any test prints. Helps the agent account for oversized stack objects (multi-MB structs, big frame arrays, by-value copies of returned structs) and relocate them to static storage while preserving behavior, then re-verify by rerunning the binary. Requires a working build command, the ability to run the binary and read its exit code and stdout. Do not use when the exit code is a different NTSTATUS (e.g. -1073741515 missing-DLL) or when the program fails with assertion messages or ordinary test failures.
---
# Fix 0xC00000FD (-1073741571) Stack-Overflow Exits of Native C/C++ Binaries on Windows

## Goal
Diagnose and eliminate 0xC00000FD (-1073741571) stack-overflow exits of a native C/C++ program on Windows by locating the oversized stack allocations, moving them to static storage without changing program semantics, and proving the fix by running the previously crashing binary and its test suite to completion.

## Scope
### In scope
- Windows exit code -1073741571 / 0xC00000FD from native C or C++ executables and test binaries, including crashes that print nothing at all.
- Static-size accounting of fixed-capacity structs and frame arrays (array length × element size) compared against the Windows default thread stack (~1 MB in the observed sessions).
- Storage-class fixes with unchanged semantics: function-local `static` frames that are reset per call, `static` fixture data members with reference members, out-of-line definitions of those members, and binding references instead of copying returned large structs.
- Rebuild-and-rerun verification of the specific binary plus the whole test suite, including checking whether the crash pre-dates the current change.

### Out of scope
- Other NTSTATUS failures such as -1073741515 (missing DLL reported in the trajectory) — these need their own remediation, not storage-class changes.
- Genuine infinite recursion bugs; this skill assumes the crash comes from fixed-size stack objects (the observed cases were fixed-size structs, not unbounded recursion).
- Raising the OS thread/stack limit as the primary fix (never demonstrated as the resolution in these trajectories).
- Ordinary assertion failures or test assertions failing while the binary runs normally.

## Inputs
1. **Exit code and harness output** — Type: text from the tool result of running the binary. Source: build/test harness output. Required: yes. Constraint: must show `Exit: -1073741571`, `exit: -1073741571`, `(exit -1073741571)` or the equivalent NTSTATUS `0xC00000FD`; output with no test lines means the crash happened before any test printed. Default: none.
2. **Source of the crashing binary and its test/fixture code** — Type: source files (C or C++) readable in the workspace. Source: project tree (e.g. `engine/solver.cpp`, `tests/test_atoms.cpp`, `main.c`). Required: yes. Constraint: you must be able to read the frame objects and helper functions that construct the large structs. Default: none.
3. **Build and run commands** — Type: shell command(s) for the project's compiler/linker and for launching the built binary. Source: project Makefile/scripts or the command previously used. Required: yes. Constraint: must capture both the compiler/linker exit code and the test binary's exit code separately. Default: none.
4. **Element sizes and capacity constants** — Type: numeric constants visible in headers/struct definitions (`CP_MAX_CANDIDATES`, `CHOICE_STACK_CAPACITY`, `ATOM_TABLE_CAPACITY`, `VAR_REGISTRY_CAPACITY` …). Source: project headers. Required: yes for size accounting. Constraint: use the values actually compiled in; recompute after any constant change. Default: none.
5. **Known stack budget** — Type: platform fact. Source: environment. Required: yes. Constraint: observed sessions ran with the Windows default ~1 MB thread stack; if the project already sets a larger `/STACK` reserve or runs on Linux, record that before comparing sizes. Default: Windows default thread stack (~1 MB).
6. **Baseline behavior of the binary before your changes** — Type: exit code of the pre-change build. Source: running the old binary (optional but valuable). Required: no. Constraint: record it so a pre-existing crash is not misattributed to your change. Default: none.

## Outputs
### Artifacts
- **Edited sources** (in place in the project): frames/fixtures that held multi-MB objects now hold them in static storage, with every call site binding a reference instead of copying. Format: ordinary C/C++ source edits.
- **Rebuilt binaries** in the project's build directory, produced by the project's normal build command.
- **Run log** of the previously crashing binary: exit code plus the printed test summary lines. Format: captured tool result text.

### Success criteria
- The binary that previously exited with -1073741571 now exits 0 and prints its expected output (e.g. `17/17 tests passed`).
- The full suite run shows every suite passing (observed end state: `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`).
- No test expectation, capacity constant, or algorithm was changed to achieve the pass.

### Failure criteria
- The binary still exits -1073741571, or crashes with no output.
- The crash code changes to a different NTSTATUS (e.g. -1073741515), which is a different problem.
- Suites that previously passed now fail after the storage-class edits.

## Preconditions
- The failing run reproduces the exact code -1073741571 / 0xC00000FD; if the harness only reports a wrapper code (e.g. PowerShell `Exit code 253`), open the tool result and confirm the inner `-1073741571` line before proceeding.
- A working build command exists and its exit code can be read separately from the test binary's exit code (a failed relink must not be mistaken for a crash).
- The source for the crashing binary and its tests/fixtures is readable, including the structs declared in function frames and the helpers that produce them.
- The stack budget for the target process is known: the observed sessions ran on the Windows default ~1 MB thread stack; if the project reserves a larger stack or runs elsewhere, state that before judging any object "too big".
- You may modify the offending source files (test fixtures and engine/test frames) but not capacity constants or test expectations.
- For each candidate frame you move to static storage, it must be acceptable for that storage to be shared across calls (the observed frames were explicitly non-reentrant or reset with `memset`/`*_init` on every entry); if a frame must be re-entrant or per-thread, stop and report that this fix does not apply.
- If any run reports a different NTSTATUS such as -1073741515, stop this procedure and handle that failure separately.

## Procedure
### Step 1: Confirm the failure is 0xC00000FD stack overflow
- Actions: run the binary (or read the existing run) and extract the innermost exit code; map -1073741571 to `0xC00000FD`. Record whether any output was printed before the crash.
- Inputs: harness/tool result text, run command.
- Outputs: a confirmed code (`-1073741571`) and a symptom note ("no output before any test line" if applicable).
- Cautions: wrapper shells may print a different top-level `Exit code`; a different inner code (e.g. `-1073741515`) means a different failure — abort this procedure.
- Preserve: the original failing command so the same command can be re-run for verification.
- Next: continue only when the code is -1073741571 / 0xC00000FD.

### Step 2: Account for every large object reachable from the crashing entry
- Actions: list the structs declared in the entry frame(s) — `main`, the engine `solve()` frame, each test body, each fixture struct — and compute each size from its fields: array length × element size, summed per struct (observed examples: a choice-point stack of 256 entries at ~1072 bytes ≈ `ChoiceStack total: 274432 bytes = 0.26 MB`; an `AtomTable` of `4096 * (256+4+4) = ~1MB`; a whole test fixture computed at ~3.4 MB). Compare totals with the ~1 MB stack budget.
- Inputs: headers with capacity constants, struct definitions.
- Outputs: a ranked list of objects whose combined footprint in one frame can exceed the budget.
- Cautions: a struct that is `static` inside a helper can still be copied onto the stack by the caller; count copies, not just declarations.
- Preserve: all constants and struct layouts — this step only measures.
- Next: if any frame's objects approach or exceed the budget, go to Step 4; if every frame is far below budget, go to Step 3.

### Step 3: Isolate a no-output crash to its source
- Actions: rebuild the crashing test/binary against a minimal object set (only the objects that test actually needs); if it still crashes, read the test source end-to-end and look for by-value declarations or assignments of large structs (the observed culprit was `AtomTable t = make_table();` copying ~1 MB onto the local stack).
- Inputs: link command, test source file.
- Outputs: the exact line(s) allocating the oversized object.
- Cautions: a missing-output run can also be a stale or unlocked exe; confirm the binary you ran is the one you just linked.
- Preserve: the original link list for the full-suite verification later.
- Next: proceed to Step 4 with the located lines.

### Step 4: Move the oversized objects to static storage, preserving semantics
- Actions: pick the variant that matches ownership:
  (a) engine/frame locals that are explicitly non-reentrant → function-local `static` plus a `memset`/`*_init` of that storage at every entry (observed in `solve()`: `solve() is non-reentrant by design.` with `static` goal/choice stacks zeroed on entry);
  (b) large state shared by a whole test binary → `static` data members of the fixture struct with out-of-line definitions (observed: `AtomTable   IdxCtx::s_atoms        = {};` plus reference members bound in the constructor);
  (c) big singletons used by helpers → a helper owning one `static` instance and returning a reference (observed comment: `AtomTable is ~1 MB — too large for the default Windows stack.`), with every call site binding `T &t = helper()` — never `T t = helper()`;
  (d) the program's top-level state object → `static` in `main` (observed: `static ReplState s;  /* too large for the stack (~4 MB) */`).
- Inputs: the ranked list from Step 2 and the lines from Step 3.
- Outputs: edited sources; no change to capacities, algorithms, or expectations.
- Cautions: static storage becomes shared state — the reset-on-entry behavior must be kept, and shared-state side effects between tests must be checked by rerunning the suite (see Invariants).
- Preserve: all call signatures where possible; prefer reference binding over API redesign.
- Next: rebuild and verify the single binary (Step 5).

### Step 5: Rebuild and run the previously crashing binary
- Actions: compile/link with the project command, check the build exit code first, then run the binary exactly as before and read its exit code and printed summary.
- Inputs: build command, run command from Step 1.
- Outputs: build exit code, run exit code, printed pass summary.
- Cautions: a relink may fail while the old exe is still running (`fatal error LNK1105: cannot close file`) — stop the lingering process and relink before judging the result; do not count a wrapper-shell error as a crash.
- Preserve: unmodified test expectations.
- Next: only when the binary exits 0 with its expected output, go to Step 6; otherwise return to Step 2 with the remaining frames.

### Step 6: Run the full suite and confirm no regressions
- Actions: run every test suite in one pass (observed end state: `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`), and compare with the pre-change baseline (the observed pre-existing crash was confirmed by running the old binary: `OLD test_atoms exit: -1073741571`).
- Inputs: suite runner command, baseline exit codes.
- Outputs: per-suite pass lines and an overall pass/fail summary.
- Cautions: a suite that prints nothing is still failing — treat empty output as a crash until proven otherwise.
- Preserve: everything outside the storage-class edits.
- Next: stop when all suites pass; if a suite still crashes, resume at Step 2 for that suite's own frames.

## Decision Rules
### When the inner exit code is -1073741571 (0xC00000FD)
Treat the run as a stack overflow of fixed-size stack objects: proceed to size accounting (Step 2) instead of hunting for assertion or logic bugs.

### When the inner exit code is a different value (observed: -1073741515)
Do not apply storage-class fixes; the trajectory reports that code as `missing DLL (ASAN runtime not in PATH)` — resolve that dependency problem first, then re-check the code.

### When the binary prints nothing before dying
The crash precedes any test output; isolate it by minimal linking and by reading the source for by-value declarations of large structs (Step 3). Empty output counts as a failing run until the binary prints its summary.

### When one frame's accounted objects reach ~1 MB or more
Move those objects to static storage, choosing the variant by ownership: non-reentrant engine frame → function-local `static` with reset-on-entry; whole-binary test fixture → `static` data members + reference members; helper-owned singleton → return `T &`; top-level program state → `static` in `main`.

### When a helper returns a reference to static storage but call sites assign by value
Rewrite every call site to bind a reference (`T &t = helper()`); the trajectory's diagnosis was that the `=` still copies the ~1 MB struct onto the local stack, so fixing only the helper is insufficient.

### When the object was already made static but the same suite still crashes
Look for the next remaining oversized local (fixtures hold several such structs: atom table, database, two term arenas, registries); fix one struct at a time and rerun after each batch.

### When a relink fails with a file-lock error (LNK1105 / "cannot close file", wrapper code 1105)
Stop the lingering test process and relink; do not interpret the relink failure as a stack-overflow result.

### When the crash also occurs on the pre-change binary
Record it as pre-existing, still fix it with the same procedure, and verify against the recorded baseline rather than claiming a regression you introduced.

### When shared static fixture state could leak between tests
Keep per-test re-initialization (`*_init`/`memset` on entry) and rely on the full-suite run to detect cross-test pollution; if a suite regresses after the storage move, restore per-test initialization before changing anything else.

## Invariants
- Do not change capacity constants (`CP_MAX_CANDIDATES`, `CHOICE_STACK_CAPACITY`, `ATOM_TABLE_CAPACITY`, `VAR_REGISTRY_CAPACITY` …), clause/index algorithms, or test expectations to make the crash disappear; only storage duration and reference binding change.
- Any object moved to static storage must be re-initialized on every use exactly as its stack incarnation was (the observed frames zeroed themselves with `memset`/`*_init` at entry); never let one call observe another call's leftover state unless the code already documented that sharing.
- Move a frame to `static` only where re-entrancy is already excluded by design (observed justification: `solve() is non-reentrant by design.`); if the function can be entered recursively or from multiple threads, do not apply this fix.
- Every call site that receives a large struct must bind a reference; no new by-value copies of the large struct may be introduced anywhere, including inside test helpers and macros.
- Do not modify unrelated files, build configuration, or linker stack settings as part of this fix; do not delete or weaken tests to reach a green run.
- Do not report success from compilation alone: a passing build proves nothing about the runtime crash — success requires re-running the binary and reading its exit code and printed summary.
- Do not treat wrapper-shell codes (e.g. `Exit code 253`) or relink/file-lock failures as the program's own exit status.
- Do not claim the crash was introduced by the current change until the pre-change binary has actually been run.

## Common Failures
### Failure: helper converted to static storage, but call sites still copy
- Symptoms: the suite still crashes with -1073741571 and no output after the helper itself was rewritten to return a reference to a `static` instance.
- Causes: each call site still declares the struct by value (`AtomTable t = make_table();`), materializing a full-size copy on the local stack. The trajectory's diagnosis reads: "So `AtomTable t = make_table()` **copies** the ~1MB AtomTable onto the local stack. That's the crash. The `=` copies it."
- Recovery: bind references at every call site (observed edit: `AtomTable &t = make_table();` with replace-all), rebuild, and rerun; verify by output, not by the edit succeeding.

### Failure: only some oversized frames were fixed; one suite keeps crashing
- Symptoms: suites that were fixed now pass (observed: `22/22 tests passed` for the solver suite) while another suite still exits -1073741571 with no output.
- Causes: each test binary has its own fixtures (atom table, database, two term arenas, registries) and each one can individually exceed the ~1 MB budget; one shared fix does not cover all binaries.
- Recovery: repeat Steps 2–5 per crashing binary; the observed session needed three separate rounds (solver stacks, indexing fixture members, atom-table by-value copy) before `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`.

### Failure: relink blocked while an old test process still holds the exe
- Symptoms: linking reports "fatal error LNK1105: cannot close file" or a wrapper `exit 1105`; the binary you run may be stale.
- Causes: a previous test process was left running or its window locked the output file.
- Recovery: stop the lingering test process, relink, confirm the link exit code is 0, then run and read the fresh exit code; after such a relink the observed run produced a normal `22/22 tests passed` result.

### Failure: misreading the exit code and fixing the wrong problem
- Symptoms: storage-class edits are made although the run actually reported -1073741515 (a missing-DLL code in the observed session), or a wrapper `Exit code` is read as the program's status.
- Causes: several NTSTATUS values look similar as signed 32-bit numbers; shells print their own wrapper code first.
- Recovery: re-read the raw tool result for the innermost code, confirm the mapping, and restart the correct procedure; the stack-overflow path applies only to -1073741571 / 0xC00000FD.

### Failure: crash blamed on the current change when it predates it
- Symptoms: an untouched suite fails with the same code mid-refactor.
- Causes: pre-existing oversized locals that were never exercised before.
- Recovery: run the pre-change binary to establish the baseline (observed: `OLD test_atoms exit: -1073741571`), document it as pre-existing, then apply this procedure anyway and verify against that baseline.

## Verification
- Re-run the exact command that produced -1073741571 and observe the program's own exit code: it must be 0 and the printed summary must be present (an empty summary line still means failure).
- Run each previously crashing test binary individually and read its pass line (the observed fixes produced `22/22 tests passed`, `13/13 tests passed`, `17/17 tests passed` for the three affected suites).
- Run the full suite once after all edits and require every suite to pass (observed terminal state: `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`).
- Confirm the build itself is clean: the compile/link exit code is 0 with no new warnings introduced by the storage edits (a relink must not be blocked by a lingering process).
- Grep the touched files for any remaining by-value declaration of the large structs (`AtomTable t = ...`, `T x = make_xxx()`) and confirm none remain.
- Grep for the new `static` declarations and confirm each one sits in a frame that re-initializes the storage on entry (`memset` / `*_init`) before first use.
- Re-check that capacity constants and test expectations are byte-identical to before the change (diff the touched files against the pre-change version).
- If a pre-change baseline run exists, compare: suites that failed before with -1073741571 must now pass, and suites that passed before must still pass.
- Confirm no other exit code appears anywhere in the run log (any -1073741515 or other NTSTATUS invalidates the result).

## Examples
### Example 1: Non-reentrant engine frame with a huge choice-point stack
- Input: solver suite exits with `Exit: -1073741571`; size estimate for the frame shows `ChoiceStack total: 274432 bytes = 0.26 MB` plus goal stack and rename map, on top of multi-hundred-KB arena locals in the same call chain.
- Procedure: Step 2 (account sizes), then Step 4a — make the engine's goal stack, choice stack and rename map function-local `static`, zero them with `memset` at every entry of `solve()` because `solve() is non-reentrant by design.`; Step 5 rebuild and run.
- Expected result: the solver suite prints `22/22 tests passed` with exit 0.
- Parameterized values: capacity `256` choice points × ~`1072` bytes per point; Windows default stack `~1 MB`; reset-on-entry via `memset(&gs, 0, sizeof(GoalStack));`.

### Example 2: Test fixture struct whose members total several MB
- Input: an indexing test binary exits `-1073741571` with no printed tests; accounting shows the fixture ≈ 3.4 MB because `But the 3.4MB still exceeds the default Windows stack size (1MB).`
- Procedure: Step 4b — convert the fixture's large members to `static` data members and define them out of line (e.g. `AtomTable   IdxCtx::s_atoms        = {};`), keep the constructor initializing them per construction; Steps 5–6 rebuild and run, then the full suite.
- Expected result: the indexing suite prints `13/13 tests passed`; the observed suite run advanced to `FINAL: 9/10 passed, 1 failed` at that point and reached `=== FINAL RESULT: 10/10 suites passed, 0 failed ===` after the last crashing binary was fixed.
- Parameterized values: fixture members `AtomTable` ≈ 1 MB, `Database` ≈ 1.6 MB, two `TermArena` ≈ 328 KB each, two `VarRegistry` ≈ 82 KB each.

### Example 3: By-value copy of a static-backed helper result
- Input: a test binary still prints nothing and exits `-1073741571` even though the helper returns a reference to a `static` instance; a grep of the test file shows `35:    AtomTable t = make_table();` plus 12 further by-value sites (13 in total).
- Procedure: Step 3 (locate by-value sites in the test source) → Step 4c — replace every site with a reference binding (observed edit: `AtomTable &t = make_table();` applied with replace-all) → Step 5 rebuild and run the single binary → Step 6 full suite.
- Expected result: the atom suite prints `17/17 tests passed` with exit 0 and the full suite passes.
- Parameterized values: struct size `4096 * (256+4+4) = ~1MB`; number of by-value call sites in this file: 13; helper comment recording the size: `AtomTable is ~1 MB — too large for the default Windows stack.`

## Evidence
Problem:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 183, source_part_index: 0, quote: "Exit: -1073741571", supports: problem — the runner's tool result showing the failing native exit code after a test-suite change.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 184, source_part_index: 0, quote: "Exit code `-1073741571` = `0xC00000FD` = stack overflow.", supports: problem — the code-to-cause mapping (0xC00000FD = stack overflow) this skill starts from.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 987, source_part_index: 0, quote: "(exit -1073741571)", supports: problem — five test binaries each dying with the same code and printing no test output at all.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 997, source_part_index: 0, quote: "-1073741515", supports: decision rule — a different observed NTSTATUS (reported as missing DLL), showing the exit code must be checked before choosing this procedure.

Diagnosis:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 186, source_part_index: 0, quote: "ChoiceStack total: 274432 bytes = 0.26 MB", supports: diagnosis — measured size of one fixed-size frame object used in the stack budget calculation.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 262, source_part_index: 0, quote: "But the 3.4MB still exceeds the default Windows stack size (1MB).", supports: diagnosis — whole fixture struct exceeding the ~1 MB default Windows stack, the comparison driving the fix.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 998, source_part_index: 0, quote: "`AtomTable` contains `4096 * (256+4+4) = ~1MB`", supports: diagnosis — deriving an object's size from capacity constants for the budget check.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 324, source_part_index: 0, quote: "copies the 1MB `AtomTable` by value onto the LOCAL stack! That's an immediate stack overflow.", supports: diagnosis — the by-value copy of a returned large struct as an independent cause of the same exit code.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 1203, source_part_index: 0, quote: "So `AtomTable t = make_table()` **copies** the ~1MB AtomTable onto the local stack.", supports: diagnosis — why converting only the helper to static storage is insufficient: the call site assignment still copies.

Action:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 191, source_part_index: 0, quote: "Static to keep these large structures off the call stack.", supports: action — moving the engine's goal/choice stacks to function-local static storage with reset-on-entry.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 271, source_part_index: 0, quote: "static ReplState s;  /* too large for the stack (~4 MB) */", supports: action — moving the program's top-level multi-MB state object out of `main`'s stack frame.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 273, source_part_index: 0, quote: "AtomTable   IdxCtx::s_atoms        = {};", supports: action — out-of-line definitions of the fixture's `static` data members (the pattern that relocates multi-MB fixture state).
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 1005, source_part_index: 0, quote: "Large structs live in static storage — too big for Windows default stack.", supports: action — static-backed helper pattern replacing by-value construction in tests.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 1036, source_part_index: 0, quote: "Large members (AtomTable ~1MB, TermArena ~4MB) live in static storage.", supports: action — fixture members held in static storage with reference members bound in the constructor.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 325, source_part_index: 0, quote: "AtomTable  &t  = make_table();", supports: action — binding a reference instead of copying the ~1 MB struct at the call site.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 1204, source_part_index: 0, quote: "AtomTable &t = make_table();", supports: action — replace-all conversion of every by-value call site to a reference binding.

Verification:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 261, source_part_index: 0, quote: "22/22 tests passed", supports: verification — the previously crashing solver suite runs to completion after its large frames became `static`.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 279, source_part_index: 0, quote: "13/13 tests passed", supports: verification — the indexing suite (previously exiting -1073741571 with no output) passes after its fixture members became `static`.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 328, source_part_index: 0, quote: "17/17 tests passed", supports: verification — the atom suite passes after the by-value copy was changed to a reference binding.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 333, source_part_index: 0, quote: "=== FINAL RESULT: 10/10 suites passed, 0 failed ===", supports: verification — end-to-end proof that every suite runs and passes after all storage-class fixes.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 303, source_part_index: 0, quote: "OLD test_atoms exit: -1073741571", supports: verification — baseline check establishing the crash pre-dated the change.

Cautions:
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 1187, source_part_index: 0, quote: "fatal error LNK1105: cannot close file", supports: caution — a relink blocked by a lingering test process must be cleared before any run result can be trusted.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 1218, source_part_index: 0, quote: "=== 5/6 suites PASSED, 2 FAILED ===", supports: caution — in the second session the same pattern was still unresolved at session end (a suite with no printed summary counts as failing), so partial fixes must not be reported as done.

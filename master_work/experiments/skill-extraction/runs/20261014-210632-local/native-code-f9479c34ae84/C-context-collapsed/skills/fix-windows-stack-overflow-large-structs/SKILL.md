---
name: fix-windows-stack-overflow-large-structs
description: Use when a program or test binary compiled with fixed-capacity, no-malloc data structures (multi-MB atom tables, term arenas, token lists) exits immediately with code -1073741571 and prints nothing. Helps the agent move those objects into static storage and re-run the suites to confirm the crash is gone. Requires rebuilding and running the affected binaries on Windows with the default thread stack. Do not use when the process produces output before failing, or when the exit code is a link/compile failure.
---
# Fix Immediate Process Death from Large Fixed-Size Structs on the Windows Stack

## Goal
Stop the immediate, output-less death (exit code -1073741571) of a Windows program or test binary caused by multi-megabyte fixed-capacity structs living on the stack, by relocating them to static storage and re-running the suites to confirm they start.

## Scope
### In scope
- Programs built with fixed-size, no-malloc-after-init data structures (atom tables, term arenas, token lists, registries) sized in the megabytes.
- Windows processes that exit with `-1073741571` before printing anything, including test binaries that therefore report `0 tests run`.
- Moving the offending objects to static storage in three verified shapes: a `static` local in `main`, a function-local `static` inside a factory that returns a reference and re-initializes per call, and `static` data members of a test context struct.
- Verification by rebuilding and running the previously crashing binaries and observing real test output.

### Out of scope
- Assertion failures and logic bugs in tests that now run.
- Deliberately increasing thread stack size or changing linker/OS flags (no evidence it was needed or tried successfully).
- Linux/macOS behavior; only Windows was exercised.
- Diagnosing failures where the program prints output before dying.

## Inputs
- **Exit code and output of the failing binary** — process result — from running the binary — required — must be `-1073741571` with empty stdout/stderr — default: none.
- **Struct inventory** — sizes of candidate objects — from headers and test sources — required — identify objects in the ~1 MB+ range (`AtomTable` 4096 slots, `TermArena` 8192 nodes + 32768-arg pool, `TokenList` 2048 tokens) and where they are declared — default: none.
- **Declaration sites** — file paths — from the sources — required — `main` function locals, factory functions returning by value, and context structs with large by-value members — default: none.
- **Build command** — string — from the project build script — required — same flags as the failing build so the comparison is valid (trajectory: `clang++ -std=c++23 -Iinclude -Itests -g -O0 ...`) — default: none.
- **Platform** — enum — environment — required — Windows with the default thread stack; the fix targets that constraint — default: Windows.
- **Unused for this skill** — none.

## Outputs
### Artifacts
- Edited sources where the large objects now live in `static` storage (function-local statics, static members with out-of-line definitions, or `static` locals in `main`), each with an initialization call in the constructor/init path.
- Rebuilt binaries for the previously crashing programs/tests.
- Run transcript with per-suite output and exit codes.

### Success criteria
- Every previously crashing binary starts and produces output (test result lines, banner, or its own error messages).
- Suites that crashed report pass counts (e.g. `15/15 tests passed`) instead of exiting silently with `-1073741571`.

### Failure criteria
- Any binary still exits `-1073741571` with no output.
- A binary starts but is reported as fixed while its suites actually fail assertions (that is a different problem and must be reported as such).
- Crashes appear only after the change (would indicate shared-static state leaking between tests).

## Preconditions
- The failure is reproducible: running the binary exits with `-1073741571` and prints nothing. If it prints output first, this skill does not apply.
- The build links cleanly first (an unresolved-symbol link failure must be fixed separately before any run-based diagnosis).
- You can identify the largest objects on the call path: sum of the by-value locals/fixtures in the failing function must plausibly exceed the default Windows thread stack.
- Permission to edit the declaring sources and to rebuild/re-run the affected binaries.
- Lingering processes holding the binaries are killed first; the trajectory had to `taskkill` old test executables before recompiling, otherwise the build result is stale.
- Because several test files may need edits at once, plan to rebuild all suites together so the verification covers the whole set.

## Procedure
### Step 1: Confirm the signature of the failure
- Actions: run each failing binary directly (not through a pipe that hides output) and record exit code and output; confirm exit `-1073741571` with empty output.
- Inputs: binaries.
- Outputs: per-binary exit code and output.
- Cautions: an empty result inside a pipeline can mask real output; run plainly and check `$LASTEXITCODE`/`%ERRORLEVEL%` explicitly. A different exit code (e.g. a missing-DLL style failure) is a different problem.
- Preserve: the exact exit codes for the record.
- Next: proceed when the exit code matches and nothing is printed.

### Step 2: Size the suspects
- Actions: list every object declared by value on the failing path — `main` locals, factory return values, test context struct members — and compute approximate sizes from capacity constants (`ATOM_TABLE_CAPACITY`, `TERM_ARENA_CAPACITY`, `ARG_POOL_CAPACITY`, `TOKEN_LIST_CAPACITY`).
- Inputs: headers and the failing function's source.
- Outputs: a ranked list of objects in the megabyte range and their declaration sites.
- Cautions: several individually-below-the-limit objects stacked together still overflow; count the sum, not the largest one.
- Preserve: source files (read-only in this step).
- Next: proceed when at least one site puts megabytes on the stack.

### Step 3: Move the large objects to static storage
- Actions: apply the shape that matches the site —
  - `main` local: declare it `static` (trajectory: `static ReplState s;  /* too large for the stack (~4 MB) */`).
  - Factory returning a large struct by value: convert to a function returning a reference to a function-local `static` instance that re-initializes on each call, keeping the old call syntax with a macro alias (trajectory: `static AtomTable &fresh_table() { static AtomTable t; atom_table_init(&t); return t; }` plus `#define make_table() fresh_table()`).
  - Context struct with large members: make the members `static` data members, bind them by reference in the constructor, and provide out-of-line definitions (trajectory: `static AtomTable s_atoms;` ... `AtomTable   SolverCtx::s_atoms        = {};`).
- Inputs: the ranked declaration-site list.
- Outputs: edited sources; every large object now in static storage with an explicit init call.
- Cautions: statics are shared across calls — each test/factory entry must re-initialize (or explicitly reset) the object, otherwise state leaks between tests; keep the public API unchanged so callers need no edits.
- Preserve: capacity constants, initialization semantics, and all call sites.
- Next: rebuild.

### Step 4: Rebuild and rerun everything
- Actions: kill lingering processes holding old binaries; rebuild every affected binary with the same flags; run each and record exit code plus output.
- Inputs: build command, binaries.
- Outputs: rebuild status; per-suite run results.
- Cautions: do not judge by compilation alone — the failure was at startup; also treat a suite that runs but fails assertions as a separate, still-open issue.
- Preserve: prior failing transcript for comparison.
- Next: proceed to verification when no binary exits `-1073741571` silently.

### Step 5: Verify suite-by-suite
- Actions: compare per-suite results against the pre-fix run; confirm suites that previously produced zero output now print pass counts.
- Inputs: run transcripts before and after.
- Outputs: table of suite → before (silent crash) → after (output and count).
- Cautions: other edits may land in the same window; report exactly which suites changed and note that assertion-level fixes were separate.
- Preserve: both transcripts.
- Next: stop when all previously silent binaries produce output.

## Decision Rules
### When the process exits -1073741571 with no output and the failing function holds multi-MB by-value objects
Move those objects to static storage (Step 3 shapes) and rerun; this is the verified path.

### When a helper returns a large struct by value
Convert it to return a reference to a function-local `static` that is re-initialized on entry; do not keep returning megabyte-sized objects on the stack.

### When a test context struct embeds several large tables
Make those members `static` data members with out-of-line definitions and bind them by reference in the constructor, re-running init in the constructor body.

### When a suite runs after the fix but reports failing assertions
Declare the stack issue resolved for that suite and open a separate investigation for the assertion; do not keep changing storage layout to chase test logic.

### When a build fails with an unresolved-symbol link error before any run
Fix the link error first; until the binary links, the stack-overflow symptom cannot be observed or verified.

### When the exit code is something other than -1073741571 (for example a missing-runtime-DLL style failure under a sanitizer build)
This skill does not apply; that path was attempted and abandoned in the trajectory with no confirmed fix — report it as unresolved rather than improvising.

## Invariants
- Do not reduce capacity constants or shrink data structures to dodge the crash; the fixed capacities are part of the design (no-malloc-after-init).
- Do not change compiler flags, linker options, or stack-size settings as the fix; only storage duration changes.
- Do not edit test assertions or production logic while making this change, so before/after differences stay attributable to storage placement.
- Re-initialize every static object at each entry point that previously relied on a fresh instance; never let state carry over silently between tests.
- Rebuild and run every affected binary; never report success from a compile-only check.
- Report suites that still fail after they start as remaining failures, not as successes.

## Common Failures
### Failure: binary exits -1073741571 before printing anything
- Symptoms: exit code `-1073741571`, empty stdout/stderr; in a suite run, the harness shows `FAIL: <name>` with no test lines at all.
- Causes: megabyte-scale fixed-capacity structs (`AtomTable` ~1 MB, `TermArena` ~4 MB, `TokenList` ~128 KB, several together) declared as stack locals or returned by value, exceeding the default Windows thread stack.
- Recovery: move them to static storage with per-entry re-initialization (Step 3), rebuild, rerun.

### Failure: crash disappears only for some suites
- Symptoms: some suites print results while others still exit silently.
- Causes: not every large-fixture site was converted (the trajectory's last visible run still had one suite with no output line).
- Recovery: re-run Step 2 over the remaining suites' fixtures and convert the missed sites; keep iterating until no silent exit remains.

### Failure: binary starts but a suite reports failures, or a run shows a compile error for one suite
- Symptoms: e.g. `test_parser` reported as `COMPILE ERROR` in the same run where others pass, or assertion failures.
- Causes: unrelated compile/assertion problems coexisting with the storage fix.
- Recovery: handle separately; do not revert the static-storage change.

### Failure: sanitizer build exits with a different code and no output (attempted, unresolved)
- Symptoms: a `-fsanitize=address` build of a test exits with code 53 / `-1073741515` and prints nothing.
- Causes: not confirmed in this trajectory (the assistant suspected a missing ASan runtime DLL, unverified).
- Recovery: abandon the sanitizer build for diagnosis and use plain `-g -O0` builds; report the sanitizer issue as open.

## Verification
For each previously crashing binary, after rebuilding with the same flags:

- Running it directly exits with a code other than `-1073741571`.
- It produces visible output (suite banner, per-test PASS lines, `N/N tests passed`, or its own error message).
- Suites that previously exited silently now report counts, e.g. `test_terms: 15/15 tests passed`, `test_solver: 22/22 tests passed`, `test_unifier: 18/18 tests passed`.
- No suite in the run shows the old silent-crash signature (`FAIL: <suite>` with an empty body and exit `-1073741571`).
- A second consecutive run gives the same results (guards against shared-static state that only fails on reuse).

These are observable checks for future runs, not claims about any already-executed session.

## Examples
### Example 1: large runtime state in `main`
- Input: the C runtime's `ReplState` (holding a ~1 MB atom table and multi-MB arenas) declared as a plain local in `main`; the program dies at startup.
- Procedure: Step 1 confirm silent `-1073741571`; Step 2 size `ReplState` from its capacity constants; Step 3 change the local to `static ReplState s;  /* too large for the stack (~4 MB) */` and likewise make large per-query `TokenList` locals `static` with a `/* 128 KB — too large for the stack */` note; Step 4 rebuild and run.
- Expected result: the program starts and reaches its REPL banner/queries instead of dying silently.
- Parameterized values: struct `ReplState`, table `AtomTable`, capacity constants `ATOM_TABLE_CAPACITY`/`TERM_ARENA_CAPACITY`.

### Example 2: test fixtures constructed by value
- Input: `static AtomTable make_table() { AtomTable t; atom_table_init(&t); return t; }` in a test file; the suite exits `-1073741571` with no output.
- Procedure: Step 2 identify `AtomTable` (~1 MB per call) returned by value; Step 3 replace with `static AtomTable &fresh_table() { static AtomTable t; atom_table_init(&t); return t; }` and `#define make_table() fresh_table()`; convert context structs the same way (static members, reference binding in the constructor, out-of-line definitions); Steps 4–5 rebuild all suites and run them.
- Expected result: the suite prints its tests and a count such as `15/15 tests passed` instead of exiting silently.
- Parameterized values: fixture name `make_table`/`fresh_table`, context structs `ParseCtx`/`SolverCtx`/`UnifyCtx`, output dir `build/tests`.

## Evidence
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 987, source_part_index: 0 — quote: `=== test_atoms ===\r\n(exit -1073741571)` — supports: five suites exited with `-1073741571` and produced no test output at all, the crash-before-any-test signature.
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 989, source_part_index: 0 — quote: `AtomTable\` = ~1MB, \`TermArena\` = ~4MB — in \`test_solver.cpp\` the \`SolverCtx\` struct has two \`TermArena\`s inline. That's ~8MB on the stack inside a test function. Need to make those \`static\`` — supports: sizes of the by-value fixtures were computed and identified as exceeding the Windows default stack.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1002, source_part_index: 0 — quote: `static AtomTable &fresh_table()\n{\n    static AtomTable t;\n    atom_table_init(&t);\n    return t;\n}` — supports: the by-value factory was converted to a function-local static returned by reference with per-call re-initialization.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1014, source_part_index: 0 — quote: `/* Large members (AtomTable ~1MB, TermArena ~4MB) live in static storage. */` — supports: context-struct members were moved to static storage with reference binding in the constructor.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-02`, source_index: 271, source_part_index: 0 — quote: `    static ReplState s;  /* too large for the stack (~4 MB) */` — supports: the same static-storage fix was applied earlier to the program's `main`, where the runtime state was a plain stack local.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1218, source_part_index: 0 — quote: `test_terms: 15/15 tests passed` — supports: `test_terms` previously exited `-1073741571` with no output and now runs and passes all its tests after the static-storage conversion (other assertion fixes also landed in the same window, so attribution is for the silent-crash symptom).
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1218, source_part_index: 0 — quote: `test_solver: 22/22 tests passed` — supports: `test_solver`, whose context embedded multi-MB arenas and which crashed silently before, now executes fully.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1218, source_part_index: 0 — quote: `test_unifier: 18/18 tests passed` — supports: a third previously silent-crashing suite now runs and reports results; note the same run still shows `COMPILE ERROR: test_parser.cpp`, so the fix was not verified for every suite before the trace ended.

---
name: fix-stack-overflow-large-test-fixtures
description: Use when a C++ test executable exits with -1073741571 (STATUS_STACK_OVERFLOW) and prints no test output. Helps the agent isolate the crash to one test file and move MB-scale fixtures out of automatic storage so suites report results. Requires Windows, a rebuild command, and the ability to edit test fixtures only. Do not use when the crash code differs, when the binary prints test results, or when the failure is a link error.
triggers:
  - "-1073741571"
  - "STATUS_STACK_OVERFLOW"
---
# Fix Test Binaries That Crash at Startup on Windows Stack Overflow

## Goal
Stop test binaries from dying with the Windows stack-overflow exit code before printing any results by moving MB-scale fixtures (e.g. `AtomTable`, `TermArena`) out of automatic storage, so every suite runs and prints `N/N tests passed`.

## Scope
### In scope
- Test-code crash diagnosed as stack overflow: exit code `-1073741571`, zero output from the binary.
- Isolating the crash with a minimal framework-only test.
- Moving large fixed-size fixtures to static storage: helpers returning `static` references, fixture structs holding `static` members bound by references in the constructor.
- Detecting remaining by-value copies of large structs at call sites.

### Out of scope
- Production/engine code changes and capacity-constant reductions.
- Different crash codes (access violation, missing DLL — the trace saw `-1073741515` from an ASAN runtime not in PATH, a tooling issue, not the bug).
- Link errors (LNK1120/LNK1105) and test assertion failures that occur once suites actually run.

## Inputs
1. **Test run output with exit code** — type: text tool result; source: running `build\tests\<suite>.exe`; required: yes; constraint: symptom is `exit: -1073741571` with no test lines printed; default: 无.
2. **Per-suite run results** — type: text tool result; source: the build-and-run loop; required: yes; constraint: distinguishes suites that crash from suites that report counts; default: 无.
3. **Test sources** — type: source files (`tests/test_atoms.cpp`, `tests/test_terms.cpp`, `tests/test_parser.cpp`, `tests/test_unifier.cpp`, `tests/test_solver.cpp`); required: yes; constraint: only test fixtures may be edited; default: 无.
4. **Fixture struct capacity constants** — type: source (headers such as `include/atoms.hpp`, `include/terms.hpp`); required: yes for sizing; constraint: the trace's size estimates (~1 MB for `AtomTable`, ~4 MB for `TermArena`) are assistant estimates, not tool-verified header reads — confirm capacities yourself; default: 无.
5. **Build command** — type: shell/PowerShell script; required: yes; constraint: recompiles a single test file for isolation (trace: `clang++ -std=c++23 -Iinclude -Itests -g -O0 <shared sources> <test file> -o <bin>`); default: 无.
6. **Windows environment** — type: OS; required: yes; constraint: default thread stack of the observed environment; the exit code mapping is Windows-specific; default: 轨迹未提供 exact stack size.

## Outputs
### Artifacts
- Edited test files: fixture structs with `static` members plus reference bindings and out-of-class static definitions; helpers returning `static` references (e.g. `static AtomTable &fresh_table()`).
- A minimal repro file used for isolation (trace: `build/minimal_test.cpp`).
- Updated call sites binding fixtures by reference instead of by value.

### Success criteria
- Every previously crashing suite prints `N/N tests passed` and exits 0; no run output contains `-1073741571`.
- Suites that already passed keep passing.

### Failure criteria
- Any suite still exits `-1073741571` or prints nothing.
- A fixture's shared static state is not re-initialised, so results differ run to run.

## Preconditions
- The observed failure is a Windows exit code of `-1073741571` with no test output; a different code means a different diagnosis (stop and re-diagnose).
- A rebuild command for a single test file is available so fixes can be verified quickly.
- Edits are limited to test files (fixtures, helpers, call sites); production sources stay untouched.
- The test framework itself can be exercised by a minimal file — this is needed for the isolation step.
- If you cannot rebuild and rerun the suite, stop: the fix must be verified by execution, not by inspection.

## Procedure
### Step 1: Capture the crash precisely
- actions: run the failing binary directly and print `$LASTEXITCODE`; confirm no `PASS`/`N/N tests passed` line is produced.
- inputs: `build\tests\<suite>.exe`.
- outputs: `exit: -1073741571` and empty stdout — the process dies before the runner reports anything.
- cautions: distinguish this from `-1073741515` (missing DLL, seen when an ASAN build ran without its runtime in PATH) — that is a tooling problem, not this bug.
- preserve: the crashing binary and its build flags for later comparison.
- next: proceed to isolation.

### Step 2: Isolate the crash to one file
- actions: write a minimal test that uses only the framework (`TEST("minimal") { EXPECT(1 == 1); }` plus `main` calling `run_all()`), compile it with the same source list, run it.
- inputs: framework header; build command.
- outputs: minimal test prints `1/1 tests passed` and exits 0 → the framework and link are fine, so the crash comes from the specific test file's own fixtures.
- cautions: a passing minimal test does not clear shared project code entirely — it clears the framework path exercised by the test bodies; keep the conclusion narrow.
- next: go to Step 3 for the crashing file.

### Step 3: Find large structs held by value
- actions: grep the crashing file for fixture declarations and helper calls (`AtomTable t`, `AtomTable t = make_table()`, `TermArena a = make_arena()`); read the helpers to see whether they return by value.
- inputs: test file(s).
- outputs: a list of by-value occurrences (trace: 13 `AtomTable t = make_table();` hits plus one local `AtomTable t;`).
- cautions: a helper returning a *reference* still copies if the call site binds by value.
- preserve: test logic and assertions.
- next: go to Step 4.

### Step 4: Move fixtures to static storage
- actions: convert helper functions to return `static` references that re-initialise on each call (`static AtomTable &fresh_table()`); convert fixture structs so their large members are `static` members bound by references in the constructor, with out-of-class definitions; call the `*_init` functions in the constructor so every test starts clean.
- inputs: crashing test file(s).
- outputs: large buffers no longer live in a test function's frame.
- cautions: static fixtures are shared by all tests in the file — re-initialise them per test; do not reduce capacity constants to fit the stack.
- preserve: the public fixture API used by the tests (rename via macro or reference binding rather than rewriting every test body).
- next: rebuild and run all suites.

### Step 5: Rebuild every suite and compare against the baseline
- actions: run the full build-and-run loop; compare with the Step 1 symptom list.
- outputs: previously crashing suites print pass counts (trace: `test_parser` `12/12 tests passed`, `test_terms` `15/15 tests passed`, plus running `test_solver`/`test_unifier` with real assertion results).
- cautions: new assertion failures may surface once a suite actually runs — treat them as separate bugs, not as the crash.
- next: if a suite still exits `-1073741571`, return to Step 3 and re-grep for by-value copies (see Common Failures).

### Step 6: Replace remaining by-value copies at call sites
- actions: change `AtomTable t = make_table();` to `AtomTable &t = make_table();` (and likewise for `TermArena`/`VarRegistry`) everywhere the grep still matches.
- inputs: grep results from Step 3.
- outputs: no by-value bindings of large fixtures remain.
- cautions: 轨迹未提供 a final verification of this step — the run captured after the edits did not show a clear pass/fail for the affected suite; rebuild and rerun it before claiming success.
- next: run Step 5's loop again.

## Decision Rules
### When a suite exits with `-1073741571` and prints nothing
Treat it as a stack overflow in that file and inspect fixture storage; do not start by suspecting the test framework or the engine logic.

### When the minimal framework-only test passes but the full file crashes
The framework and link are fine — the crash lies in the crashing file's fixture declarations/helpers, so keep the investigation inside that file.

### When a fixture helper returns a large struct by value
Bind the result by reference at the call site (`T &t = make_table();`); the by-value binding copies the whole struct into the frame. In the trace the helper was first converted to return a `static` reference while call sites still copied, and the crash persisted until the call sites were changed — but the final verification of that call-site change was not captured in the trace, so re-run it yourself.

### When a suite starts running after the conversion but reports assertion failures
Report those separately as test/engine bugs; the crash fix only claims restored execution.

## Invariants
- Do not modify production/engine sources or reduce capacity constants to make the fixtures fit the stack.
- Do not change test assertions while fixing storage — assertion edits are a separate concern and need their own evidence.
- Re-initialise shared static fixtures for every test so results stay order-independent.
- Do not report the by-value call-site fix as verified without a fresh run of the affected suite.
- Do not treat an ASAN/missing-DLL exit code (`-1073741515`) as this bug.

## Common Failures
### Failure: helpers converted to static references but the crash persists
- symptoms: suites still exit `-1073741571` after helpers return `static` references.
- causes: call sites still bind by value, e.g. `AtomTable t = make_table();`, copying the whole struct back onto the stack (the trace's grep showed 13 such hits; the earlier crash run still reproduced after only the helper was changed).
- recovery: bind by reference everywhere (`AtomTable &t = make_table();`). The edit was applied in the trace, but 轨迹未提供 a clear post-edit pass for the affected suite — rebuild and rerun before claiming success.

### Failure: assertion failures surface once the suite finally runs
- symptoms: the crash disappears, but tests fail that never had a chance to run before, e.g. `FAIL ... ctx.deref(x) == ctx.atom("alice")`.
- causes: the assertion compares a captured handle against a *freshly created* one — in an arena-based API each creation mints a new handle, so identity comparison fails even when contents match.
- recovery: create and capture the handle before the mutation/undo being asserted (`TermRef alice = ctx.atom("alice");` before binding), then compare against the captured handle. Verified: the unifier suite went from `16/18` with those two failures to `18/18 tests passed`.

### Failure: newly visible failures blamed on shared static state
- symptoms: long rounds of theorising about "cross-test contamination" while an isolated repro of the same scenario passes.
- causes: in this trace the isolated repro silently differed from the real test input, so the true error was elsewhere; no contamination existed.
- recovery: add a temporary diagnostic inside the harness that prints the real underlying error and read it before theorising (this exposed the parse error described in the clause-separator skill).

## Verification
- No suite run output contains `-1073741571`; every suite prints a `<passed>/<total> tests passed` line and exits 0.
- The minimal framework-only test still prints `1/1 tests passed` (already observed in the trace).
- Grep every test file for by-value bindings of large fixtures (`T x = make_...();` where `T` is `AtomTable`/`TermArena`/`VarRegistry`) — zero hits should remain.
- Each fixture constructor still calls the `*_init` functions, so shared static state is reset per test.
- Suites that previously passed (lexer `22/22`, variables `17/17`, terms `15/15`, parser `12/12`) keep passing — a regression here means the static conversion changed behaviour.
- The Step 6 call-site fix is only claimed after a fresh run of the suite that previously crashed (not captured in this trace).

## Examples
### Example 1: five suites crash at startup, four are fixed by static fixtures
- input: build-and-run loop where `test_atoms`, `test_terms`, `test_parser`, `test_unifier`, `test_solver` all report `(exit -1073741571)` with no output.
- procedure: Step 1 record the exit code; Step 3 grep fixtures; Step 4 convert `ParseCtx`/`UnifyCtx`/`SolverCtx` members to `static` members bound by references (with out-of-class definitions) and helpers to `static` references; Step 5 rerun the loop.
- expected result: `test_parser` prints `12/12 tests passed`, `test_terms` `15/15`, `test_solver` and `test_unifier` produce real PASS/FAIL output instead of dying; remaining assertion failures are reported separately.
- parameterized values: suite paths `build\tests\<name>.exe`, compiler `clang++ -std=c++23 -Iinclude -Itests -g -O0`, fixture types `AtomTable`/`TermArena`/`VarRegistry`.

### Example 2: isolating which file crashes
- input: several suites crash identically; suspicion falls on the shared framework.
- procedure: write `TEST("minimal") { EXPECT(1 == 1); }` with `int main() { return epilog_test::run_all(); }`, compile with the same source list, run.
- expected result: `1/1 tests passed`, exit 0 — the framework is cleared and the investigation moves into the crashing file's fixtures; later greps there found 13 by-value `AtomTable` copies.
- parameterized values: minimal test name, build output path `build/minimal_test.exe`.

## Evidence
**Problem**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 987, source_part_index: 0, quote: `(exit -1073741571)`, supports: five suites (`test_atoms`, `test_terms`, `test_parser`, `test_unifier`, `test_solver`) died with the same stack-overflow exit code and produced no test output at all.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1053, source_part_index: 0, quote: `exit: -1073741571`, supports: `test_atoms` still crashed after only the helper was converted, showing that additional by-value copies remained.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1199, source_part_index: 0, quote: `1/1 tests passed`, supports: a minimal framework-only test ran and passed, isolating the crash to the individual test file rather than the framework or link.

**Action**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1014, source_part_index: 0, quote: `/* Large members (AtomTable ~1MB, TermArena ~4MB) live in static storage. */`, supports: fixture structs were converted so the large members live in static storage and are bound by references in the constructor.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1002, source_part_index: 0, quote: `static AtomTable &fresh_table()`, supports: helper functions were changed to return a re-initialised `static` reference instead of a by-value struct.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1204, source_part_index: 0, quote: `AtomTable &t = make_table();`, supports: remaining by-value call-site copies were converted to reference bindings — action executed, but 轨迹未提供 a clear post-edit pass for that suite.

**Verification**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1048, source_part_index: 0, quote: `12/12 tests passed`, supports: `test_parser`, which crashed with `-1073741571` before the conversion, ran and passed after fixtures moved to static storage (the same run shows `test_terms` `15/15` and live PASS/FAIL output from `test_solver`/`test_unifier`).
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1191, source_part_index: 0, quote: `18/18 tests passed`, supports: the unifier suite, previously crashing, runs fully after the storage conversion (with the handle-capture assertion fix) and reports every case passing.

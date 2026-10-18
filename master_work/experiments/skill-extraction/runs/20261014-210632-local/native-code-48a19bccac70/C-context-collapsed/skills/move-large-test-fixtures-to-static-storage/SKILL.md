---
name: move-large-test-fixtures-to-static-storage
description: Use when a compiled test executable exits with -1073741571 (0xC000000D) and prints no test output at all. Helps the agent move MB-scale fixture structs off the thread stack into static storage so the suites actually run. Requires Windows test binaries, a compiler, and edit access to the test sources. Do not use when the binary never links, when it prints failing assertions, or when the process cannot be launched because the file is locked.
---
# Stop Windows Test Binaries Crashing at Startup with Exit -1073741571

## Goal
Make Windows test executables survive start-up by keeping multi-megabyte fixture objects out of the thread stack, so each suite reaches its first test and prints results instead of dying with exit code -1073741571.

## Scope
### In scope
- Windows test binaries that exit with `-1073741571` / `0xC000000D` before printing any test line, while the same suite compiles and links normally.
- Test fixtures of MB scale used in the observed project: `AtomTable` (fixed 4096 slots × ~264 bytes ≈ 1 MB), term arenas and a clause database of several MB, token lists, variable registries.
- Moving such objects from function-local/automatic storage to static storage (static struct members referenced by references, or helper functions returning a `static T&` that is re-initialised per test).

### Out of scope
- Link-stage problems (LNK2019/LNK1120/LNK1105); the binary must already exist.
- Suites that run and report `FAIL` lines — those are assertion failures, not start-up crashes.
- Growing the process stack or raising the OS stack limit as a workaround (not exercised or verified in this trace).

## Inputs
- **Crash evidence for the binary** — type: string; source: tool result of launching `build\tests\<name>.exe`; required: yes; constraints: exit code `-1073741571` with no test output, or a suite line printed as blank; default: none.
- **Test source declaring the fixture** — type: file path; source: project tree (observed: `tests\test_atoms.cpp`, `tests\test_terms.cpp`, `tests\test_parser.cpp`, `tests\test_unifier.cpp`, `tests\test_solver.cpp`); required: yes; constraints: contains struct definitions or locals holding the large tables; default: none.
- **Fixture type declarations** — type: headers; source: project tree (observed: `<project-dir>\include\atoms.hpp`, `terms.hpp`, `database.hpp`); required: yes; needed to read the fixed capacities that determine object size; default: none.
- **Test build/run command** — type: command; source: test harness; required: yes; constraints: must rebuild the affected binary and run it after each edit; default: none.
- **Call-site binding style** — type: code pattern; source: test sources; required: recommended; constraints: when a helper returns `static T&`, call sites that declare `T t = helper();` create another full-size copy — this pattern was diagnosed and edited in the trace, but no confirming run appears after that edit; default: none.

## Outputs
### Artifacts
- Edited test sources with fixture storage moved to static storage (static struct members bound by reference, or factory helpers returning `static T&` that call `*_init` on each use).
- Rebuilt test executables under `<project-dir>\build\tests\`.

### Success criteria
- Every previously crashing binary starts and prints its registered tests instead of a bare exit code.
- The suite run ends with a counted result line (`N/N tests passed`) for that suite.

### Failure criteria
- The binary still exits `-1073741571`, or prints nothing at all.
- A suite runs but shares state with the previous test (stale data leaking through the now-shared static storage) — that is a regression to report, not to hide.

## Preconditions
- The binary already links successfully; if it does not, fix the link stage first (separate failure class).
- You can launch the binary and observe its exit code and stdout/stderr.
- The crash signature matches: exit `-1073741571` with no test output, or a suite line printed with no content.
- You can identify the fixture types and their sizes from the header capacities, or measure them; do not guess which object is large.
- Edit permission on the test sources and the ability to rebuild and rerun each affected suite after every change.
- If the binary prints `PASS`/`FAIL` lines, stop: the crash phase is already past and this skill does not apply.

## Procedure
### Step 1: Confirm the crash signature
- Actions: launch each suspect binary directly and record the exit code and any output.
- Inputs: `build\tests\<name>.exe`.
- Outputs: table of binary → exit code; expect `(exit -1073741571)` and zero printed tests for the crashing ones.
- Cautions: an empty suite line can also mean the binary never started because the file is locked (LNK1105) — check the build log for that first; it is a different failure.
- Preserve: raw exit codes for before/after comparison.
- Next: continue when the exit code is `-1073741571` with no test output.

### Step 2: Identify which fixtures are MB-scale
- Actions: read the fixture headers for fixed capacities (`ATOM_TABLE_CAPACITY 4096`, `ATOM_MAX_LEN 255`, arena and database capacities) and compute the object sizes; list every place a test declares one of these as an automatic variable or as a struct member by value.
- Inputs: fixture headers, test sources.
- Outputs: list of large types and their declaration sites in tests.
- Cautions: several medium objects on one stack frame add up; a struct embedding two arenas is the sum of its members.
- Preserve: all test logic and assertions.
- Next: continue when at least one declaration site exceeds the Windows default thread stack (1 MB) on its own.

### Step 3: Move the fixtures into static storage
- Actions: convert large fixture members to `static` struct members held by reference (observed pattern: `static AtomTable s_atoms;` … constructor initialises references and calls `atom_table_init(&atoms)`), and replace by-value factory helpers with ones returning `static T&` that re-initialise on each call; add a short comment recording the size reason.
- Inputs: test sources.
- Outputs: tests where large objects live in static (BSS) storage, re-initialised per test.
- Cautions: sharing static storage means one test's state persists into the next unless re-initialisation happens; every constructor/helper must still call the corresponding `*_init`.
- Preserve: per-test initialisation calls, test ordering, and expectations.
- Next: go to Step 4.

### Step 4: Rebuild and run each affected suite
- Actions: rebuild the crashing binaries; run them; compare exit codes and output with Step 1.
- Inputs: test build/run command.
- Outputs: suites printing `N/N tests passed`.
- Cautions: one binary may remain crashing while others recover — keep the per-binary table rather than trusting an aggregate summary.
- Preserve: the earlier crash evidence.
- Next: go to Step 5 when a binary still exits `-1073741571`.

### Step 5: Check every call site for by-value copies of the fixture
- Actions: grep the still-crashing test for declarations of the large type; a call site written as `AtomTable t = fresh_table();` copies the whole object back onto the stack even though the helper returns a reference — change it to bind by reference (`AtomTable &t = fresh_table();`).
- Inputs: grep output of the test file, helper signature.
- Outputs: all call sites bound by reference.
- Cautions: this correction was applied in the trace but the recording ends before a confirming run; verify it yourself with Step 4 before reporting success.
- Preserve: helper signatures and re-initialisation behaviour.
- Next: rerun the suite; stop only when the binary prints its tests and a counted result line.

## Decision Rules
### When a test binary exits -1073741571 with no output
Treat it as a stack-overflow-class start-up crash: inventory MB-scale fixtures and move them to static storage (Steps 1–4). This branch is verified for the parser, terms, unifier and solver suites in this trace.

### When the build log shows LNK1105 for that binary instead
The file is locked by a running process, not crashing — kill the lingering process and relink; do not touch fixture storage.

### When a helper already returns `static T&` but the binary still crashes
Grep for by-value call sites (`T t = helper();`) and bind by reference; if the crash persists after that, stop and report — the trace contains no further confirmed recovery.

### When the suite runs but later tests see earlier tests' data
The shared static storage lacks re-initialisation: make each constructor/helper call the matching `*_init` before use; this risk is structural to the fix and must be reported if observed.

### When a binary prints PASS/FAIL lines
Crash handling is complete; remaining failures are assertion-level and out of scope here.

## Invariants
- Do not modify test expectations, assertion counts, or test ordering to make a suite look green.
- Keep re-initialisation of every moved fixture at the start of each test context — moving storage must not silently carry state between tests.
- Do not change product code (engine, parser, atom/term implementations) when the defect is in test fixture placement.
- Do not raise stack limits or linker/OS settings as a substitute for fixing storage placement.
- Do not report a binary as fixed without a run showing its tests and a counted result line.
- Do not treat an aggregate suite summary as proof for a binary that printed no output — check per binary.

## Common Failures
### Failure: all suites exit -1073741571 before printing anything
- Symptoms: five binaries each report `(exit -1073741571)` and no test lines, while the build is clean.
- Causes: MB-scale fixtures (`AtomTable`, arenas, clause `Database`) declared as automatic variables or as by-value struct members inside test functions, overflowing the default Windows thread stack.
- Recovery: move those objects to static storage with per-test re-initialisation (Steps 2–4); after the change the parser and terms suites printed `12/12 tests passed` and `15/15 tests passed`, and solver/unifier started producing results.

### Failure: one binary keeps crashing after the storage move
- Symptoms: helper returns `static T&`, yet the binary still exits `-1073741571` (observed: `test_atoms` after its factory was converted).
- Causes: diagnosed in the trace as call sites written `AtomTable t = make_table();`, which copy the ~1 MB object back onto the stack; the correcting edit was applied, but the trace ends without a confirming run, so the cause remains unconfirmed here.
- Recovery: bind by reference at every call site, rebuild, rerun; if the crash persists, report it as unresolved rather than assuming the fix worked.

### Failure: suite output is blank because the binary never started
- Symptoms: an empty suite line in the harness output.
- Causes: either the start-up crash above or a file lock (LNK1105) from a lingering process.
- Recovery: distinguish by launching the binary directly — a lock failure shows `LNK1105 ... cannot close file ... error code 1224` at build time instead of a crash at run time.

## Verification
Observable checks to run after the storage change (none are claims about the current session):

1. Direct launch of each previously crashing binary returns exit code `0` (or at least no `-1073741571`) and prints its first `PASS` line.
2. Each suite prints a counted result such as `12/12 tests passed`, `15/15 tests passed`, `16/18 tests passed`, `18/18 tests passed`, `22/22 tests passed`.
3. The harness loop reports no blank suite line for any test (a blank line means the binary produced no output).
4. Grep the test sources for remaining by-value declarations of the large types (`AtomTable ` / `TermArena ` / `Database ` locals); none may remain in a crashing suite.
5. State isolation: run the suite twice in the same build and confirm identical results, and confirm each test still starts from re-initialised fixtures (no test depends on a previous test's data).
6. Before/after table: every binary listed in Step 1 has a post-change run recorded next to its pre-change exit code.

## Examples
### Example 1: five suites die at start-up while the build is clean
- Input: build succeeds for all `tests\test_*.cpp`; launching the binaries gives `=== test_atoms ===` `(exit -1073741571)`, `=== test_terms ===` `(exit -1073741571)`, `=== test_parser ===` `(exit -1073741571)`, `=== test_unifier ===` `(exit -1073741571)`, `=== test_solver ===` `(exit -1073741571)`; headers show `ATOM_TABLE_CAPACITY 4096` with `ATOM_MAX_LEN 255` (≈1 MB per `AtomTable`) and multi-MB arenas/database embedded in the test context structs.
- Procedure: Step 1 record the crash table; Step 2 list every fixture declaration site; Step 3 convert large members to static members bound by reference (`/* Large members (AtomTable ~1MB, TermArena ~4MB) live in static storage. */`) and replace by-value factories with `static T&` helpers that re-init on each call; Step 4 rebuild and rerun.
- Expected result: the crashing suites start printing tests — observed after the change: `12/12 tests passed` (parser), `15/15 tests passed` (terms), and solver/unifier producing full PASS/FAIL listings instead of an empty exit; a later full loop reports `=== 6 PASSED, 1 FAILED ===`.
- Parameterized values: `<suite>` = affected test binary; `<fixture-type>` = MB-scale table/arena/database; `<size>` = capacity × record size; `<exit-code>` = `-1073741571`; `<project-dir>` = project root.

### Example 2: one suite still crashes after the storage move
- Input: `test_atoms` uses `fresh_table()` returning `static AtomTable&`, but grep shows `35:    AtomTable t = make_table();` in thirteen test bodies; the binary still produces a blank suite line.
- Procedure: Step 5 — bind by reference at each call site (`AtomTable &t = make_table();`), rebuild, rerun the single binary and record its exit code.
- Expected result: the binary prints its tests and a counted result line. Verification status: in the trace the correcting edit was applied but the recording ends before a rerun, so treat the expected result as the check you must perform yourself.
- Parameterized values: `<fixture-type>` = the large table; `<helper>` = factory returning `static T&`.

## Evidence
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 987, source_part_index: 0, quote: `(exit -1073741571)`, supports: five test binaries (test_atoms, test_terms, test_parser, test_unifier, test_solver) exit with `-1073741571` immediately after launch, printing no test output, while the build itself succeeded.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1005, source_part_index: 0, quote: `/* Large structs live in static storage — too big for Windows default stack. */`, supports: by-value factory helpers for `TermArena`/`VarRegistry`/`AtomTable` were replaced by helpers returning references to function-local `static` objects that are re-initialised per call.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1014, source_part_index: 0, quote: `/* Large members (AtomTable ~1MB, TermArena ~4MB) live in static storage. */`, supports: the test context struct's large members were converted to `static` members bound by reference in the constructor, with the size rationale recorded in the code (edits at 1024 and 1036 do the same for the unifier and solver contexts).
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1048, source_part_index: 0, quote: `15/15 tests passed`, supports: after the storage change the previously crashing terms suite runs and passes; the same output contains `12/12 tests passed` for the previously crashing parser suite, and full PASS/FAIL listings for the unifier and solver suites.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1191, source_part_index: 0, quote: `22/22 tests passed`, supports: in a later rebuild the solver suite (formerly exiting `-1073741571`) runs to completion with all tests passing, so static-storage fixtures remain stable across rebuilds.
- residual-problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1053, source_part_index: 0, quote: `exit: -1073741571`, supports: `test_atoms` still crashed after its factory was converted to return a `static` reference, so the storage move alone did not fix that binary.
- diagnosis (assistant judgment, unverified) — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1202, source_part_index: 0, quote: `35:    AtomTable t = make_table();`, supports: grep output shows test call sites declaring the fixture by value even though the helper returns a `static` reference — i.e. the object is copied onto the stack at each call site; the accompanying assistant diagnosis (source_index 1203) states it `**copies** the ~1MB AtomTable onto the local stack`, and the correcting edit follows at source_index 1204, but the trace ends before a run that would confirm it.

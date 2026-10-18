---
name: fix-lnk1120-unresolved-global-in-test-links
description: Use when clang++/clang-cl test links fail with LNK2019 naming a project global and LNK1120 '1 unresolved externals'. Helps the agent relocate the definition into the header so every test binary links without touching the test link line. Requires a C++17+ compiler and permission to edit both the header and the defining translation unit. Do not use when the unresolved symbol is a function, a missing object file, or a missing library.
triggers:
  - "LNK2019"
  - "LNK1120"
  - "unresolved external symbol"
  - "unresolved externals"
---
# Fix LNK1120/LNK2019 Unresolved Globals When Linking Test Binaries

## Goal
Resolve LNK1120/LNK2019 link failures for test binaries that reference a header-declared global whose only definition sits in a translation unit excluded from the test link, producing a build in which every test suite links, starts, and reports its results.

## Scope
### In scope
- MSVC/clang-cl link diagnostics `LNK2019: unresolved external symbol "<symbol>"` plus `fatal error LNK1120: N unresolved externals` for a project global *variable* declared `extern` in a header.
- Moving the definition into the header as an `inline` variable (C++17+) and deleting the old definition from the excluded TU.
- Rebuilding and re-running the per-file test binaries afterwards, including recovering from LNK1105 file-lock errors during relink.

### Out of scope
- Unresolved symbols that are functions, third-party libraries, or absent object files — this trace provides no fix for those.
- Test binaries that link but crash or fail assertions (a separate problem; report separately).
- Changing compiler flags, adding source files to the test link line, or renaming the symbol.

## Inputs
1. **Link error output** — type: text tool result; source: the test build command's stderr; required: yes; constraint: must contain `LNK2019`/`LNK1120` and name the symbol (here `int g_verbose`); default: 无.
2. **Test build command** — type: shell/PowerShell script in tool-call arguments; source: agent-authored build loop; required: yes; constraint: reveals the exact source list linked into each test binary (in the trace: `internals/*.cpp parser/*.cpp engine/*.cpp repl.cpp`, no `main.cpp`); default: 无.
3. **Header declaring the symbol** — type: source file (e.g. `<project>/include/log.hpp`); required: yes; constraint: contains `extern <type> <name>;`; default: 无.
4. **Defining translation unit** — type: source file (e.g. `<project>/main.cpp`); required: yes; constraint: holds the only definition and is not part of the test link list; default: 无.
5. **Toolchain** — type: compiler; source: environment; required: yes; constraint: must support `inline` variables, i.e. C++17 or newer (trace used `clang++ -std=c++23` on Windows); default: `clang++ -std=c++23`.
6. **Running test processes** — type: OS state; required: no; constraint: lingering test executables hold their output files and block relink; default: 无.

## Outputs
### Artifacts
- Edited header containing `inline <type> <name> = <init>;` (trace: `<project>/include/log.hpp`).
- Edited defining TU with the old definition removed (trace: `<project>/main.cpp`).
- Test run report printed by the build loop — one `N/N tests passed` line per suite plus a suite summary.

### Success criteria
- Build output contains no `LNK2019` and no `LNK1120` for any test binary.
- Every `tests/test_*.cpp` binary links, starts, and prints its pass count.

### Failure criteria
- The same symbol is still unresolved after the edit.
- A new link error reports a duplicated/redefined symbol.
- A suite links but crashes or fails assertions — report separately; this fix does not claim to solve it.

## Preconditions
- The test build command is available and reproduces the error on demand (trace: a PowerShell loop compiling each `tests/test_*.cpp` against the shared source list).
- The unresolved symbol is a *variable* declared `extern` in a project header; if it is a function or a library symbol, stop — this skill does not cover it.
- The defining TU has been located and is confirmed absent from the test link source list (read the link command, do not assume).
- The compiler supports `inline` variables (`clang++ -std=c++23` in the trace); if only C++14 or older is available, stop and report.
- Permission to edit both the header and the defining TU; if only one may be touched, stop and report which precondition failed.

## Procedure
### Step 1: Confirm the failure is at link time
- actions: run the test build loop unchanged and capture full stderr; separate compiler-stage errors from linker-stage errors.
- inputs: test build command; error output.
- outputs: text containing `LNK2019: unresolved external symbol "<symbol>"` and `fatal error LNK1120: 1 unresolved externals`.
- cautions: if the compiler stage itself failed, fix that first — this procedure only applies once objects compile and the failure moves to `linker command failed`.
- preserve: test source list, flags, and test files.
- next: when the named symbol is a project global, go to Step 2; otherwise stop and report the symbol.

### Step 2: Locate the declaration, the definition, and the link source list
- actions: grep headers for `extern <type> <name>;` (trace found `extern int g_verbose;` in `include/log.hpp`); grep `*.cpp` for the definition (trace: `int g_verbose = 0;` in `main.cpp`); read the test link command's source list.
- inputs: project tree; test build command.
- outputs: confirmation that the defining TU is not linked into tests (trace list: `internals/atoms.cpp ... engine/solver.cpp repl.cpp` — no `main.cpp`), which explains why the symbol is never defined for the test binaries.
- cautions: IDE "cannot find symbol" markers are not evidence — use grep/Read on the real files.
- next: go to Step 3.

### Step 3: Move the definition into the header as an inline variable
- actions: edit the header declaration `extern int g_verbose;` → `inline int g_verbose = 0;`; edit the defining TU and delete `int g_verbose = 0;`.
- inputs: header path; defining TU path; original initializer.
- outputs: exactly one definition of the symbol, visible to every TU that includes the header.
- cautions: keep the original initializer value; do not leave a second, non-inline definition behind; do not touch other declarations such as the `vlog` function that reads the variable.
- preserve: all call sites and includes.
- next: rebuild every test binary.

### Step 4: Rebuild all test binaries and run them
- actions: rerun the identical build+run loop; record each suite's pass count and the loop summary.
- inputs: unchanged build command.
- outputs: no `LNK2019`/`LNK1120` lines; suites print `N/N tests passed`.
- cautions: an `LNK1105 ... error code 1224` here means a previously run test exe is still holding its output file — apply the recovery in Common Failures before concluding anything about the fix; a suite that links but fails assertions is a separate issue.
- next: stop when all suites link and start; report residual assertion failures separately.

## Decision Rules
### When the unresolved external is a variable declared `extern` in a header and defined only in a TU that the test link excludes
Replace the header declaration with `inline <type> <name> = <init>;` (C++17+) and delete the old definition from the excluded TU, then relink all test binaries with the *unchanged* source list.

### When the symbol still has a definition in a `.cpp` after the header edit
Remove that definition so only the inline definition remains (performed in this trace for `main.cpp` immediately after the header edit).

### When relinking fails with LNK1105 'cannot close file' instead of LNK1120
Stop lingering test processes and relink before judging the fix — see Common Failures.

## Invariants
- Do not add the excluded TU (e.g. `main.cpp`) to the test link line; each test file provides its own `main()`.
- Do not change test sources, compiler flags, or the shared source list to work around the error.
- Do not rename the symbol or alter its initializer semantics; existing readers (e.g. `vlog`) must keep working unchanged.
- Do not report success without a fresh link of *every* test binary; a passing compile of one suite is not enough.
- Do not present the LNK1105 recovery or the main-binary relink as verified unless it was actually run.

## Common Failures
### Failure: LNK1105 cannot close file when relinking a test binary
- symptoms: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224` for some suites while others build fine; the same suites fail again on the next run.
- causes: a previously launched test executable is still running and holds the output file (consistent with the trace; the recovery resolving it is the evidence).
- recovery: stop lingering test processes (`Stop-Process -Name <suite> ...`, `taskkill /F /IM <suite>.exe`), sleep briefly, and relink. Verified in the trace: after killing processes the previously locked suites linked and passed (`=== 6 PASSED, 1 FAILED ===`, with the remaining failure being the still-locked `test_atoms`).

### Failure: a second, non-inline definition left behind
- symptoms: after the header edit the link reports a redefinition/multiple-definition error for the same symbol, or LNK2019 persists because a stale declaration is still in use.
- causes: the old `int <name> = <init>;` in the defining TU was not removed, or another header still declares it `extern` without seeing the inline definition.
- recovery: grep the project for the symbol name and keep exactly one definition. 轨迹未提供 an observed instance of this failure; the deletion was performed preventively.

## Verification
- Test build output contains no line matching `LNK2019` and no line matching `LNK1120`.
- Every suite prints a `<passed>/<total> tests passed` line (e.g. `22/22 tests passed`) and the loop summary reports zero compile/link errors.
- Grep the project for the symbol: exactly one definition, in the header, written as `inline ...`; no remaining `extern <type> <name>;` declaration of it.
- The defining TU no longer contains its old definition.
- Rebuild the *main* binary with the edited header and confirm it still links — 轨迹未提供 this check in the trace; run it before finishing.
- If a suite links but reports assertion failures or a non-zero exit code, report that as a separate, unresolved problem rather than claiming full success.

## Examples
### Example 1: `g_verbose` referenced by `vlog` but defined only in `main.cpp`
- input: test build output with `error LNK2019: unresolved external symbol "int g_verbose" ... fatal error LNK1120: 1 unresolved externals` for every test binary.
- procedure: Step 1 (confirm link-stage failure), Step 2 (grep header → `extern int g_verbose;` in `include/log.hpp`; grep sources → `int g_verbose = 0;` in `main.cpp`; test link list has no `main.cpp`), Step 3 (header → `inline int g_verbose = 0;`, delete the `main.cpp` definition), Step 4 (rebuild and run all suites).
- expected result: suites link and run — in the trace the first post-fix run already produced `22/22 tests passed` for the lexer suite and a summary of `=== 2 suite(s) PASSED, 5 FAILED ===` (the 5 failures were runtime assertion failures/crashes, not link errors); after later unrelated fixes the same pipeline reported `=== 6 PASSED, 1 FAILED ===`.
- parameterized values: symbol `g_verbose`, header `include/log.hpp`, defining TU `main.cpp`, compiler `clang++ -std=c++23`, test sources `tests/test_*.cpp`.

### Example 2: relink blocked by a still-running test process
- input: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224` while other suites compile.
- procedure: stop lingering test executables (`taskkill /F /IM test_parser.exe`), sleep briefly, rerun the same build loop.
- expected result: the previously locked suites link and print their pass counts; only genuinely failing suites remain.
- parameterized values: suite names, output directory `build/tests`, wait interval.

## Evidence
**Problem**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 975, source_part_index: 0, quote: `solver-c181c1.o : error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)" (?vlog@@YAXPEBD0ZZ)`, supports: every test binary failed at link time because the global `g_verbose` had no definition in the test link.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 975, source_part_index: 0, quote: `build\tests\test_atoms.exe : fatal error LNK1120: 1 unresolved externals`, supports: the reported error key LNK1120 arises from one unresolved external, so a single missing definition is the whole problem.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 983, source_part_index: 0, quote: `"engine/database.cpp","engine/unifier.cpp","engine/builtins.cpp","engine/solver.cpp",`, supports: the test link source list contains the engine sources and `repl.cpp` only — `main.cpp`, where the definition lived, is excluded.

**Action**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 977, source_part_index: 0, quote: `inline int g_verbose = 0;`, supports: the `extern int g_verbose;` declaration in `include/log.hpp` was converted into an inline definition visible to every TU.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 981, source_part_index: 0, quote: `int g_verbose = 0;`, supports: the now-duplicate definition was removed from `main.cpp` (the edit's `old_string`), leaving one inline definition.

**Verification**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 984, source_part_index: 0, quote: `=== 2 suite(s) PASSED, 5 FAILED ===`, supports: immediately after the inline fix the same build loop linked and ran suites with no `LNK1120`/`LNK2019` anywhere in the output; remaining failures were runtime assertion failures/crashes unrelated to linking.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 984, source_part_index: 0, quote: `22/22 tests passed`, supports: a test binary produced by that loop linked and executed to completion after the fix.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1191, source_part_index: 0, quote: `=== 6 PASSED, 1 FAILED ===`, supports: later rebuilds of the same pipeline still link all suites (only a file-locked binary failed), so the fix is stable across rebuilds.

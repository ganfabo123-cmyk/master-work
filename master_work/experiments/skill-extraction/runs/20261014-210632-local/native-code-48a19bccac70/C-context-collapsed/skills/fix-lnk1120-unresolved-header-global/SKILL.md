---
name: fix-lnk1120-unresolved-header-global
description: Use when MSVC-style linking reports LNK1120 "N unresolved externals" together with LNK2019 naming a global variable that test executables reference but the link line does not define. Helps the agent relocate the definition into the shared header as an inline variable and rebuild every test binary. Requires clang++/clang-cl or MSVC linker output and edit access to both the header and the app translation unit. Do not use when the symbol has no definition anywhere in the project, when the failing link is the main application binary, or when the error is LNK1105/LNK2005.
---
# Fix LNK1120/LNK2019 for a Header-Declared Global Missing from Test Links

## Goal
Eliminate the LNK1120/LNK2019 link failures that stop every test executable from building by making the shared header the single definition site of the offending global, so all test binaries link and run.

## Scope
### In scope
- C++ projects (observed: `-std=c++23`) where a global is declared with `extern` in a header included by library code and defined only in an application entry translation unit (for example `main.cpp`) that the test link command does not include.
- Test builds that compile each `test_*.cpp` together with a fixed list of shared source files but exclude the app entry TU, producing the same LNK2019/LNK1120 pair for every test.
- Windows MSVC-style linking driven by `clang++` (clang-cl style flags also available in the observed project).

### Out of scope
- A symbol that is not defined in any translation unit of the project (needs a new definition, not a relocation of one).
- Link failures of the main application binary itself, which links its own entry TU.
- LNK1105 (file locked by a running process), LNK2005 (duplicate definition), and runtime test failures after a successful link — separate mechanisms, separate skills.

## Inputs
- **Linker output text** — type: string; source: build/test-harness tool result; required: yes; constraints: must contain at least one `LNK2019` line naming the unresolved symbol and the summarising `LNK1120` line; default: none.
- **Header with the `extern` declaration** — type: file path; source: project source tree (observed: `<project-dir>\include\log.hpp`); required: yes; constraints: header must be included by the translation units that reference the symbol; default: none.
- **Translation unit holding the out-of-line definition** — type: file path; source: project source tree (observed: `<project-dir>\main.cpp`); required: yes; constraints: this TU must be absent from the test link line; default: none.
- **Test link command / list of linked sources** — type: command or build rule; source: test harness script or Makefile; required: yes; constraints: must show which sources are compiled into each `build\tests\test_*.exe`; default: none.
- **Language standard of the project** — type: compiler flag; source: build flags; required: yes; constraints: C++17 or later so an `inline` variable definition in a header is valid (observed: `-std=c++23`); default: none.

## Outputs
### Artifacts
- Edited header (observed: `<project-dir>\include\log.hpp`): the `extern` declaration replaced by a single `inline` definition with an initialiser.
- Edited app translation unit (observed: `<project-dir>\main.cpp`): the out-of-line definition removed.
- Rebuilt test executables under `<project-dir>\build\tests\`.

### Success criteria
- The test build emits no `LNK2019` and no `LNK1120` lines for any test binary.
- Every `test_*.exe` is produced and starts, printing its own test results.
- The main application binary still builds with exactly one definition of the global in the program.

### Failure criteria
- Any test link still reports `LNK2019`/`LNK1120`, or reports `LNK2005` duplicate definition.
- The main binary fails to build after the edit.
- Tests link but the suite summary never advances beyond link errors (stale build).

## Preconditions
- The project compiles as C++17 or later; if the project is C, the `inline` variable form is not available and this skill must not be applied unchanged.
- The full linker output for at least one failing test is available, including the `LNK2019` line with the mangled/unmangled symbol name.
- The test link line (the exact set of source/object files) is known, so you can confirm the defining TU is excluded.
- Edit permission on both the header and the app translation unit, and the ability to rebuild and rerun all test binaries.
- If any of these cannot be confirmed, stop and report the missing information instead of guessing which symbol to relocate.

## Procedure
### Step 1: Read the LNK2019 lines, not the LNK1120 line
- Actions: from the linker output take every `LNK2019` line; extract the symbol (`"int g_verbose"`, mangled `(?g_verbose@@3HA)`) and the referencing function (`"void __cdecl vlog(char const *,char const *,...)"`), plus the object file that references it (`solver-c181c1.o`).
- Inputs: linker output text.
- Outputs: a list of unresolved symbols and which object references each.
- Cautions: `LNK1120` only summarises the count (`1 unresolved externals`); it carries no symbol name. The same pair of errors repeats once per test binary — that repetition is a symptom of one shared cause, not seven separate bugs.
- Preserve: the raw error text for later comparison.
- Next: continue when the referencing object is a shared library TU; otherwise this skill does not apply.

### Step 2: Confirm the definition lives in a TU excluded from the test link
- Actions: search the header for the declaration (`extern int g_verbose;`); search the project for the definition (`int g_verbose = 0;`); compare with the test link source list.
- Inputs: header path, project sources, test link command.
- Outputs: confirmation that the only definition sits in the app entry TU (observed: `main.cpp`) while tests link only shared sources plus the test file.
- Cautions: the harness may label these as `COMPILE ERROR:` even though compilation succeeded — only the link stage failed.
- Preserve: untouched build flags.
- Next: go to Step 3 when exactly one definition exists and it is outside the test link; stop and report if zero or multiple definitions exist.

### Step 3: Move the definition into the header as an inline variable
- Actions: replace `extern int g_verbose;` with `inline int g_verbose = 0;` in the header; delete `int g_verbose = 0;` from the app translation unit so exactly one definition remains.
- Inputs: header file, app translation unit.
- Outputs: header now owns the single definition; app TU no longer defines it.
- Cautions: keep the variable assignable — the project's `LOG_INIT`/`log_init` write to it at start-up; only its storage definition changes.
- Preserve: all other header content and macros (`VLOG`, `log_init`).
- Next: go to Step 4.

### Step 4: Rebuild every test binary and rerun the suite
- Actions: rerun the test build loop that compiles each `tests\test_*.cpp` with the shared source list into `build\tests\*.exe`; then run the suites.
- Inputs: test build/run command.
- Outputs: build log without `LNK2019`/`LNK1120`, followed by per-suite results.
- Cautions: a clean-looking summary can hide a still-locked binary (LNK1105) or a crash-before-first-test — check for those separately; they are different failures.
- Preserve: existing test expectations; do not edit tests to make them pass.
- Next: stop when no link errors remain and every suite prints its own result line; otherwise return to Step 1 with the new error text.

## Decision Rules
### When the same LNK2019 symbol appears in every test binary
Treat it as one shared-cause defect: fix the definition once in the header/TU pair instead of patching each test target.

### When the referencing object is a shared library TU and the only definition sits in the app entry TU that tests do not link
Replace the header's `extern` declaration with an initialised `inline` variable definition (C++17 or later) and delete the out-of-line definition from the app TU. This is the branch verified in this trace.

### When the LNK2019 names a function rather than a variable
Stop: this skill's verified action covers a header-declared global variable; a missing function definition needs its own diagnosis (missing source in the link, missing implementation, or declaration/definition mismatch) and was not exercised here.

### When the build output shows LNK1105 or LNK2005 instead
Stop and switch to the corresponding separate failure mode; do not apply the inline-variable edit again.

### When after the edit the test build produces binaries but suites still fail
Link stage is fixed; remaining failures are runtime and must be handled outside this skill.

## Invariants
- Keep exactly one definition of the global in the whole program — moving it to the header requires deleting the old out-of-line definition.
- Do not add the app entry TU to the test link line just to satisfy the linker; the test/link separation is intentional.
- Do not change compiler flags, warnings, or language standard to make the error disappear.
- Do not edit test sources or test expectations as part of this fix.
- Do not claim success from a compile-only check: the reported failure is at link time, so every test binary must be relinked and observed.
- Do not report suite results as passing unless they come from the tool output of a run performed after the edit.

## Common Failures
### Failure: harness labels the link failure as "COMPILE ERROR"
- Symptoms: output starts with `COMPILE ERROR: test_atoms.cpp` followed immediately by `LNK2019`/`LNK1120` text; no compiler diagnostics present.
- Causes: the build loop prints one label for any non-zero exit of the compiler+linker invocation.
- Recovery: read past the label to the actual diagnostic; treat it as a link-stage defect and follow Steps 1–4.

### Failure: identical error repeated for seven test binaries
- Symptoms: seven `LNK2019 ... g_verbose` blocks, one per `test_*.exe`.
- Causes: every test links the same shared objects but none links the TU holding the definition; the count is an artifact of the loop.
- Recovery: apply the single header/TU fix once, then rebuild the whole loop.

### Failure: link errors disappear but suites report failures
- Symptoms: build log has no `LNK2019`/`LNK1120`, yet suites fail or produce no output.
- Causes: unrelated runtime defects (observed in the same session: fixtures too large for the Windows default stack, and binaries locked by lingering processes).
- Recovery: the link problem is resolved; hand the new symptom to the matching separate skill instead of revisiting the header edit.

## Verification
Observable checks to run after the edit (none are claims about the current session):

1. The full test build log contains no substring `LNK2019` and no substring `LNK1120`.
2. No test entry in the build log carries the harness label `COMPILE ERROR:` for a link reason.
3. Each expected binary exists, e.g. `<project-dir>\build\tests\test_atoms.exe`, `test_lexer.exe`, `test_parser.exe`, `test_solver.exe`, `test_terms.exe`, `test_unifier.exe`, `test_variables.exe`.
4. Running the suites produces per-suite result lines (pattern `NN/NN tests passed`) instead of empty output — immediately after the fix the loop reported `=== 2 suite(s) PASSED, 5 FAILED ===`, and after unrelated runtime fixes the same loop reported `=== 6 PASSED, 1 FAILED ===`; any of these summaries proves the executables linked and started.
5. A clean rebuild of the main binary still links, with no `LNK2005` for the relocated global.
6. Verbose behaviour still works: setting the global (or the CLI flag that writes it) still gates the logging path that references it.

## Examples
### Example 1: verbose flag global breaks every test link
- Input: build log for `<project-dir>` containing `solver-c181c1.o : error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)" (?vlog@@YAXPEBD0ZZ)` and `build\tests\test_atoms.exe : fatal error LNK1120: 1 unresolved externals`, repeated for all seven test binaries; header `<project-dir>\include\log.hpp` declares `extern int g_verbose;`; `<project-dir>\main.cpp` defines `int g_verbose = 0;`; test loop compiles `internals/*.cpp parser/*.cpp engine/*.cpp repl.cpp` plus one `tests\test_*.cpp` — `main.cpp` absent.
- Procedure: Step 1 extract the symbol from LNK2019; Step 2 confirm the definition is only in the excluded `main.cpp`; Step 3 edit the header to `inline int g_verbose = 0;` and delete `int g_verbose = 0;` from `main.cpp`; Step 4 rerun the build/run loop for all tests.
- Expected result: no `LNK2019`/`LNK1120` in the new log; all seven test executables produced; suites print results (observed first rerun: `=== 2 suite(s) PASSED, 5 FAILED ===`, with `22/22 tests passed` for the lexer suite; later `=== 6 PASSED, 1 FAILED ===`).
- Parameterized values: `<project-dir>` = project root; `<header>` = header owning the logging macros; `<global>` = the `extern` int; `<app-tu>` = entry file excluded from the test link; `<test-count>` = number of test binaries.

## Evidence
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 975, source_part_index: 0, quote: `solver-c181c1.o : error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)" (?vlog@@YAXPEBD0ZZ)`, supports: the unresolved symbol is the header-declared global `g_verbose`, referenced from a shared object compiled into every test link. The same event also contains `build\tests\test_atoms.exe : fatal error LNK1120: 1 unresolved externals` and `=== 0 suite(s) PASSED, 7 FAILED ===`.
- problem-context — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-03`, source_index: 795, source_part_index: 0, quote: `extern int g_verbose;`, supports: the shared header `log.hpp` declares the global with `extern` while its header-only `vlog` function references it, so every test link needs a definition of that global.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 977, source_part_index: 0, quote: `inline int g_verbose = 0;`, supports: the header declaration was replaced by an initialised inline variable definition (the edit's `old_string` is `extern int g_verbose;`).
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 981, source_part_index: 0, quote: `int g_verbose = 0;`, supports: the out-of-line definition was removed from `main.cpp` in the same pass (edit `old_string` is `int g_verbose = 0;\n\nint main`, `new_string` is `int main`), keeping exactly one definition after the header change.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 984, source_part_index: 0, quote: `=== 2 suite(s) PASSED, 5 FAILED ===`, supports: after the two edits the same build-and-run loop no longer emits `LNK2019`/`LNK1120`; all seven test binaries compiled, linked and executed (the same output contains `22/22 tests passed` and `17/17 tests passed`; the remaining failures are runtime, not link).
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1191, source_part_index: 0, quote: `=== 6 PASSED, 1 FAILED ===`, supports: with the inline definition still in place, six of seven suites link and run to completion in a later rebuild, so the link-stage fix is stable across rebuilds.

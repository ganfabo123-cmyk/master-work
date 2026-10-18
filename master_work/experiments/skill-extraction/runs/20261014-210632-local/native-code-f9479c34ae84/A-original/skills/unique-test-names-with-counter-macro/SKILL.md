---
name: unique-test-names-with-counter-macro
description: Use when a single-header C++ test framework's TEST(name) macro produces redefinition errors (_reg___LINE__ / _reg___COUNTER__) or undeclared identifiers (_test_body_N) during compilation of test files. Helps the agent build a TEST macro that yields one unique id per test by pasting through an indirection macro and capturing __COUNTER__ exactly once. Requires an editable test framework header, clang with __COUNTER__ support, and a build command that compiles every tests/test_*.cpp. Do not use when the failures are linker (LNK) errors or runtime crashes rather than macro expansion errors in the TEST macro.
---
# Generate Unique Test Identifiers in a Macro-Based TEST Framework

## Goal
Make a macro-based TEST(name) framework compile: every test case gets a unique, matching identifier pair (forward declaration, registrar, body) so all `tests/test_*.cpp` compile instead of failing with redefinition or undeclared-identifier errors.

## Scope
### In scope
- Diagnosing `redefinition of '_reg___LINE__'` / `redefinition of '_reg___COUNTER__'` produced by a `TEST` macro that pastes a unique suffix directly with `##`.
- Diagnosing `use of undeclared identifier '_test_body_N'` when `__COUNTER__` appears several times inside one macro and expands to different numbers.
- The two-part fix: a two-level concatenation macro (`EPILOG_CONCAT` / `EPILOG_CONCAT2`) plus an implementation macro that captures `__COUNTER__` exactly once (`TEST_IMPL(name, uid)` called as `TEST(name) TEST_IMPL(name, __COUNTER__)`).
- Verifying by compiling every test file and running the suites.

### Out of scope
- Link errors (LNK2019/LNK1105) and runtime crashes of the produced binaries.
- Test assertion logic, EXPECT/REQUIRE semantics, and the runner's `run_all()`.
- clangd/editor diagnostics that disagree with the real compiler (the trace saw cross-file analysis noise; only the build counts).

## Inputs
- **Compiler output for the test files**: string; source = tool result of the test build script; required; must show either `redefinition of '_reg_...'` / `redefinition of '_test_body_...'` or `use of undeclared identifier '_test_body_N'` with the expansion notes; default: none.
- **Test framework header**: file path (e.g. `tests/test_framework.hpp`); source = project; required; must contain the `TEST` macro definition to edit; default: none.
- **Preprocessor notes**: the `note: expanded from macro 'TEST'` / `note: expanded from here` lines in the error; source = compiler; required for distinguishing failure mode 1 (literal, unexpanded token) from failure mode 2 (mismatched counter values); default: none.
- **Full test build command**: shell script compiling each `tests/test_*.cpp` together with all engine sources; source = project; required for verification; default: none.
- **Counter macro support**: compiler provides `__COUNTER__`; source = toolchain (clang in the trace); required; default: none.

## Outputs
### Artifacts
- Edited `TEST` macro block in the framework header containing `EPILOG_CONCAT2`/`EPILOG_CONCAT`, `TEST_IMPL(name, uid)`, and `#define TEST(name) TEST_IMPL(name, __COUNTER__)`.
- A test build in which no file reports macro-expansion errors.

### Success criteria
- Compilation of every `tests/test_*.cpp` proceeds past preprocessing with zero `redefinition of '_reg_...'` and zero `use of undeclared identifier '_test_body_...'` errors.
- The suites link and run, printing registered test names and `N/N tests passed`.

### Failure criteria
- Any test file still emits `redefinition of '_reg___LINE__'` or `redefinition of '_reg___COUNTER__'`.
- Any test file emits `use of undeclared identifier '_test_body_N'`.
- Tests compile but zero tests are registered (registration silently broken) — the runner's totals must be non-zero.

## Preconditions
- The project has a single-header test framework with a `TEST(name)` macro that declares a per-test function and registers it; if registration uses a different mechanism, this skill's macro shape may not apply.
- A real compiler run is available (e.g. `clang++ -std=c++23 ... tests/test_atoms.cpp`); editor-only diagnostics are not sufficient evidence — the trace repeatedly saw clangd disagreeing with the compiler.
- You can edit the framework header and re-run the full test build.
- The compiler supports `__COUNTER__` (clang does in the trace); if it does not, stop and report — no verified alternative exists in the trace.

## Procedure
### Step 1: Classify the macro error from the expansion notes
Actions: read the first error of a test file and look at the token that was actually produced. Inputs: compiler output. Outputs: one of — (a) literal `_reg___LINE__` / `_reg___COUNTER__` (token pasted without expansion), or (b) `_test_body_2`/`_test_body_6` undeclared while `_test_body_0` exists (each `__COUNTER__` use produced a different number). Cautions: do not rely on IDE diagnostics; the trace saw clangd report cross-file false positives. Preserve: test sources. Next: Step 2 for case (a), Step 3 once (a) is fixed.

### Step 2: Add an indirection level for token pasting
Actions: define `#define EPILOG_CONCAT2(a, b) a##b` and `#define EPILOG_CONCAT(a, b)  EPILOG_CONCAT2(a, b)`, then rewrite `TEST` so every name is built through `EPILOG_CONCAT(_test_body_, ...)` and `EPILOG_CONCAT(_reg_, ...)` instead of `_test_body_##...`. Inputs: framework header. Outputs: expanded names are numeric rather than literal. Cautions: this alone does not fix case (b). Preserve: the rest of the header (EXPECT, REQUIRE, runner). Next: Step 3.

### Step 3: Capture __COUNTER__ exactly once per TEST expansion
Actions: introduce an implementation macro that takes the id as a parameter and uses only that parameter for the forward declaration, the registrar, and the body —
`#define TEST_IMPL(name, uid) static void EPILOG_CONCAT(_test_body_, uid)(); static ::epilog_test::Registrar EPILOG_CONCAT(_reg_, uid)(name, EPILOG_CONCAT(_test_body_, uid)); static void EPILOG_CONCAT(_test_body_, uid)()` and `#define TEST(name) TEST_IMPL(name, __COUNTER__)`. Inputs: framework header. Outputs: one counter value shared by declaration, registration, and body. Cautions: writing `__COUNTER__` three times in one macro increments it three times and yields three different ids. Preserve: macro line-continuation style. Next: Step 4.

### Step 4: Compile every test file with the real build
Actions: run the project's script that compiles each `tests/test_*.cpp` against the full source list. Inputs: build script. Outputs: per-file compile status. Cautions: reaching a linker error means macro expansion already succeeded — do not keep editing the macro at that point. Next: Step 5 when no macro errors remain.

### Step 5: Run the suites and confirm registration
Actions: execute the linked binaries and read each `N/N tests passed` line. Inputs: linked test executables. Outputs: per-suite pass counts and the script's final tally. Next: stop when suites register and execute tests; report remaining assertion failures as unrelated defects.

## Decision Rules
### When the error says `redefinition of '_reg___LINE__'` (literal, unexpanded token)
The unique suffix never expanded before pasting; introduce the two-level `EPILOG_CONCAT`/`EPILOG_CONCAT2` indirection (Step 2).

### When the error says `redefinition of '_reg___COUNTER__'`
The same literal-paste problem with `__COUNTER__`; Step 2 applies — swapping `__LINE__` for `__COUNTER__` alone does not help (the trace's first attempt still failed).

### When the error says `use of undeclared identifier '_test_body_2'` while `_test_body_0` is declared here
Pasting is now correct but `__COUNTER__` was expanded several times inside one macro, so declaration, registration, and body got different ids; capture it once through `TEST_IMPL` (Step 3).

### When clangd reports redefinitions but the compiler run succeeds
Treat it as editor cross-file analysis noise; verify with an actual build only (Step 4).

### When the build output advances from macro errors to a linker error
Macro expansion is fixed; stop editing the framework and handle link/runtime issues separately.

## Invariants
- Only the `TEST`-related macros in the framework header change; `EXPECT*`, `REQUIRE`, the runner, and all test files stay untouched.
- `__COUNTER__` may appear exactly once per `TEST` expansion — the implementation macro must receive it as a parameter and reuse that parameter.
- Every pasted name goes through the two-level concatenation macro; no direct `prefix##__COUNTER__` / `prefix##__LINE__` remains.
- Registration must remain static/automatic: no manual per-test registration lists are introduced.
- Never claim compilation success from IDE diagnostics; only the compiler's exit status and messages count.
- Do not delete or rename failing tests to make the errors disappear.

## Common Failures
### Failure: Swapping __LINE__ for __COUNTER__ without indirection
Symptoms: `redefinition of '_reg___COUNTER__'` for every test after the swap. Causes: the token is still pasted directly, so it is not expanded before `##`. Recovery: add `EPILOG_CONCAT`/`EPILOG_CONCAT2` and paste through them (the trace's first fix attempt failed exactly this way).

### Failure: Indirection added but __COUNTER__ still written three times
Symptoms: `use of undeclared identifier '_test_body_2'` with `'_test_body_0' declared here`. Causes: each of the three occurrences increments the counter, so declaration, registration, and body get different ids. Recovery: capture the counter once in `TEST_IMPL(name, uid)` and use only `uid` inside.

### Failure: Trusting editor diagnostics instead of the compiler
Symptoms: "Redefinition of ..." lists in the editor while the real build compiles, or numeric expansions in the editor while the real build shows literals. Causes: clangd analyzes all test files together, but `__COUNTER__` is per translation unit. Recovery: decide only from an actual `clang++` run.

### Failure: Stopping while errors remain but the message changed
Symptoms: macro errors gone, now LNK2019 for an unrelated symbol; risk of endless macro edits. Causes: a different defect surfaced after compilation succeeded. Recovery: treat macro work as done and handle the link/runtime problem separately.

## Verification
- The full test build reports no `redefinition of '_reg_...'`, no `redefinition of '_test_body_...'`, and no `use of undeclared identifier '_test_body_...'` for any `tests/test_*.cpp`.
- Progress marker: if the build output moves from those macro errors to `LNK2019: unresolved external symbol` / `LNK1120`, macro expansion has succeeded (compile stage completed for that file).
- Each linked suite prints individually named tests (e.g. `PASS  lex empty string produces only EOF`) rather than skipping, proving `Registrar` ran per test.
- Each suite prints a non-zero tally such as `22/22 tests passed`, and the harness prints its final `=== N suite(s) PASSED, M FAILED ===` line.
- The same result appears when re-running the whole script from a clean build directory, not only for a single hand-compiled file.

## Examples
### Example 1: Literal token after direct pasting
Input: `#define TEST(name) static void _test_body_##__LINE__(); static ::epilog_test::Registrar _reg_##__LINE__(name, _test_body_##__LINE__); static void _test_body_##__LINE__()` with build errors `D:\Epilog\tests\test_atoms.cpp:26:1: error: redefinition of '_reg___LINE__'`.
Procedure: Step 1 (classify as case (a)), Step 2 (add `EPILOG_CONCAT2`/`EPILOG_CONCAT` and paste through them), Step 4 (rebuild all test files).
Expected result: names expand to real numbers; the `_reg___LINE__` redefinitions disappear; if you only swapped in `__COUNTER__` you would still get `redefinition of '_reg___COUNTER__'`.
Parameterized values: header `tests/test_framework.hpp`, macro line ~118, compiler `clang++ -std=c++23 -Iinclude -Itests`.

### Example 2: Three counter values inside one macro
Input: pasting works, but the build fails with `D:\Epilog\tests\test_atoms.cpp:19:1: error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?` because `TEST` expanded `__COUNTER__` in three places.
Procedure: Step 3 (introduce `TEST_IMPL(name, uid)`; `#define TEST(name) TEST_IMPL(name, __COUNTER__)`), Step 4, Step 5.
Expected result: all seven test files compile past preprocessing, the suite links, and runners print counts such as `22/22 tests passed` and `17/17 tests passed`.
Parameterized values: unique-suffix base `_test_body_` / `_reg_`, counter macro `__COUNTER__`, suite list `test_atoms, test_lexer, test_parser, test_solver, test_terms, test_unifier, test_variables`.

## Evidence
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 946; source_part_index: 0; quote: `D:\Epilog\tests\test_atoms.cpp:26:1: error: redefinition of '_reg___LINE__'`; supports: problem case (a) — direct `##` pasting left the suffix token literal, so every test produced the same identifier.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 955; source_part_index: 0; quote: `error: redefinition of '_reg___COUNTER__'`; supports: failed attempt — replacing `__LINE__` with `__COUNTER__` alone does not fix literal pasting.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 964; source_part_index: 0; quote: `D:\Epilog\tests\test_atoms.cpp:19:1: error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`; supports: problem case (b) — with pasting fixed, three `__COUNTER__` uses in one macro produced three different ids.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 967; source_part_index: 0; quote: `each invocation increments it, so the forward declaration, registration, and body get three different numbers`; supports: diagnosis of case (b) (assistant judgement preceding the fix).
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 968; source_part_index: 0; quote: `#define TEST(name) TEST_IMPL(name, __COUNTER__)`; supports: action — final macro shape capturing the counter once through an implementation macro.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 975; source_part_index: 0; quote: `COMPILE ERROR: test_atoms.cpp`; supports: verification (stage marker) — in the very next full build every test file reached the link stage: its only remaining complaint was `LNK2019 ... exit code 1120`, i.e. no macro-expansion errors were reported for any of the 7 files.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 984; source_part_index: 0; quote: `PASS  lex empty string produces only EOF`; supports: verification — registered tests actually executed and passed after the macro fix (suite reported `22/22 tests passed`).

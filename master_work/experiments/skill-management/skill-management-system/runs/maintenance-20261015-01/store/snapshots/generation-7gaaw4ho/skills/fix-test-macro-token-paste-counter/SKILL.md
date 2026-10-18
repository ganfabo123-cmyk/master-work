---
name: fix-test-macro-token-paste-counter
description: Use when a header-only C++ test framework's TEST(name) macro fails to compile with redefinition of '_reg___LINE__'/'_reg___COUNTER__' or undeclared '_test_body_N' identifiers. Helps the agent build a two-level token-paste helper and capture __COUNTER__ exactly once per macro expansion. Requires a C/C++ compiler (clang++/MSVC) to verify. Do not use when the macro already compiles or when the failure is unrelated to token pasting.
triggers:
  - "redefinition of '_reg___LINE__'"
  - "redefinition of '_reg___COUNTER__'"
  - "use of undeclared identifier '_test_body_"
---
# Fix unique test-name generation in header-only C++ TEST macros

## Goal
Make a header-only TEST(name) macro produce a unique function name and a unique registrar name for every test case, so each test_*.cpp translation unit compiles and links with no redefinition or undeclared-identifier errors.

## Scope
### In scope
- Diagnosing compile errors whose diagnostic text contains the literal text `_reg___LINE__`, `_reg___COUNTER__`, or `use of undeclared identifier '_test_body_<N>'`.
- Rewriting the TEST macro with a two-level token-paste helper (`CONCAT2`/`CONCAT`) and an intermediate implementation macro that captures `__COUNTER__` exactly once.
- Verifying by recompiling and running the test suite with the real compiler.

### Out of scope
- Test assertion macros (EXPECT/REQUIRE) and their semantics.
- Cross-translation-unit uniqueness: `__COUNTER__` is per translation unit; that is fine because each test file is compiled as its own binary here.
- IDE/clangd diagnostics as the sole source of truth (see Invariants).

## Inputs
- `test_framework.hpp` (file path): the header-only test framework containing the TEST macro; required; must be the file the compiler diagnostic points into.
- Compiler error output (string): full stderr of the failing compile; required; must show either `redefinition of '_reg___LINE__'`, `redefinition of '_reg___COUNTER__'`, or `use of undeclared identifier '_test_body_<N>'`.
- Build command (string): the exact compile/link command used for the test suite (e.g. `clang++ -std=c++23 -Iinclude -Itests ... tests/test_x.cpp -o build/tests/test_x.exe`); required; no default.
- Test source files (`tests/test_*.cpp`): consumers of the macro; required unchanged (the fix must not require editing test bodies). No default.

## Outputs
### Artifacts
- Edited `tests/test_framework.hpp` containing `EPILOG_CONCAT2`/`EPILOG_CONCAT` (or equivalently named) two-level paste macros, a `TEST_IMPL(name, uid)` macro, and `#define TEST(name) TEST_IMPL(name, __COUNTER__)`.

### Success criteria
- The test suite compiles with no `redefinition of '_reg_*'` or `use of undeclared identifier '_test_body_*'` errors, and every `TEST("...")` block runs (PASS/FAIL lines are printed for each test name).

### Failure criteria
- Any remaining redefinition or undeclared-identifier error naming the generated identifiers.
- The fix "works" only after also editing individual test bodies, or compiles only on one compiler with non-standard behavior.

## Preconditions
- A working C++ compiler invocation for the project is available (in the trace: `clang++` on Windows producing `.exe` test binaries). If no compile can be run, stop and report: the fix cannot be considered done without a real compiler run.
- The failing compile reproduces the identifier errors above; if the compiler reports unrelated errors first, fix those first.
- The project compiles each `test_*.cpp` as its own translation unit (each defines its own `main()` calling the runner). If tests are combined into one binary, per-TU uniqueness is insufficient and a different scheme is needed — report this before proceeding.

## Procedure
### Step 1: Confirm the token-paste failure mode
- Actions: Compile a test file and read the first error. If the diagnostic shows the generated name containing the literal characters `__LINE__` or `__COUNTER__` (e.g. `redefinition of '_reg___LINE__'`), the `##` operator prevented expansion of the special macro — this is the bug to fix.
- Inputs: compiler stderr, `tests/test_framework.hpp`.
- Outputs: confirmed diagnosis.
- Cautions: do not "fix" test files; the bug is in the macro. Do not dismiss the error as an IDE false positive — in this trace the same diagnostics initially appeared from clangd and then reproduced in the real compile.
- Preserve: all existing EXPECT/REQUIRE macros.
- Next: proceed to Step 2.

### Step 2: Add a two-level token-paste helper and switch to __COUNTER__
- Actions: Insert `#define EPILOG_CONCAT2(a, b) a##b` and `#define EPILOG_CONCAT(a, b) EPILOG_CONCAT2(a, b)` and rewrite the TEST macro to use `EPILOG_CONCAT(_test_body_, __COUNTER__)` and `EPILOG_CONCAT(_reg_, __COUNTER__)` in place of `_test_body_##__LINE__` / `_reg_##__LINE__`.
- Inputs: `tests/test_framework.hpp`.
- Outputs: edited header.
- Cautions: the two-level macro is required so arguments are expanded before pasting.
- Preserve: the registrar-based auto-registration design and the runner.
- Next: recompile; if the error changes to `use of undeclared identifier '_test_body_<N>'` with mismatched numbers, go to Step 3.

### Step 3: Capture __COUNTER__ exactly once per TEST expansion
- Actions: Add an implementation macro `TEST_IMPL(name, uid)` that uses `uid` for the forward declaration, the registrar object, and the body definition (all via `EPILOG_CONCAT`), then define `#define TEST(name) TEST_IMPL(name, __COUNTER__)`.
- Inputs: `tests/test_framework.hpp`.
- Outputs: edited header.
- Cautions: `__COUNTER__` increments on every appearance in a macro body; a TEST macro that references `__COUNTER__` three times yields three different numbers (`_test_body_0` declared, `_test_body_2` referenced). The indirection must be exactly one level: `TEST` passes `__COUNTER__` to `TEST_IMPL`, and `TEST_IMPL` only ever mentions the `uid` parameter.
- Preserve: macro parameter name `name` and the public call syntax `TEST("description") { ... }`.
- Next: recompile every test file.

### Step 4: Verify with the real compiler and runner
- Actions: Rebuild all `tests/test_*.cpp` (each with the project sources it needs) and run each binary; confirm every test name prints PASS or FAIL and the runner summary appears.
- Inputs: build command, test binaries.
- Outputs: pass/fail summary per suite.
- Cautions: on Windows, a leftover test process can hold the output `.exe` open (`LNK1105: cannot close file`) — kill stale test processes and rerun rather than misreading it as a code error.
- Preserve: all test sources unchanged.
- Next: stop when all suites compile and run; report any genuine assertion failures separately from this macro fix.

## Decision Rules
### When the diagnostic names the literal string `_reg___LINE__` or `_test_body___LINE__`
The `##` paste blocked `__LINE__` expansion. Replace direct pasting with the two-level `CONCAT2`/`CONCAT` helper and use `__COUNTER__` (seen to be required here because `__LINE__` was not expanding in this toolchain invocation).

### When the diagnostic names the literal string `_reg___COUNTER__`
Same root cause with `__COUNTER__`: direct `name##__COUNTER__` pastes the unexpanded token. Apply the two-level helper.

### When the diagnostic is `use of undeclared identifier '_test_body_<N>'` and the referenced number differs from the declared one
`__COUNTER__` was expanded multiple times inside one macro body. Route the whole macro body through an intermediate `TEST_IMPL(name, uid)` macro so the counter is evaluated once.

### When clangd/IDE shows redefinition errors but you have not compiled yet
Compile with the real compiler before concluding anything; in this trace the IDE warnings were initially dismissed as false positives, yet the real compile reproduced the same errors.

## Invariants
- Never paste `##` directly against `__LINE__` or `__COUNTER__`; always go through a two-level expansion macro.
- `__COUNTER__` must appear exactly once per public macro expansion; every generated name derives from the captured `uid` parameter.
- Test bodies (`tests/test_*.cpp`) are not modified by this fix.
- The public syntax `TEST("description") { ... }` and the `main() { return ...run_all(); }` entry point are unchanged.
- No success is reported until a real compiler invocation compiles the suite and the binaries execute.

## Common Failures
### Failure: generated identifiers contain the literal `__LINE__`/`__COUNTER__`
- Symptoms: `error: redefinition of '_reg___LINE__'` for every TEST after the first.
- Causes: `##` suppresses expansion of its operand, so `_reg_##__COUNTER__` pastes the characters `__COUNTER__` itself.
- Recovery: insert the two-level `CONCAT2`/`CONCAT` helper.

### Failure: declared and referenced test bodies get different numbers
- Symptoms: `error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`
- Causes: `__COUNTER__` was referenced three times inside the TEST macro (forward declaration, registrar argument, body definition), incrementing each time.
- Recovery: define `TEST_IMPL(name, uid)` containing the whole body and `#define TEST(name) TEST_IMPL(name, __COUNTER__)`.

### Failure: output binary cannot be overwritten while rebuilding
- Symptoms: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_atoms.exe'` misread as a code failure.
- Causes: a previous test process still holds the binary open on Windows.
- Recovery: terminate lingering test processes, wait briefly, rebuild; this is environmental, not a macro problem.

## Verification
- Compile every `tests/test_*.cpp` with the project sources and the real compiler; zero occurrences of `redefinition of '_reg_` and `use of undeclared identifier '_test_body_` in the output.
- Each test binary prints one `PASS <name>` or `FAIL <name>` line per TEST block and ends with a `<passed>/<total> tests passed` summary, proving every registration was executed (a macro bug typically collapses registrations, so a full total is the check).
- Re-running a suite produces the same total, confirming names are stable per build.
- IDE-only green is not accepted as verification.

## Examples
### Example 1: `__LINE__` pasting yields literal `_reg___LINE__`
- Input: `#define TEST(name) static void _test_body_##__LINE__(); static ::epilog_test::Registrar _reg_##__LINE__(name, _test_body_##__LINE__); static void _test_body_##__LINE__()` used by 22 TEST blocks in one file; compile error `redefinition of '_reg___LINE__'` at the second TEST.
- Procedure: Step 2 — add `EPILOG_CONCAT2(a,b) a##b` / `EPILOG_CONCAT(a,b) EPILOG_CONCAT2(a,b)` and switch to `EPILOG_CONCAT(_test_body_, __COUNTER__)`.
- Expected result: the literal-`__LINE__` redefinitions disappear.
- Parameterized values: macro prefix `_test_body_` / `_reg_`, counter `__COUNTER__`, compiler `clang++ -std=c++23`.

### Example 2: three `__COUNTER__` uses per macro give mismatched ids
- Input: after Example 1's change, compile error `use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`.
- Procedure: Step 3 — `#define TEST_IMPL(name, uid) static void EPILOG_CONCAT(_test_body_, uid)(); static ::epilog_test::Registrar EPILOG_CONCAT(_reg_, uid)(name, EPILOG_CONCAT(_test_body_, uid)); static void EPILOG_CONCAT(_test_body_, uid)()` and `#define TEST(name) TEST_IMPL(name, __COUNTER__)`.
- Expected result: all test files compile; a 22-test suite prints 22 PASS lines and `22/22 tests passed`.
- Parameterized values: three TEST blocks in the trace's lexer suite each expanded to one shared uid.

## Evidence
- problem — file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index 946, source_part_index 0, quote: "error: redefinition of '_reg___LINE__'", supports: direct-paste `##` blocked `__LINE__` expansion, reproduced by the real compiler (not just the IDE).
- problem — same file_id, source_index 955, source_part_index 0, quote: "error: redefinition of '_reg___COUNTER__'", supports: after switching to `__COUNTER__` while keeping direct pasting, the same class of error persisted.
- problem — same file_id, source_index 964, source_part_index 0, quote: "error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?", supports: three separate `__COUNTER__` expansions inside one TEST body produced three different ids.
- action — same file_id, source_index 968, source_part_index 0, quote: "#define TEST(name) TEST_IMPL(name, __COUNTER__)", supports: the working fix captures the counter once via an intermediate TEST_IMPL macro, added together with the two-level EPILOG_CONCAT helper in the same edit.
- verification — same file_id, source_index 975, source_part_index 0, quote: "solver-c181c1.o : error LNK2019: unresolved external symbol \"int g_verbose\"", supports: compilation got past the TEST macro to the link stage (the remaining error is a different, unrelated symbol issue), proving the macro fix compiled.
- verification — same file_id, source_index 1048, source_part_index 0, quote: "  PASS  lex empty string produces only EOF   PASS  lex atom: lowercase identifier", supports: after the TEST_IMPL fix, all 22 lexer tests registered and executed, i.e. every TEST block produced a unique function and registrar.

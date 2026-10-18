---
name: fix-test-macro-unique-name-paste
description: Use when a TEST-style macro that builds unique static function/registrar names via token pasting produces redefinition errors such as 'redefinition of _reg___LINE__' or mismatched declaration/definition identifiers. Helps the agent make the macro expand a single unique id through an indirection layer and verify by compiling every test file. Requires clang/gcc with __COUNTER__ support and a build script that compiles all test sources. Do not use when the failures are linker or runtime errors unrelated to the macro.
---
# Fix Test-Registration Macros That Paste __LINE__/__COUNTER__ into Identifiers

## Goal
Make a TEST-style registration macro generate genuinely unique, correctly expanded identifiers so every test file compiles, and prove it by compiling and running the whole test set.

## Scope
### In scope
- Macros that build static function/registrar names with `##` pasted against `__LINE__` or `__COUNTER__`, producing literal `_reg___LINE__`-style identifiers and `redefinition of ...` errors.
- Macros that use `__COUNTER__` several times in one expansion, so the forward declaration, registrar, and body receive three different numbers.
- The two-level fix: a CONCAT indirection macro for pasting, plus a single intermediate macro that captures the counter value exactly once and passes it down.
- Verification by compiling every test source with the project's build command and then running the suites.

### Out of scope
- Linker errors and runtime failures of the test binaries after they compile.
- Test assertion logic, fixture setup, and framework API changes.
- Non-test macros whose expansion problems were not exercised by this trajectory.

## Inputs
- **Compiler diagnostics** — string — from compiling a test file — required — must show `redefinition of '<identifier>'` with the `note: expanded from macro 'TEST'` trail, or declarations that do not match their definitions — default: none.
- **Macro header** — file path — from the include tree (e.g. `tests/test_framework.hpp`) — required — contains the `TEST` macro definition to rewrite — default: none.
- **Test source set** — file list — from the project (e.g. `tests/test_*.cpp`) — required — all files exercising the macro must be recompiled — default: glob `tests/test_*.cpp`.
- **Build command** — string — from the project's test build script — required — must compile each test together with the shared sources using the same flags as the failing run (trajectory: `clang++ -std=c++23 -Wall -Wextra -Wpedantic -Iinclude -Itests -g -O0 ...`) — default: none.
- **Unique-id macro** — enum — toolchain capability — required — `__COUNTER__` (used and verified) or `__LINE__` (must be expanded through an indirection) — default: `__COUNTER__`.
- **Unused for this skill** — none.

## Outputs
### Artifacts
- Edited macro header defining CONCAT helpers, an `TEST_IMPL(name, uid)`-style implementation macro, and the public `TEST(name)` wrapper that expands the counter once.
- Recompiled test binaries under the project's test output directory (trajectory: `build/tests/*.exe`).
- Build/run transcript covering every test file.

### Success criteria
- Compiling every test file yields no `redefinition of '_reg...'` / `redefinition of '_test_body...'` diagnostics.
- The only diagnostics left (if any) concern other subsystems such as linking.
- The suites execute and print per-test results (e.g. `N/N tests passed`), proving the macro both declares and defines each test consistently.

### Failure criteria
- Any redefinition or 'undeclared identifier' error still referencing the generated names.
- The forward declaration, registrar, and body of a test resolve to different identifiers (symptom: undefined symbol at link time for the generated names).
- Only some test files compile.

## Preconditions
- A reproducible compile of at least one failing test file, with diagnostics that name the generated identifier.
- The macro header is editable and is the only place the macro is defined (no duplicate definitions in other headers).
- The compiler provides `__COUNTER__` (clang and gcc do); if only `__LINE__` is available, it must be passed through an expansion indirection rather than pasted directly.
- The test build command compiles all test files in one run so the fix can be checked everywhere at once.
- Stale binaries from earlier runs are removed or overwritten, otherwise a passing run may be an artifact.

## Procedure
### Step 1: Capture the failing expansion
- Actions: compile one test file with the project's flags; save the full diagnostic, including the `note: expanded from macro 'TEST'` lines and the literal identifier in `redefinition of '<name>'`.
- Inputs: build command, one test file.
- Outputs: diagnostic showing the literal, unexpanded identifier (e.g. `_reg___LINE__`).
- Cautions: read the generated name in the error — if it contains the characters `__LINE__` or `__COUNTER__`, the id never expanded; that determines which branch of Step 3 applies.
- Preserve: the raw compiler output for before/after comparison.
- Next: proceed to Step 2 once the generated name is identified.

### Step 2: Confirm how many times the id macro is used per expansion
- Actions: read the macro body and count every occurrence of the id macro across the forward declaration, the registrar, and the function definition.
- Inputs: macro header.
- Outputs: count (the trajectory had three uses inside one macro).
- Cautions: `__COUNTER__` increments on each expansion; three uses means three different numbers, which shows up as declarations that never match their definitions.
- Preserve: nothing to change yet.
- Next: proceed to Step 3.

### Step 3: Rewrite the macro in two layers
- Actions: (a) add a two-level paste helper so arguments are expanded before pasting, e.g. `#define EPILOG_CONCAT2(a, b) a##b` and `#define EPILOG_CONCAT(a, b) EPILOG_CONCAT2(a, b)`; (b) move the body into an implementation macro that takes the id as a parameter, e.g. `#define TEST_IMPL(name, uid) ... EPILOG_CONCAT(_test_body_, uid)() ...`; (c) make the public macro expand the counter exactly once, e.g. `#define TEST(name) TEST_IMPL(name, __COUNTER__)`.
- Inputs: macro header.
- Outputs: rewritten macro block.
- Cautions: never reference `__COUNTER__`/`__LINE__` more than once across the whole expansion — every use pastes a different value; keep the macro's public signature unchanged so test files need no edits.
- Preserve: the registrar mechanism, test body signature, and all call sites.
- Next: recompile everything.

### Step 4: Recompile every test file
- Actions: run the project's test build over the whole `test_*.cpp` set; record per-file results.
- Inputs: build command, test file list.
- Outputs: per-file compile status.
- Cautions: the script may label link failures as compile failures; distinguish `redefinition` diagnostics (still broken) from `LNK2019`-style diagnostics (macro fixed, separate problem).
- Preserve: existing sources outside the macro header.
- Next: proceed to Step 5 when no redefinition diagnostics remain.

### Step 5: Run the suites
- Actions: execute each compiled test binary; record pass counts and exit codes.
- Inputs: test binaries.
- Outputs: per-suite pass counts (trajectory: `22/22 tests passed`, `15/15 tests passed`, `18/18 tests passed`, `17/17 tests passed`).
- Cautions: suites may still fail for reasons unrelated to the macro (crashes, assertions); report them separately rather than attributing them to this fix.
- Preserve: run transcripts.
- Next: stop when all files compile and the suites execute.

## Decision Rules
### When the generated identifier literally contains `__LINE__` (e.g. `_reg___LINE__`)
The operand of `##` was never expanded. Add a CONCAT indirection layer so the argument expands before pasting; do not try to patch call sites.

### When the id macro is pasted directly with `##` anywhere in the macro
Route the paste through the two-level CONCAT helper; direct pasting suppresses expansion of the id macro.

### When the id macro appears more than once in a single macro expansion
Restructure so the public macro expands it exactly once and passes the value as a parameter to an implementation macro; multiple uses yield different numbers and mismatched identifiers.

### When, after the macro fix, compilation succeeds but linking fails with LNK2019
The macro work is done; the remaining failure is a separate missing-definition problem (see the header-only shared global skill). Do not keep editing the macro.

### When only some test files still fail with redefinition errors
Check for a second definition of the macro in another header before changing the macro again (not observed in this trajectory — unconfirmed cause).

## Invariants
- Keep the public macro signature unchanged (`TEST(name)`), so no test source file has to be edited.
- Expand the unique-id macro exactly once per macro invocation.
- Perform all identifier pasting through the two-level CONCAT helper, never with raw `##` against `__LINE__`/`__COUNTER__`.
- Touch only the macro header; test files, the registrar implementation, and build scripts stay as they are.
- Rebuild every test file, not just the one that failed first, before declaring success.
- Do not report a suite as passing based on compilation alone — execution output is required.

## Common Failures
### Failure: redefinition of '_reg___LINE__'
- Symptoms: `error: redefinition of '_reg___LINE__'` and `redefinition of '_test_body___LINE__'` repeated for every test in the file, with `note: expanded from macro 'TEST'`.
- Causes: `##` pasted the unexpanded token `__LINE__`, so every test produced the same identifier.
- Recovery: replace the direct paste with a CONCAT indirection and/or switch to `__COUNTER__` passed through an intermediate macro; recompile all test files.

### Failure: identifiers still collide or never match after switching to __COUNTER__
- Symptoms: either literal `__COUNTER__` appears in the generated name, or the declaration and definition carry different numbers (undefined symbol at link for the generated names).
- Causes: the counter was pasted directly with `##` (no expansion), or it was expanded several times inside one macro so each use produced a different value.
- Recovery: one CONCAT layer plus a single capture — the public macro expands `__COUNTER__` once and forwards it to an implementation macro; recompile.

### Failure: macro compiles but tests fail at runtime
- Symptoms: suites link yet exit non-zero or crash (trajectory: exit `-1073741571` with no output, or assertion failures).
- Causes: unrelated to the macro — typically large stack fixtures or test logic.
- Recovery: stop macro work; handle with the corresponding runtime diagnosis. Do not report macro success from a crash.

## Verification
Recompile the full test set with the project's build command and check:

- No `redefinition of '_reg...` and no `redefinition of '_test_body...` diagnostics in any file.
- No diagnostic whose `expanded from` trail shows a literal `__LINE__` or `__COUNTER__` inside an identifier.
- Every `tests/test_*.cpp` file reaches the link stage.
- Each produced binary runs and prints per-test results such as `N/N tests passed`, with the registrar having registered every test in the file (the printed count equals the number of `TEST(...)` blocks).
- Suites that previously produced no output now produce output.

These are observable checks for future runs, not claims about any already-executed session.

## Examples
### Example 1: pasting `__LINE__` directly
- Input: `#define TEST(name) static void _test_body_##__LINE__(); static ::epilog_test::Registrar _reg_##__LINE__(name, _test_body_##__LINE__); static void _test_body_##__LINE__()`; compiling `tests/test_atoms.cpp` fails with `error: redefinition of '_reg___LINE__'`.
- Procedure: Step 1 capture the diagnostic; Step 2 count three uses of the id macro; Step 3 rewrite with CONCAT helpers plus `TEST_IMPL(name, uid)` and `#define TEST(name) TEST_IMPL(name, __COUNTER__)`; Step 4 recompile all seven test files; Step 5 run the suites.
- Expected result: no redefinition diagnostics; all test files compile; suites print pass counts.
- Parameterized values: macro name `TEST`, prefix `_reg_`/`_test_body_`, counter `__COUNTER__`, header `tests/test_framework.hpp`.

### Example 2: counter captured once through an implementation macro
- Input: header body referencing `__COUNTER__` three times with a CONCAT helper already present.
- Procedure: keep `EPILOG_CONCAT2`/`EPILOG_CONCAT`, move the body into `TEST_IMPL(name, uid)`, define `TEST(name) TEST_IMPL(name, __COUNTER__)`.
- Expected result: forward declaration, registrar, and function definition all share one id, so declaration matches definition and the file compiles.
- Parameterized values: implementation macro `TEST_IMPL`, uid parameter name `uid`, project prefix `EPILOG_`.

## Evidence
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 946, source_part_index: 0 — quote: `error: redefinition of '_reg___LINE__'` — supports: the original macro pasted `__LINE__` unexpanded, so every `TEST` in a file produced the identical static registrar name and compilation failed.
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 946, source_part_index: 0 — quote: `    static ::epilog_test::Registrar _reg_##__LINE__(name, _test_body_##__LINE__); \` — supports: shows the exact macro line and that the id was pasted directly with `##` in three places.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 957, source_part_index: 0 — quote: `#define EPILOG_CONCAT2(a, b) a##b\n#define EPILOG_CONCAT(a, b)  EPILOG_CONCAT2(a, b)` — supports: the two-level paste indirection was added so arguments expand before concatenation.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 968, source_part_index: 0 — quote: `#define TEST(name) TEST_IMPL(name, __COUNTER__)` — supports: the final structure expands `__COUNTER__` exactly once and forwards the value to `TEST_IMPL`, fixing the three-different-numbers problem.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 975, source_part_index: 0 — quote: `COMPILE ERROR: test_lexer.cpp\nsolver-307aaf.o : error LNK2019: unresolved external symbol "int g_verbose"` — supports: after the macro rewrite every test file compiles — the only remaining diagnostics are link errors for an unrelated symbol, i.e. no `redefinition` errors remain.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1218, source_part_index: 0 — quote: `test_lexer: 22/22 tests passed` — supports: with the macro in place, a suite executes and reports all of its registered tests passing, proving declarations and definitions matched.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1218, source_part_index: 0 — quote: `test_unifier: 18/18 tests passed` — supports: a second suite runs its full registered test set under the same macro.

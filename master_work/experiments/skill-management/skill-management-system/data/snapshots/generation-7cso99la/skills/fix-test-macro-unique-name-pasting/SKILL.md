---
name: fix-test-macro-unique-name-pasting
description: Use when a single-header C++ test framework fails to compile with preprocessor errors like redefinition of '_reg___LINE__', redefinition of '_reg___COUNTER__', or use of undeclared identifier '_test_body_2'. Helps the agent build a TEST macro whose forward declaration, registrar and body all share one unique per-test identifier. Requires compiler/preprocessor output from building the test translation units. Do not use when the tests compile but fail at runtime, or when the failure is a linker error rather than an expansion error.
triggers:
  - "redefinition of '_reg___LINE__'"
  - "redefinition of '_reg___COUNTER__'"
  - "use of undeclared identifier '_test_body_"
---
# Make a TEST macro produce unique identifiers with a single-captured counter

## Goal
Make a header-only test framework's TEST macro compile everywhere, so each TEST declaration expands to a distinct forward declaration, registrar object and function body instead of colliding identifiers.

## Scope
### In scope
- A `TEST(name)` macro in a header-only framework that must expand into a forward declaration, a registrar construction, and a function definition carrying one unique identifier per test.
- Preprocessor identifier-pasting failures: `##` blocking expansion of `__LINE__`/`__COUNTER__` (literal `_reg___LINE__`, `_reg___COUNTER__`), and multiple `__COUNTER__` evaluations inside one macro producing mismatched identifiers (`_test_body_0` declared, `_test_body_2` used).
- The two-level `CONCAT2`/`CONCAT` indirection plus a single-capture implementation macro (`TEST_IMPL(name, uid)`).

### Out of scope
- Runtime test failures, assertion logic, or fixtures.
- Linker errors reached after the macro compiles (e.g. the LNK2019 seen in the same build output).
- Framework features beyond name uniqueness (reporting, REQUIRE semantics, registration order guarantees).

## Inputs
- **Preprocessor/compiler error output** — type: tool result text. Source: the build of each `tests/test_*.cpp`. Required: yes. Constraint: errors must show the literal identifiers (`_reg___LINE__`, `_reg___COUNTER__`) or mismatched numeric identifiers (`_test_body_0` vs `_test_body_2`) with the macro expansion notes. Default: 无.
- **Test framework header** — type: file path. Source: project tree (trajectory: `tests/test_framework.hpp`). Required: yes. Constraint: single-header framework included by every test translation unit. Default: 无.
- **Current TEST macro definition** — type: source snippet. Source: the header. Required: yes. Constraint: must show the declaration/registrar/definition triple that needs unique names. Default: 无.
- **Compiler identity** — type: string. Source: build command (trajectory: `clang++` on Windows). Required: yes. Constraint: the fix relies on standard `__COUNTER__` support; behaviour observed is with clang targeting MSVC. Default: `clang++`.
- **C++ standard** — type: version flag. Source: build flags (trajectory: `-std=c++23`). Required: no. Constraint: C++17+ convenient but not required by the macro pattern. Default: `-std=c++23`.

## Outputs
### Artifacts
- Updated test framework header containing:
  - `#define EPILOG_CONCAT2(a, b) a##b` and `#define EPILOG_CONCAT(a, b) EPILOG_CONCAT2(a, b)` (name prefix project-specific).
  - A `TEST_IMPL(name, uid)` macro holding the forward declaration, registrar construction, and body definition, all pasted through the indirection macro with `uid`.
  - `#define TEST(name) TEST_IMPL(name, __COUNTER__)` so the counter is expanded exactly once per TEST.

### Success criteria
- Building each test translation unit produces no `redefinition` and no `undeclared identifier` errors originating from the TEST macro; compilation proceeds to the link stage.
- Test binaries run and print distinct test names with pass counts (e.g. `22/22 tests passed`).

### Failure criteria
- Any preprocessor error still names `_reg___LINE__`/`_reg___COUNTER__` literally, or identifiers declared with one number are used with another; or the macro compiles but registration order/contents change unexpectedly.

## Preconditions
- The errors originate from the test framework's name-generating macro, shown by compiler notes pointing at the macro definition lines (trajectory: notes cite `tests/test_framework.hpp:118` expanded into the failing test files).
- Each test translation unit is compiled as its own TU (so per-file uniqueness is sufficient); the framework is header-only and included by all tests.
- The compiler provides `__COUNTER__` (clang and MSVC do; the trajectory used clang on Windows).
- Edit access to the framework header is available; test bodies themselves must not need renaming.
If the redefinition errors also occur when a single test file is compiled alone with a compiler that defines `__COUNTER__` correctly, stop and investigate other causes.

## Procedure
### Step 1: Read the preprocessor error to classify the failure
- actions: Inspect the first errors and the macro-expansion notes. Distinguish (a) literal `_reg___LINE__` / `_reg___COUNTER__` (expansion blocked by `##`) from (b) mismatched numeric identifiers such as `_test_body_0` declared but `_test_body_2` used.
- inputs: compiler output for one failing test file.
- outputs: classification (a) or (b), or both in sequence.
- cautions: ignore clangd/IDE diagnostics; only the real compiler invocation counts (in the trace the IDE reported spurious cross-file redefinitions while the compiler output was authoritative).
- next condition: proceed with the matching fixes; they can be applied in sequence as the failure evolves.

### Step 2: Add token-pasting indirection
- actions: Define a two-level pair: `#define EPILOG_CONCAT2(a, b) a##b` and `#define EPILOG_CONCAT(a, b) EPILOG_CONCAT2(a, b)`, so arguments expand before pasting.
- inputs: framework header.
- outputs: a paste macro that expands its arguments first.
- cautions: single-level paste macros do not expand their arguments; both levels are required.
- next condition: identifiers now contain numbers rather than the literal macro name.

### Step 3: Capture the counter exactly once per TEST
- actions: Move the declaration, registrar construction and body definition into an implementation macro parameterised by a uid, and make TEST pass the counter into it: `#define TEST(name) TEST_IMPL(name, __COUNTER__)`.
- inputs: existing TEST macro body.
- outputs: all three identifier pastes share the single expanded counter value.
- cautions: a TEST body that mentions `__COUNTER__` three times evaluates three different numbers (observed: declared `_test_body_0` but registered/defined `_test_body_2`) — do not "fix" this by hand-numbering tests.
- next condition: macro layering complete; rebuild.

### Step 4: Rebuild every test translation unit and run them
- actions: Compile each `tests/test_*.cpp`; confirm errors no longer reference the TEST macro; run the binaries and record pass counts.
- inputs: test source list; build command.
- outputs: per-suite pass counts.
- cautions: a new error class (e.g. LNK2019) appearing after this step is a separate problem; do not conflate it with the macro fix.
- next condition: stop when every suite compiles past the preprocessor stage and runs.

## Decision Rules
### When the compiler reports redefinition of a literal `_reg___LINE__` or `_reg___COUNTER__`
The `##` operator blocked expansion of `__LINE__`/`__COUNTER__`. Add two-level paste indirection (`CONCAT2`/`CONCAT`) so the counter expands before pasting.

### When the compiler reports use of an undeclared identifier whose number differs from the declared one (e.g. `_test_body_0` declared, `_test_body_2` used)
The counter was evaluated multiple times inside one macro. Capture it once by moving the macro body into `TEST_IMPL(name, uid)` and defining `TEST(name) TEST_IMPL(name, __COUNTER__)`.

### When IDE/clangd diagnostics disagree with the compiler
Trust the compiler invocation only. In the trace, clangd reported spurious cross-file redefinitions (it analyses all test files as one unit while `__COUNTER__` is per-file); the actual per-TU builds were the arbiter.

## Invariants
- Keep the macro layering exact: exactly two paste levels (`CONCAT2`/`CONCAT`) and exactly one evaluation of `__COUNTER__` per TEST expansion.
- Do not hand-number or rename individual tests to dodge collisions.
- Do not change TEST's public syntax (`TEST("description") { ... }`) or the registrar/registry design.
- Do not treat IDE/clangd diagnostics as the source of truth; verify with the real compiler.
- Do not claim the macro is fixed based on one test file; build every test translation unit, since uniqueness is per file.
- Do not report success while later-stage errors (e.g. linker errors) remain without distinguishing them.

## Common Failures
### Failure: counter name is still literal (`_reg___COUNTER__`)
symptoms: redefinition errors naming `_reg___COUNTER__` after simply swapping `__LINE__` for `__COUNTER__`.
causes: direct `##` pasting prevents expansion of the counter token, exactly as it did for `__LINE__`.
recovery: introduce the two-level `CONCAT2`/`CONCAT` indirection. Observed in the trace and fixed by the next step.

### Failure: identifiers with mismatched counter numbers
symptoms: `use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`.
cautions aside: the macro pasted `__COUNTER__` three separate times (declaration, registrar argument, definition), each expanding to a different number.
recovery: capture the counter once via `TEST_IMPL(name, uid)`. Observed and fixed in the trace.

### Failure: suites fail at runtime after the macro compiles
symptoms: binaries build and run but tests crash or fail assertions.
causes: unrelated issues (link errors for globals, stack overflow in fixtures, wrong expectations).
recovery: stop applying this skill; the macro objective (clean preprocessing) is already met.

## Verification
- Compile a test file that previously failed with `redefinition of '_reg___LINE__'` (or `_reg___COUNTER__`); the output must contain no redefinition or undeclared-identifier errors pointing at the TEST macro lines.
- Compile a second, different test file and confirm it also builds: uniqueness is per translation unit, so at least two files must be checked.
- Confirm the compile proceeds past preprocessing to the linker stage (any remaining errors must be of a different class, e.g. LNK2019).
- Run the produced binaries and confirm distinct test names execute with full pass counts (e.g. `22/22 tests passed`).
- Do not accept IDE/clangd diagnostics as evidence either way; only compiler output counts.

## Examples
### Example 1: three-stage fix for a TEST macro that blocked expansion, then over-expanded
input: A single-header framework with `#define TEST(name) static void _test_body_##__LINE__(); ...`; compiling `tests/test_atoms.cpp` reports `error: redefinition of '_reg___LINE__'`; swapping to `__COUNTER__` reports `error: redefinition of '_reg___COUNTER__'`; adding CONCAT indirection reports `error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`.
procedure: Step 1 classify each error from the compiler notes; Step 2 add `#define EPILOG_CONCAT2(a, b) a##b` and `#define EPILOG_CONCAT(a, b) EPILOG_CONCAT2(a, b)`; Step 3 move the three declarations into `TEST_IMPL(name, uid)` pasting `uid` through `EPILOG_CONCAT`, and define `#define TEST(name) TEST_IMPL(name, __COUNTER__)`; Step 4 rebuild all test files and run them.
expected result: preprocessing errors disappear for every test file; compilation proceeds to the link stage; test binaries run and print distinct names with counts such as `22/22 tests passed`.
parameterized values: macro name prefix, framework header path, test file list, compiler.

## Evidence
- problem — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 946, source_part_index: 0, quote: `D:\Epilog\tests\test_atoms.cpp:26:1: error: redefinition of '_reg___LINE__'`, supports: direct `##__LINE__` pasting produced the literal identifier `_reg___LINE__` for every TEST, colliding across tests.
- problem — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 955, source_part_index: 0, quote: `D:\Epilog\tests\test_atoms.cpp:26:1: error: redefinition of '_reg___COUNTER__'`, supports: simply swapping in `__COUNTER__` failed the same way under direct `##` pasting.
- problem — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 964, source_part_index: 0, quote: `D:\Epilog\tests\test_atoms.cpp:19:1: error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`, supports: with CONCAT indirection the counter expanded, but three separate `__COUNTER__` uses inside TEST produced mismatched identifiers.
- action — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 968, source_part_index: 0, quote: `#define TEST(name) TEST_IMPL(name, __COUNTER__)`, supports: the counter is now evaluated once and passed into `TEST_IMPL(name, uid)`, which holds the declaration, registrar and body.
- verification — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 975, source_part_index: 0, quote: `solver-c181c1.o : error LNK2019`, supports: compilation of the test translation units now proceeds past preprocessing to the linker — no TEST-macro errors remain.
- verification — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 984, source_part_index: 0, quote: `22/22 tests passed`, supports: uniquely named tests register and run successfully after the macro fix.

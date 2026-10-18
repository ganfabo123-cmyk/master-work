---
name: unique-symbols-in-test-registration-macro
description: Use when a self-registering test macro fails to compile with "redefinition of '_reg_...'" or "use of undeclared identifier '_test_body_...'". Helps the agent fix the macro layer so each TEST expands to uniquely named, consistently referenced test functions. Requires a preprocessor error log from compiling a test file and edit access to the test framework header. Do not use when the duplicate-symbol error comes from two source files sharing one definition, or when tests fail at run time.
---
# Make a TEST Macro Emit Unique Identifiers in One Translation Unit

## Goal
Produce a TEST(name) macro that expands each test into a uniquely named function plus registrar in the same translation unit, so a test file with many TEST cases compiles and every case registers exactly once.

## Scope
### In scope
- Single-header test frameworks whose `TEST(name)` macro declares a static test function, registers it through a static registrar object, and defines the body — all in one macro expansion (observed: `tests\test_framework.hpp` used by `tests\test_*.cpp`).
- Preprocessor errors produced when compiling a test translation unit: `redefinition of '<reg-ident>'`, `redefinition of '<body-ident>'`, `use of undeclared identifier '<body-ident>'`.
- Identifier uniqueness obtained from `__LINE__`/`__COUNTER__` plus token pasting.

### Out of scope
- Duplicate symbols that originate in two separate source files or in a header included by several TUs.
- Link-time errors (LNK2019/LNK1120) and run-time test failures; the macro must first compile cleanly, then other failures are handled elsewhere.
- Rewriting the assertion/EXPECT macros or the test runner.

## Inputs
- **Compiler error text for a test translation unit** — type: string; source: compiler tool result when building any `tests\test_*.cpp`; required: yes; constraints: must show the redefinition or undeclared-identifier diagnostics with the macro expansion notes (`expanded from macro 'TEST'`); default: none.
- **Test framework header** — type: file path; source: project tree (observed: `<project-dir>\tests\test_framework.hpp`); required: yes; constraints: contains the `TEST` macro and any concat helpers; default: none.
- **A test file with many TEST cases** — type: file path; source: project tree (observed: `<project-dir>\tests\test_atoms.cpp`); required: yes; constraints: several `TEST("...")` invocations, each on its own line; default: none.
- **Compiler** — type: executable and flags; source: build command (observed: `clang++ -std=c++23 -Iinclude -Itests -g -O0`); required: yes; constraints: must predefine `__COUNTER__` (clang/gcc/MSVC do); default: none.
- **Unique-token strategy** — type: choice; source: agent; required: yes; constraints: `__COUNTER__` is required when more than one TEST may appear on the same line; `__LINE__` alone cannot distinguish two cases sharing a line; default: `__COUNTER__`.

## Outputs
### Artifacts
- Edited test framework header (observed: `<project-dir>\tests\test_framework.hpp`) containing a two-level concatenation helper and a single-capture counter macro for `TEST`.
- Cleanly compiled test translation units (`build\tests\*.exe` objects).

### Success criteria
- Compiling any test file emits no `redefinition of` and no `use of undeclared identifier` diagnostics originating from the `TEST` macro.
- Each `TEST("...")` in a file yields a distinct registered test that appears as its own PASS/FAIL line at run time.

### Failure criteria
- Either diagnostic class reappears after the edit.
- Only some test cases register (silently dropped tests), which shows as fewer result lines than `TEST` invocations.

## Preconditions
- The compiler output for at least one failing test file is available, including the `expanded from macro 'TEST'` notes that show which macro line produced the bad identifier.
- The compiler provides `__COUNTER__` (clang, gcc and MSVC do); if it does not, stop and report.
- The whole macro is visible so you can count how many times the unique token is referenced inside one expansion.
- Edit permission on the test framework header and the ability to recompile a test file; test sources themselves stay untouched.
- If tests already compile and only fail at run time, stop — this skill does not apply.

## Procedure
### Step 1: Diagnose the first redefinition error
- Actions: compile one test file; read the first `redefinition of '<ident>'` diagnostic and check whether the identifier literally contains `__LINE__` or `__COUNTER__`.
- Inputs: compiler output, current `TEST` macro definition.
- Outputs: classification — (a) unique token never expanded into the name, or (b) unique token expanded inconsistently.
- Cautions: the compiler lists dozens of repeated errors; only the first one matters, the rest are copies of the same defect.
- Preserve: the failing source file unchanged.
- Next: go to Step 2 for classification (a), Step 3 for classification (b).

### Step 2: Make token pasting expand the unique token
- Actions: if the macro pastes directly (`_reg_##__LINE__` or `_reg_##__COUNTER__`), introduce a two-level helper `#define EPILOG_CONCAT2(a, b) a##b` / `#define EPILOG_CONCAT(a, b)  EPILOG_CONCAT2(a, b)` and paste through `EPILOG_CONCAT(_reg_, __COUNTER__)` (same for the body function); recompile.
- Inputs: test framework header.
- Outputs: header with working concat helpers; recompile result.
- Cautions: this step fixes only literal-paste problems; expect the next, different error if the unique token is used more than once per expansion.
- Preserve: macro argument order and the registrar/bodies semantics.
- Next: go to Step 3 when the new compile error is an undeclared identifier; go to Step 4 when compilation succeeds.

### Step 3: Evaluate the unique token exactly once per expansion
- Actions: when the error is `use of undeclared identifier '_test_body_<n>'; did you mean '_test_body_<m>'?`, move the expansion into an intermediate macro: define `TEST_IMPL(name, uid)` that uses `uid` for the forward declaration, the registrar and the body, and make `#define TEST(name) TEST_IMPL(name, __COUNTER__)`; recompile.
- Inputs: test framework header, compiler output.
- Outputs: single-evaluation macro; recompile result.
- Cautions: `__COUNTER__` increments on every expansion, so three uses inside one macro yield three different ids; the intermediate macro is what freezes one value.
- Preserve: the public `TEST(name)` spelling so test files need no edits.
- Next: go to Step 4 when the test file compiles.

### Step 4: Recompile all test files and run one suite
- Actions: rebuild every `tests\test_*.cpp`; run a suite and count registered tests against the number of `TEST(` occurrences in the file.
- Inputs: test build/run command.
- Outputs: build log free of macro diagnostics; per-suite result line.
- Cautions: a suite that compiles but registers fewer tests than expected indicates a remaining identifier collision — re-read the expansion.
- Preserve: test names and expectations.
- Next: stop when all test files compile and each suite prints a full `N/N tests passed` line.

## Decision Rules
### When the identifier in the redefinition error literally contains `__LINE__` or `__COUNTER__`
The pasted name never included the token's value — route the paste through a two-level concatenation macro (`EPILOG_CONCAT2`/`EPILOG_CONCAT`) so arguments expand before `##`.

### When the error changes to `use of undeclared identifier '_test_body_<n>'; did you mean '_test_body_<m>'?`
Concatenation now works, but the unique token was expanded several times with different values inside one macro — capture it once via an intermediate macro (`TEST_IMPL(name, uid)` called with `__COUNTER__`).

### When two TEST cases can share a source line
Use `__COUNTER__`, not `__LINE__`: line-based ids collide for two cases on one line.

### When the test file compiles but a suite registers fewer tests than there are TEST invocations
An identifier collision remains; re-read the expanded macro before touching any test file.

### When the diagnostics come from a header included by several TUs rather than from the macro
Stop — that is an ordinary duplicate-definition problem outside this skill.

## Invariants
- Fix only the macro layer; test files keep their `TEST("description")` calls unchanged.
- Keep the public macro name and argument shape (`TEST(name)`) so existing tests still compile.
- Keep exactly one definition and one registrar per TEST expansion — uniqueness must not come from dropping registrations.
- Do not disable warnings, change language standards, or add `-fpermissive` to silence the diagnostics.
- Do not report success from an edited macro alone: the test file must recompile after the change.
- Do not claim every test registered unless a run output shows one result line per TEST case.

## Common Failures
### Failure: `redefinition of '_reg___LINE__'`
- Symptoms: hundreds of `error: redefinition of '_reg___LINE__'` / `_test_body___LINE__` notes, each pointing at a different TEST line but naming the same identifier.
- Causes: direct pasting `_reg_##__LINE__` keeps the literal token name; every expansion yields one identical symbol.
- Recovery: two-level concatenation helper, then recompile (Step 2).

### Failure: `redefinition of '_reg___COUNTER__'` after switching the token
- Symptoms: same shape of error, identifier now literally `_reg___COUNTER__`.
- Causes: swapping the token without fixing the paste changes nothing — `##` still swallows the macro name.
- Recovery: same as above; the token choice only matters after pasting expands correctly (Step 2).

### Failure: `use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`
- Symptoms: compilation reports undeclared identifiers whose numbers differ from any declared one (`_test_body_0` declared, `_test_body_2` used).
- Causes: `__COUNTER__` appears several times inside one macro, and each expansion consumes a new value, so the declaration, registrar reference and body definition disagree.
- Recovery: capture the counter once in an intermediate macro (`#define TEST(name) TEST_IMPL(name, __COUNTER__)`) and use the parameter everywhere (Step 3).

## Verification
Observable checks to run after the macro edit (none are claims about the current session):

1. Compiling a test file emits no `redefinition of` diagnostic mentioning `_reg_` or `_test_body_`.
2. Compiling a test file emits no `use of undeclared identifier '_test_body_` diagnostic.
3. The build log progresses past the compiler stage for every test file — if failures remain they are linker-stage (`LNK...`), which is a different class of problem.
4. Running a suite prints one `PASS`/`FAIL` line per `TEST(` occurrence in its source file, ending in a full line such as `22/22 tests passed` or `17/17 tests passed`.
5. Grep count: number of `TEST(` occurrences in a test file equals the number of registered tests printed by that suite.
6. A rebuild from clean (`rm -rf build` equivalent, then rebuild) reproduces the same result, so no stale object hides the defect.

## Examples
### Example 1: registration macro collides across every TEST case
- Input: compiling `<project-dir>\tests\test_atoms.cpp` fails with `error: redefinition of '_reg___LINE__'` (first attempt used `_reg_##__LINE__`), then with `error: redefinition of '_reg___COUNTER__'` after switching the token but keeping direct pasting, then with `error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?` after introducing `EPILOG_CONCAT` with three inline `__COUNTER__` uses.
- Procedure: Step 1 classify the first error as literal pasting; Step 2 add `#define EPILOG_CONCAT2(a, b) a##b` and `#define EPILOG_CONCAT(a, b)  EPILOG_CONCAT2(a, b)` and paste through it; Step 3 on the undeclared-identifier error, split into `TEST_IMPL(name, uid)` used by `#define TEST(name) TEST_IMPL(name, __COUNTER__)` so the counter is evaluated once; Step 4 recompile all test files and run a suite.
- Expected result: all test files compile (the next reported errors are link-stage only), and suites print every registered case, e.g. `22/22 tests passed` for the lexer suite.
- Parameterized values: `<project-dir>` = project root; `<framework-header>` = single-header test framework; `<test-file>` = any file with many `TEST("...")` cases; `<unique-token>` = `__COUNTER__` (or `__LINE__` when at most one case per line).

## Evidence
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 946, source_part_index: 0, quote: `error: redefinition of '_reg___LINE__'`, supports: the original macro `_reg_##__LINE__` pasted the token literally, so every TEST produced the same registrar name. The same event shows the matching `error: redefinition of '_test_body___LINE__'`.
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 955, source_part_index: 0, quote: `error: redefinition of '_reg___COUNTER__'`, supports: swapping `__LINE__` for `__COUNTER__` without fixing the paste leaves the same literal-name collision.
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 964, source_part_index: 0, quote: `error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`, supports: once pasting expands, the remaining defect is that `__COUNTER__` was evaluated multiple times inside one macro, so the declared name and the referenced name disagree.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 957, source_part_index: 0, quote: `#define EPILOG_CONCAT2(a, b) a##b`, supports: two-level concatenation helper added to the framework header so arguments expand before `##` (the edit's `new_string` also adds `#define EPILOG_CONCAT(a, b)  EPILOG_CONCAT2(a, b)` and routes the TEST identifiers through it).
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 968, source_part_index: 0, quote: `#define TEST(name) TEST_IMPL(name, __COUNTER__)`, supports: the counter is now captured once and passed as a parameter into `TEST_IMPL(name, uid)`, which uses `uid` for the forward declaration, the registrar and the body definition.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 975, source_part_index: 0, quote: `solver-c181c1.o : error LNK2019: unresolved external symbol "int g_verbose"`, supports: after the final macro edit all seven test files compile — the only diagnostics left are linker-stage, with no `redefinition of` or `use of undeclared identifier` anywhere in the output.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 984, source_part_index: 0, quote: `22/22 tests passed`, supports: a suite built with the final macro registers and runs every one of its 22 TEST cases as distinct tests.

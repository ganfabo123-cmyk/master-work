---
name: capture-counter-once-for-test-macros
description: Use when a TEST-style macro fails with 'redefinition of _reg___LINE__' or 'use of undeclared identifier _test_body_N' because token pasting produces literal or mismatched suffixes. Helps the agent build a TEST macro that emits one unique, self-consistent identifier pair per test case. Requires a compiler supporting __COUNTER__ (clang/MSVC) and a real build command to verify against. Do not use when the errors come from the linker or from test logic rather than macro expansion.
triggers:
  - "redefinition of '_reg___LINE__'"
  - "redefinition of '_reg___COUNTER__'"
  - "use of undeclared identifier '_test_body_"
---
# Generate Unique Test Names in a Single-Header TEST Macro

## Goal
Produce a working single-header `TEST(name)` macro whose forward declaration, registrar instantiation, and body definition all share one unique suffix per invocation, so a test file containing many `TEST(...)` cases compiles cleanly.

## Scope
### In scope
- Macro-level fixes for unique test identifier generation: literal `__LINE__`/`__COUNTER__` after `##`, and mismatched counter values within one macro expansion.
- The two-level concatenation macro and the single-capture wrapper macro (`TEST(name) TEST_IMPL(name, __COUNTER__)`).
- Verifying macro diagnostics are gone by running the real compiler instead of trusting IDE/clangd reports.

### Out of scope
- clangd/IDE configuration and cross-file indexing behaviour.
- Test framework features beyond the `TEST` macro (assertions, runner, registration data structures).
- Linker errors and test assertion failures that appear after the macro compiles.

## Inputs
1. **Compiler error output** — type: text tool result; source: the real test build command; required: yes; constraint: must show macro diagnostics such as `redefinition of '_reg___LINE__'` or `use of undeclared identifier '_test_body_2'`; default: 无.
2. **Framework macro definitions** — type: source file (`tests/test_framework.hpp`); required: yes; constraint: only the macro layer (`TEST`, concat helpers) may be edited; default: 无.
3. **Build command** — type: shell/PowerShell script; source: agent-authored; required: yes; constraint: compiles each `tests/test_*.cpp` as its own translation unit (trace: `clang++ -std=c++23 -Iinclude -Itests -g -O0 <shared sources> <test file> -o <bin>`); default: 无.
4. **Test file with many cases** — type: source (`tests/test_atoms.cpp`, 17 `TEST(...)` cases); required: yes; constraint: multiple invocations in one TU are what expose the bug; default: 无.
5. **Compiler support for `__COUNTER__`** — type: toolchain property; required: yes; constraint: clang and MSVC provide it (trace used `clang++` on Windows); default: 无.

## Outputs
### Artifacts
- Edited `tests/test_framework.hpp` containing `EPILOG_CONCAT2(a, b) a##b`, `EPILOG_CONCAT(a, b) EPILOG_CONCAT2(a, b)`, `TEST_IMPL(name, uid)`, and `#define TEST(name) TEST_IMPL(name, __COUNTER__)`.
- Compiler output for the rebuilt suites.

### Success criteria
- Compiling every `tests/test_*.cpp` emits no diagnostic mentioning `_reg_`, `_test_body_`, `redefinition`, or `undeclared identifier` from the macro.
- Each suite links (link-stage errors may remain from unrelated causes) and, once linking, runs its cases.

### Failure criteria
- Any remaining `redefinition` or `undeclared identifier` error originating in `test_framework.hpp`.
- Test call sites had to be rewritten to make it compile.

## Preconditions
- A real build command can be executed; IDE/clangd diagnostics alone are insufficient (in this trace two "clangd false positive" dismissals were contradicted by the actual compiler).
- The compiler defines `__COUNTER__` (clang, MSVC do); otherwise stop and choose a different uniqueness scheme — 轨迹未提供 an alternative.
- Edits are confined to the macro definitions in the framework header; test call sites `TEST("...") { ... }` stay untouched.
- The test file contains more than one `TEST(...)` case, since a single case cannot reveal collisions.

## Procedure
### Step 1: Reproduce with the real compiler
- actions: compile one multi-case test file exactly as the build loop does; capture the full stderr.
- inputs: build command; `tests/test_atoms.cpp`.
- outputs: `error: redefinition of '_reg___LINE__'` / `redefinition of '_test_body___LINE__'` reported at every `TEST(...)` after the first.
- cautions: do not dismiss these as IDE noise — in this trace the agent twice labelled identical errors a clangd false positive, and the real compiler failed with the same errors both times.
- preserve: test files, framework API surface.
- next: go to Step 2 while the error names a literal `__LINE__`/`__COUNTER__` suffix.

### Step 2: Make pasted operands expand before concatenation
- actions: add `#define EPILOG_CONCAT2(a, b) a##b` and `#define EPILOG_CONCAT(a, b) EPILOG_CONCAT2(a, b)`; rewrite the `TEST` body to paste through `EPILOG_CONCAT`.
- inputs: current macro definitions.
- outputs: pasted names now contain real numbers instead of the literal text.
- cautions: merely swapping `__LINE__` for `__COUNTER__` directly inside `##` does **not** work — that failed attempt still produced literal `_reg___COUNTER__`.
- preserve: the registrar/registry machinery (`epilog_test::Registrar`, `run_all`).
- next: recompile; if the literal-suffix errors are gone, go to Step 3.

### Step 3: Capture `__COUNTER__` exactly once per `TEST` expansion
- actions: introduce `#define TEST_IMPL(name, uid)` holding the three statements (forward declaration, registrar instantiation, body definition) using `uid`, and reduce `TEST` to `#define TEST(name) TEST_IMPL(name, __COUNTER__)`.
- inputs: macro that currently writes `__COUNTER__` in three places.
- outputs: declaration, registration, and body all use the same number.
- cautions: writing `__COUNTER__` three times inside one macro increments it three times, producing mismatched names; adding a concat layer does not fix that.
- preserve: `TEST(name)` call-site syntax.
- next: recompile.

### Step 4: Verify with the compiler and then run the suites
- actions: rebuild all `tests/test_*.cpp`; confirm no macro diagnostics remain, then run the linked suites.
- inputs: unchanged build command.
- outputs: compile stage completes (only unrelated errors, e.g. a linker error from another cause, may remain); after linking, suites print pass counts.
- cautions: treat a *link* error as a different problem — it proves the macro stage succeeded.
- next: stop when macro diagnostics are gone and suites run.

## Decision Rules
### When pasted identifiers remain literal (`_reg___LINE__`, `_reg___COUNTER__`)
Use a two-level concatenation macro (`EPILOG_CONCAT2(a,b) a##b` / `EPILOG_CONCAT(a,b) EPILOG_CONCAT2(a,b)`) so the arguments expand before `##` pastes them. Verified: this removed the literal-suffix errors (the following compile failed only on a *different*, counter-mismatch error).

### When pasting works but declaration and body use different numbers (`_test_body_0` declared, `_test_body_2` referenced)
The unique counter was expanded more than once inside a single macro; capture it once by forwarding it to an implementation macro that takes the id as a parameter (`TEST(name) TEST_IMPL(name, __COUNTER__)`).

### When IDE/clangd reports macro errors that you are about to dismiss as false positives
Run the real build command first; in this trace both dismissals ("clangd false positive", "clangd is confused because it sees all files at once") were contradicted by the next real compile.

## Invariants
- Change only the macro layer; every `TEST("...") { ... }` call site must compile unchanged.
- Keep the framework's public API (`TEST`, `EXPECT`, `EXPECT_EQ`, `REQUIRE`, `epilog_test::run_all`) intact.
- Keep compiling each `test_*.cpp` as its own translation unit — do not "fix" collisions by merging or splitting files.
- Never report the macro fixed on the basis of IDE diagnostics; only a real compiler invocation counts.

## Common Failures
### Failure: dismissing real compiler errors as clangd noise
- symptoms: the agent labels `redefinition of '_reg___LINE__'` a clangd false positive because "each `test_*.cpp` is compiled as its own translation unit", then the real build fails with the same errors.
- causes: assuming cross-file IDE analysis is the only source of the report; the error was genuine macro behaviour.
- recovery: run the exact build command and read its stderr before theorising. Verified twice in the trace: dismissals at two points were both contradicted by the next real compile.

### Failure: swapping `__LINE__` for `__COUNTER__` inside `##` alone
- symptoms: `error: redefinition of '_reg___COUNTER__'` — the suffix is now the literal word `__COUNTER__`.
- causes: operands adjacent to `##` are not expanded in that position.
- recovery: add the two-level concat macro (Step 2).

### Failure: counter expanded multiple times in one macro
- symptoms: `error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?` — the forward declaration, registrar, and body reference three different numbers (`0`, `2`, ...).
- causes: `__COUNTER__` written three times in the macro body; each use increments it.
- recovery: capture it once in a wrapper macro that passes the id to `TEST_IMPL` (Step 3).

## Verification
- Compile every `tests/test_*.cpp`; stderr contains no `redefinition`, no `undeclared identifier`, and no `_reg___LINE__`/`_test_body___LINE__`/`_reg___COUNTER__` text.
- The compile stage completes for each file — any remaining message comes from `link` (e.g. an unrelated `LNK2019`), which proves the macro stage passed.
- After linking, each suite prints its pass count (trace: `22/22 tests passed` for the lexer suite, `17/17` for variables, `15/15` for terms, `18/18` for the unifier, `12/12` for the parser, `22/22` for the solver) and the summary reports `=== 6 PASSED, 1 FAILED ===` with the single failure being an unrelated file lock.
- Diff the test files: no `TEST(...)` call site was modified.

## Examples
### Example 1: 17 `TEST(...)` cases in one file all colliding
- input: `tests/test_atoms.cpp` with `#define TEST(name) static void _test_body_##__LINE__(); ...` in `test_framework.hpp`; compile fails with `redefinition of '_reg___LINE__'` at every case after the first.
- procedure: Step 1 reproduce with `clang++ -std=c++23 -Iinclude -Itests ...`; Step 2 add `EPILOG_CONCAT` two-level concat; Step 3 (after the counter-mismatch error) add `TEST_IMPL(name, uid)` and `#define TEST(name) TEST_IMPL(name, __COUNTER__)`; Step 4 recompile.
- expected result: the macro diagnostics disappear; the compile proceeds to the link stage, and after unrelated link fixes the suite runs and prints its pass count.
- parameterized values: macro prefix `_test_body_`/`_reg_`, framework path `tests/test_framework.hpp`, compiler `clang++ -std=c++23`, test file(s) `tests/test_*.cpp`.

### Example 2: counter mismatch inside one expansion
- input: macro using `EPILOG_CONCAT(_test_body_, __COUNTER__)` in three statements; compile fails with `use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`.
- procedure: move the three statements into `TEST_IMPL(name, uid)` and forward `__COUNTER__` once from `TEST`.
- expected result: declaration, registrar, and body share one suffix; the file compiles.
- parameterized values: counter macro (`__COUNTER__`), wrapper names (`TEST_IMPL`/`EPILOG_CONCAT`).

## Evidence
**Problem**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 946, source_part_index: 0, quote: `D:\Epilog\tests\test_atoms.cpp:26:1: error: redefinition of '_reg___LINE__'`, supports: with `_reg_##__LINE__` the suffix stayed literal, so every `TEST(...)` after the first defined the same identifier — the real compiler failed, contradicting the earlier dismissal of these errors as clangd noise.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 937, source_part_index: 0, quote: `The redefinition errors are a clangd false positive from the IDE analyzing all files together`, supports: the first recovery attempt was to dismiss the diagnostics — an approach the next real compile disproved.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 955, source_part_index: 0, quote: `D:\Epilog\tests\test_atoms.cpp:26:1: error: redefinition of '_reg___COUNTER__'`, supports: replacing `__LINE__` with `__COUNTER__` directly inside `##` still yields a literal suffix, so that change alone is insufficient.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 964, source_part_index: 0, quote: `D:\Epilog\tests\test_atoms.cpp:19:1: error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`, supports: once pasting worked, the remaining defect was that `__COUNTER__` incremented three times inside one `TEST` expansion.

**Action**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 957, source_part_index: 0, quote: `#define EPILOG_CONCAT2(a, b) a##b`, supports: two-level concatenation was added so arguments expand before pasting.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 968, source_part_index: 0, quote: `#define TEST(name) TEST_IMPL(name, __COUNTER__)`, supports: the counter is now captured once and forwarded to `TEST_IMPL(name, uid)`, which uses the same `uid` for declaration, registrar, and body.

**Verification**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 975, source_part_index: 0, quote: `solver-c181c1.o : error LNK2019: unresolved external symbol "int g_verbose"`, supports: after the final macro edit the compile stage completed for `test_atoms.cpp` — the only failure left was at link time, i.e. all macro diagnostics were gone.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1191, source_part_index: 0, quote: `=== 6 PASSED, 1 FAILED ===`, supports: with the final macro, all seven test files compile and six suites run to completion (the single failure was a file-locked binary, not a macro error).

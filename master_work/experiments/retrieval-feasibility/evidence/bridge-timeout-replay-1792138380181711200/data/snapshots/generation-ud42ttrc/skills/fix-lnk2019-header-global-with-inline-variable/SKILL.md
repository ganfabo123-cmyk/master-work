---
name: fix-lnk2019-header-global-with-inline-variable
description: Use when linking any binary (especially test binaries that exclude a main.cpp translation unit) fails with LNK2019/unresolved external symbol for a global declared 'extern' in a header and defined only in one excluded .cpp file. Helps the agent convert the global to an inline variable in the header and remove the stale definition. Requires a compiler/linker run to verify. Do not use when the symbol is genuinely defined in a linked translation unit or the error is a name-mangling mismatch of a function signature.
triggers:
  - "LNK2019"
  - "unresolved external symbol"
---
# Fix LNK2019 unresolved external for header-declared globals with inline variables

## Goal
Resolve LNK2019/unresolved-external errors for a global variable that is declared `extern` in a shared header but defined only in one translation unit (typically main.cpp) that is excluded from secondary binaries such as test executables, by making the header the single definition site.

## Scope
### In scope
- Link failures naming an unresolved data symbol (e.g. `error LNK2019: unresolved external symbol "int g_verbose"`) referenced from code compiled into test binaries.
- Converting the header declaration to an inline variable definition (`inline int g_verbose = 0;`) and deleting the now-duplicate definition from the former defining translation unit.
- Verifying by rebuilding both the test binaries and the main program.

### Out of scope
- Function-level unresolved externals caused by missing source files in the link line (fix by adding the file, not by inlining).
- Symbol name/mangling mismatches between declaration and definition.
- Constants better expressed as `constexpr`.

## Inputs
- Linker error output (string): required; must contain `LNK2019: unresolved external symbol` plus the mangled/unmangled symbol name; the referencing object (e.g. `solver-*.o`) tells you which translation unit needs it.
- Header file declaring the global (file path, e.g. `include/log.hpp`): required.
- Defining translation unit (file path, e.g. `main.cpp`) that is compiled into the main program but not into the test binaries: required.
- Build/link command for the secondary binaries (the test build script): required; no default.
- No defaults for the above.

## Outputs
### Artifacts
- Edited header where the global is defined as `inline T name = <initializer>;`.
- Edited former defining .cpp with the duplicate definition removed.

### Success criteria
- Every binary links: test executables no longer report LNK2019 for the symbol, and the main program still builds and runs (no duplicate-definition/multiple-definition errors).

### Failure criteria
- Multiple-definition errors at link time (old definition not removed).
- The main program's behavior changes because the variable's value is no longer set as before.

## Preconditions
- The error is a data or function symbol that is genuinely defined in exactly one .cpp that the failing binary does not link (confirmed by reading the header's `extern` declaration and the .cpp definition).
- You know which binaries exclude that .cpp (here: test binaries link the engine/parser/internals sources plus repl.cpp but not main.cpp).
- You can rebuild both the secondary binaries and the main program to check both directions.
- If the main program is currently running and holds its own executable open on Windows, terminate it before relinking.

## Procedure
### Step 1: Confirm the symbol's single definition sits in an excluded translation unit
- Actions: Read the header to find `extern T name;` and grep the sources for its definition. If the only definition is in a file not part of the failing binary's link line (e.g. main.cpp excluded from test builds), that is the cause.
- Inputs: linker output, header, sources.
- Outputs: confirmed diagnosis.
- Cautions: if the symbol is a function, prefer adding the source file to the link over any header trick.
- Preserve: the variable's name, type, and initializer semantics.
- Next: proceed to Step 2.

### Step 2: Convert to an inline variable in the header
- Actions: Replace `extern int g_verbose;` with `inline int g_verbose = 0;` in the header (C++17 inline variables give one definition across all translation units).
- Inputs: header.
- Outputs: edited header.
- Cautions: keep the initializer identical to the old definition so runtime behavior is unchanged; `inline` works for variables of literal type only — do not use it for non-literal types.
- Preserve: all uses of the variable.
- Next: proceed to Step 3.

### Step 3: Remove the old definition
- Actions: Delete the now-redundant definition (e.g. `int g_verbose = 0;`) from the former defining .cpp file.
- Inputs: defining .cpp.
- Outputs: edited file.
- Cautions: leaving it causes a multiple-definition link error on toolchains that do not treat it as the inline definition.
- Preserve: everything else in that file, including `main`.
- Next: rebuild everything.

### Step 4: Verify both kinds of binary
- Actions: Rebuild the test binaries and confirm the symbol error is gone and tests run; rebuild/run the main program to confirm it still works and that any code that sets the variable (e.g. a --verbose flag) still behaves.
- Inputs: build commands for both.
- Outputs: link/run results.
- Cautions: a locked output binary on Windows (`LNK1105`) is environmental; kill the stale process and retry.
- Next: stop when both build and run cleanly.

## Decision Rules
### When the unresolved symbol is a global variable declared extern in a header and defined in exactly one excluded .cpp
Replace the header declaration with an inline variable definition and delete the .cpp definition.

### When the unresolved symbol is a function
Do not inline it via the header; add the defining source file to the failing binary's link line instead.

### When the build now reports a multiple-definition error for the same symbol
The old definition was not removed (Step 3 incomplete); remove it rather than reverting the header.

### When the failing binary links every source except the one defining the symbol and adding that source would drag in main()
Prefer the inline-variable route: it avoids duplicate `main` and keeps the binary's source list minimal.

## Invariants
- The variable keeps its exact name, type, and initializer so observable behavior is unchanged in every binary.
- Exactly one definition conceptually exists: the inline definition in the header; the previous .cpp definition is deleted, not commented out or guarded.
- Both the secondary binaries (tests) and the primary program are rebuilt after the change; fixing one at the expense of the other is not acceptable.
- No unrelated source files are added to link lines as part of this fix.

## Common Failures
### Failure: LNK2019 persists for the data symbol in every test binary
- Symptoms: `error LNK2019: unresolved external symbol "int g_verbose" ... referenced in function "void __cdecl vlog(...)"` on each test link.
- Causes: the only definition lived in main.cpp, which test binaries do not link.
- Recovery: inline-variable definition in the header plus removal of the old definition.

### Failure: multiple-definition error after the header change
- Symptoms: the main program now fails to link with a duplicate symbol for the same name.
- Causes: the .cpp definition was left in place.
- Recovery: delete the old definition; do not remove the inline definition.

### Failure: behavior differs between the main program and tests
- Symptoms: verbose logging on in one binary, off in the other.
- Causes: the initializer in the header differs from the old definition, or the program's flag-setting path was disturbed.
- Recovery: restore the original initializer (`0`) and re-check the flag-handling code path in the main program.

## Verification
- Rebuild the test binaries: no LNK2019 mentions the symbol; each test binary links and starts.
- Run the test suites: they print PASS/FAIL lines as before (the fix must not alter engine behavior).
- Rebuild the main program: it links (proving no multiple definition) and still runs its acceptance scenario.
- Grep the sources: the symbol appears as an `inline` definition in exactly one header and nowhere else as a definition.

## Examples
### Example 1: verbose-logging flag unreachable from test binaries
- Input: `include/log.hpp` declares `extern int g_verbose;`, `vlog()` in the engine reads it, and only `main.cpp` defines `int g_verbose = 0;`. Every test link fails with `LNK2019: unresolved external symbol "int g_verbose"`.
- Procedure: replace the header declaration with `inline int g_verbose = 0;`, delete `int g_verbose = 0;` from main.cpp, rebuild tests and the main program.
- Expected result: tests link and run (in the trace the very next run compiled all suites and executed them, e.g. `22/22 tests passed` in the lexer suite); the main program still builds.
- Parameterized values: symbol `g_verbose`, type `int`, initializer `0`, header `include/log.hpp`, excluded TU `main.cpp`.

## Evidence
- problem — file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index 975, source_part_index 0, quote: "solver-c181c1.o : error LNK2019: unresolved external symbol \"int g_verbose\" (?g_verbose@@3HA) referenced in function \"void __cdecl vlog(char const *,char const *,...)\" (?vlog@@YAXPEBD0ZZ)", supports: all seven test binaries failed to link for the same reason — the engine object referenced a global defined only in the unlinked main.cpp.
- action — same file_id, source_index 977, source_part_index 0, quote: "inline int g_verbose = 0;", supports: the header declaration `extern int g_verbose;` was replaced with an inline variable definition (same edit shows the old string in old_string).
- action — same file_id, source_index 981, source_part_index 0, quote: "int main", supports: the duplicate definition was removed from main.cpp by deleting `int g_verbose = 0;\n\n` immediately before `int main`.
- verification — same file_id, source_index 984, source_part_index 0, quote: "=== 2 suite(s) PASSED, 5 FAILED ===", supports: immediately after the change every test binary linked and executed (two suites fully passed; the remaining failures were runtime test issues, not link errors), confirming the LNK2019 was resolved for all suites.

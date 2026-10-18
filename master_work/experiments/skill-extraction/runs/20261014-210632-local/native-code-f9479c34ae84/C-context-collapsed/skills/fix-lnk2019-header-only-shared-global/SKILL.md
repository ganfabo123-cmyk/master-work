---
name: fix-lnk2019-header-only-shared-global
description: Use when clang++/clang-cl on Windows reports LNK2019/LNK1120 unresolved external for a variable declared extern in a shared header while its only definition lives in a translation unit (e.g. main.cpp) that the test binaries do not link. Helps the agent relocate the definition into the header as an inline variable and rebuild the test executables. Requires a C++17-or-later toolchain and the ability to rebuild every affected binary. Do not use when the symbol is genuinely missing everywhere, when the project is C (no inline variables), or when the failure is a compile error rather than a link error.
---
# Fix LNK2019 Unresolved External for a Header-Declared Shared Global

## Goal
Eliminate the LNK2019/LNK1120 "unresolved external symbol" link failure for a variable that is declared `extern` in a shared header but defined only in a translation unit that the failing binaries do not link, so that every affected test executable links and starts.

## Scope
### In scope
- Link failures where the diagnostic names a specific symbol (`error LNK2019: unresolved external symbol "..."`) and that symbol is declared in a header included by both the application and the test binaries.
- Moving the single definition into the header as an `inline` variable (C++17 and later) and removing the now-duplicate definition from the application translation unit.
- Rebuilding the affected binaries with the same compiler command that produced the failure and confirming the linker diagnostics disappear.

### Out of scope
- Runtime failures of the linked binaries (e.g. tests that link but then crash or assert).
- Compile-time errors, template instantiation errors, or missing object files on the link line.
- C projects, where an `inline` variable definition is not available; this trajectory contains no verified alternative for that case.
- Any change to unrelated globals, build configuration, or optimization flags.

## Inputs
- **Linker diagnostic text** — string — from the failing build command's stdout/stderr — required — must contain `LNK2019` (or the GCC/Clang equivalent `undefined reference to`) and name the unresolved symbol — default: none.
- **Shared header path** — file path — from the diagnostic's referencing function and the include tree — required — must be a header included by both the application and the test binaries — default: none.
- **Definition site** — file path — from searching the project for the variable's definition — required — typically `main.cpp` / `main.c` in the application entry point — default: none.
- **Build command** — string — from the project's test build script — required — must be the exact command that produced the failure so the verification is comparable — default: none.
- **C++ standard in use** — enum — from the build flags — required — `inline` variables need `-std=c++17` or newer (the trajectory used `-std=c++23`) — default: `c++23`.
- **Unused for this skill** — none.

## Outputs
### Artifacts
- Edited header (e.g. `<project>/include/log.hpp`) containing the `inline` definition instead of the `extern` declaration.
- Edited application source (e.g. `<project>/main.cpp`) with the old definition removed.
- Rebuilt test binaries (e.g. `build/tests/*.exe`) produced by the same build command.

### Success criteria
- The build output for every previously failing binary contains no `LNK2019`, no `LNK1120`, and no `unresolved external symbol` text.
- Each affected binary links and, when executed, runs far enough to print its own output (test results, prompts, or its own error messages).

### Failure criteria
- Any `LNK2019`/`LNK1120`/`undefined reference` still naming the same symbol.
- A new duplicate-definition error (`LNK2005`, `multiple definition`) appears after the change.
- The toolchain cannot compile `inline` variables (e.g. a C build), in which case stop and report instead of improvising.

## Preconditions
- The failing link step is reproducible by re-running the project's build command; if it cannot be reproduced, stop and report.
- The diagnostic identifies the unresolved symbol by name and the referencing function, so the declaration site can be found.
- The header declaring the symbol is on the include path of every binary that fails to link.
- The compiler supports `inline` variables (`-std=c++17` or newer); the trajectory used clang++ 21 with `-std=c++23`. If the project is C or an older standard, stop and report rather than guessing an alternative.
- Permission to edit the header, the application source that holds the definition, and to rebuild the test binaries.
- If any earlier build left stale `.o`/`.obj` files or locked `.exe` files, resolve that first (the trajectory had to kill lingering test processes before recompiling); otherwise the rebuild result is not trustworthy.

## Procedure
### Step 1: Reproduce and classify the failure
- Actions: run the exact build command that builds the failing binaries; capture the full output; confirm the text contains `LNK2019`/`LNK1120` (MSVC/clang-cl ABI) or `undefined reference` (Itanium ABI) and names one symbol.
- Inputs: build command, toolchain flags.
- Outputs: classified diagnostic (link failure naming a symbol).
- Cautions: a script may print a generic label such as `COMPILE ERROR` even for link failures — classify by the linker text itself, not by the label.
- Preserve: the raw build output for later comparison.
- Next: if a specific symbol is named and a shared header declares it `extern`, go to Step 2; otherwise stop.

### Step 2: Locate declaration, definition, and link membership
- Actions: find the header that contains the `extern` declaration; find the single file that defines the symbol; confirm the failing link command does not list that file.
- Inputs: project sources, link command.
- Outputs: declaration path, definition path, confirmation that the defining TU is absent from the failing link.
- Cautions: do not add the definition's TU to the test link line as a quick workaround — it drags `main()` into test binaries.
- Preserve: unchanged build scripts.
- Next: proceed when exactly one definition exists and it lives in a TU the failing binaries do not link.

### Step 3: Replace the extern declaration with an inline definition
- Actions: edit the header so the declaration becomes a definition with internal-linkage-per-program semantics, e.g. change `extern int g_verbose;` to `inline int g_verbose = 0;`; then remove the old definition from the application source (e.g. delete `int g_verbose = 0;` above `int main`).
- Inputs: header path, definition path.
- Outputs: header with the `inline` definition; application source without the duplicate definition.
- Cautions: keep the initializer exactly as the old definition had it; do not change the symbol's type or name.
- Preserve: all other declarations and uses of the symbol; every call site keeps working unchanged.
- Next: rebuild.

### Step 4: Rebuild and compare against the original output
- Actions: re-run the same build command for all affected binaries; diff the diagnostics against the Step 1 capture.
- Inputs: build command.
- Outputs: new build output; rebuilt binaries.
- Cautions: stale object files or locked executables produce misleading results — clear or kill lingering processes first if the build fails oddly.
- Preserve: the binaries that already linked before the change.
- Next: proceed to verification when no `LNK2019`/`LNK1120` remains for the symbol.

### Step 5: Run the linked binaries
- Actions: execute each rebuilt binary and record its exit code and output.
- Inputs: rebuilt binaries.
- Outputs: per-binary exit code and stdout/stderr.
- Cautions: the binary may now fail for unrelated runtime reasons; that does not invalidate the link fix, but it must not be reported as success either.
- Preserve: test output for follow-up debugging.
- Next: stop when link diagnostics are gone; report any runtime failures separately.

## Decision Rules
### When the linker names one global variable as unresolved and it is declared `extern` in a shared header
Replace the `extern` declaration with an `inline` definition in that header, remove the definition from the application translation unit, and rebuild. This is the path verified in this trajectory.

### When the failing link command does not include the file that defines the symbol
Keep the definition out of the link line; move it into the header as above instead of adding the application source (and its `main`) to the test link.

### When the same build produces both link failures and, after the fix, runtime failures
Treat them as separate problems: the link fix is complete once the linker diagnostics disappear; the runtime failures are handled by their own diagnosis (see the large-struct stack-overflow skill if the process exits with -1073741571 and prints nothing).

### When the project is C, or the standard is older than C++17
No verified alternative exists in this trajectory — stop and report the limitation rather than inventing a linker-flag or weak-symbol workaround.

### When the unresolved symbol is a function rather than a variable
The same header-definition idea applies in principle, but this trajectory only verified a variable; state that as untested if attempted.

## Invariants
- Do not modify build scripts, compiler flags, or include paths to mask the unresolved symbol; the fix belongs in the declaration/definition placement.
- Do not add the application translation unit (the one containing `main`) to the test link line.
- Do not change the symbol's name, type, or initializer while relocating its definition.
- Do not touch unrelated warnings, tests, or sources during this fix, so the before/after build comparison stays attributable.
- Do not report success from a build that merely recompiled without relinking; success requires the linker stage output to be clean and the binary to run.
- Do not claim runtime correctness of binaries that linked but failed their tests.

## Common Failures
### Failure: Build script prints a misleading generic label
- Symptoms: the script prints `COMPILE ERROR: <file>` while the underlying text is `error LNK2019 ... linker command failed`.
- Causes: the script treats any non-zero exit from a combined compile+link invocation as a compile error.
- Recovery: read the actual diagnostic text and classify it as a link failure; fix the diagnosis step before editing code. Trajectory showed the same script later reporting clean compiles once the symbol moved into the header.

### Failure: Symbol still unresolved after the header edit
- Symptoms: `LNK2019` persists for the same symbol.
- Causes: stale object files, an `extern` declaration left somewhere, or the header edit not on the include path of the failing binary (none of these causes was observed failing in this trajectory — unconfirmed).
- Recovery: rebuild from clean, re-check that exactly one `inline` definition exists in a header every binary includes.

### Failure: Link succeeds but the binary dies immediately
- Symptoms: exit code `-1073741571` with no output at all.
- Causes: unrelated stack overflow from multi-MB fixed-size structs placed on the stack — not caused by this fix.
- Recovery: apply the large-struct static-storage fix; do not re-open the link change.

## Verification
Run the same build command that produced the original `LNK2019` and check each of the following in its output:

- No occurrence of `LNK2019` for the moved symbol.
- No occurrence of `LNK1120` (`1 unresolved externals`) in any binary's link step.
- No occurrence of `unresolved external symbol` anywhere in the output.
- Each previously failing binary is produced on disk (e.g. `build/tests/test_atoms.exe`, `test_lexer.exe`, ..., `test_variables.exe`).
- Executing a rebuilt binary reaches the program's own code: it prints test results, a REPL banner, or its own error message — anything except an empty immediate exit with a link-stage code.
- No new `LNK2005` / `multiple definition of` diagnostics appear (would indicate the old definition was not removed).

These are observable checks for future runs; they are not claims about any already-executed session.

## Examples
### Example 1: Shared `g_verbose` flag breaks every test link
- Input: seven test binaries built with `clang++ -std=c++23 -Iinclude -Itests <sources> tests/test_X.cpp -o build/tests/test_X.exe`; each fails with `error LNK2019: unresolved external symbol "int g_verbose" ... referenced in function "void __cdecl vlog(char const *,char const *,...)"` and `fatal error LNK1120: 1 unresolved externals`.
- Procedure: Step 1 classify as link failure; Step 2 find `extern int g_verbose;` in `include/log.hpp` and `int g_verbose = 0;` in `main.cpp` (not on the test link line); Step 3 change the header to `inline int g_verbose = 0;` and delete the definition from `main.cpp`; Step 4 rebuild with the same command.
- Expected result: no `LNK2019`/`LNK1120` in the rebuild output; all seven test executables are produced and start running (some may still fail their own assertions — report separately).
- Parameterized values: symbol `g_verbose`, header `include/log.hpp`, application source `main.cpp`, compiler `clang++ -std=c++23`, output dir `build/tests`.

### Example 2: Only one binary type fails
- Input: the main application links fine because it compiles `main.cpp`; only test binaries fail.
- Procedure: same Steps 1–5, with the confirmation in Step 2 that the definition's TU is missing exactly from the failing link commands.
- Expected result: application still builds unchanged after the header edit (the removed definition is replaced by the inline one), and test links now succeed.
- Parameterized values: application target `epilog`/`epilog.exe`, test targets `test_*.exe`.

## Evidence
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 975, source_part_index: 0 — quote: `solver-c181c1.o : error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)" (?vlog@@YAXPEBD0ZZ)` — supports: the failing state is a link error naming one global referenced by `vlog`, reproduced for all seven test binaries in the same tool result.
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-05`, source_index: 795, source_part_index: 0 — quote: `extern int g_verbose;` — supports: the declaration lived in the shared `log.hpp` header included by the tests, while the definition lived elsewhere.
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-05`, source_index: 834, source_part_index: 0 — quote: `int g_verbose = 0;` — supports: the only definition was in `main.cpp`, which is not linked into the test binaries.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 977, source_part_index: 0 — quote: `inline int g_verbose = 0;` — supports: the header declaration was converted to an inline definition (Edit on `d:\Epilog\include\log.hpp`, replacing `extern int g_verbose;`).
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 981, source_part_index: 0 — quote: `int g_verbose = 0;\n\nint main` — supports: the old definition in `main.cpp` was removed as part of the same change (its Edit `old_string` shows the definition being deleted in favor of `int main`).
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 984, source_part_index: 0 — quote: `FAIL: test_atoms` — supports: the rebuild that previously stopped at `COMPILE ERROR`/`LNK2019` for every test now reaches execution (the build script at index 983 prints `COMPILE ERROR: $($test.Name)` only when the compile/link step fails, and no such label appears in this result), i.e. the link errors are gone; remaining failures are runtime, not link.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 984, source_part_index: 0 — quote: `  PASS  lex empty string produces only EOF` — supports: at least one rebuilt binary runs its full test body after the fix.

---
name: fix-lnk2019-header-inline-global
description: Use when a secondary binary (test executable) fails to link with LNK2019/LNK1120 for a global variable declared extern in a shared header but defined only in the program's entry-point source. Helps the agent relocate the definition so every linked translation unit resolves the symbol without adding files to the link line. Requires an actionable link error naming the symbol and edit access to the header and the defining source. Do not use when the unresolved symbol is a function, when the defining object file is simply absent from the link line, or when tests fail only at runtime after linking succeeds.
triggers:
  - "LNK2019"
  - "LNK1120"
  - "unresolved external symbol"
---
# Fix LNK2019 for a shared global missing from a secondary link

## Goal
Eliminate LNK2019 unresolved-external errors for a header-declared global variable when linking secondary binaries (test executables) that exclude the program's entry-point translation unit, so every secondary binary links and runs.

## Scope
### In scope
- Global variables declared `extern` in a shared header whose only definition lives in a translation unit excluded from a secondary link (trajectory case: `g_verbose` declared in `include/log.hpp`, defined in `main.cpp`, while test binaries link only `internals/ parser/ engine/ repl.cpp`).
- Replacing the declaration with a C++17 (or later) `inline` variable definition in the header.
- Deleting the now-redundant definition in the entry-point source so no duplicate definition remains.
- Re-running the exact failing link and executing the resulting binaries, including handling a stale-file lock (LNK1105) as a separate, recoverable condition.

### Out of scope
- Unresolved symbols that are functions, or symbols whose defining object file is merely missing from the link line.
- Link failures of the main binary itself (this skill only guarantees the main binary still links after the header change).
- Runtime test failures that occur after linking succeeds (they are separate problems, e.g. the stack-overflow and string-concatenation issues seen later in the same session).
- Build-system restructuring such as creating a static library for shared sources.

## Inputs
- **Link error output** — type: tool result text from the failing build command. Source: the compiler/linker invocation. Required: yes. Constraint: must contain `LNK2019` naming the exact symbol and the referencing function, plus `LNK1120` if all binaries fail. Default: 无.
- **Shared header path** — type: file path. Source: project tree; it is where the `extern` declaration lives (trajectory: `include/log.hpp`). Required: yes. Constraint: header must be included by every referencing translation unit. Default: 无.
- **Defining source path** — type: file path. Source: the file containing the single definition (trajectory: `main.cpp` containing `int g_verbose = 0;`). Required: yes. Constraint: this translation unit must remain excluded from the secondary link. Default: 无.
- **Secondary link source list** — type: ordered list of .cpp files. Source: the failing build command. Required: yes. Constraint: must not gain the entry-point file. Default: 无.
- **C++ language standard in use** — type: version flag. Source: build flags (trajectory: `-std=c++23`). Required: yes. Constraint: C++17 or later for `inline` variables. Default: `-std=c++23` as in the traced build.
- **Secondary binary name pattern** — type: string. Source: build script (trajectory: `build\tests\test_*.cpp` compiled to `build\tests\<name>.exe`). Required: no. Constraint: none. Default: 无.

## Outputs
### Artifacts
- Updated shared header: the `extern T name;` declaration replaced by `inline T name = <original value>;` (trajectory: `include/log.hpp`).
- Updated entry-point source: the standalone definition removed (trajectory: `main.cpp` no longer contains `int g_verbose = 0;`).
- A relinked set of secondary binaries under the build output directory (trajectory: `build\tests\*.exe`).

### Success criteria
- The exact command that previously printed `error LNK2019: unresolved external symbol` now exits 0 for compile and link of every secondary binary.
- No `LNK2019` or `LNK1120` lines appear in the build output; each binary starts and produces its normal output.
- The main binary still compiles and links after the header change.

### Failure criteria
- `LNK2019` persists for the same or another symbol; or `LNK2005` (duplicate definition) appears; or the main binary fails to build; or binaries link but cannot start for an unrelated reason that was not addressed.

## Preconditions
- The unresolved symbol is a **variable**, identified from the mangled name (trajectory: `?g_verbose@@3HA` denotes `int g_verbose`, not a function).
- The symbol is declared `extern` in a header included by the referencing code, and its single definition sits in a translation unit that is excluded from the failing link and must stay excluded (adding `main.cpp` would collide with the test's own `main`).
- The toolchain supports C++17 inline variables; confirm from build flags (trajectory used `clang++ -std=c++23`).
- Edit access to both the header and the defining source is available.
- The build output can be re-run verbatim so before/after comparison is meaningful.
If any of these cannot be confirmed, stop and report the actual symbol kind and link line instead of applying this fix.

## Procedure
### Step 1: Confirm the symbol and the linkage topology
- actions: Read the link error; extract the symbol name, its mangled form, and the referencing function. List the sources compiled into the failing link command. Locate the definition and check whether its translation unit is in that list.
- inputs: link error output; build command.
- outputs: confirmation that the definition lives in a translation unit excluded from the secondary link (trajectory: `g_verbose` defined in `main.cpp`, which is not among the test link sources).
- cautions: `LNK2019` can also mean a missing object file or a genuinely undefined function — verify the mangled name denotes a variable before proceeding.
- preserve: the original failing build command, for the before/after comparison.
- next condition: proceed only if the definition exists in an excluded translation unit.

### Step 2: Turn the header declaration into an inline definition
- actions: In the shared header, replace `extern int g_verbose;` with `inline int g_verbose = 0;` — same type, same name, same initial value.
- inputs: shared header; original initializer from the defining source.
- outputs: a header-only definition that every including translation unit shares as one entity.
- cautions: do not change the symbol's type, name, or value; do not use `static` (that would create per-TU copies and break cross-TU sharing).
- next condition: the header now compiles standalone.

### Step 3: Remove the old out-of-header definition
- actions: Delete `int g_verbose = 0;` from the entry-point source, leaving `main` and everything else untouched.
- inputs: defining source file.
- outputs: no duplicate definition remains.
- cautions: if the same symbol is defined in more than one place, all duplicate definitions must go; check before rebuilding.
- next condition: both edits applied.

### Step 4: Re-run the exact failing link and execute the binaries
- actions: Re-run the identical build loop; check per-binary exit codes; grep the output for `LNK2019`/`LNK1120`; then run each produced binary. Also rebuild the main binary to confirm it still links.
- inputs: build command; output directory.
- outputs: link status per secondary binary; first execution output.
- cautions: `LNK1105: cannot close file` means a previous test process still holds the output file — kill the stale processes and relink rather than treating it as a regression of this fix.
- next condition: stop when no `LNK2019` remains and the binaries produce their expected runtime output; otherwise report the remaining error verbatim.

## Decision Rules
### When LNK2019 names a variable declared extern in a shared header and its defining translation unit is not in the failing link
Replace the declaration with an `inline` definition (same type, name, value) in the header, and delete the definition from the excluded translation unit. Do not add the excluded file to the link.

### When the build reports LNK1105 (cannot close the output file) after the header change
A previously launched test binary still holds the output file. Kill the stale processes, wait briefly, and relink. This is an environmental lock, not a regression of the header change.

### When more than one LNK2019 symbol appears
If the additional symbols are variables with the same extern-in-header pattern, apply the same treatment to each. If they are functions or the defining objects are genuinely absent from the build, stop and fix the build inputs instead — this rule set does not cover them.

## Invariants
- Do not add the entry-point translation unit to the secondary link to silence the error (it carries its own `main` and would collide with the test entry points).
- Do not change the symbol's name, type, or initial value; only its definition site changes.
- Do not use per-TU `static` in the header — that would silently break cross-TU sharing of the variable.
- Do not skip re-running the exact command that failed before reporting success; a claim of "fixed" requires that link to succeed.
- Do not report the whole build as fixed when only some binaries linked; report per-binary status.
- Do not attribute later runtime failures to this change; they are separate problems to be handled on their own evidence.

## Common Failures
### Failure: duplicate definition after the header change
symptoms: `LNK2005` naming the same symbol, or a redefinition compile error.
causes: the old definition in the entry-point source was left in place while the header gained the inline definition.
recovery: delete the out-of-header definition. Note: in the traced session both edits were made before the first relink, so this failure was never observed — the pairing follows from the language rules, not from a recorded incident.

### Failure: LNK2019 persists for a different symbol
symptoms: the same error class with another symbol name.
causes: another extern variable with the same pattern, or a genuinely missing source/object in the link line.
recovery: repeat the header-inline treatment for variables; for missing objects, correct the build inputs. Not observed in the traced session (only `g_verbose` was reported), so verify rather than assume.

### Failure: binaries link but crash immediately
symptoms: link succeeds, the binary exits with a negative code and no output.
causes: unrelated runtime problem (the traced session then hit stack overflow in test fixtures).
recovery: hand off to the runtime diagnosis; do not revert the header change.

## Verification
- Re-run the exact build command that previously emitted `error LNK2019: unresolved external symbol "int g_verbose"`; each secondary binary must reach a successful link (exit 0 for the compile+link step).
- Grep the combined build output for `LNK2019` and `LNK1120`: zero matches.
- Execute every produced binary; each must start and print its normal output (in the trace, suites printed pass counts such as `22/22 tests passed` after the fix).
- Rebuild the main binary and confirm it still compiles and links with the changed header.
- Confirm no `LNK2005` for the symbol appears anywhere in the output.
- Note: if a build step fails with LNK1105, kill stale processes and rerun before judging the result.

## Examples
### Example 1: header inline variable unblocks a test-only link
input: Building `tests/test_atoms.cpp` with sources `internals/*.cpp parser/*.cpp engine/*.cpp repl.cpp` (no `main.cpp`) fails with `solver-c181c1.o : error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)" (?vlog@@YAXPEBD0ZZ)` followed by `LNK1120: 1 unresolved externals` for all seven test binaries.
procedure: Step 1 confirm the mangled name denotes a variable and that its definition sits in `main.cpp`, which is not in the test link list; Step 2 replace `extern int g_verbose;` in the shared log header with `inline int g_verbose = 0;`; Step 3 delete `int g_verbose = 0;` from `main.cpp`; Step 4 relink every test binary and run them.
expected result: all test binaries link and execute; the build output contains no `LNK2019`/`LNK1120`; suites print pass counts such as `22/22 tests passed`; the main binary still builds.
parameterized values: symbol (`g_verbose`), header path, entry-point source, test source list, compiler (`clang++ -std=c++23`), output directory.

## Evidence
- problem — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 975, source_part_index: 0, quote: `solver-c181c1.o : error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)" (?vlog@@YAXPEBD0ZZ)`, supports: all seven test binaries failed to link because the global `g_verbose` had no definition among the linked translation units.
- action — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 977, source_part_index: 0, quote: `inline int g_verbose = 0;`, supports: the header edit replaced the extern declaration with an inline definition (new_string of the edit to `include/log.hpp`).
- action — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 981, source_part_index: 0, quote: `int g_verbose = 0;`, supports: the old definition was removed from the entry-point source (old_string of the edit to `main.cpp`).
- verification — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 984, source_part_index: 0, quote: `=== 2 suite(s) PASSED, 5 FAILED ===`, supports: after the change every one of the seven test binaries compiled, linked and executed (the remaining failures were runtime issues addressed by other fixes, not linker errors).
- verification — file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 984, source_part_index: 0, quote: `22/22 tests passed`, supports: the previously unlinkable test binaries now run and produce test results.

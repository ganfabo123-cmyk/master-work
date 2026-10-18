---
name: fix-lnk1120-header-extern-global
description: Use when clang++/MSVC links fail with LNK2019 unresolved external plus fatal error LNK1120 for a global (e.g. a logging flag) that is declared extern in a header and referenced by header inline functions, while its only definition lives in a translation unit that is not part of the failing target's link set (typical for test binaries). Helps the agent move the definition into the header as a C++17 inline variable, remove the duplicate definition, and re-verify the link. Requires the full linker output, the declaring header, the defining source file, and the exact link command/source list. Do not use when the unresolved symbol's defining TU is supposed to be linked (missing-source link errors), for LNK1105 locked-output errors, or for binaries that link but crash at runtime.
---
# Fix MSVC LNK1120/LNK2019 for an extern Global Declared in a Header but Defined Outside the Link Set

## Goal
Eliminate MSVC/clang++ linker failures `error LNK2019: unresolved external symbol` followed by `fatal error LNK1120: N unresolved externals` for a header-declared `extern` global by giving the header its own definition (C++17 `inline` variable) and removing the stale definition, so that every target that includes the header links and produces runnable binaries.

## Scope
### In scope
- C++ projects (trajectory used `clang++ -std=c++23` on Windows/MSVC linker) where a global such as a verbose-logging flag is declared `extern` in a header, used by `static`/`inline` helper functions defined in that header, and defined in exactly one `.cpp` that is excluded from some target's link set (e.g. test binaries that link all sources except `main.cpp`).
- The two-edit fix verified in the trajectory: change the header `extern` declaration into an `inline` variable definition, then delete the now-duplicate definition in the original defining `.cpp`.
- Re-running the exact same build/test link command as verification.

### Out of scope
- LNK2019 caused by a genuinely missing source/object that is intended to be linked (adding the TU to the link command was not attempted or verified in this trajectory).
- LNK1105 "cannot close file" locked-output errors (separate skill: clear-lnk1105-locked-output-exe).
- Test binaries that link successfully but crash at startup with exit code `-1073741571`; that is a runtime problem not resolved by this skill.
- C-language projects, where `inline` variable semantics differ and were not exercised.

## Inputs
- **Linker output text**: string, from the failing link/build tool result, required. Must contain `error LNK2019: unresolved external symbol` and `fatal error LNK1120` naming the symbol and the referencing function. Default: 无.
- **Declaring header**: file path (trajectory: `d:\Epilog\include\log.hpp`), from the project source tree, required. Must contain the `extern` declaration plus the header-inline function that references it. Default: 无.
- **Defining source file**: file path (trajectory: `d:\Epilog\main.cpp`), from the project source tree, required; it holds the single `int g_verbose = 0;`-style definition. Default: 无.
- **Link command or source list**: string (trajectory: the PowerShell `$SOURCES` array in the test loop, and the Makefile comment `# Shared object files (everything except main.o) linked into each test binary`), from build scripts, required; used to confirm the defining TU is absent from the failing target. Default: 无.
- **Language standard**: string/flag (trajectory: `-std=c++23`), from build flags, required; the inline-variable fix needs C++17 or newer. Default: 无.
- **Edit tool**: available file-editing capability, required. Default: 无.

## Outputs
### Artifacts
- Updated header (trajectory: `d:\Epilog\include\log.hpp`) where `extern int g_verbose;` is replaced by `inline int g_verbose = 0;` — format: edited source file.
- Updated defining source (trajectory: `d:\Epilog\main.cpp`) with the duplicate `int g_verbose = 0;` definition removed — format: edited source file.
- Rebuilt target binaries from the unchanged link command (trajectory: `build\tests\test_*.exe`) — format: executables.

### Success criteria
- The re-run link output contains no `LNK2019`, no `LNK1120`, and no `linker command failed with exit code 1120` for the previously unresolved symbol.
- Every test binary is produced (no `COMPILE ERROR:`/link-failure line for any suite) and each binary starts and prints its own test output.

### Failure criteria
- Any `LNK2019`/`LNK1120` still reported for the same symbol.
- A new compile error `Redefinition of '<symbol>'` appears, meaning the old definition was not removed.
- The compiler rejects the inline variable because the language standard is older than C++17.

## Preconditions
- The exact failing link command can be re-run (trajectory: the PowerShell per-test loop with `$SOURCES` and `-std=c++23 -Iinclude -Itests -g -O0`).
- The unresolved symbol is declared `extern` in a header and referenced only from functions defined in headers, while its sole definition lives in a `.cpp` that the failing target does not link; confirm this by reading the header, the defining file, and the link source list before editing. If the defining TU is supposed to be linked, stop — this skill's fix was not verified for that case.
- The project language standard is C++17 or newer (trajectory: `-std=c++23`); otherwise stop and report, because the inline-variable form is unavailable.
- No output file of the failing target is locked by a running process; if the build instead reports `LNK1105 ... error code 1224`, switch to the locked-output procedure first.
- An edit capability for both the header and the defining source file is available.

## Procedure
### Step 1: Pin down the unresolved symbol and its (missing) definition
- actions: Read the linker output and extract the symbol and referencing function (trajectory: `unresolved external symbol "int g_verbose"` referenced from `vlog(char const *,char const *,...)`). Grep the project for the `extern` declaration and for the single definition. Read the failing target's link source list and confirm the defining `.cpp` is absent (trajectory: test loop `$SOURCES` lists `repl.cpp` but not `main.cpp`; Makefile says `# Shared object files (everything except main.o) linked into each test binary`).
- inputs: linker output, header, defining source, link command.
- outputs: confirmed root cause: header-inline function needs a symbol whose defining TU is not linked into this target.
- cautions: do not "fix" this by editing the linker flags; the trajectory never verified that branch. Do not proceed if the defining TU is in fact on the link line.
- preserve: all other sources and the build scripts.
- next: go to Step 2 only when the declaration is in a header and the definition is outside the link set.

### Step 2: Give the header its own definition as an inline variable
- actions: Edit the header so the declaration becomes a definition, e.g. old_string `extern int g_verbose;` → new_string `inline int g_verbose = 0;` (trajectory source_index 977).
- inputs: header path from Step 1.
- outputs: header now defines the symbol for every includer.
- cautions: an inline variable requires C++17; a diagnostic such as `Inline variables are a C++17 extension` means the active standard is too low for at least one compilation path.
- preserve: the header's guard, includes, and function/macro bodies.
- next: after the edit, read compiler diagnostics before rebuilding.

### Step 3: Remove the now-duplicate definition in the original `.cpp`
- actions: When diagnostics report the old definition as an error (trajectory source_index 979: `Redefinition of 'g_verbose'` in `main.cpp`), delete it — trajectory source_index 981 replaced `int g_verbose = 0;\n\nint main` with `int main`.
- inputs: diagnostic attachment, defining source path.
- outputs: exactly one definition (the inline one) remains project-wide.
- cautions: keep the rest of `main()` untouched; this is a deletion of the definition only.
- preserve: all other code in the defining file.
- next: proceed to Step 4 when no redefinition diagnostic remains.

### Step 4: Re-run the original link command unchanged
- actions: Execute the same build/test script used to produce the LNK1120 failure (trajectory source_index 983 PowerShell loop).
- inputs: unchanged build script.
- outputs: new linker output.
- cautions: if the run reports `LNK1105 ... error code 1224` instead, an output exe is still locked — handle that separately before judging this fix.
- preserve: flags, source lists, output paths.
- next: go to Step 5 when the output contains no `LNK2019`/`LNK1120` lines.

### Step 5: Launch the produced binaries to confirm they are runnable
- actions: Run each rebuilt binary and capture its output/exit code.
- inputs: binaries from Step 4.
- outputs: evidence that linking succeeded end-to-end (trajectory: suites printing `22/22 tests passed`).
- cautions: a binary that links but exits with `-1073741571` is a separate runtime defect; report it as such instead of claiming full success.
- preserve: the binaries and logs.
- next: report link success; report test results separately.

## Decision Rules
### When LNK2019 names a symbol that is declared `extern` in a header and referenced from a header-defined function, and the defining `.cpp` is not in the failing target's link set
Replace the header declaration with an inline variable definition (Step 2) and delete the old definition (Step 3), then rebuild (Step 4). This is the only branch verified in the trajectory.

### When a `Redefinition of '<symbol>'` diagnostic appears right after Step 2
The original `.cpp` still defines the symbol; proceed with Step 3 to delete it. Do not revert the header change.

### When the compiler warns that inline variables are a language extension
The compilation path is below C++17. The trajectory did not verify any fallback for pre-C++17 standards; stop and report the standard mismatch instead of guessing.

### When the same build later fails with `LNK1105 ... error code 1224`
That is a locked-output failure, not an unresolved symbol; stop this skill and clear the lingering process first.

### When linking succeeds but a binary exits with `-1073741571` at startup
The unresolved-external problem is solved; treat the crash as an unrelated runtime issue (its root cause was never confirmed in the trajectory) and do not report the test suite as passing.

## Invariants
- Do not modify any file other than the declaring header and the file that held the duplicate definition.
- Do not change compiler flags, link commands, Makefiles, or source lists to work around the unresolved symbol; the trajectory's verified fix is source-level only.
- Keep exactly one definition of the symbol project-wide after the change.
- Do not skip the rebuild with the original link command — an edit without a re-link proves nothing.
- Do not report "tests pass" based on a successful link; report link success and test results separately, and only from observed output.
- Do not claim the runtime crash `-1073741571` is fixed; its cause and repair were never verified.
- Do not treat IDE diagnostics (e.g. the C++17-extension warning) as proof that the build failed or succeeded; the authoritative signal is the re-run link output.

## Common Failures
### Failure: header made `inline` but the old `.cpp` definition kept
- symptoms: compiler diagnostic `Redefinition of 'g_verbose'` on the defining file (trajectory source_index 979), build stops before linking.
- causes: the header now defines the variable while the original translation unit still defines it non-inline.
- recovery: delete the definition in the `.cpp` (Step 3), keeping the rest of the file intact.

### Failure: rebuilding while an output exe is still locked
- symptoms: the rerun fails with `LINK : fatal error LNK1105: cannot close file '...'; error code 1224` instead of LNK1120.
- causes: a process from a previous run still has the output binary open (trajectory diagnosis: `The binary is still running (file locked).`).
- recovery: terminate the lingering project process, sleep briefly, and rerun the same link command (see clear-lnk1105-locked-output-exe), then re-evaluate this skill's fix.

### Failure: link clean but binaries crash immediately with exit `-1073741571`
- symptoms: no linker errors; running a binary prints `(exit -1073741571)` with no test output (trajectory source_index 987).
- causes: not confirmed — the trajectory hypothesized oversized stack objects in test code but never verified a fix; the crash reappeared at source_index 1194 after relinking.
- recovery: treat as a separate runtime investigation; report only that linking succeeded.

### Failure: applying the fix while the unresolved symbol is actually missing from the link set for another reason
- symptoms: not exercised in this trajectory; if the defining TU is meant to be linked, this skill's edit may mask a broken build configuration.
- causes: trajectory did not test this case.
- recovery: stop and re-check the link source list before editing.

## Verification
Run these checks against the output of a rebuild with the original, unmodified link command (do not tick from memory — each item must be matched in fresh output):

1. Link output contains no `error LNK2019: unresolved external symbol` for the target symbol.
2. Link output contains no `fatal error LNK1120` and no `linker command failed with exit code 1120`.
3. No `COMPILE ERROR:`/link-failure line for any target in a multi-target loop; previously failing targets now appear as built.
4. No `Redefinition of '<symbol>'` diagnostic appears in compiler output after the change.
5. Each produced binary executes and prints its own runtime output (e.g. a suite line such as `22/22 tests passed`) instead of failing before any output.
6. Regression check: other suites that already built before the change still build and run afterwards (trajectory: suites moved from `=== 0 suite(s) PASSED, 7 FAILED ===` to `=== 2 suite(s) PASSED, 5 FAILED ===`, later `=== 4 suite(s) PASSED, 3 FAILED ===` with zero link errors).

Report separately: "link errors resolved" (checks 1–4) versus "test results" (checks 5–6); never merge them.

## Examples
### Example 1: test binaries fail to link on a header-only logging flag
- input: Linker output for seven test executables, each ending with `error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)"` and `fatal error LNK1120: 1 unresolved externals`; project built with `clang++ -std=c++23 -Iinclude -Itests -g -O0`; test loop links `internals/*.cpp parser/*.cpp engine/*.cpp repl.cpp` but not `main.cpp`, where `int g_verbose = 0;` was defined.
- procedure: Step 1 confirm `log.hpp` declares `extern int g_verbose;` and is included by the `vlog` header function while `main.cpp` is off the test link line; Step 2 edit `log.hpp` `extern int g_verbose;` → `inline int g_verbose = 0;`; Step 3 observe `Redefinition of 'g_verbose'` on `main.cpp` and delete `int g_verbose = 0;` from it; Step 4 rerun the identical PowerShell test loop; Step 5 run the produced binaries.
- expected result: the loop output contains zero `LNK2019`/`LNK1120` lines, every `build\tests\test_*.exe` is produced, and suites run and print results such as `22/22 tests passed`; overall summary changes from `=== 0 suite(s) PASSED, 7 FAILED ===` (all failures were link errors) to suites being counted as run (e.g. `=== 2 suite(s) PASSED, 5 FAILED ===`, later `=== 4 suite(s) PASSED, 3 FAILED ===`) with no `COMPILE ERROR` entries.
- parameterized values: symbol name (`g_verbose`), header (`include/log.hpp`), defining file (`main.cpp`), test source list (all sources except the main entry point), compiler standard (`-std=c++23`), output dir (`build\tests`).

### Example 2: keep a single definition when the entry-point TU is shared
- input: A project where `main.cpp` both defines the flag and is linked into the release binary but not into unit tests.
- procedure: Steps 2–4 only: make the header the single definition site and delete the definition from `main.cpp`; rebuild both the release target and the test target with their unchanged commands.
- expected result: both targets link with no unresolved-external errors and no redefinition diagnostics; the release binary still compiles because `main.cpp` merely lost a redundant definition.
- parameterized values: release target name (trajectory: `epilog`), test target pattern (`test_*.cpp`), flag type (`int` logging flag).

## Evidence
All quotes from file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original`.

- problem — source_index 975, source_part_index 0, quote: `solver-c181c1.o : error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)" build\tests\test_atoms.exe : fatal error LNK1120: 1 unresolved externals clang++: error: linker command failed with exit code 1120 (use -v to see invocation)`, supports: the exact LNK1120 failure mode this skill targets (all seven suites reported `COMPILE ERROR` with summary `=== 0 suite(s) PASSED, 7 FAILED ===` in the same event).

- problem (link set excludes the defining TU) — source_index 940, source_part_index 0, quote: `# Shared object files (everything except main.o) linked into each test binary`, supports: test binaries deliberately omit `main.o`, the file holding the definition.

- diagnosis — source_index 976, source_part_index 0, quote: `The only issue is \`g_verbose\` is \`extern int\` in \`log.hpp\` but defined in \`main.cpp\` which isn't linked into tests. Fix: change it to an \`inline\` definition in \`log.hpp\`:`, supports: problem interpretation and chosen action.

- action 1 — source_index 977, source_part_index 0, quote: `inline int g_verbose = 0;`, supports: header edit turning the `extern` declaration into an inline definition (the Edit call's old_string in the same event is `extern int g_verbose;`).

- action trigger — source_index 979, source_part_index 0, quote: `Redefinition of 'g_verbose'`, supports: after the header edit the old definition in `main.cpp` errors, requiring its removal.

- action 2 — source_index 981, source_part_index 0, quote: `int g_verbose = 0;\n\nint main`, supports: the Edit's old_string whose replacement (`int main`) deletes the duplicate definition in `main.cpp`.

- verification — source_index 984, source_part_index 0, quote: `=== 2 suite(s) PASSED, 5 FAILED ===`, supports: rerunning the identical link loop (source_index 983) produced no `COMPILE ERROR`/`LNK2019`/`LNK1120` lines for any of the seven suites — every binary linked and executed, whereas the pre-fix run (source_index 975) reported seven link failures.

- verification (later full run) — source_index 1048, source_part_index 0, quote: `=== 4 suite(s) PASSED, 3 FAILED ===`, supports: with the same source-level fix in place, all seven binaries compile and run repeatedly; remaining failures are test assertions, not linker errors.

- verification (individual suite runs) — source_index 1191, source_part_index 0, quote: `--- test_solver ---`, supports: rebuilt binaries launch and print test output (`22/22 tests passed` appears in the same event), confirming linked executables are runnable.

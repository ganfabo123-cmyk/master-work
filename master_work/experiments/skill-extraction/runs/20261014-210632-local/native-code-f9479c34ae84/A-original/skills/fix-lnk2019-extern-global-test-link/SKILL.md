---
name: fix-lnk2019-extern-global-test-link
description: Use when clang/MSVC linking of test binaries fails with LNK2019 unresolved external plus LNK1120 (linker exit code 1120 = 0x460) for a variable declared extern in a header. Helps the agent relocate the definition into the header as an inline variable, remove the duplicate definition, and re-verify by relinking every test binary. Requires an editable header plus the translation unit that holds the definition, a command that rebuilds all tests, and a C++ standard of at least C++17. Do not use when the defining source file is already on the link line, when the error is LNK1105 file-lock (see recover-lnk1105-locked-test-binary), or when the failure is a runtime crash after a successful link.
---
# Fix LNK2019/LNK1120 Unresolved extern Global in Test Links

## Goal
Eliminate the LNK2019/LNK1120 link failure (linker exit code 1120 = 0x460) that blocks every test binary because a global declared `extern` in a header is defined only in a translation unit the test link does not include, producing test executables that link and run.

## Scope
### In scope
- C++ header that declares `extern`-style global state (for example `extern int g_verbose;`) used by inline helpers in that header.
- The single translation unit that currently holds the definition (for example `main.cpp`) and is not part of the test link line.
- Converting the declaration to an inline definition in the header (C++17 or later) and deleting the now-duplicate definition.
- Relinking all test binaries and confirming the LNK2019/LNK1120 messages disappear.

### Out of scope
- LNK1105 "cannot close file" locking errors (covered by recover-lnk1105-locked-test-binary).
- Startup/runtime crashes of test binaries after a successful link (exit -1073741571; covered by windows-static-fixtures-avoid-stack-overflow).
- Assertion failures inside suites that already run.
- Projects whose compiler standard is below C++17 (the inline-variable form is rejected there; the trace never exercised that branch).

## Inputs
- **Link failure output**: string; source = tool result of the test build script (e.g. `Exit code 96` block); required; must contain `LNK2019: unresolved external symbol` and `fatal error LNK1120` / `linker command failed with exit code 1120`; default: none.
- **Header holding the extern declaration**: file path (e.g. `d:\Epilog\include\log.hpp`); source = path of the declaration named in the unresolved symbol; required; must be editable; default: none.
- **Translation unit holding the definition**: file path (e.g. `d:\Epilog\main.cpp`); source = the file whose `main` is excluded from the test link; required; default: none.
- **Test build-and-run command**: shell script (PowerShell loop compiling each `tests/test_*.cpp` with the full source list via `clang++ -std=c++23 ... -o build\tests\<name>.exe`); source = existing project workflow; required; default: none.
- **Language standard flag**: compile option (trace used `-std=c++23`); source = build script; required; must be at least C++17 for inline variables; default: none.

## Outputs
### Artifacts
- Edited header containing a single inline definition of the global (e.g. `inline int g_verbose = 0;` replacing `extern int g_verbose;`).
- Edited entry-point TU with the duplicate definition removed.
- Rebuilt test executables under `build\tests\*.exe` produced by the same build script.

### Success criteria
- No `LNK2019`, no `fatal error LNK1120`, and no `linker command failed with exit code 1120` anywhere in the build output.
- Every test suite is compiled, linked, launched, and emits its own PASS/FAIL lines or `N/N tests passed` line, plus a final summary count.

### Failure criteria
- Any test still reports `LNK2019` / exit code 1120.
- The header edit introduces `Redefinition of '<global>'` diagnostics.
- The compiler rejects the inline definition (inline variables need C++17 or newer).

## Preconditions
- `clang++` (or the project compiler) is installed and the project's test build script runs to completion; otherwise stop and report the missing toolchain.
- The failing output really shows `LNK2019` for a symbol that a header declares `extern` and only one non-test TU defines; if the defining source is already in the link list, stop and report — the trace gives no procedure for that case.
- The compile standard in the build script is C++17 or newer (the trace compiles with `-std=c++23`); if it is older, stop and report instead of forcing the inline form.
- Write access to the header and to the entry-point TU.
- A build command that links *every* test binary is available so the fix can be verified across all suites; without it, verification is limited to whichever suite you can link.

## Procedure
### Step 1: Read the link error and locate the declaration and definition
Actions: from the failing output take the unresolved symbol (e.g. `int g_verbose`), find its `extern` declaration in the header, and confirm the only definition sits in a TU (e.g. `main.cpp`) that the test link command does not include. Inputs: link failure output; test link command. Outputs: a one-line root cause (`extern in <header>, defined only in <main TU>, <main TU> not linked into tests`). Cautions: the mangled name (`?g_verbose@@3HA`) is decoration only; do not treat it as a second problem. Preserve: the test sources and the build script. Next: proceed only when the defining TU is absent from the link line.

### Step 2: Move the definition into the header
Actions: edit the header, replacing `extern int g_verbose;` with `inline int g_verbose = 0;`. Inputs: header path. Outputs: header with one inline definition. Cautions: inline variables require C++17 or newer; the IDE may warn `Inline variables are a C++17 extension`. Preserve: the rest of the header (logging macros, helpers). Next: Step 3.

### Step 3: Delete the duplicate definition in the entry-point TU
Actions: edit `main.cpp` so the standalone `int g_verbose = 0;` line is removed and `int main` follows directly; watch the editor diagnostics until `Redefinition of 'g_verbose'` disappears. Inputs: entry-point TU path. Outputs: a single remaining definition. Cautions: keeping both definitions turns a link error into a compile error. Preserve: `main()` logic and all other globals. Next: Step 4.

### Step 4: Relink every test binary with the unchanged build script
Actions: re-run the same PowerShell loop that compiles `tests/test_*.cpp` against the full source list into `build\tests\*.exe` and executes each binary. Inputs: build-and-run script. Outputs: per-suite compile status, per-suite output, and a final `=== N suite(s) PASSED, M FAILED ===` line. Cautions: a suite that compiles but crashes at startup is a different defect; do not revert the link fix for it. Preserve: flags, source list, and output directory. Next: stop when no LNK2019/LNK1120 line remains and every suite produced run output.

## Decision Rules
### When LNK2019 names a symbol that a header declares extern and only a non-test TU defines
Replace the `extern` declaration with an inline definition in the header (`inline int g_verbose = 0;`) so every test TU gets its own merged definition.

### When the header edit triggers "Redefinition of '<global>'"
The old out-of-line definition still exists in the entry-point TU; delete it so exactly one definition form remains.

### When the compiler warns that inline variables are a C++17 extension
The standard flag is at the boundary; the trace proceeded with `-std=c++23` and only a warning. If the project standard is older than C++17, stop and report rather than changing the language mode unilaterally.

### When relinking succeeds but suites still fail
The link defect is fixed; remaining `FAIL` lines or exit `-1073741571` are runtime defects from another cause (see windows-static-fixtures-avoid-stack-overflow). Keep the inline fix and continue with that separate procedure.

### When the defining source already appears in the test link line
The trace does not cover this branch; do not apply this skill — report the mismatch and choose another diagnosis.

## Invariants
- Touch only the header declaration and the duplicate definition; test sources, engine sources, and build script stay byte-identical.
- Exactly one definition form of the global survives (inline in the header); never keep both the inline and the out-of-line definition.
- Never disable, stub, or `#define away` the global to force a link.
- Never skip the full relink of all test binaries — a partial recompile of one file is not evidence.
- Do not treat IDE/clangd diagnostics as build results; only the compiler and linker output counts.
- Do not report the suites as passing; report only what the build script printed (in the trace: linking succeeded while 5 of 7 suites still failed for unrelated reasons).
- Do not change the language standard, optimization flags, or source list as part of this fix.

## Common Failures
### Failure: Redefinition after making the variable inline
Symptoms: editor/compiler diagnostic `Redefinition of 'g_verbose'` on `main.cpp` right after the header edit. Causes: the original `int g_verbose = 0;` in the entry-point TU was left in place next to the new inline definition. Recovery: delete the out-of-line definition, keep `int main`, and re-check that the diagnostic clears before relinking.

### Failure: Expecting the link fix to make the whole suite green
Symptoms: no more LNK2019, but the summary still reads `=== 2 suite(s) PASSED, 5 FAILED ===` with suites printing nothing. Causes: independent runtime defect (startup stack overflow, exit -1073741571) unrelated to the unresolved symbol. Recovery: keep the link fix, then treat the crash as a separate problem; the link step is already verified at that point.

### Failure: Undoing the inline definition because a test still crashes
Symptoms: revert of the header edit followed by LNK2019 returning for all suites. Causes: conflating link success with test success. Recovery: restore the inline definition and relink; track the runtime failure separately.

### Failure: Unresolved symbol whose definition TU is already linked
Symptoms: LNK2019 persists after the header change. Causes: a different root cause (wrong linkage, missing object, C/C++ name mismatch) — not observed in this trace. Recovery: stop applying this skill and report; the trace provides no verified procedure for this case.

## Verification
Run the project's full test build-and-run script and check all of the following in its output:
- No line contains `LNK2019`, `fatal error LNK1120`, or `linker command failed with exit code 1120` (hex 0x460).
- No suite is reported as `COMPILE ERROR: <name>.cpp`, meaning every `tests/test_*.cpp` reached the link and run stage.
- Each suite that runs prints its own test lines (`PASS ...` or `FAIL ...`) and a `N/N tests passed` summary.
- The script prints an end-of-run tally such as `=== 2 suite(s) PASSED, 5 FAILED ===`, proving the harness executed rather than aborted at link time.
- The editor diagnostic `Redefinition of 'g_verbose'` is gone from the entry-point TU.
- Main-program link is re-checked separately if the project also builds `main.cpp` with the edited header (the trace did not show a post-edit main-binary build; report this as unverified if you skip it).

## Examples
### Example 1: Seven test suites blocked by one unresolved global
Input: build output where all 7 suites report `COMPILE ERROR` with `LNK2019: unresolved external symbol "int g_verbose"` and `fatal error LNK1120: 1 unresolved externals ... exit code 1120`; header `include/log.hpp` declares `extern int g_verbose;`; `main.cpp` defines it; the test link compiles 10 engine sources plus one `tests/test_*.cpp` and never includes `main.cpp`.
Procedure: Step 1 (root cause: definition TU not linked), Step 2 (header → `inline int g_verbose = 0;`), Step 3 (drop `int g_verbose = 0;` from `main.cpp`), Step 4 (re-run the script).
Expected result: no LNK lines; suites run and the script ends with a tally such as `=== 2 suite(s) PASSED, 5 FAILED ===` — link failure resolved, runtime failures reported separately.
Parameterized values: compiler `clang++ -std=c++23 -Iinclude -Itests -g -O0`; output dir `build\tests`; suites `test_atoms, test_lexer, test_parser, test_solver, test_terms, test_unifier, test_variables`.

### Example 2: Verify after the second edit, not after the first
Input: header edited but `main.cpp` still contains the old definition; editor reports `Redefinition of 'g_verbose'`.
Procedure: Step 3 only (remove duplicate), then Step 4.
Expected result: diagnostic disappears and the relink shows no LNK2019; if you had stopped after Step 2 you would have traded a link error for a compile error.
Parameterized values: file `d:\Epilog\main.cpp`, old string `int g_verbose = 0;` immediately before `int main`.

## Evidence
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 975; source_part_index: 0; quote: `solver-c181c1.o : error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)" (?vlog@@YAXPEBD0ZZ) build\tests\test_atoms.exe : fatal error LNK1120: 1 unresolved externals clang++: error: linker command failed with exit code 1120 (use -v to see invocation)`; supports: problem — every suite fails to link with LNK2019 + LNK1120 and linker exit code 1120 (0x460).
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 976; source_part_index: 0; quote: `The only issue is \`g_verbose\` is \`extern int\` in \`log.hpp\` but defined in \`main.cpp\` which isn't linked into tests.`; supports: problem diagnosis — declaration/definition split across a TU excluded from the test link (assistant judgement preceding the fix).
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 977; source_part_index: 0; quote: `inline int g_verbose = 0;`; supports: action — header edited from `extern int g_verbose;` to an inline definition.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 979; source_part_index: 0; quote: `Redefinition of 'g_verbose'`; supports: side effect of the action — the old definition in `main.cpp` must also be removed (clang diagnostic on `main.cpp`).
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 981; source_part_index: 0; quote: `int g_verbose = 0;\n\nint main`; supports: action — duplicate definition removed from `main.cpp`.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 984; source_part_index: 0; quote: `=== 2 suite(s) PASSED, 5 FAILED ===`; supports: verification — after the two edits the same script reports no `COMPILE ERROR` (all 7 binaries linked and ran) and produced a final tally; suites that printed nothing crashed at runtime, which is a separate defect.

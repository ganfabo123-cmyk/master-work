---
name: fix-msvc-lnk1107-odin-dll-import
description: Use when an Odin Windows build fails with MSVC linker LNK1107 'invalid or corrupt file' on a DLL referenced by `foreign import`. Helps the agent generate an import library (.lib) from a .def file, relink the project, and verify the FFI binary runs end-to-end. Requires clang/llvm toolchain (llvm-dlltool or clang++ with -Wl,/DEF), Odin using the MSVC linker, and the DLL's exported C function list. Do not use when the DLL is genuinely corrupt, or for Linux/macOS shared-library linking.
---
# Fix MSVC LNK1107 when Odin foreign-imports a Windows DLL

## Goal
Eliminate the MSVC linker error `LNK1107: invalid or corrupt file` that occurs when an Odin project's `foreign import` points directly at a Windows DLL, by generating an import library (.lib) from the DLL's export list, switching the `foreign import` to the .lib, and verifying the built executable loads the DLL and passes a runtime FFI smoke test.

## Scope
### In scope
- Diagnosing LNK1107 on a path ending in `.dll` when building an Odin project on Windows with the MSVC linker (`odin build`).
- Confirming the DLL itself is a valid PE binary (so the error is "linker cannot read a DLL as an input library", not file corruption).
- Generating an import library with `llvm-dlltool` from a hand-written `.def` file listing the C FFI exports.
- Generating the import library automatically at DLL link time via `clang++ -shared -Wl,/DEF:<name>.def`.
- Editing the Odin `foreign import` declaration to reference the `.lib` instead of the `.dll`.
- End-to-end verification: `odin build` succeeds and the produced exe runs and calls into the DLL (runtime smoke test with exit 0).

### Out of scope
- Linux/macOS `foreign import` of `.so`/`.a` files.
- Genuinely corrupt DLLs (e.g., truncated files, wrong architecture) — LNK1107 can also stem from real corruption; this skill assumes PE validity was confirmed first.
- Extracting export names from a DLL when no header is available (`llvm-nm` on the DLL returned "no symbols" in the observed case).
- Non-linker failures: runtime DLL-not-found, Raylib/vendor-library linking, Odin compiler installation.

## Inputs
- **LNK1107 build output**: string; from running `odin build src -out:build\\dmls.exe` (or the project's build script) on Windows; required; must contain `fatal error LNK1107: invalid or corrupt file: cannot read at <offset>` naming a `.dll` path; default: the current failing build log.
- **Odin foreign import declaration**: source text in the project's Odin bridge file (e.g., `src/bridge.odin`); required; must currently reference the DLL path, e.g. `foreign import epilog_lib "../engine/epilog/epilog.dll"`; default: existing project source.
- **C FFI export list**: list of exported `extern "C"` function names (from the public header, e.g. `epilog_ffi.h`); required for writing the `.def` file; no default — if unavailable, export discovery from the DLL may fail (`llvm-nm` returned "no symbols" in the observed case).
- **DLL source tree and build script**: C/C++ sources plus a `clang++`-based build script (e.g., `build.bat`); optional but preferred for the automatic `.lib` generation path; default: project's existing build script.
- **LLVM/clang toolchain**: `clang++` (≥ 17 in the observed project) and `llvm-dlltool`; required; must be on PATH; default: system installation.
- **Odin compiler**: `odin` on PATH, configured to use the MSVC linker on Windows; required; default: system installation.
- **Target machine architecture**: x86-64 Windows (`x86_64-pc-windows-msvc`); required to pick `llvm-dlltool -m i386:x86-64`; default: x86-64.

## Outputs
### Artifacts
- **Module-definition file**: `<engine_dir>/<name>.def` (e.g., `engine/epilog/epilog.def`) — plain text with `LIBRARY <name>` and an `EXPORTS` list of every FFI function.
- **Import library**: `<engine_dir>/<name>.lib` (e.g., `engine/epilog/epilog.lib`) — COFF import library, either produced by `llvm-dlltool` or automatically by the DLL linker via `-Wl,/DEF`.
- **Updated Odin source**: the bridge file's Windows branch now reads `foreign import epilog_lib "../engine/epilog/epilog.lib"` (path adapted to the project).
- **Updated build script** (when using the automatic path): the DLL compile line includes `-Wl,/DEF:<engine_dir>\<name>.def` so `<name>.lib` is regenerated on every DLL build.
- **Built executable**: e.g., `build/dmls.exe`, linking successfully with no LNK1107.

### Success criteria
- `odin build` completes with exit code 0 and no LNK1107 diagnostic.
- The DLL build step reports creation of the import library (e.g., `Creating library engine\epilog\epilog.lib and object engine\epilog\epilog.exp`).
- Running the produced exe from the directory containing the DLL executes FFI calls successfully and exits 0 (smoke test prints expected query results).

### Failure criteria
- LNK1107 persists after the `foreign import` points at the `.lib`.
- Link fails with unresolved external symbols (the `.def` export list does not match what the Odin code imports).
- The exe builds but fails to start or crashes when calling the DLL (DLL missing from the exe directory or exports missing from the DLL).

## Preconditions
- **Windows host with MSVC linker**: the error is produced by the MSVC `link.exe` invoked by Odin; confirm the build is running on Windows with the MSVC toolchain reachable. Otherwise this skill does not apply.
- **Valid PE DLL**: verify with `file <path>/<name>.dll` that the DLL is a PE executable for MS Windows, x86-64. In the observed case `file` reported `PE32+ executable for MS Windows 6.00 (DLL), x86-64, 6 sections` while the linker still said LNK1107 — confirming the DLL was not corrupt. If `file` shows a non-PE or wrong-architecture file, stop and fix the DLL build instead.
- **LLVM tools on PATH**: `llvm-dlltool` (for the manual import-lib path) and/or `clang++` supporting `-target x86_64-pc-windows-msvc` and `-Wl,/DEF:` (for the automatic path). If neither is available, stop and report the missing dependency.
- **Export list obtainable**: you must know the DLL's exported C function names, ideally from the public FFI header. Do not rely on scanning the DLL for symbols — `llvm-nm epilog.dll | grep -i 'epilog_'` returned `epilog.dll: no symbols` in the observed case.
- **Odin build reproduces the error**: run the failing `odin build` command once and capture the exact LNK1107 message before changing anything.

## Procedure
### Step 1: Confirm the diagnosis
- Actions: Read the failing build output; confirm it contains `fatal error LNK1107: invalid or corrupt file: cannot read at <offset>` and that the offending path ends in `.dll`. Locate the `foreign import` line in the Odin source that names that DLL. Run `file "<path>/<name>.dll"` to confirm the DLL is a valid x86-64 PE DLL.
- Inputs: build log, Odin bridge source, DLL path.
- Outputs: confirmed diagnosis "linker was fed a DLL where it expects an import library".
- Cautions: do not waste attempts on rebuilding or copying the DLL first — in the observed trajectory, copying the DLL to the build directory (twice) and adding `-extra-linker-flags:"/LIBPATH:engine\\epilog"` all still produced the identical LNK1107.
- Preserve: the existing DLL; it is fine and will still be needed at runtime.
- Next: proceed to Step 2 with the export list from the FFI header.

### Step 2: Write the module-definition (.def) file
- Actions: Create `<engine_dir>/<name>.def` containing `LIBRARY <name>` followed by `EXPORTS` and one line per exported C function (e.g., `epilog_create`, `epilog_destroy`, `epilog_load_string`, `epilog_query`, … `epilog_version_string` — 15 exports in the observed case). Derive the list from the public FFI header, not from scanning the DLL.
- Inputs: public FFI header export list.
- Outputs: `<engine_dir>/<name>.def`.
- Cautions: `llvm-nm <name>.dll` returned `no symbols` in the observed case — export discovery from the built DLL is unreliable here; the header is the source of truth. Every function the Odin `foreign` block declares must appear in the `EXPORTS` list or linking will fail later with unresolved externals.
- Preserve: keep the `.def` in the repo and regenerate/extend it whenever the FFI surface changes.
- Next: proceed to generate the import library.

### Step 3: Generate the import library
- Actions: Run `llvm-dlltool -m i386:x86-64 -d <name>.def -l <name>.lib` in the engine directory. Verify the file exists (observed: a 4458-byte `epilog.lib`).
- Inputs: `<name>.def`, llvm-dlltool.
- Outputs: `<engine_dir>/<name>.lib`.
- Cautions: `-m i386:x86-64` must match the DLL architecture; a mismatched machine type produces a link failure.
- Preserve: keep the DLL unchanged.
- Next: proceed to update the Odin source.

### Step 4: Point the `foreign import` at the import library
- Actions: Edit the Odin bridge file so the Windows branch imports the `.lib`: replace `foreign import epilog_lib "../engine/epilog/epilog.dll"` with `foreign import epilog_lib "../engine/epilog/epilog.lib"`. Keep the non-Windows branch (`.so`) untouched.
- Inputs: `<name>.lib` path relative to the Odin source file.
- Outputs: updated bridge source.
- Cautions: the `.lib` must be resolvable relative to the file containing the `foreign import`, or reachable via linker library paths.
- Preserve: the rest of the `foreign` block and all procedure declarations.
- Next: proceed to build and run.

### Step 5: Rebuild and run the runtime smoke test
- Actions: Copy the DLL into the output directory (it is still required at runtime), run `odin build src -out:build\\dmls.exe`, then execute the built exe from that directory and check its exit code and output.
- Inputs: updated source, `<name>.lib`, `<name>.dll` next to the exe.
- Outputs: built exe; smoke-test output (observed: FFI queries returning correct solution counts, `=== Bridge smoke test: PASS ===`, `Exit: 0`).
- Cautions: a clean link does not prove runtime loading — always execute the binary and exercise at least one call into the DLL.
- Preserve: the DLL copy step in the build script; the import library is link-time only.
- Next: proceed to Step 6 to make the setup durable.

### Step 6: Make the DLL build emit the import library automatically
- Actions: In the DLL build script, pass the `.def` to the linker so the `.lib` is regenerated whenever the DLL is rebuilt, e.g. `clang++ <flags> -shared -Wl,/DEF:<engine_dir>\epilog.def <sources> -o "<name>.dll"`. Verify a clean build reports both `Creating library engine\epilog\epilog.lib and object engine\epilog\epilog.exp` and a successful Odin link, then re-run the smoke test.
- Inputs: `<name>.def`, DLL build script.
- Outputs: updated build script; import library regenerated in lockstep with the DLL.
- Cautions: removing the manual `llvm-dlltool` step is safe only after the `-Wl,/DEF` build has been verified to produce a `.lib` that links the Odin project.
- Preserve: the existing DLL output path so the runtime copy step keeps working.
- Next: stop when the full build script runs clean and the smoke test passes.

## Decision Rules
### When LNK1107 names a `.dll` that `file` confirms is a valid PE32+ x86-64 DLL
Treat the DLL as fine and the linkage setup as wrong: MSVC `link.exe` cannot consume a DLL as an input library. Generate an import library (Steps 2–4) instead of rebuilding or re-copying the DLL. Evidence: the identical LNK1107 persisted across a fresh DLL copy and a rebuild, while `file` kept reporting a valid PE32+ DLL.

### When copying the DLL to the build directory or adding `/LIBPATH` does not remove LNK1107
Stop retrying path-level fixes. In the observed trajectory, `Copy-Item ...epilog.dll build\` (twice) and `-extra-linker-flags:"/LIBPATH:engine\\epilog"` all reproduced `fatal error LNK1107 ... cannot read at 0x2F8`. The only change that fixed linking was switching the `foreign import` target from the DLL to a `.lib`.

### When the DLL's exports cannot be enumerated (`llvm-nm <dll>` → "no symbols")
Do not attempt to derive the export list from the binary; author the `.def` `EXPORTS` list from the public C FFI header, which enumerates the full `extern "C"` surface.

### When the project owns the DLL build script
Prefer the durable fix: add `-Wl,/DEF:<name>.def` to the DLL link step so `<name>.lib` and `<name>.exp` are regenerated with every DLL build, replacing the one-shot `llvm-dlltool` generation. Evidence: the updated script printed `Creating library engine\epilog\epilog.lib and object engine\epilog\epilog.exp` followed by a successful Odin build and passing smoke test.

### When the link succeeds but verification is requested
A clean `odin build` alone is insufficient: run the exe from the directory containing the DLL and exercise at least one FFI call, checking both program output and exit code.

## Invariants
- Never report the DLL as corrupt when `file` identifies it as a valid PE32+ executable — LNK1107 here means "a DLL was passed where a library is expected".
- The import library is link-time only; the DLL must still exist next to the produced executable (or on PATH) at runtime. Both artifacts are required, for different phases.
- The `.def` `EXPORTS` list must stay in sync with the C FFI header and the Odin `foreign` block; adding a new exported FFI function without updating the `.def` breaks the next link or DLL rebuild.
- Do not delete the non-Windows (`else` branch, `.so`) `foreign import` or other platform-conditional code while fixing the Windows branch.
- Do not declare success from a clean compile alone — runtime execution of the exe with at least one DLL call is the acceptance test.
- Keep the failing-attempt record straight: rebuilding/copying the DLL and `/LIBPATH` flags were tried and did not help; do not reintroduce them as fixes.

## Common Failures
### Failure: LNK1107 persists after rebuilding or re-copying the DLL
- Symptoms: every `odin build` ends with `fatal error LNK1107: invalid or corrupt file: cannot read at 0x2F8`, identical before and after DLL rebuilds and after copying the DLL into `build/`.
- Causes: the Odin `foreign import` still names the `.dll`; the MSVC linker is being handed the DLL as an input file. Verified in the observed case — the error was byte-identical across three attempts that changed only the DLL/build-dir state.
- Recovery: switch the `foreign import` path to the `.lib` (Step 4) after generating it (Steps 2–3).

### Failure: `llvm-nm <name>.dll` reports "no symbols"
- Symptoms: export enumeration from the DLL yields nothing, blocking an automated `.def` generation.
- Causes: not confirmed in the trajectory; the DLL built without a symbol table visible to `llvm-nm`.
- Recovery: write the `.def` manually from the public FFI header's function list (the observed successful path).

### Failure: Odin link fails with unresolved external symbols after switching to the `.lib`
- Symptoms: LNK1107 is gone but `link.exe` reports unresolved externals for one or more FFI functions.
- Causes: the `.def` EXPORTS list (and therefore the import library) is missing functions declared in the Odin `foreign` block; likely if the FFI header grew after the `.def` was written.
- Recovery: diff the Odin `foreign` block against the `.def`, add missing exports, regenerate the `.lib` (or rebuild the DLL with `-Wl,/DEF`).

### Failure: exe links and builds but fails at startup or on first FFI call
- Symptoms: build exits 0, but running the exe from another directory fails to find the DLL.
- Causes: the import library resolved at link time, but the actual DLL is not next to the exe or on PATH.
- Recovery: copy `<name>.dll` into the output directory as part of the build script (observed pattern: `Copy-Item -Path "engine\epilog\epilog.dll" -Destination "build\" -Force` before/after `odin build`).

### Failure: `Copy-Item` "Cannot overwrite the item ... with itself"
- Symptoms: a no-op copy of `<name>.lib` onto its own path errors in PowerShell, though the build continues.
- Causes: a redundant copy step added to the build script.
- Recovery: remove the self-copy line; the `.lib` is already in its final location.

## Verification
Run these checks in order after applying the fix; each is an observable output, not an assumption:

1. **PE sanity**: `file "<engine_dir>/<name>.dll"` prints `PE32+ executable for MS Windows ... (DLL), x86-64` — the DLL was never the problem.
2. **Import library exists**: `ls -la "<engine_dir>/<name>.lib"` shows a non-empty file (observed: 4458 bytes).
3. **Clean link**: `odin build src -out:build\\dmls.exe` exits 0 with no `LNK1107` text in the output.
4. **Automatic generation** (durable path): a full build-script run prints `Creating library engine\epilog\epilog.lib and object engine\epilog\epilog.exp`, then `[odin] Built build\dmls.exe`.
5. **Runtime FFI smoke test**: executing the built exe from the directory containing the DLL prints the expected FFI results (observed: `Epilog version: 0.2.0`, correct per-query solution counts, `=== Bridge smoke test: PASS ===`) and `Exit: 0`.
6. **Regression guard**: re-running the full build script from clean reproduces all of the above without manual steps.

## Examples
### Example 1: One-shot import library from a prebuilt DLL
- Input: `odin build src -out:build\dmls.exe` fails with `d:\dmls\engine\epilog\epilog.dll : fatal error LNK1107: invalid or corrupt file: cannot read at 0x2F8`; `bridge.odin` contains `foreign import epilog_lib "../engine/epilog/epilog.dll"`; the FFI header lists 15 `epilog_*` functions.
- Procedure: write `engine/epilog/epilog.def` with `LIBRARY epilog` + `EXPORTS` + the 15 function names; run `llvm-dlltool -m i386:x86-64 -d epilog.def -l epilog.lib`; edit `bridge.odin` to `foreign import epilog_lib "../engine/epilog/epilog.lib"`; copy `epilog.dll` to `build/`; run `odin build src -out:build\dmls.exe`; run `build\dmls.exe`.
- Expected result: link succeeds with no LNK1107; the exe prints `=== Bridge smoke test: PASS ===` and exits 0.
- Parameterized values: engine dir `engine/epilog/`, DLL `epilog.dll`, import lib `epilog.lib`, machine type `i386:x86-64`, output `build/dmls.exe`.

### Example 2: Durable fix — DLL build emits the import library itself
- Input: Example 1's manual `llvm-dlltool` step works, but the `.lib` could go stale whenever `epilog.dll` is rebuilt from source by `build.bat`.
- Procedure: edit the engine section of `build.bat` so the DLL is linked with the module-definition file: `!CXX! !CXXFLAGS! -shared -Wl,/DEF:!EPILOG_DIR!\epilog.def !EPILOG_SRCS! -o "!EPILOG_DLL!"`; run the full script (`build.bat` → engine build → DLL copy → `odin build` → run).
- Expected result: engine step prints `Creating library engine\epilog\epilog.lib and object engine\epilog\epilog.exp` and `[engine] Built engine\epilog\epilog.dll + epilog.lib`; Odin step prints `[odin] Built build\dmls.exe`; the run prints the bridge smoke test PASS with `Exit: 0`.
- Parameterized values: compiler `clang++` with `-target x86_64-pc-windows-msvc`, flags `-std=c++23 -O2 -DNDEBUG`, definition file `epilog.def`.

## Evidence
All quotes from file_id `claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02`.

- problem — source_index 225, source_part_index 0 (tool_result of `odin build` after copying the DLL): "Exit code 83\nDLL copied to build/\r\nd:\dmls\engine\epilog\epilog.dll : fatal error LNK1107: invalid or corrupt file: cannot read at 0x2F8" — shows LNK1107 naming the DLL even after the DLL was freshly copied into `build/`. A second identical failure after a DLL rebuild is at source_index 232: "Exit code 83\nRebuilt DLL copied.\r\nd:\dmls\engine\epilog\epilog.dll : fatal error LNK1107: invalid or corrupt file: cannot read at 0x2F8".
- problem (DLL is not corrupt) — source_index 235, source_part_index 0 (tool_result of `file` + `-extra-linker-flags:/LIBPATH` attempt): "d:\DMLS\engine\epilog\epilog.dll: PE32+ executable for MS Windows 6.00 (DLL), x86-64, 6 sections\nd:\dmls\engine\epilog\epilog.dll : fatal error LNK1107: invalid or corrupt file: cannot read at 0x2F8" — the DLL is a valid PE yet LNK1107 persists, and `/LIBPATH` did not help.
- problem (export discovery blocked) — source_index 237, source_part_index 0 (tool_result of `llvm-nm epilog.dll | grep -i 'epilog_'`): "epilog.dll: no symbols" — the export list cannot be read from the DLL, motivating the header-derived `.def`.
- action (generate import lib) — source_index 254, source_part_index 0 (tool_call:Bash): "llvm-dlltool -m i386:x86-64 -d epilog.def -l epilog.lib 2>&1" run over a `.def` containing "LIBRARY epilog\nEXPORTS\n    epilog_create\n    epilog_destroy" and the remaining FFI exports; result at source_index 257: "-rw-r--r-- 1 [NAME] 197121 4458 Jun  7 15:30 epilog.lib".
- action (switch foreign import) — source_index 262, source_part_index 0 (tool_call:Edit on `d:\DMLS\src\bridge.odin`): "foreign import epilog_lib \"../engine/epilog/epilog.lib\"" replaced the DLL reference; the old_string was "when ODIN_OS == .Windows {\n    foreign import epilog_lib \"../engine/epilog/epilog.dll\"".
- action (durable build script fix) — source_index 297, source_part_index 0 (tool_call:Edit to build.bat): "!CXX! !CXXFLAGS! -shared -Wl,/DEF:!EPILOG_DIR!\\epilog.def !EPILOG_SRCS! -o \"!EPILOG_DLL!\"" with the comment ":: -Wl,/DEF generates epilog.lib (import library) alongside the DLL".
- verification (link + import lib generation) — source_index 282, source_part_index 0 (tool_result of the DLL rebuild with `/DEF`): "Building DLL with 12 source files...\r\n   Creating library epilog.lib and object epilog.exp\r\nExit: 0"; and source_index 317, source_part_index 0 (full clean build-script run): "[engine] Built engine\\epilog\\epilog.dll + epilog.lib\r\n[odin] Building DMLS...\r\n[odin] Built build\\dmls.exe".
- verification (Odin build clean after the .lib switch) — source_index 274, source_part_index 0 (tool_result of `odin build src -out:build\dmls.exe` with the `.lib` import): "(PowerShell completed with no output)" — no LNK1107, exit 0.
- verification (runtime smoke test) — source_index 288, source_part_index 0 (tool_result of running `build\dmls.exe`): "=== Bridge smoke test ===\nEpilog version: 0.2.0\n\nparent(alice, bob): 1 solution(s)\ngrandparent(alice, X): 1 solution(s)\nparent(carol, _): 0 solution(s) [expect 0]\nparent(X, Y): 2 solution(s) [expect 2]\n\n=== Bridge smoke test: PASS ===\n\nM1 complete. Raylib window and simulation loop come in Phase 2.\nExit: 0" — the exe loads the DLL at runtime and FFI calls return correct results, confirmed again by the clean scripted run at source_index 317 ("=== Bridge smoke test: PASS ===").

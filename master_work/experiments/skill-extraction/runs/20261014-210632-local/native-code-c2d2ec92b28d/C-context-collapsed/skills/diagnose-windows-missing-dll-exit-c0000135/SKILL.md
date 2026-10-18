---
name: diagnose-windows-missing-dll-exit-c0000135
description: Use when a Windows-native executable built locally exits immediately with code -1073741515 / 0xC0000135. Helps the agent identify which imported DLL is absent, place it next to the exe, and harden the build script that silently failed to copy it. Requires Windows PowerShell, read access to the exe directory, and the toolchain install directory. Do not use for compile/link errors, for processes that stay alive without a window, or when the exit code is a different NTSTATUS.
---
# Diagnose Windows exe Exit 0xC0000135 (Missing Dependency DLL)

## Goal
Diagnose why a locally built Windows executable terminates at launch with exit code -1073741515 (0xC0000135, STATUS_DLL_NOT_FOUND), identify the exact missing dependency DLL by comparing the exe's import list against the files present next to it, copy the DLL from the toolchain installation into the exe's directory, fix the build step that silently failed to do that copy, and confirm the fix by launching the program and observing its own runtime initialization output.

## Scope
### In scope
- Windows (x64, PowerShell host) launching a locally built .exe that returns -1073741515 / 0xC0000135 immediately after start.
- Determining the real process exit code when the tool wrapper reports a different number.
- Extracting the set of DLL names an exe imports when dumpbin/dxdiag/gflags are not installed.
- Diffing that import list against the DLLs actually present in the exe's directory, including transitive (indirect) dependencies such as a graphics runtime DLL that is not referenced by project source files.
- Locating the missing DLL inside the compiler/toolchain installation and copying it next to the exe.
- Repairing a build script that copies runtime DLLs using an undefined environment variable while suppressing output with `>nul 2>&1`, so the failure is visible and path resolution is derived from the tool itself.
- Verifying the fix by running the exe and reading its own startup log.

### Out of scope
- Odin/compiler source-level errors and warnings (fix those in the normal build-error loop first; the exe must link before this applies).
- Linker failures such as LNK1105 where the output exe cannot be closed because it is locked — that is a separate mechanism (see the companion skill).
- Processes that launch and stay alive but never open their window (observed later in the same project; runtime/GUI initialization, not DLL loading).
- Installing DLLs into System32 or changing the system PATH — the trace only verified placing the DLL beside the exe.
- Non-Windows platforms and non-PowerShell shells.
- Rebuilding the third-party DLL from source; only copying a prebuilt one was verified.

## Inputs
1. **failing_exe_path** — type: string (filesystem path). Source: project build output (the agent located it as `<project>\build\dmls.exe` by listing the build directory). Required: yes. Constraints: must be the exact binary that exits with 0xC0000135; the exe's own directory is the DLL search location that matters. Default: 无.
2. **observed_exit_code** — type: string/integer. Source: tool result of running the exe (`$LASTEXITCODE` or `Start-Process ... -PassThru -Wait` → `$proc.ExitCode`). Required: yes. Constraints: the wrapper's own "Exit code N" line can differ from the process exit code; only the process code (`-1073741515`) is meaningful here. Default: 无.
3. **exe_directory_listing** — type: list of file names. Source: `ls <exe dir>` tool result. Required: yes. Constraints: shows which dependency DLLs are already deployed next to the exe. Default: 无.
4. **toolchain_root** — type: string (directory path). Source: `(Get-Command odin -ErrorAction SilentlyContinue).Source | Split-Path` tool result (returned `D:\Odin\dist`). Required: yes. Constraints: must be the installation that produced the binary; vendor DLLs live under `<toolchain_root>\vendor\raylib\windows\`. Default: 无.
5. **build_script** — type: string (batch file content). Source: `Read <project>\build.bat`. Required: optional (only if a build script is supposed to deploy DLLs). Constraints: look for `copy` lines referencing `%ODIN_ROOT%`/`%ODIN_PATH%` with output redirected to `>nul 2>&1`. Default: 无.
6. **shell** — type: string. Source: environment. Required: yes. Constraints: Windows PowerShell; commands in this skill are PowerShell syntax. Default: PowerShell.

## Outputs
### Artifacts
- **Import-list report** — location: tool output. Format: sorted unique DLL names extracted from the exe binary (e.g. `ADVAPI32.dll / bcrypt.dll / epilog.dll / KERNEL32.dll / raylib.dll`).
- **Missing-DLL diagnosis** — location: agent report. Format: name of the missing DLL plus the source path it was copied from.
- **Deployed DLL** — location: `<exe_dir>\<missing>.dll`. Format: unmodified binary copied from the toolchain directory.
- **Patched build script** — location: the project's `build.bat` (or equivalent). Format: batch code that resolves the toolchain directory from `where odin`, guards the copy with `if exist`, and prints a warning instead of swallowing output.

### Success criteria
- The exe directory contains every DLL in the import list (system DLLs such as KERNEL32/ADVAPI32 excluded).
- Launching the exe produces its own runtime output instead of an immediate exit; in the verified case the log contained `INFO: Initializing raylib 5.5` and ended with `INFO: Window closed successfully`.
- A re-run of the launcher no longer reports `-1073741515`.
- The build script emits a visible warning when the DLL source path does not exist.

### Failure criteria
- The process still exits with `-1073741515` after the copy.
- The import list cannot be extracted, or no source location for the missing DLL can be found.
- The copy reports an error (path not found, access denied) that was not resolved.

## Preconditions
- Host is Windows and the commands are executed in PowerShell (the whole procedure is PowerShell syntax; `cd C:\... && ...` in a bash-style call failed with `cd: too many arguments` in this trace).
- The binary has already compiled and linked successfully; only its runtime launch fails. If the build itself fails, finish that first.
- You can read the exe directory and write to it (the DLL must be placed beside the exe).
- The compiler/toolchain is installed locally and its root can be resolved from PATH (`(Get-Command odin).Source | Split-Path`); if the toolchain root cannot be determined, stop and report — the DLL's source location is unknown.
- No instance of the same exe is holding files open if you also need to rebuild afterward.
- Not satisfied → stop and report which precondition failed; do not substitute installing the DLL into System32 (unverified in this trace).

## Procedure
### Step 1: Reproduce and capture the real process exit code
- Actions: run the exe from its own directory and print `$LASTEXITCODE`, or use `cd <dir>; $proc = Start-Process -FilePath ".\app.exe" -PassThru -Wait; "Exit: $($proc.ExitCode)"`.
- Inputs: `failing_exe_path`.
- Outputs: `observed_exit_code`.
- Caution: the tool wrapper's own `Exit code 53` line is not the process exit code; trust `$LASTEXITCODE` / `$proc.ExitCode` (which showed `-1073741515`).
- Preserve: the raw command and its full output for the report.
- Next condition: if the code is `-1073741515` (0xC0000135), go to Step 2; otherwise stop — this skill does not apply.

### Step 2: Check the dependency DLLs already deployed next to the exe
- Actions: list the exe directory and the project tree for `*.dll`.
- Inputs: `failing_exe_path`.
- Outputs: `exe_directory_listing`.
- Caution: the presence of the DLL the project builds itself (here `epilog.dll`) only rules out that direct dependency; 0xC0000135 usually means a transitive dependency is missing.
- Next condition: proceed to Step 3 regardless — the import list is what settles it.

### Step 3: Extract the DLL import list straight from the exe binary
- Actions: read the exe bytes, decode as ASCII, regex-match DLL names, dedupe and sort:
  `$bytes = [System.IO.File]::ReadAllBytes("app.exe"); $text = [System.Text.Encoding]::ASCII.GetString($bytes); $matches = [regex]::Matches($text, '[A-Za-z0-9_\-]+\.dll'); $matches | ForEach-Object { $_.Value } | Sort-Object -Unique`
- Inputs: `failing_exe_path`.
- Outputs: import-list report.
- Caution: `dumpbin`, `gflags` and `handle64` were absent on this host; do not depend on Windows Kits tools — this byte-scan is the fallback that was actually used. It can over-report (matching DLL-like strings in resources), so treat the list as candidates, not proof.
- Next condition: go to Step 4.

### Step 4: Diff the import list against the exe directory
- Actions: for each imported DLL, check whether it exists in `exe_directory_listing`; ignore Windows system DLLs (KERNEL32, ADVAPI32, bcrypt, …) which always resolve from System32.
- Inputs: import-list report, `exe_directory_listing`.
- Outputs: the missing DLL name (in the trace: `raylib.dll`).
- Next condition: if exactly one non-system DLL is missing → Step 5; if none is missing, the failure is not a beside-the-exe DLL problem — stop and report.

### Step 5: Locate the missing DLL in the toolchain installation
- Actions: derive the toolchain root (`(Get-Command odin -ErrorAction SilentlyContinue).Source | Split-Path`), then look under `<root>\vendor\raylib\windows\` (and search the root recursively as a fallback: `Get-ChildItem <root> -Recurse -Filter "<name>.dll" | Select FullName -First 5`).
- Inputs: `toolchain_root`, missing DLL name.
- Outputs: full source path of the DLL (verified: `D:\Odin\dist\vendor\raylib\windows\raylib.dll`).
- Caution: do not trust environment variables such as `%ODIN_ROOT%` to be defined — in this trace they were not, which is exactly why the original copy failed.
- Next condition: source path found → Step 6; not found → stop, report the search locations.

### Step 6: Copy the DLL next to the exe and confirm by listing
- Actions: `Copy-Item "<source>" "<exe_dir>\<name>.dll" -Force; ls <exe_dir>\*.dll`.
- Inputs: source path, `failing_exe_path`.
- Outputs: `exe_directory_listing` updated (verified listing showed `epilog.dll` plus `raylib.dll` with size 1783296).
- Caution: the copy must target the directory the exe is launched from, not the project root.
- Next condition: both DLLs present → Step 7.

### Step 7: Fix the build script so the copy can never fail silently again
- Actions: in the build script, replace `copy /y "%ODIN_ROOT%\vendor\raylib\windows\raylib.dll" build\ >nul 2>&1` style lines with: resolve the tool directory at runtime and warn on miss —
  `for /f "tokens=*" %%i in ('where odin 2^>nul') do set ODIN_BIN=%%i` / `for %%i in ("!ODIN_BIN!") do set ODIN_DIR=%%~dpi` / `set RAYLIB_SRC=!ODIN_DIR!vendor\raylib\windows\raylib.dll` / `if exist "!RAYLIB_SRC!" ( copy /y "!RAYLIB_SRC!" build\ >nul ) else ( echo [warn] raylib.dll not found at !RAYLIB_SRC! -- ensure it is in build\ )`.
- Inputs: `build_script`.
- Outputs: patched build script.
- Caution: remove the `>nul 2>&1` suppression on failure paths; keep `build.bat`'s `setlocal enabledelayedexpansion` semantics (`!var!` inside blocks). Preserve every other build step untouched.
- Next condition: script edited → Step 8.

### Step 8: Rebuild (if the script changed) and verify by running the program
- Actions: run the build script's run action (`.\<build>.bat run`), capture the full output.
- Inputs: patched build script.
- Outputs: runtime log.
- Cautions: if the linker reports `LNK1105 ... cannot close file`, a previous instance still holds the output exe — switch to the locked-output-exe recovery procedure, then return here.
- Preserve: the complete console output as evidence.
- Next condition: output contains the application's own initialization lines (verified: `INFO: Initializing raylib 5.5` … `INFO: Window closed successfully`) → done; otherwise return to Step 4.

## Decision Rules
### When the process exit code is -1073741515 (0xC0000135)
Treat it as a missing load-time dependency and run Steps 2–6; do not debug source code, and do not treat the build as broken.

### When the tool wrapper's "Exit code N" differs from `$LASTEXITCODE`
Use `$LASTEXITCODE` or `Start-Process -PassThru -Wait` → `$proc.ExitCode`. In this trace the wrapper printed `Exit code 53` while the real code was `-1073741515`.

### When the DLL the project itself produces is already present next to the exe
That only clears the direct dependency; continue to the import-list diff (Step 4) because the missing DLL is usually a transitive one (here `raylib.dll`, not `epilog.dll`).

### When dumpbin / gflags / handle64 are unavailable
Use the pure-PowerShell byte-scan import extraction (Step 3). Verified: `where.exe`/tool probes returned "not recognized" and the byte-scan still produced the full DLL list.

### When the build script copies a DLL from `%SOME_VAR%` with `>nul 2>&1`
Classify it as a silent-failure hazard: the variable was unset on this host, so the copy failed invisibly while the build reported success. Rewrite it with tool-derived paths and a visible warning (Step 7).

### When no source path for the missing DLL can be found
Stop and report the missing DLL name and every location searched; installing into System32 or rebuilding the DLL was not verified in this trace.

### When after the copy the exe starts but never shows its window
Exit this skill — the process is no longer failing to load DLLs; that is a runtime initialization problem with different evidence.

## Invariants
- Never report success on build output alone; success requires the exe to actually run and print its own runtime output.
- Never install or overwrite DLLs in System32 or edit the machine PATH — only the exe's own directory was verified.
- Never swallow error output of deployment steps (`>nul 2>&1` on a path that can fail is what caused this bug); warnings must stay visible.
- Do not delete, patch, or hex-edit the built exe; the fix belongs to the DLL placement or the build script.
- Do not modify unrelated build steps (engine DLL compilation, compiler flags) while patching the copy section.
- Preserve the original failing exit code and command output as evidence; do not overwrite them with later successful runs.
- Do not assume environment variables (`%ODIN_ROOT%`, `%ODIN_PATH%`) are defined — derive paths from the installed tool.
- Do not claim the missing DLL was identified from project source inspection; the identification comes from the binary's import list.

## Common Failures
### Failure: Concluding "the DLL is fine" because the project-built DLL is already in the directory
- Symptoms: exit code stays `-1073741515`; agent keeps re-running the exe.
- Causes: only the direct dependency (`epilog.dll`) was checked; the missing one is a transitive dependency (`raylib.dll`) that no source file mentions by name.
- Recovery: extract the exe's import list (Step 3) and diff it against the directory (Step 4) before drawing any conclusion.

### Failure: Trusting the tool wrapper's "Exit code 53"
- Symptoms: diagnosis chases the wrong number; no hex mapping to a known NTSTATUS.
- Causes: the wrapper reports its own status, not the child process code.
- Recovery: capture `$LASTEXITCODE` or `Start-Process ... -PassThru -Wait` → `$proc.ExitCode`, which yielded `-1073741515`.

### Failure: Silent DLL copy failure in the build script
- Symptoms: build reports success, exe still exits 0xC0000135 on every fresh build/clean.
- Causes: `copy ... "%ODIN_ROOT%\vendor\raylib\windows\raylib.dll" ... >nul 2>&1` with `%ODIN_ROOT%` unset; output suppressed, so the failure was invisible. Cause of why the variable was unset was not confirmed beyond "not defined in that shell".
- Recovery: derive the path with `where odin`, guard with `if exist`, print `[warn] ...` otherwise, and drop output suppression on that line.

### Failure: Reaching for diagnostic tools that are not installed
- Symptoms: `gflags.exe ... is not recognized`, `handle64.exe: The term 'handle64.exe' is not recognized...`; time lost before any progress.
- Causes: Windows Kits / Sysinternals utilities absent on the host.
- Recovery: use PowerShell-native inspection (byte-scan regex for import names, `Get-ChildItem` for location search).

### Failure: Rebuilding while the previous run still holds the output exe
- Symptoms: `LINK : fatal error LNK1105: cannot close file '...dmls.exe'; error code 1224`.
- Causes: a leftover process keeps the output binary open (specific holder not identified in the trace).
- Recovery: stop same-named processes, delete the output binary if needed, rebuild — see the locked-output-exe procedure; then return to verification.

## Verification
Observable checks (none of them are claims that they were executed here):
- Running the exe reports an exit code other than `-1073741515` (previously: `Exit: -1073741515`).
- The exe directory listing shows every non-system DLL from the import list (observed pattern: `epilog.dll` plus `raylib.dll`, size `1783296`).
- The program's own startup log appears in the captured output, e.g. lines `INFO: Initializing raylib 5.5`, `INFO: Platform backend: DESKTOP (GLFW)`, `INFO: DISPLAY: Device initialized successfully`, ending with `INFO: Window closed successfully`.
- Re-running `build.bat` after a `clean` still leaves the DLL in place, and the script prints `[warn] raylib.dll not found at ...` if the source path disappears.
- The patched copy line no longer contains `>nul 2>&1` on the branch that can fail, and contains `if exist` + `echo [warn]`.
- No new files outside the exe directory and the build script were created or modified.

## Examples
### Example 1: Odin + raylib game exe exits immediately with 0xC0000135
- Input: `<project_root>` = `D:\DMLS`, exe = `D:\DMLS\build\dmls.exe`, run result `Exit: -1073741515`; directory listing shows `dmls.exe` and `epilog.dll` only; toolchain resolves to `D:\Odin\dist`.
- Procedure: Step 1 capture exit code (`Start-Process -PassThru -Wait`) → `-1073741515`; Step 2 list directories (only the project's own `epilog.dll` present); Step 3 byte-scan import list → `ADVAPI32.dll, bcrypt.dll, epilog.dll, KERNEL32.dll, raylib.dll`; Step 4 diff → `raylib.dll` missing; Step 5 search `D:\Odin\dist\vendor\raylib\windows\` → `raylib.dll` found; Step 6 `Copy-Item` into `D:\DMLS\build\`; Step 7 patch `build.bat` to derive the path via `where odin` with `if exist`/`[warn]`; Step 8 run `build.bat run`.
- Expected result: no more `-1073741515`; the captured run log starts with `INFO: Initializing raylib 5.5` and ends with `INFO: Window closed successfully`.
- Parameterized values: project root (`D:\DMLS`), toolchain root (`D:\Odin\dist`), missing DLL (`raylib.dll`), dependency DLL built by the project (`epilog.dll`), DLL source (`<toolchain>\vendor\raylib\windows\raylib.dll`), runtime port used later (`7771`).

### Example 2: Wrapper exit code differs from the real one
- Input: `cd D:\DMLS; .\build\dmls.exe 2>&1; echo "Exit: $LASTEXITCODE"`.
- Procedure: read the full tool result instead of the first line.
- Expected result: output contains both the wrapper status and the true code, e.g. `Exit code 53` followed by `Exit: -1073741515`; only the latter maps to `0xC0000135`.
- Parameterized values: exe name, wrapper-reported code (varies), process code (`-1073741515` = `0xC0000135`).

## Evidence
problem:
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 404, source_part_index: 0, quote: "Exit: -1073741515" — supports: the launched exe's real process exit code (tool result of running `.\build\dmls.exe`).
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 405, source_part_index: 0, quote: "Exit code `-1073741515` is `0xC0000135` — **DLL not found**. The `epilog.dll` isn't next to the executable. Let me check:" — supports: mapping of the code to a load-time DLL failure and the first (wrong) hypothesis that the project-built DLL was missing.
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 409, source_part_index: 0, quote: "The DLL is already in `build\\` alongside the exe — so that's not it. The exit code `0xC0000135` means a dependency DLL is missing. Let me check which DLL it can't find:" — supports: direct dependency was present, so a transitive dependency must be identified.

action:
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 416, source_part_index: 0, quote: "$matches | ForEach-Object { $_.Value } | Sort-Object -Unique" — supports: the PowerShell byte-scan used to extract the exe's DLL import list without dumpbin.
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 419, source_part_index: 0, quote: "ls D:\\DMLS\\build\\*.dll; Get-ChildItem D:\\DMLS -Recurse -Filter \"raylib.dll\" | Select-Object FullName" — supports: listing the exe directory and searching the project for the DLL that the import list showed missing.
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 426, source_part_index: 0, quote: "Line 90 tries to copy `raylib.dll` from `%ODIN_ROOT%\\vendor\\raylib\\windows\\` — but the `copy` output was suppressed with `>nul 2>&1`. The copy silently failed. Let me find where raylib.dll actually lives:" — supports: root cause of why the DLL was absent despite a "successful" build.
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 431, source_part_index: 0, quote: "Copy-Item \"D:\\Odin\\dist\\vendor\\raylib\\windows\\raylib.dll\" \"D:\\DMLS\\build\\raylib.dll\" -Force; ls D:\\DMLS\\build\\*.dll" — supports: the corrective copy from the toolchain install into the exe directory plus immediate listing.
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 435, source_part_index: 0, quote: "for /f \"tokens=*\" %%i in ('where odin 2^>nul') do set ODIN_BIN=%%i" — supports: the build-script fix that derives the toolchain path from the compiler instead of an undefined environment variable.

verification:
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 432, source_part_index: 0, quote: "-a---          03-05-2026 08:33 PM        1783296 raylib.dll" — supports: the DLL is now present in the exe's directory (tool result of the listing after the copy).
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 465, source_part_index: 0, quote: "INFO: Initializing raylib 5.5" — supports: after rebuild and launch, the previously missing library actually loads and the application runs (tool result of `build.bat run`).
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 465, source_part_index: 0, quote: "INFO: Window closed successfully" — supports: the run completed without the earlier immediate 0xC0000135 termination.
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 417, source_part_index: 0, quote: "raylib.dll" — supports: the import extracted from the exe binary, i.e. the DLL the executable requires at load time.

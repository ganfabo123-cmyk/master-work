---
name: diagnose-windows-dll-not-found
description: Use when a Windows executable built by a script exits immediately with -1073741515 / 0xC0000135 or shows no window. Helps the agent identify exactly which dependency DLL is missing, place it next to the exe, and make the build script copy it reliably. Requires PowerShell access to the build directory and the toolchain install directory. Do not use when the build itself fails, or when the exit code is a different NTSTATUS value.
---
# Diagnose and Fix Windows STATUS_DLL_NOT_FOUND (0xC0000135) for a Built GUI Executable

## Goal
Given a Windows exe that builds successfully but dies at launch with exit code -1073741515 (0xC0000135, STATUS_DLL_NOT_FOUND), identify the exact missing dependency DLL, place it beside the exe, fix the build script so the copy does not silently fail again, and prove the app starts by observing its own runtime initialization log.

## Scope
### In scope
- Windows GUI/console exe that builds fine but exits with -1073741515 / 0xC0000135 before showing a window.
- Extracting the exe's imported DLL names from the binary when no PE tool (dumpbin, gflags, handle64) is available.
- Comparing imports against the DLLs actually present next to the exe and copying the missing one from the toolchain's vendor directory (e.g. `<odin>\vendor\raylib\windows\raylib.dll`).
- Making the build script copy DLLs non-silently and derive the toolchain path from `where odin` instead of an environment variable that may be unset.

### Out of scope
- Failures that occur before or during compilation/link (see the LNK1105 skill for locked-output relink failures).
- DLL version conflicts, architecture mismatches (x86 vs x64), or missing Visual C++ runtime redistributables — none of these were observed or tested here.
- Runtime crashes after the window has initialized successfully.

## Inputs
- **Failing exe path**: string, source = user report or your own launch attempt, required = yes, constraint = must be the binary Windows actually executes (here `<project>\build\dmls.exe`), default = 无
- **Observed exit code**: integer/string, source = tool result of launching the exe (e.g. `Start-Process -PassThru -Wait` → `Exit: -1073741515`), required = yes, constraint = must be captured from the process launch, not inferred from "no window appeared", default = 无
- **Build output directory**: directory path, source = build script configuration (here `build\`), required = yes, constraint = this is where DLLs must sit next to the exe, default = 无
- **Toolchain install directory**: directory path, source = `where odin` / `Get-Command odin .Source | Split-Path` (here `D:\Odin\dist`), required = yes, constraint = must contain `vendor\raylib\windows\raylib.dll` or equivalent, default = 无
- **Build script**: file, source = project repository (here `d:\DMLS\build.bat`), required = no, constraint = only needed to make the fix survive rebuilds, default = 无

## Outputs
### Artifacts
- **Missing-DLL diagnosis**: identified DLL name(s) plus the import list extracted from the exe (tool output, no file written).
- **DLL placed in build directory**: e.g. `<build>\raylib.dll` alongside `<build>\<app>.exe`, filesystem.
- **Patched build script**: e.g. `build.bat` copying the DLL from the directory of `where odin` with an explicit warning when the source path does not exist, file edit.
- **Runtime log excerpt**: the application's own initialization output captured from the run.

### Success criteria
- Launching the exe no longer yields -1073741515; the process reaches its own initialization (raylib INFO lines) and exits with a normal close (e.g. `INFO: Window closed successfully`).
- The build directory contains one DLL per non-system import found in the exe.

### Failure criteria
- Exit code is still -1073741515 after placing the DLL (then a different import is still missing — repeat extraction).
- The exe exits with a different code, or produces no output at all — the problem is not this skill's scope.
- The build script cannot locate the toolchain directory and prints its warning: the immediate manual copy still stands, but the permanent fix is incomplete.

## Preconditions
- The executable builds successfully — if the build fails, fix that first; this skill only addresses post-build launch failure.
- The observed exit code is confirmed as -1073741515 / 0xC0000135 by capturing the process exit code (e.g. `Start-Process -FilePath ".\app.exe" -PassThru -Wait` then reading `$proc.ExitCode`). A "no window" report alone is not confirmation.
- You can list the build directory and know which DLLs are already there (here only `epilog.dll` was present while `raylib.dll` was required).
- You can reach the toolchain install directory that ships the vendor DLL (here located via `Get-Command odin ... | Split-Path`, which printed `D:\Odin\dist` and a `raylib.dll` under `vendor\raylib\windows\`).
- You have write permission to the build directory for the DLL copy.
- If any precondition fails (no write access, toolchain directory unknown), stop and report what is missing instead of guessing a DLL location.

## Procedure
### Step 1: Confirm the exit code from a real launch
- actions: run the exe from its own directory capturing the process exit code (`Start-Process -FilePath ".\app.exe" -PassThru -Wait; "Exit: $($proc.ExitCode)"`). Direct `& .\app.exe` in a constrained shell can return a misleading shell-level code (here `Exit code 53`), so prefer `Start-Process`.
- inputs: exe path.
- outputs: numeric exit code.
- cautions: do not treat a wrapper's exit code as the NTSTATUS value.
- preserve: the original build artifacts.
- next: if the code is -1073741515 continue; otherwise stop — different problem.

### Step 2: List what DLLs sit next to the exe
- actions: `ls <build>\*.dll` and, for the project's own DLL, search the whole project (`Get-ChildItem <root> -Recurse -Filter "<name>.dll"`).
- inputs: build directory.
- outputs: set of DLLs present.
- cautions: presence of the project's own DLL does NOT rule out a missing dependency.
- preserve: nothing to change yet.
- next: continue to import extraction.

### Step 3: Extract the exe's imported DLL names without PE tools
- actions: read the exe bytes and regex ASCII for DLL names: `$bytes = [System.IO.File]::ReadAllBytes("<exe>"); $text = [System.Text.Encoding]::ASCII.GetString($bytes); [regex]::Matches($text, '[A-Za-z0-9_\-]+\.dll') | ForEach-Object { $_.Value } | Sort-Object -Unique` (do this before hunting for `dumpbin`/`gflags`/`handle64`, which may not be installed).
- inputs: exe path.
- outputs: unique import list (observed: `ADVAPI32.dll`, `bcrypt.dll`, `epilog.dll`, `KERNEL32.dll`, `raylib.dll`).
- cautions: this is a string scan, not a PE parse — expect system DLLs too; it is enough to spot the one non-system DLL absent from the build directory.
- preserve: raw output for the report.
- next: compare with Step 2; continue if a non-system import is missing.

### Step 4: Locate the missing DLL in the toolchain install
- actions: derive the toolchain root from the compiler itself (`$odinRoot = (Get-Command odin -ErrorAction SilentlyContinue).Source | Split-Path; Get-ChildItem "$odinRoot\vendor\raylib\windows\" ...` and/or a recursive `-Filter "raylib.dll"`).
- inputs: compiler on PATH.
- outputs: absolute path of the DLL (observed `D:\Odin\dist\vendor\raylib\windows\raylib.dll`).
- cautions: do not assume an env var like `%ODIN_ROOT%` is set — it may be empty even though the compiler is on PATH.
- preserve: nothing.
- next: copy it.

### Step 5: Copy the DLL next to the exe and confirm both are listed
- actions: `Copy-Item "<toolchain>\vendor\raylib\windows\<dll>" "<build>\<dll>" -Force; ls <build>\*.dll`.
- inputs: source path from Step 4, build directory.
- outputs: directory listing showing every required DLL.
- cautions: none.
- preserve: existing DLLs in the build directory.
- next: run the app (Step 7) and, in parallel, harden the build script (Step 6).

### Step 6: Make the build script copy DLLs reliably (permanent fix)
- actions: read the build script's DLL copy lines; if they copy from `%ODIN_ROOT%`/`%ODIN_PATH%` with output suppressed (`>nul 2>&1`), replace with: locate the compiler via `for /f "tokens=*" %%i in ('where odin 2^>nul') do set ODIN_BIN=%%i`, derive its directory, build the vendor path, `if exist` copy it, otherwise `echo [warn] ...` naming the expected path.
- inputs: build script.
- outputs: edited script.
- cautions: suppressed copy failures (`>nul 2>&1`) are exactly how the DLL went missing while the build looked green; never leave a silent copy in place.
- preserve: all other build logic (engine build, odin flags, run action).
- next: rebuild via the script and confirm no `[warn]` line and a "Built" line.

### Step 7: Verify by running the app and reading its own startup log
- actions: launch through the build script (`build.bat run`) and capture full output.
- inputs: rebuilt exe.
- outputs: runtime log.
- cautions: `build.bat run` blocks while the window is open; a clean "Window closed successfully" is acceptable proof of a full start/stop cycle.
- preserve: log excerpt.
- next: done when initialization lines appear and the process closes without an NTSTATUS failure.

## Decision Rules
### When exit code is -1073741515 / 0xC0000135
Treat as STATUS_DLL_NOT_FOUND: skip all source-code investigation and go straight to import extraction (Step 3).

### When the exe's own DLL is already beside it but the code still is 0xC0000135
The failing DLL is a transitive/vendor import (here `raylib.dll` while `epilog.dll` was present) — diff the import list against the directory listing rather than assuming.

### When dumpbin / gflags / handle64 are unavailable
Use the byte-scan regex import extraction (Step 3); do not block on installing PE tooling.

### When the build script copies DLLs with output suppressed (`>nul 2>&1`)
Treat any such copy as possibly failing silently; rewrite with `where odin` discovery plus an explicit `[warn]` (Step 6).

### When the app's own init log is produced and the window closes normally
Stop — the DLL problem is resolved; further "verify it really worked" steps are unnecessary.

### When the launch exits with a different code or no NTSTATUS value
Do not apply this skill; the evidence points elsewhere (the wrapper `Exit code 53` case, for example, was a shell artifact, not the process status).

## Invariants
- Do not modify source code to "fix" a missing-DLL launch failure; the fix is a file placement plus build-script copy, never an app change.
- Do not delete or overwrite DLLs already present in the build directory.
- Do not remove the project's own DLL (e.g. `epilog.dll`) while investigating — only add the missing one.
- Preserve every other line of the build script (engine build, odin flags, run/clean actions) when editing the DLL copy block.
- Never leave a copy step whose output is fully suppressed (`>nul 2>&1`) without an existence check and warning.
- Do not claim success from a successful build alone: the failure is at launch, so verification must include actually running the exe and reading its own startup output.
- Do not report the window appearing unless a tool output shows it (here the evidence was raylib's init log ending in `INFO: Window closed successfully`).
- Do not attribute the runtime success solely to the build-script edit: the manual DLL copy preceded it; state which action produced which result.

## Common Failures
### Failure: Checking the project's own DLL and concluding "DLLs are fine"
- symptoms: `epilog.dll` sits next to the exe, so the diagnosis stops there, yet the exit code is still 0xC0000135.
- causes: the missing DLL is a second-level/vendor import (`raylib.dll`) not produced by this project.
- recovery: extract the full import list from the binary and diff it against the directory listing.

### Failure: Trusting a wrapper's exit code instead of the process status
- symptoms: a shell reports `Exit code 53` (or similar) for the launch command.
- causes: the shell/tool wrapper reports its own failure, not the child's NTSTATUS.
- recovery: relaunch with `Start-Process ... -PassThru -Wait` and print `$proc.ExitCode`; the real value was `-1073741515`.

### Failure: Assuming an environment variable points at the toolchain
- symptoms: the build script's copy step silently does nothing; `%ODIN_ROOT%` resolves to nothing even though `odin` is on PATH.
- causes: the variable was never set in that environment; output was suppressed with `>nul 2>&1`.
- recovery: derive the path from `where odin`/`Get-Command odin`, add an `if exist` guard and an explicit warning line.

### Failure: Declaring victory from the build alone
- symptoms: build passes after the edit, but the original complaint ("no screen/output") was never re-tested.
- causes: verification not matched to the reported problem.
- recovery: run the exe (or `build.bat run`) and require its own startup log as evidence.

### Failure: Cause of the original DLL absence not fully proven
- symptoms: `raylib.dll` was absent from the build directory after many successful builds.
- causes: plausible (clean step, silent copy failure) but not demonstrated in the trajectory.
- recovery: state the absence as fact and the history as unconfirmed; the guarded copy prevents recurrence either way.

## Verification
- Directory listing of the build folder shows one DLL for every non-system import extracted from the exe (observed: `epilog.dll` and `raylib.dll` both present after the copy).
- Relaunching the exe no longer produces -1073741515; the captured process exit is a normal termination.
- The application's own startup log contains its framework initialization lines (observed: `INFO: Initializing raylib 5.5`, `INFO: Platform backend: DESKTOP (GLFW)`, `INFO: PLATFORM: DESKTOP (GLFW - Win32): Initialized successfully`) — this is runtime evidence, independent of the build.
- The log ends with a clean shutdown line (observed: `INFO: Window closed successfully`) with no loader error in between.
- Running the build script again reports its DLL copy path without the `[warn] raylib.dll not found at ...` message (i.e. the guarded copy found the file), and the build still prints its "Built <exe>" success line.
- Negative check: no source file outside the build script was modified for this fix.

## Examples
### Example 1: raylib.dll missing beside an Odin-built game exe
- input: user report "no screen/output on running"; exe at `<project>\build\dmls.exe` with `epilog.dll` beside it; toolchain at `D:\Odin\dist`.
- procedure: capture exit code with `Start-Process -PassThru -Wait` → `-1073741515`; list `build\*.dll` → only `epilog.dll`; regex-scan the exe for imports → `ADVAPI32.dll, bcrypt.dll, epilog.dll, KERNEL32.dll, raylib.dll`; find `raylib.dll` under the odin directory's `vendor\raylib\windows\`; `Copy-Item` it into `build\`; rewrite the build script copy to derive the path from `where odin` with an `[warn]` guard; run `build.bat run`.
- expected result: build prints its "Built" line with no warning, then the app's runtime log appears and ends with a clean window close — no 0xC0000135.
- parameterized values: exe `<project>\build\<app>.exe`; missing DLL `<vendor DLL>`; toolchain root `<odin install dir>`; build script `<project>\build.bat`; env var that may be unset `%ODIN_ROOT%`.

### Example 2: wrapper exit code mistaken for the NTSTATUS
- input: a direct `& ".\dmls.exe"` invocation inside a constrained shell returning `Exit code 53`.
- procedure: do not interpret 53 as the app's status; relaunch with `Start-Process ... -PassThru -Wait` and read `$proc.ExitCode`.
- expected result: the true code `-1073741515` appears, redirecting the diagnosis to DLL loading.
- parameterized values: shell/wrapper may be any tool runner; the numeric mismatch value varies by environment.

## Evidence
- problem — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 413, source_part_index 0, quote: `Exit: -1073741515`, supports: the launched exe's process exit code is the NTSTATUS for DLL-not-found (captured via Start-Process, not inferred).
- problem — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 404, source_part_index 0, quote: `Exit code 53`, supports: a direct invocation reported a misleading wrapper code 53 while the process status (same result) was `Exit: -1073741515`.
- problem — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 420, source_part_index 0, quote: `-a---          07-06-2026 09:06 PM         475136 epilog.dll`, supports: the build directory contained the project's own DLL but (per this listing) nothing else — the missing dependency was a second DLL.
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 417, source_part_index 0, quote: `raylib.dll`, supports: the regex extraction of the exe's imports (full result `ADVAPI32.dll`, `bcrypt.dll`, `epilog.dll`, `KERNEL32.dll`, `raylib.dll`) named `raylib.dll` as the only non-system import absent from the build directory — command used at source_index 416: `[regex]::Matches($text, '[A-Za-z0-9_\\-]+\.dll')`.
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 423, source_part_index 0, quote: `copy /y "%ODIN_ROOT%\vendor\raylib\windows\raylib.dll" build\ >nul 2>&1 || copy /y "%ODIN_PATH%\vendor\raylib\windows\raylib.dll" build\ >nul`, supports: the build script copied raylib.dll from env-var paths with all output suppressed — the silent-failure mechanism that left the DLL missing.
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 428, source_part_index 0, quote: `ODIN_ROOT: D:\Odin\dist`, supports: the toolchain directory was derived from the compiler's own location, giving the vendor path used for the copy.
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 431, source_part_index 0, quote: `Copy-Item "D:\Odin\dist\vendor\raylib\windows\raylib.dll" "D:\DMLS\build\raylib.dll" -Force; ls D:\DMLS\build\*.dll`, supports: the corrective action — manual copy of the missing DLL into the build directory.
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 432, source_part_index 0, quote: `-a---          03-05-2026 08:33 PM        1783296 raylib.dll`, supports: the copy succeeded; `raylib.dll` now sits beside the exe.
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 435, source_part_index 0, quote: `for /f "tokens=*" %%i in ('where odin 2^>nul') do set ODIN_BIN=%%i`, supports: the permanent build-script fix derives the DLL path from the compiler location instead of possibly-unset env vars, with an explicit warning branch.
- verification — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 465, source_part_index 0, quote: `INFO: Initializing raylib 5.5`, supports: the application actually reached runtime graphics initialization — the DLL loaded (runtime proof, not a build proof).
- verification — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 465, source_part_index 0, quote: `INFO: Window closed successfully`, supports: full clean start→close cycle with no loader failure — 0xC0000135 is gone.
- verification — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 465, source_part_index 0, quote: `[odin] Built build\dmls.exe`, supports: the rebuild through the patched script still succeeds.

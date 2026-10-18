---
name: recover-lnk1105-locked-output-exe
description: Use when a Windows rebuild fails with `LNK1105: cannot close file '<path>.exe'; error code 1224` because the output binary is still open. Helps the agent release or remove the locked output file and complete the rebuild plus a run check. Requires Windows PowerShell and write access to the output directory. Do not use for source/compile errors, for missing-DLL launch failures (exit 0xC0000135), or for locks on source/header files.
---
# Recover from LNK1105: Windows Output exe Locked by a Running Process

## Goal
Restore a Windows rebuild that aborts with `LINK : fatal error LNK1105: cannot close file '<output>.exe'; error code 1224` by freeing or removing the output binary that a previous run still holds open, then rebuild and prove recovery by the program's own runtime output.

## Scope
### In scope
- Windows rebuild of a project whose linker cannot write/close the output executable: `LNK1105 ... error code 1224`.
- A leftover instance of the same program keeping the output binary open after an earlier `build … run` invocation.
- Determining whether any process still matches the program, stopping same-named processes, and (when nothing matches) force-deleting the output binary so the linker can recreate it.
- Verifying recovery by relaunching and reading the program's own startup log.
- Interaction with a build script whose `run` action blocks while the program runs (so the build session can outlive the tool call).

### Out of scope
- Missing dependency DLL at launch (exit `-1073741515` / `0xC0000135`) — separate diagnosis procedure.
- Compiler/source errors in the same build output; fix those first, they are unrelated to the lock.
- Locks on source files, headers, or import libraries (`.lib`/`.exp`) — only the output `.exe` lock was observed and handled here.
- Determining the exact PID holding the file when no diagnostic utility is available: `handle64.exe` was not installed and `Get-Process … Path -like` returned nothing in this trace, so the holder was never identified.
- Non-Windows platforms.

## Inputs
1. **build_failure_output** — type: string (tool result text). Source: running the project's build script (e.g. `.\<root>\build.bat run` → PowerShell tool result). Required: yes. Constraints: must contain the linker line `LNK1105: cannot close file '<path>'; error code 1224`; if a different error appears (e.g. `error C…`), this skill does not apply. Default: 无.
2. **output_exe_path** — type: string (filesystem path). Source: parsed from the LNK1105 message (trace: `D:\DMLS\build\dmls.exe`). Required: yes. Constraints: this is the file the linker cannot rewrite; the directory must be writable. Default: 无.
3. **program_name** — type: string (process name without extension). Source: the output exe name (trace: `dmls`). Required: yes. Constraints: used for `Stop-Process -Name`. Default: derived from `output_exe_path`.
4. **build_command** — type: string (command line). Source: project build script usage (trace: `Set-Location <root>; .\build.bat run`). Required: yes. Constraints: run from the project root; PowerShell host. Default: 无.
5. **process_listing** — type: tool result. Source: `Get-Process | Where-Object {$_.Path -like "*<Project>*"}` or `tasklist`. Required: optional. Constraints: may come back empty even while the file is locked (observed: "(PowerShell completed with no output)"). Default: 无.
6. **shell** — type: string. Source: environment. Required: yes. Constraints: Windows PowerShell. Default: PowerShell.

## Outputs
### Artifacts
- **Lock diagnosis** — location: agent report. Format: the LNK1105 line, plus what process listing showed (including "no matching process found").
- **Released output file** — location: `<output_exe_path>` deleted or closed. Format: `Remove-Item -Force` returning `True`.
- **Successful rebuild** — location: build tool output. Format: `[odin] Built build\dmls.exe` style completion lines with no `LNK1105`.
- **Run evidence** — location: captured console output of the rebuilt program. Format: the program's own initialization log.

### Success criteria
- The build completes with no `LNK1105` / `error code 1224` line.
- The output exe exists freshly written (new timestamp/size) or the build reports it built.
- The program runs and emits its own startup output (observed pattern: `INFO: Initializing raylib 5.5` … `INFO: Window closed successfully`).

### Failure criteria
- `LNK1105` reappears on the next attempt after the recovery steps.
- The output file cannot be deleted (access denied) and no process could be stopped.
- The build succeeds but the program still fails to launch for a different reason (report separately; do not call this recovered).

## Preconditions
- Windows host with PowerShell; commands below are PowerShell syntax.
- Write/delete permission on the output directory (the file must be removable if the lock persists).
- The failing step is the linker writing the output exe (`LNK1105 … error code 1224`), not a compile error — otherwise fix compilation first.
- The project root and its build command are known (this trace: `Set-Location D:\DMLS; .\build.bat run`).
- If identifying the locking PID is required, a handle-inspection utility would be needed — `handle64.exe` was absent here, so the plan must not depend on it.
- Not satisfied → stop and report which precondition failed.

## Procedure
### Step 1: Confirm the failure signature
- Actions: read the full build tool result and locate `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224`.
- Inputs: `build_failure_output`.
- Outputs: confirmed LNK1105 + `output_exe_path`.
- Caution: ignore other diagnostics in the same output (this build also showed separate `Error:` lines at other times); only the LNK1105 line means a lock.
- Next condition: signature matched → Step 2.

### Step 2: Look for surviving instances of the program
- Actions: `Get-Process | Where-Object {$_.Path -like "*<Project>*"}` and/or `Stop-Process -Name <program_name> -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500`.
- Inputs: `program_name`.
- Outputs: process listing (may be empty).
- Caution: an empty listing does NOT prove the file is unlocked — in this trace the listing returned "(PowerShell completed with no output)" while the link still failed moments earlier. Do not stop at "no process found".
- Next condition: proceed to Step 3 regardless.

### Step 3: Retry the build once after stopping same-named processes
- Actions: re-run `build_command`.
- Inputs: `build_command`.
- Outputs: build result.
- Caution: this attempt may still fail with LNK1105 (it did in the trace), which means the stop alone was insufficient.
- Next condition: if it succeeds → Step 5; if LNK1105 persists → Step 4.

### Step 4: Force-remove the output binary
- Actions: `Remove-Item -Force <output_exe_path> -ErrorAction SilentlyContinue; $?` and verify the boolean (`True`).
- Inputs: `output_exe_path`.
- Outputs: deletion result.
- Cautions: do not delete anything else in the output directory (dependency DLLs must stay); if the deletion returns `False`/errors, stop and report — the holder could not be identified (`handle64.exe` is not installed on this host).
- Preserve: the deletion result as evidence.
- Next condition: `True` → Step 5; otherwise stop.

### Step 5: Rebuild and verify with a real run
- Actions: run `build_command` again (the script's run action), capture the complete output.
- Inputs: `build_command`.
- Outputs: rebuild log + program startup log.
- Caution: the build script's `run` action blocks while the program runs, so the tool call may time out or hold the terminal; that is expected and is also how a new lock can be created for the next build.
- Preserve: full console output.
- Next condition: no `LNK1105` and the program's own initialization lines appear (verified: `INFO: Initializing raylib 5.5` … `INFO: Window closed successfully`) → recovered; if LNK1105 returns, return to Step 2 with a wider process search.

## Decision Rules
### When the build output contains `LNK1105 ... cannot close file ... error code 1224`
Treat it as a file lock on the output exe and run Steps 2–5; do not change source code or linker flags.

### When the process listing shows nothing for the project
Continue anyway: proceed to stop by name, retry, and if it still fails, delete the output file. In this trace the listing was empty yet the lock was real.

### When `Stop-Process -Name <prog>` followed by a rebuild still yields LNK1105
Do not repeat the same stop; escalate to force-deleting the output exe (`Remove-Item -Force`), which returned `True` here and unblocked the next build.

### When deletion of the output exe fails and no handle utility is available
Stop and report: the locking process could not be identified (`handle64.exe: The term 'handle64.exe' is not recognized ...`), so there is no verified further step.

### When the build succeeds but the program exits immediately with `-1073741515`
The lock issue is resolved; switch to the missing-DLL diagnosis procedure for the remaining problem.

### When the build script's run action blocks on a GUI program
Expect the terminal/tool call to stay occupied while the program runs; before the next rebuild, stop that program first, otherwise a new LNK1105 lock is created.

## Invariants
- Never modify sources, headers, or build configuration to work around a file lock; the code is not the problem.
- Never delete anything in the output directory other than the locked output exe (dependency DLLs must remain for the program to start).
- Never report the build as fixed without a subsequent successful build output showing no `LNK1105`.
- Never claim a process was found or killed when the listing came back empty; report exactly what was observed.
- Do not treat an empty `Get-Process` filter result as proof the file is unlocked.
- Preserve the original LNK1105 text and the deletion boolean as evidence.
- Do not depend on `handle64.exe`/Sysinternals or other tools unless they are actually installed.

## Common Failures
### Failure: Stopping the named process and rebuilding immediately, still LNK1105
- Symptoms: `Stop-Process -Name dmls -Force ...; .\build.bat run` output still contains `LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224`.
- Causes: the holder was not that named process, or the file handle was not yet released. Which one was the case was not confirmed in the trace.
- Recovery: escalate to `Remove-Item -Force <output_exe>` (returned `True`) and rebuild.

### Failure: Assuming "no process → no lock"
- Symptoms: agent concludes the file is free and retries the link repeatedly.
- Causes: `Get-Process | Where-Object {$_.Path -like "*DMLS*"}` returned "(PowerShell completed with no output)" even though the lock existed.
- Recovery: rely on the linker's verdict and on direct deletion of the output file, not on process listings alone.

### Failure: Diagnostic tool missing
- Symptoms: `handle64.exe: The term 'handle64.exe' is not recognized as a name of a cmdlet, function, script file, or executable program.`
- Causes: Sysinternals not installed on the host.
- Recovery: use PowerShell-native steps (stop by name → force delete → rebuild); if deletion also fails, stop and report.

### Failure: Rebuilding while the program from the previous run is still up
- Symptoms: LNK1105 recurs on the very next iteration.
- Causes: the build script's `run` action starts the GUI program and blocks until exit, so a live instance is normal after any run.
- Recovery: stop the program (and delete the output exe if needed) before each rebuild; this ordering is what made the final rebuild succeed.

## Verification
Observable checks (stated as checks, not as claims of execution here):
- The captured build output no longer contains `LNK1105` or `error code 1224`, and ends with the project's success line (pattern: `[odin] Built build\dmls.exe`).
- `Remove-Item -Force <output_exe>; $?` printed `True` before the successful rebuild (evidence that the lock was cleared).
- The rebuilt program produces its own runtime log, e.g. `INFO: Initializing raylib 5.5`, `INFO: Platform backend: DESKTOP (GLFW)`, `INFO: DISPLAY: Device initialized successfully`, and terminates with `INFO: Window closed successfully`.
- Immediately after a run, a follow-up rebuild either succeeds or is preceded by stopping the program — no unexplained `LNK1105` remains.
- Only the output exe was deleted; DLLs and sources are untouched (list the output directory to confirm).

## Examples
### Example 1: GUI game rebuild blocked by its own previous run
- Input: build result containing `LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224`; project root `D:\DMLS`; program name `dmls`.
- Procedure: Step 1 confirm signature → Step 2 `Get-Process | Where-Object {$_.Path -like "*DMLS*"}` (returned no output) plus `Stop-Process -Name dmls -Force` → Step 3 rebuild still failed with LNK1105 → Step 4 `Remove-Item -Force D:\DMLS\build\dmls.exe; $?` → `True` → Step 5 `Set-Location D:\DMLS; .\build.bat run`.
- Expected result: build completes without LNK1105 and the run log shows `INFO: Initializing raylib 5.5` … `INFO: Window closed successfully`.
- Parameterized values: project root (`D:\DMLS`), output exe (`build\dmls.exe`), process name (`dmls`), build command (`.\build.bat run`).

### Example 2: Distinguishing the lock error from other errors in the same build log
- Input: a build log that also contains ordinary `Error:`/`Warning:` lines from earlier iterations.
- Procedure: scan only for `LNK1105 ... error code 1224`; treat everything else as normal build-error work.
- Expected result: the lock branch is entered only when the LNK1105 line is present; otherwise the generic build-error loop applies.
- Parameterized values: error token (`LNK1105`), win32 error code (`1224`).

## Evidence
problem:
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 453, source_part_index: 0, quote: "LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224" — supports: the rebuild failure signature (output exe locked), from a build tool result.
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 456, source_part_index: 0, quote: "LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224" — supports: the same failure persisted after stopping the named process, so the stop alone did not release the file.
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 458, source_part_index: 0, quote: "(PowerShell completed with no output)" — supports: the process search for the project's path returned nothing, so absence of a visible process does not rule out a lock.

action:
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 455, source_part_index: 0, quote: "Stop-Process -Name dmls -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500; Set-Location D:\DMLS; .\build.bat run 2>&1" — supports: first recovery attempt (stop by name, then rebuild); its result at source_index 456 still showed LNK1105, so this attempt alone did not resolve it.
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 460, source_part_index: 0, quote: "handle64.exe: The term 'handle64.exe' is not recognized as a name of a cmdlet, function, script file, or executable program." — supports: no handle-inspection utility on the host, forcing a PowerShell-only recovery path.
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 461, source_part_index: 0, quote: "Remove-Item -Force D:\DMLS\build\dmls.exe -ErrorAction SilentlyContinue; $? " — supports: the escalation step that removes the locked output binary directly.

verification:
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 462, source_part_index: 0, quote: "True" — supports: the output exe was successfully deleted, i.e. the file was no longer locked (tool result of the `Remove-Item` command).
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 465, source_part_index: 0, quote: "[odin] Built build\dmls.exe" — supports: the linker completed without LNK1105 once the output file was free (tool result of the rebuild after the deletion).
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 465, source_part_index: 0, quote: "INFO: Initializing raylib 5.5" — supports: the rebuilt program then started and loaded its libraries (same tool result).
- file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02, source_index: 465, source_part_index: 0, quote: "INFO: Window closed successfully" — supports: the run finished normally rather than failing at load time.

---
name: clear-locked-output-exe-lnk1105
description: Use when a Windows link step fails with LNK1105 "cannot close file ... error code 1224" because the previously built exe is still held open. Helps the agent release the lock with the recovery that actually worked in this project and re-verify with a successful relink. Requires PowerShell access to the build output directory. Do not use when the link fails for any other reason (missing libs, compile errors).
---
# Unblock LNK1105 (error 1224) When the Linker Cannot Close the Output Executable

## Goal
Given a Windows link step that fails with LNK1105 "cannot close file '<output exe>'; error code 1224", release the lock on the output executable so the relink succeeds, and confirm with a clean `[odin] Built <path>` style build result.

## Scope
### In scope
- `LNK1105: cannot close file '<output.exe>'; error code 1224` at link time on Windows when a previously produced exe is still open.
- Releasing the lock by force-deleting the output file, then rebuilding.
- Documenting which lock-release attempts did NOT work in this project so they are not repeated blindly.

### Out of scope
- Any other linker error (LNK1104 permission denied on a different path, missing import libraries, unresolved externals).
- Diagnosing which process holds the handle when deletion keeps failing — attempts to identify the holder (Get-Process path filter, process module scan, `handle64.exe`) all failed or were unavailable here; no root cause was confirmed.
- Program-level graceful shutdown design.

## Inputs
- **Failing build command**: command string, source = project build entry point (here `build.bat run` or a direct `odin build src -out:build/dmls.exe ...`), required = yes, constraint = must reproduce `LNK1105 ... error code 1224` before you act, default = 无
- **Locked output path**: file path, source = the LNK1105 message itself (here `D:\DMLS\build\dmls.exe`), required = yes, constraint = exact path from the error text, default = 无
- **Write/delete permission on the build directory**: permission, source = OS/user context, required = yes, constraint = must allow force-deleting the exe, default = 无
- **Toolchain on PATH**: environment, source = shell (`odin` / `clang++`), required = yes, constraint = needed for the rebuild verification, default = 无

## Outputs
### Artifacts
- **Deletion confirmation**: tool output of the forced removal of the locked exe (e.g. `True`).
- **Successful rebuild**: build output containing the "Built <output path>" line and no LNK1105.

### Success criteria
- The same build command that produced LNK1105 now completes and emits the output executable.

### Failure criteria
- LNK1105 persists after forced deletion — the handle is re-acquired within the same command (e.g. a background `-Wait` launch inside the build script) or held by a process that cannot be terminated; the root cause was never confirmed in this trajectory, so report the unresolved state rather than claiming a fix.

## Preconditions
- The exact LNK1105 message is captured, including the locked file path — this names the only file you may delete.
- You have delete permission on that file and the build directory.
- The compiler/linker toolchain is on PATH so a rebuild can run immediately after releasing the lock.
- No source changes are pending that would otherwise explain the link failure; LNK1105 is purely a file-handle problem.
- If you cannot delete the file even with `-Force`, stop and report the unresolved lock — the trajectory never established a confirmed root cause for persistent locks.

## Procedure
### Step 1: Confirm the failure signature
- actions: run the build and capture the exact linker line.
- inputs: build command.
- outputs: `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224`.
- cautions: only this signature belongs here.
- preserve: the error text (it names the file).
- next: continue.

### Step 2: Release the lock on the output exe
- actions: delete the output file directly with `Remove-Item -Force <path> -ErrorAction SilentlyContinue; $?` and check the boolean.
- inputs: locked output path.
- outputs: `True` when the file is gone.
- cautions: deleting only the exe is enough; do not touch the `.lib`/`.exp` or other build outputs.
- preserve: all other artifacts.
- next: rebuild immediately (Step 3).

### Step 3: Rebuild and confirm success
- actions: rerun the same build command; look for the "Built <output path>" line and absence of LNK1105.
- inputs: build command.
- outputs: successful link + new exe.
- cautions: if the build script itself relaunches the app with a blocking `-Wait`, the new exe may be locked again for the next build.
- preserve: build log.
- next: done on a clean build; otherwise go to Common Failures.

### Step 4 (only if Step 2 failed): attempt to find the holding process
- actions: tried in this trajectory and NOT effective here — `Stop-Process -Name <app> -Force` before rebuild (error returned again), `Get-Process | Where { $_.Path -like "*<app>*" }` (no output), a `Process.Modules` scan for the file (permission/tooling failed), `handle64.exe` (not installed).
- inputs: none beyond shell.
- outputs: usually nothing usable.
- cautions: do not report success from these; none produced a confirmed holder.
- preserve: report the unresolved lock honestly.
- next: stop and escalate (e.g. reboot or close the launcher) — root cause unconfirmed.

## Decision Rules
### When the error is exactly `LNK1105 ... error code 1224` on the output exe
Force-delete that file and rebuild immediately (Steps 2–3).

### When `Stop-Process -Name <app>` before rebuilding does not clear the error
Do not retry the same kill with variations as the primary plan — in this trajectory both `Stop-Process -Name dmls` and a `Get-Process ... Path -like '*dmls*'` kill were followed by the same LNK1105; go to direct `Remove-Item -Force` of the exe instead.

### When `Remove-Item -Force` reports success
Proceed straight to the rebuild; the lock was held by something the delete could still override.

### When the lock returns on subsequent builds even after successful deletion
Suspect something in the run path re-launching and holding the exe (a blocking `-Wait`/`run` step inside the build script was hypothesised here, never confirmed) — inspect the build script's run step, and if no holder can be identified, report the state as unresolved.

## Invariants
- Delete only the file named in the LNK1105 message; never the import library or unrelated build outputs.
- Do not change source code or build flags in response to LNK1105 — it is a handle problem, not a code problem.
- Do not report the lock as "cleared" based on a kill command alone; the verification is a subsequent successful relink.
- Do not claim a root cause for the lock: none was confirmed in this trajectory, so any causal statement must be marked unconfirmed.
- Preserve the rest of the build directory while deleting the exe.

## Common Failures
### Failure: Killing the app by name and rebuilding, still LNK1105
- symptoms: `Stop-Process -Name <app> -Force` (and even killing `dmls,cmd`) followed by rebuild yields the identical LNK1105 message.
- causes: unconfirmed — the holder is either not named as expected or is re-created by the build/run flow.
- recovery: bypass process hunting and force-delete the exe itself (`Remove-Item -Force`), which succeeded in this trajectory.

### Failure: Tools to identify the handle holder are missing or blocked
- symptoms: `handle64.exe: The term ... is not recognized`; a `Process.Modules` scan returns a permission/tooling error; `Get-Process | Where Path -like '*dmls*'` prints nothing.
- causes: Sysinternals not installed; enumeration restricted.
- recovery: accept that the holder may stay unknown; rely on forced deletion, and if deletion itself fails, report unresolved instead of guessing.

### Failure: Lock reappears on later builds after a previous success
- symptoms: LNK1105 recurs (observed repeatedly near the end of the session) even though an earlier delete+rebuild worked.
- causes: unconfirmed; a blocking run step in the build script was hypothesised but never verified.
- recovery: inspect the build script's run/`-Wait` step and ensure no process is left holding the exe before the next build; otherwise escalate (reboot/close launcher) and say the cause is unresolved.

## Verification
- `Remove-Item -Force <locked exe>` returns `True` (the file was actually removed).
- The same build command that printed `LINK : fatal error LNK1105: cannot close file '...'; error code 1224` now completes without that line.
- The build output contains the success marker for the output binary (observed: `[odin] Built build\dmls.exe`) and exits without a link error status.
- The output executable exists again in the build directory with a fresh timestamp.
- If any of the above is missing, the lock is not cleared — report failure rather than "fixed".

## Examples
### Example 1: force-delete the locked exe, then rebuild
- input: build output `LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224` after a previous run of the app.
- procedure: `Remove-Item -Force D:\DMLS\build\dmls.exe -ErrorAction SilentlyContinue; $?` → `True`; immediately rerun the same build command.
- expected result: build completes and prints `[odin] Built build\dmls.exe` with no LNK1105.
- parameterized values: output `<build>\<app>.exe`; build command `<build script or compiler invocation>`.

### Example 2: kill-by-name attempts that did not clear the lock
- input: same LNK1105 after `Stop-Process -Name <app> -Force` (and after also killing `cmd`).
- procedure: observe that the rebuilt attempt returns the identical LNK1105 line; do not repeat kill variations as the main strategy; switch to direct deletion of the exe.
- expected result: the kill-only path is recorded as ineffective; deletion path is what leads to a successful relink.
- parameterized values: process name `<app>`; holder remains unknown — never asserted.

## Evidence
- problem — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 453, source_part_index 0, quote: `LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224`, supports: the exact failure signature and the locked file path, taken from the build tool output.
- problem — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 456, source_part_index 0, quote: `LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224`, supports: kill-by-name (`Stop-Process -Name dmls ...` in the preceding call at index 455) did NOT clear the lock — the same error returned.
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 461, source_part_index 0, quote: `Remove-Item -Force D:\DMLS\build\dmls.exe -ErrorAction SilentlyContinue; $? `, supports: the recovery that worked — force-deleting the locked output exe directly.
- action — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 462, source_part_index 0, quote: `True`, supports: the deletion succeeded, so the file handle was no longer blocking removal.
- verification — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 465, source_part_index 0, quote: `[odin] Built build\dmls.exe`, supports: the rebuild immediately after the deletion completed without LNK1105 — lock released.
- verification (limit) — file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 974, source_part_index 0, quote: `Exit: 81`, supports: LNK1105 recurred later in the session despite further kill attempts, so the underlying holder was never confirmed — the skill claims only delete-then-rebuild, not a root-cause fix.

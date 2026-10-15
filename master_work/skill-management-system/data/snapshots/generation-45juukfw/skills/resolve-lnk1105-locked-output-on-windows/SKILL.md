---
name: resolve-lnk1105-locked-output-on-windows
description: Use when a Windows link step fails with LNK1105 and error code 1224 naming the output .exe. Helps the agent identify the process holding the output file, release or bypass the lock, and relink successfully. Requires a Windows host with PowerShell (Stop-Process/Get-Process/Remove-Item) or Git-Bash (taskkill/sleep) and the project's normal build command. Do not use when the linker reports missing objects, undefined symbols, or any error other than LNK1105/1224.
triggers:
  - "LNK1105"
  - "error code 1224"
  - "cannot close file"
---
# Resolve LNK1105 "cannot close file" Output Locks on Windows

## Goal
Diagnose and clear a Windows link failure reported as `LINK : fatal error LNK1105: cannot close file '<output>'; error code 1224`, so the project's normal build command links the intended output binary successfully and the produced binary can be executed.

## Scope
### In scope
- Windows link failures whose message is exactly `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224` (MSVC `link.exe` invoked through clang/clang++/clang-cl, `make`, `.bat` build scripts, or PowerShell build loops).
- Identifying which running process holds the output `.exe` (by image name or by full path).
- Releasing the lock by terminating the holding process, waiting for handle release, force-deleting the output file, or — as an unblock workaround — relinking to a fresh output filename.
- Confirming the original build command then links and the binary runs.

### Out of scope
- Link errors other than LNK1105/1224 (undefined symbols, missing object files, LNK1123/LNK1104 media errors).
- Source-code or compiler-flag problems; compilation of `.c/.cpp` objects (these already succeeded in every observed case).
- Linux/macOS build environments and non-Windows error codes.
- Runtime crashes of the produced binary that occur after a successful link (those are separate failures).

## Inputs
- **Failing build output**: text of the failed link step; source = the shell/tool result that contained `LNK1105` and `error code 1224`; required = yes; constraint = must name the output file path (e.g. `bin\yggdrasil.exe`, `build\frost_smoke.exe`); default = 无.
- **Locked output path**: the `.exe` path quoted in the LNK1105 message; source = parsed from the error line; required = yes; constraint = used verbatim for deletion/existence checks; default = 无.
- **Output binary image name**: file name without directory (e.g. `yggdrasil.exe` → process name `yggdrasil`); source = derived from the locked output path; required = yes; constraint = process names on Windows omit the `.exe` suffix in `Stop-Process -Name`; default = 无.
- **Build command**: the exact command that produced the failure (`make`, `.\build.bat run`, direct `clang++ ... -o <out>`); source = the failed tool call; required = yes; constraint = must be re-run unchanged after the lock is cleared; default = 无.
- **Shell environment**: PowerShell or Git-Bash on Windows; source = observed session shell; required = yes; constraint = PowerShell uses `Stop-Process`/`Get-Process`/`Remove-Item`, Bash uses `taskkill`/`sleep`; default = 无.
- **Post-lock delay**: wait before relink; source = 无 (operator choice); required = no; constraint = observed working values 300–1000 ms; default = 500 ms.
- **Fresh output filename** (workaround only): alternative `-o` target such as `test_solver2025.exe`; source = 无 (operator choice); required = no; constraint = only unblocks running under a new name; does not satisfy a build system that expects the canonical name; default = 无.

## Outputs
### Artifacts
- **Rebuilt output binary** at the original output path (e.g. `bin\yggdrasil.exe`, `build\frost_smoke.exe`), format = PE executable produced by the project's own link command.
- **Relink log** (tool result text) showing the link command completing without `LNK1105`.
- **Optional workaround binary** under a fresh name (e.g. `build\tests\test_solver2025.exe`), only if the fresh-name branch was used.

### Success criteria
- The original build command exits with the success status of that build system and its output contains no `LNK1105` / `error code 1224`.
- The output `.exe` exists at the expected path and (when the original task requires it) launches and produces its normal output.

### Failure criteria
- `LNK1105 ... error code 1224` still appears after the remediation steps.
- The binary exists but crashes or exits abnormally when run — this is a separate runtime problem, not an LNK1105 resolution.
- A process was terminated that was not matched to the locked output (unintended collateral kill).

## Preconditions
- The failing output must show both `LNK1105` and `error code 1224`; if either is absent, stop and diagnose the actual linker error instead.
- All compilation steps must already succeed — object files (`.o`) build cleanly and only the final link fails. If compilation also fails, fix that first.
- The shell must be Windows-capable with permission to terminate processes and delete files in the build directory (PowerShell `Stop-Process` / `Get-Process` / `Remove-Item`, or Git-Bash `taskkill`); without process-kill permission, fall back to the fresh-filename branch only.
- The exact original build command must be recoverable from the failed tool call so the identical command can be re-run for verification.
- A process-kill or file-delete must be authorized in the session; if the environment forbids killing processes, report the blocker instead of guessing at source-level "fixes".

## Procedure
### Step 1: Confirm the failure signature
- Actions: read the failed build output; require the line `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224` and note the exact output path.
- Inputs: failed tool result text.
- Outputs: locked output path, output image name (without `.exe` for `Stop-Process -Name`).
- Cautions: compilation lines preceding the error are context only — they succeeded; do not change compiler flags or sources.
- Preserve: the original build command verbatim for Step 4.
- Next: proceed to Step 2 when both LNK1105 and 1224 are present; otherwise stop and handle the real error.

### Step 2: Find and terminate the process holding the output
- Actions: kill processes by expected image name first, e.g. PowerShell `Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue`, or Bash `taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe 2>/dev/null`. If the name-based kill finds nothing or the lock persists, enumerate by path pattern, e.g. `Get-Process | Where-Object { $_.Path -like '*dmls*' -or $_.Name -like '*dmls*' } | Stop-Process -Force -EA 0`, then kill it.
- Inputs: output image name; shell type.
- Outputs: a process list (possibly empty) and terminated matching processes.
- Cautions: `Stop-Process -Name x -ErrorAction SilentlyContinue` prints nothing when no such process exists — an empty result does not prove the lock is gone; check the file before relinking.
- Preserve: only processes whose name/path matches the locked output; never a blanket `Stop-Process` of everything.
- Next: proceed to Step 3.

### Step 3: Short wait, then verify the file handle is releasable
- Actions: sleep briefly (`Start-Sleep -Milliseconds 500` / `sleep 1`), then optionally test deletability with `Remove-Item -Force <path> -ErrorAction SilentlyContinue` and check `$?`, or check existence with `[System.IO.File]::Exists('<path>')`.
- Inputs: locked output path.
- Outputs: whether the output file can now be deleted / exists.
- Cautions: Windows may keep the handle a moment after process exit — an immediate relink can still fail even after a successful kill.
- Preserve: if `Remove-Item` returns `True`, the file is gone; the build system will recreate it.
- Next: proceed to Step 4; if deletion fails and no matching process exists, use the Step 5 workaround.

### Step 4: Re-run the identical build command
- Actions: re-run the exact command from Step 1 (e.g. `make`, `.\build.bat run`, or the direct `clang++ ... -o <out>` line).
- Inputs: original build command.
- Outputs: new link log.
- Cautions: one retry immediately after a kill may still report LNK1105; retry once more after another ~1 s wait before escalating.
- Preserve: all flags, object lists, and output paths unchanged — this is verification of the lock fix, not a build-system refactor.
- Next: if the log contains no LNK1105 and the build's success message appears, go to Verification; if it still fails, go to Step 5.

### Step 5 (workaround): Link to a fresh output filename
- Actions: when the canonical output must stay locked or the lock cannot be cleared, relink with a different `-o` target (e.g. `build\tests\test_solver2025.exe`, `build\tests\test_indexing2025.exe`) using the same sources and objects; run that binary instead.
- Inputs: link command with `-o` replaced by a fresh filename.
- Outputs: fresh-named executable that links and runs.
- Cautions: this only unblocks running under the new name; the canonical binary remains stale/locked, so the original build must still be retried after the lock clears for any deliverable that requires the canonical path.
- Preserve: sources, objects, and flags identical to the canonical link.
- Next: after running the fresh binary, return to Step 2–4 to restore the canonical output when it is required.

## Decision Rules
### When the error is LNK1105 with `error code 1224`
Treat the output `.exe` as locked by a running process (or a not-yet-released handle). Skip compiler-flag and source investigation entirely; go to process termination (Step 2).

### When a name-based kill returns no output / the lock persists
Enumerate processes by path or partial name match (`Get-Process | Where-Object { $_.Path -like '*<name>*' }`) and kill the matches; background launchers that `Wait` on the binary can hold the handle under a different process name. Observed in this group: a background `-Wait` process kept `dmls.exe` locked after `Stop-Process -Name dmls` had already run.

### When the relink immediately after a kill still reports LNK1105
Wait ~1 second and re-run the same build command; handle release can lag process exit. Observed: `Stop-Process -Name yggdrasil ...; make` still failed with LNK1105, while `Start-Sleep -Seconds 1; make` then linked successfully.

### When no matching process exists but the file still cannot be closed
Force-delete the output file (`Remove-Item -Force <path> -ErrorAction SilentlyContinue`, check `$?`) and relink; a successful delete (`$? == True`) means the build system can recreate the file.

### When the canonical output must remain locked (e.g. a hung test binary cannot be killed) and a runnable binary is needed now
Link to a fresh output filename with the same sources/objects and run that instead; return to restoring the canonical name later. Observed: `test_solver2025.exe` / `test_indexing2025.exe` linked with exit 0 while the canonical `.exe` was still locked.

### When the relink succeeds but the binary then exits abnormally
Stop treating it as LNK1105 — the lock problem is solved; report the runtime failure separately (in this group, a test binary linked fine and then exited `-1073741571`, a stack-overflow crash unrelated to the lock).

## Invariants
- Never modify source files, build scripts, compiler flags, or object lists to "fix" LNK1105; the fault is a file lock, not the build definition.
- Only terminate processes whose name or path matches the locked output binary; do not kill unrelated processes or the whole shell session.
- Do not report build success without a fresh link log showing the original command completing with no `LNK1105`.
- Do not treat the existence of an old `.exe` as proof of a successful relink — the file may be a stale, still-locked binary from a previous build.
- Re-run the identical build command for verification; a link under a different output name only proves the workaround branch, not that the canonical target is buildable.
- Do not claim the lock is gone because a kill command was silent — `-ErrorAction SilentlyContinue`/`2>/dev/null` suppress both "killed" and "not found".
- Distinguish the lock problem from any subsequent runtime failure of the produced binary; report them separately.

## Common Failures
### Failure: name-based kill silently does nothing
- Symptoms: `Stop-Process -Name <x> -ErrorAction SilentlyContinue; make` prints nothing extra and the very next link still fails with LNK1105/1224.
- Causes: the holder's process name differs from the output name (launcher/`-Wait` parent, test harness, IDE), or no such named process exists so the kill was a no-op.
- Recovery: enumerate by path pattern (`Get-Process | Where-Object { $_.Path -like '*<name>*' -or $_.Name -like '*<name>*' }`), kill the matches, wait ~1 s, relink. If nothing matches, go to the delete branch.

### Failure: relink retried too quickly after a successful kill
- Symptoms: kill appears to work but the immediate relink still reports `error code 1224`.
- Causes: the OS releases the image file handle slightly after process termination.
- Recovery: `Start-Sleep -Seconds 1` (or `sleep 1`) and re-run the same build command; observed to succeed where the immediate retry failed.

### Failure: file locked but not deletable and no owning process found
- Symptoms: `Remove-Item -Force` fails and `Get-Process` by name/path returns nothing.
- Causes: unknown holder (driver-level or non-enumerable handle); the trace did not confirm a cause in this situation.
- Recovery: use the fresh-output-filename workaround to get a runnable binary, keep the canonical build reported as blocked, and escalate rather than deleting unrelated files.

### Failure: stale binary mistaken for a successful rebuild
- Symptoms: the `.exe` exists and runs, but it is the pre-lock version (e.g. a test binary that was crashing before the change).
- Causes: assuming existence equals a fresh link.
- Recovery: require a link log from the post-fix run of the original command; compare timestamps or content before claiming success.

### Failure: LNK1105 resolved but the binary crashes on run
- Symptoms: link succeeds, then the program exits with a crash code (e.g. `-1073741571`) or no output.
- Causes: unrelated runtime defect (in this group, a stack-overflow crash from large on-stack test fixtures).
- Recovery: stop LNK1105 work here — the lock is fixed — and handle the runtime failure as its own problem.

## Verification
Check each item against a fresh tool result from the post-fix run (do not mark based on memory or on the pre-fix log):
- The original build command's output contains no `LNK1105` and no `error code 1224`.
- The build's own success indicator appears (e.g. a `"Built: <path>"` line from the build script, `make` exiting 0, or the script's `Built build\<name>.exe` banner).
- The output file exists at the expected path (e.g. `[System.IO.File]::Exists('<path>')` → `True`, or the build script reports it).
- If a process kill was performed, a re-query shows no remaining process matching the output name/path (`Get-Process | Where-Object { $_.Name -like '*<name>*' }` returns empty).
- If the original task requires running the binary, the produced executable launches and emits its expected output (e.g. test summary lines, application startup log) with a normal exit status.
- If only the fresh-filename workaround succeeded, the report explicitly states the canonical output is still blocked and must be relinked later.

## Examples
### Example 1: kill test binaries by image name, wait, rebuild (Bash on Windows)
- Input: `LINK : fatal error LNK1105: cannot close file 'build\frost_smoke.exe'; error code 1224` while `make CC=clang AR=llvm-ar OPT="-O0" BUILD=build` linked smoke/subsystem/bytecode test executables.
- Procedure: Step 1 signature confirmed → Step 2 `taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make CC=clang AR=llvm-ar OPT="-O0" BUILD=build 2>&1` → Step 4 re-run of the same `make`.
- Expected result: link completes, `make` runs the tests, log ends with `All smoke tests PASSED.` and `Results: 135 passed, 0 failed`.
- Parameterized values: image names = the three test executables; wait = `sleep 1`; build command = project `make` with its `CC/AR/OPT/BUILD` variables.

### Example 2: immediate retry fails, delayed retry succeeds (PowerShell)
- Input: `Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make 2>&1` still returned `LINK : fatal error LNK1105: cannot close file 'bin\yggdrasil.exe'; error code 1224`.
- Procedure: treat as handle-release lag (Step 3/4 retry branch) → `Start-Sleep -Seconds 1; make 2>&1`.
- Expected result: the relinked binary builds and the log ends with `"Built: bin/yggdrasil.exe"`.
- Parameterized values: process name = `yggdrasil`; wait = 1 second; output = `bin\yggdrasil.exe`.

### Example 3: find holder by path, delete the locked file, full rebuild (PowerShell)
- Input: `LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224` persisted after `Stop-Process -Name dmls -Force -ErrorAction SilentlyContinue; ... .\build.bat run`.
- Procedure: Step 2 path-based enumeration (`Get-Process | Where-Object { $_.Path -like "*DMLS*" }`), later killing everything matching `*dmls*` (the session traced it to a background `-Wait` launcher) → Step 3 `Remove-Item -Force D:\DMLS\build\dmls.exe -ErrorAction SilentlyContinue; $?` → `True` → Step 4 `.\build.bat run`.
- Expected result: `[odin] Built build\dmls.exe`, the app starts (`INFO: Initializing raylib 5.5`) and exits cleanly (`Window closed successfully`).
- Parameterized values: path pattern = `*DMLS*`/`*dmls*`; output = `D:\DMLS\build\dmls.exe`; build command = `.\build.bat run`.

### Example 4: fresh output filename to unblock immediately (PowerShell)
- Input: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_indexing.exe'; error code 1224` (a still-running/crashed test binary held the canonical name).
- Procedure: Step 5 — relink the same sources/objects with `-o build\tests\test_solver2025.exe` and `-o build\tests\test_indexing2025.exe`, then run those binaries; canonical output restored later once the lock clears.
- Expected result: `test_solver: 0` / `test_indexing: 0` link exit codes, and the fresh binary prints `22/22 tests passed`.
- Parameterized values: fresh suffix = `2025`; sources/objects unchanged from the canonical link.

## Evidence
**Problem**
- file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index 575, source_part_index 0 — quote: `LINK : fatal error LNK1105: cannot close file 'build\frost_smoke.exe'; error code 1224` — supports: the failure signature (LNK1105 + 1224 naming the output exe) during a `make` link of test binaries.
- file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02`, source_index 453, source_part_index 0 — quote: `LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224` — supports: same signature for an Odin/clang link of an application exe.
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index 1068, source_part_index 0 — quote: `LINK : fatal error LNK1105: cannot close file 'bin\yggdrasil.exe'; error code 1224` — supports: a name-based `Stop-Process` in the same command line did not prevent the lock on the immediate retry.

**Action**
- file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index 577, source_part_index 0 — quote: `taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make CC=clang AR=llvm-ar OPT="-O0" BUILD=build 2>&1` — supports: kill-by-image-name + 1 s wait + identical rebuild as the remediation.
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index 1069, source_part_index 0 — quote: `Start-Sleep -Seconds 1; make 2>&1` — supports: delayed retry branch after an immediate post-kill retry failed.
- file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02`, source_index 461, source_part_index 0 — quote: `Remove-Item -Force D:\DMLS\build\dmls.exe -ErrorAction SilentlyContinue; $? ` — supports: force-delete branch when the holder could not be identified by name.
- file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-04`, source_index 985, source_part_index 0 — quote: `The file is still locked — probably by the background `-Wait` process from earlier. Let me find and kill it:` — supports: name-based kill can miss a differently-named launcher holding the exe.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 258, source_part_index 0 — quote: `# Link just test_solver and test_indexing (fresh filenames to avoid lock)` — supports: the fresh-output-filename workaround branch.

**Verification**
- file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index 580, source_part_index 0 — quote: `All smoke tests PASSED.` — supports: after kill + sleep + rebuild the same `make` linked and ran the smoke test successfully.
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index 1070, source_part_index 0 — quote: `"Built: bin/yggdrasil.exe"` — supports: delayed retry produced a successful link of the canonical output.
- file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02`, source_index 462, source_part_index 0 — quote: `True` — supports: `Remove-Item -Force` on the locked exe succeeded, so the build could recreate it.
- file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02`, source_index 465, source_part_index 0 — quote: `[odin] Built build\dmls.exe` — supports: the unchanged build script linked the canonical output after the lock was cleared; the same result shows the app then ran (`INFO: Initializing raylib 5.5`) and closed cleanly.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 261, source_part_index 0 — quote: `22/22 tests passed` — supports: a fresh-filename binary linked (no LNK1105) and ran to completion, proving the workaround unblocks execution.
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index 1194, source_part_index 0 — quote: `LINK : build\\tests\\test_atoms.exe not found or not built by the last incremental link; performing full link` — supports: after killing test processes the link step no longer reports LNK1105; the remaining `exit: -1073741571` in that same result is a runtime crash, not a lock failure.

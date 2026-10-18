---
name: fix-lnk1105-locked-output-exe
description: Use when MSVC link fails with "LINK : fatal error LNK1105: cannot close file '<output>.exe'; error code 1224" on Windows. Helps the agent identify and kill the running process that locks the output executable, then relink successfully. Requires PowerShell or cmd with taskkill/Get-Process access. Do not use when the error is a different LNK code, when no exe is named in the error, or when the target is not on Windows.
---
# Fix LNK1105 "cannot close file" by Killing the Process Holding the Output EXE

## Goal
Unblock a Windows MSVC/clang link step that fails with LNK1105 (error code 1224, "cannot close file '<output>.exe'") by identifying and terminating the process that still holds the output executable open, then rerunning the link so the build completes.

## Scope
### In scope
- Diagnosing LNK1105 + error code 1224 on a named output executable (e.g. `bin\app.exe`, `build\tests\test_x.exe`, `D:\proj\build\tool.exe`) produced by clang/clang++ driving the MSVC `link.exe`, or by `make`, `build.bat`, or language toolchains (Odin, CMake) that link to a `.exe` on Windows.
- Locating the locking process (running instance of the just-built binary from a previous test run, a REPL left open, a game window, or a background launcher that was started with `Start-Process -Wait`).
- Killing the locking process via `Stop-Process -Force` (PowerShell) or `taskkill /F /IM`, waiting briefly, and relinking.
- Distinguishing this failure from compile errors that merely appear next to it in shared build output.

### Out of scope
- LNK errors other than LNK1105 (missing libraries LNK1104, unresolved externals LNK2019, etc.).
- File locks held by antivirus/indexer or other non-user processes — the sessions only demonstrated locks held by the project's own running binaries; if killing the named process does not free the file, the cause is unconfirmed and further diagnosis is needed.
- Non-Windows linkers (ld, lld direct) where this MSVC LINK message does not occur.
- Editing Makefiles, source code, or linker flags to work around the error.

## Inputs
- Link error output: string; source: the failed build tool result; required: yes; constraints: must contain `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224` — the quoted path identifies the locked file; default: none.
- Build command that failed: string; source: the agent's own prior tool call (e.g. `make`, `odin build ... -out:build/app.exe`, `clang++ ... -o bin/app.exe`, `build run`); required: yes; constraints: rerun the identical command after unlocking so no build configuration changes; default: none.
- Shell flavor: enum (PowerShell or bash/cmd); source: the execution environment; required: yes; constraints: observed sessions used PowerShell tool calls, `powershell.exe -Command "..."` from bash, and `taskkill` from bash; PowerShell cmdlets like `Get-Process` are not available directly in bash (they produced "command not found"); default: detect from the environment.
- Executable base name(s) to kill: string list; source: parsed from the LNK1105 path (e.g. `yggdrasil.exe`, `dmls.exe`, `frost_smoke.exe`, `test_atoms.exe`); required: yes; constraints: use the exact image name; killing by a loose pattern risks stopping unrelated processes; default: the file name in the LNK1105 message.
- Short settle delay: integer seconds; source: agent choice; required: no; constraints: sessions used `sleep 1`, `Start-Sleep -Seconds 1`, or `Start-Sleep -Milliseconds 600-800` after killing before relinking; default: 1.

## Outputs
### Artifacts
- A successful link step: build tool output showing the link command completing and the output exe being produced (e.g. `"Built: bin/yggdrasil.exe"`, `[odin] Built build\dmls.exe`), with no LNK1105 message.
- If the link still fails: a report naming the locked file, the processes that were found/killed, and the fact that the lock source remains unidentified.

### Success criteria
- The same build command that produced LNK1105 now exits 0 and emits the output executable.
- No `LNK1105` / `error code 1224` text appears in the new build output.

### Failure criteria
- LNK1105 recurs after killing the named process(es) and waiting — the locker is something else and is not confirmed by these traces.
- The build fails with a different error, which is out of scope for this skill.

## Preconditions
- The platform is Windows and the linker message comes from MSVC `LINK` (the message text begins with `LINK : fatal error LNK1105`); otherwise stop — this skill does not apply.
- The error names a specific output file with `error code 1224` (Windows ERROR_SHARING_VIOLATION). If a different error code is present, stop and diagnose separately.
- You have permission to terminate processes on the machine. If process-kill commands fail with access-denied, stop and report.
- The build was launched within this session or by a known prior step, so the locking process is likely one of the project's own binaries (test exe, REPL, app window, or a background launcher). If the exe path is unknown to the project, do not blindly kill processes.
- A shell is available that can run `powershell.exe -Command` or native PowerShell; in a bash shell, wrap PowerShell commands with `powershell.exe -Command "..."` — `Get-Process` run directly in bash fails with "command not found".

## Procedure
### Step 1: Confirm the failure mode
- Actions: Read the failed build output. Verify it contains `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224`. Extract the image name from `<path>` (e.g. `bin\yggdrasil.exe` → `yggdrasil.exe`). Note which command produced it (`make`, direct compiler link, `build.bat`, `odin build`).
- Inputs: build tool result.
- Outputs: locked file path, image name, original build command.
- Cautions: In a test-suite build the LNK1105 for one test binary sits next to pass/fail output of other suites; "COMPILE ERROR: x.cpp" printed by a custom test runner may actually be a link failure for that suite's exe, not a source-level compile error. Do not start editing source code based on those lines.
- Preserve: the exact build command so it can be rerun unchanged.
- Next: proceed to Step 2.

### Step 2: Identify candidate locking processes
- Actions: List processes whose name or path matches the image name. PowerShell: `Get-Process | Where-Object { $_.Name -like "*<base>*" -or $_.Path -like "*<path fragment>*" } | Select-Object Id, Name, Path`. Also consider that a launcher process (e.g. a `cmd /k` or `Start-Process -Wait` shell started in an earlier step) can keep the exe open even after the visible app is gone.
- Inputs: image name from Step 1.
- Outputs: list of PIDs/names to terminate, or an empty list.
- Cautions: `Get-Process`/`Stop-Process` are PowerShell-only; from bash use `powershell.exe -Command "..."`. A `-Wait` background launcher blocks until the child exits and can hold the file; killing only the child image may be insufficient.
- Next: if candidates were found, proceed to Step 3; if none, go to Step 4 and retry once with a delay.

### Step 3: Kill the locking processes and wait
- Actions: Force-stop the candidates. PowerShell: `Stop-Process -Name <base> -Force -ErrorAction SilentlyContinue` or `taskkill /F /IM <base>.exe`. When several test binaries may be running, kill them together (e.g. `taskkill /F /IM a.exe /IM b.exe /IM c.exe`). Then wait 1–2 seconds (`Start-Sleep -Seconds 1` / `sleep 1`) to let Windows release the file handles.
- Inputs: process list from Step 2.
- Outputs: processes terminated; short settle delay elapsed.
- Cautions: killing by a broad pattern (e.g. anything matching `*test*`) can stop unrelated processes; prefer the exact image name. Killing processes ends their user-visible sessions (open windows/REPLs) — acceptable here because they are stale instances of the artifact being rebuilt.
- Next: proceed to Step 5.

### Step 4: Delayed retry when no process is visible
- Actions: If Step 2 found nothing (the process may have just exited while the handle lingers), simply wait ~1 second and rerun the build: `Start-Sleep -Seconds 1; make`. In observed sessions a relink that failed twice succeeded on the delayed retry once the handle was released.
- Inputs: original build command.
- Outputs: relink result.
- Cautions: a single blind retry is a diagnostic, not a fix; if it fails again, escalate to Step 5 with explicit process search by file path.
- Next: proceed to Step 5 either way.

### Step 5: Relink and verify
- Actions: Rerun the identical build command from Step 1. Inspect the output for the LNK1105 line and for the success marker the build normally prints.
- Inputs: original build command.
- Outputs: fresh link result.
- Cautions: do not modify Makefiles, linker flags, or output paths to sidestep the lock — the artifact location is part of the project's contract.
- Next: if the link succeeds, stop (done). If LNK1105 repeats, the lock source is not the named process: report the still-locked file and the processes already tried; do not claim success.

## Decision Rules
### When the build output contains "LINK : fatal error LNK1105: cannot close file '<exe>'; error code 1224"
Treat it as a file lock on the output executable, not a code or configuration error. Do not edit source, Makefiles, or flags. Go straight to killing the owning process and relinking.

### When a test-suite run prints "COMPILE ERROR: <file>.cpp" immediately followed by LNK1105 for that suite's exe
Interpret the suite as failing at the link step because its previous exe is still running, not as having a source compile error. Kill the test exe processes and rerun; only treat it as a compile error if a rerun after unlocking shows a real compiler diagnostic.

### When Stop-Process by name followed immediately by make still fails with LNK1105
The handle may not have been released yet, or the locker is a launcher/parent process. Add a short sleep before relink, and search for processes whose Path matches the exe or that were started as background launchers (e.g. `Start-Process -Wait`, `cmd /k`) in earlier steps.

### When running from bash and Get-Process/Stop-Process fail with "command not found"
Wrap them: `powershell.exe -Command "Get-Process ... | Stop-Process -Force"`, or use `taskkill /F /IM <name>.exe` which works in bash.

### When no process matching the image name exists
Do not conclude the lock is gone or gone forever — retry once after a 1–2 s delay. If the retry succeeds, done. If it fails, report that the locker is unidentified rather than repeating kill attempts blindly.

### When the link fails after killing processes and a delayed retry
Stop and report: locked file path, processes killed, commands tried. The traces only confirm locks held by the project's own running binaries; other lock holders (antivirus, indexer) were never demonstrated, so do not speculate or claim a fix.

## Invariants
- Never edit source files, build scripts, linker flags, or output paths in response to LNK1105; the error is environmental (file lock), and the observed fixes changed no project files.
- Rerun the exact same build command after unlocking so that a successful link is attributable to releasing the lock, not to a configuration change.
- Do not report the build as fixed until a fresh link of the same command completes without the LNK1105 line.
- Do not label neighboring test-suite failures as compile errors when their output shows LNK1105 — link-lock failures and genuine compile failures must be reported distinctly.
- Kill only processes whose names/paths match the locked exe (or its known test binaries); do not use broad wildcard kills.
- Do not attribute the lock to antivirus or any other unverified holder; if the named process was not the locker, say the cause is unconfirmed.

## Common Failures
### Failure: Stop-Process by image name, then immediate make, still yields LNK1105
- Symptoms: `Stop-Process -Name <base> -Force ...; make` outputs the same `LNK1105 ... error code 1224` line.
- Causes (observed or plausible): the OS had not yet released the file handle when the relink ran; or the exe was opened by a parent/launcher process rather than an image with that name (one session suspected a background `Start-Process -Wait` process). Root cause unconfirmed in the traces.
- Recovery: wait 1–2 s and retry the same build (observed to succeed); if it persists, enumerate processes by Path/Modules matching the exe and kill those, including launcher shells.

### Failure: PowerShell cmdlets invoked from bash fail with "command not found"
- Symptoms: `Get-Process: command not found`, `Select-Object: command not found` while trying to inspect/kill processes.
- Causes: the Bash tool runs GNU bash, not PowerShell.
- Recovery: call `powershell.exe -Command "..."` with the cmdlet inside, or use `taskkill /F /IM <name>.exe`.

### Failure: LNK1105 persists after all matching processes are gone
- Symptoms: relink still reports `cannot close file ... error code 1224` with no candidate process found.
- Causes: unidentified lock holder; the traces do not establish any cause beyond the project's own running binaries.
- Recovery: report the locked path and attempted remediations; stop rather than looping kill/retry or altering the build.

### Failure: stale `-Wait` launcher keeps the exe locked invisibly
- Symptoms: no process named like the exe is visible, yet the file stays locked; the locker was traced to an earlier background launcher (`Start-Process ... -Wait`, `cmd /k` running the exe).
- Causes: a launcher process holds a handle until its child exits or is killed.
- Recovery: kill the launcher shell processes (e.g. `Stop-Process -Name cmd -Force` for the specific stale instances) along with the exe, wait, then relink.

## Verification
- The relink tool result contains the linker invocation completing with no `LNK1105` and no `error code 1224` line.
- The build's own success marker for the artifact appears (examples seen: `"Built: bin/yggdrasil.exe"`, `[odin] Built build\dmls.exe`, the smoke/subsystem/bytecode test binaries linking and their test suites running to "All tests PASSED" / "Results: ... 0 failed").
- The previously failing target now links as part of the same command (e.g. the whole `make` finishes rather than stopping at `make: *** [...] Error 1105`).
- If the target is a test binary, rerunning the suite shows its output instead of the "COMPILE ERROR"/LNK1105 pair, and suites that had passed still pass.
- Negative check: if a second attempt still prints LNK1105, verification has failed — report the unresolved lock; do not count partial builds of other targets as success for the locked one.

## Examples
### Example 1: Kill the stale app instance, wait, relink (compiler-built exe)
- Input: `make` fails with `LINK : fatal error LNK1105: cannot close file 'bin\yggdrasil.exe'; error code 1224` — a previous run of the CLI is still alive.
- Procedure: `Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make` — if it fails once more, `Start-Sleep -Seconds 1; make`.
- Expected result: link completes and prints `Built: bin/yggdrasil.exe`; no LNK1105.
- Parameterized values: image name `yggdrasil.exe`, output `bin\yggdrasil.exe`, delay 1 s.

### Example 2: Kill multiple running test binaries before a make-driven test rebuild
- Input: Stage-3 `make` fails at `clang ... -o build/frost_smoke.exe ...` with `LNK1105: cannot close file 'build\frost_smoke.exe'; error code 1224`; smoke/subsystem tests from the prior run may still be running.
- Procedure: `taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make CC=clang AR=llvm-ar OPT="-O0" BUILD=build`.
- Expected result: all three binaries link and the suites run to completion (`Results: 101 passed, 0 failed` for the bytecode suite).
- Parameterized values: three test image names, settle delay 1 s, same make invocation as before.

### Example 3: PowerShell process sweep for a GUI/headless app exe
- Input: `odin build src -out:build/dmls.exe ...` fails with `LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224`; the simulation app was launched in earlier steps, possibly via a background launcher.
- Procedure: `powershell.exe -Command "Get-Process dmls -EA 0 | Stop-Process -Force"`; `sleep 1`; rerun the identical `odin build` command. If still locked, also stop launcher shells and processes whose `Path` matches the DMLS build dir, wait 2 s, and relink.
- Expected result: `[odin] Built build\dmls.exe` and the app can be started again.
- Parameterized values: image `dmls.exe`, output `D:\DMLS\build\dmls.exe`, toolchain Odin/MSVC link.

### Example 4: Test-suite exe locked → false "COMPILE ERROR" lines disappear after kill
- Input: a custom runner reports `COMPILE ERROR: test_parser.cpp` followed by `LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224` for several suites while others pass.
- Procedure: `Get-Process | Where-Object { $_.Name -like "*test*" } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800`, then recompile/relink and rerun the previously "COMPILE ERROR"-ed suites individually.
- Expected result: the targeted suites link and run (e.g. `1/1 tests passed`), confirming the earlier failure was a link lock, not a source error.
- Parameterized values: process name filter for the project's test binaries, settle delay 0.8 s.

## Evidence
- problem: file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original`, source_index 491, source_part_index 0, quote "LINK : fatal error LNK1105: cannot close file 'bin\\yggdrasil.exe'; error code 1224", supports: LNK1105 + 1224 signature on a compiler-linked CLI exe during `make`.
- problem: file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__original`, source_index 575, source_part_index 0, quote "LINK : fatal error LNK1105: cannot close file 'build\\frost_smoke.exe'; error code 1224", supports: same signature for a C test binary inside a make-driven suite.
- problem: file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 453, source_part_index 0, quote "LINK : fatal error LNK1105: cannot close file 'D:\\DMLS\\build\\dmls.exe'; error code 1224", supports: same signature for an Odin-built app exe.
- problem: file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original`, source_index 1187, source_part_index 0, quote "COMPILE ERROR: test_parser.cpp\nLINK : fatal error LNK1105: cannot close file 'build\\tests\\test_parser.exe'; error code 1224 clang++: error: linker command failed with exit code 1105 (use -v to see invocation)", supports: custom runners can mislabel a link-lock failure as a compile error for that suite.
- action: file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__original`, source_index 577, source_part_index 0, quote "taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make CC=clang AR=llvm-ar OPT=\"-O0\" BUILD=build 2>&1", supports: killing all possibly running test images plus a 1 s settle delay before relinking.
- action: file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original`, source_index 1065, source_part_index 0, quote "Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make 2>&1", supports: PowerShell Stop-Process by image name immediately before rerunning the same build command.
- action: file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original`, source_index 1193, source_part_index 0, quote "cd d:\\Epilog; Get-Process | Where-Object { $_.Name -like \"*test*\" -or $_.Name -like \"*epilog*\" } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800", supports: process sweep filtered to the project's own binaries with a sub-second settle delay.
- action: file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original`, source_index 1069, source_part_index 0, quote "Start-Sleep -Seconds 1; make 2>&1", supports: delayed retry when an immediate kill+relink still failed.
- diagnosis: file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original`, source_index 1189, source_part_index 0, quote "Solver passes 22/22. The \"compile errors\" are just file-locked binaries from the previous run still in memory. `test_atoms` still crashes silently. Kill old processes and rerun:", supports: explicit agent diagnosis that the failures were file locks, not compile errors.
- diagnosis: file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 985, source_part_index 0, quote "The file is still locked — probably by the background `-Wait` process from earlier. Let me find and kill it:", supports: a `Start-Process -Wait` launcher can hold the exe lock invisibly.
- environment: file_id `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__original`, source_index 853, source_part_index 0, quote "/usr/bin/bash: line 1: Get-Process: command not found", supports: PowerShell cmdlets must be wrapped via powershell.exe when the shell is bash.
- verification: file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original`, source_index 1070, source_part_index 0, quote "clang++ -std=c++17 -Wall -Wextra -Wpedantic -Iinclude  -o bin/yggdrasil.exe build/codegen.o build/diagnostics.o build/lexer.o build/main.o build/parser.o\r\n\"Built: bin/yggdrasil.exe\"", supports: after kill+delay the same link completed and the build printed its success marker.
- verification: file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__original`, source_index 580, source_part_index 0, quote "clang -std=c11 -O0 -Wall -Wextra -Wno-unused-parameter -Wno-sign-compare -Wno-missing-field-initializers -D_GNU_SOURCE -DCONFIG_VERSION=\\\"frostcore-stage3\\\" -DWIN32_LEAN_AND_MEAN -D_WINSOCKAPI_ -o build/frost_smoke.exe build/smoke_test.o build/libfrostcore.a \r\nclang -std=c11 -O0 -Wall -Wextra -Wno-unused-parameter -Wno-sign-compare -Wno-missing-field-initializers -D_GNU_SOURCE -DCONFIG_VERSION=\\\"frostcore-stage3\\\" -DWIN32_LEAN_AND_MEAN -D_WINSOCKAPI_ -o build/frost_subsystems.exe build/subsystem_test.o build/libfrostcore.a", supports: relink after taskkill+sleep succeeded for the previously locked binaries and the suites ran.
- verification: file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original`, source_index 1199, source_part_index 0, quote "  PASS  minimal\r\n\r\n1/1 tests passed\r\nexit: 0", supports: after killing lingering processes, the previously link-blocked test binary built and its suite passed.

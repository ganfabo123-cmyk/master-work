---
name: fix-lnk1105-locked-output-exe
description: Use when clang/lld on Windows reports "LINK : fatal error LNK1105: cannot close file ... error code 1224" while relinking a binary that a running process still holds open. Helps the agent free or bypass the file lock and re-run the link until it succeeds, then re-run the binary to confirm. Do not use for compile errors, other LNK codes, or non-Windows platforms.
---
# Recover a Windows link step failing with LNK1105 (error 1224) on a locked output EXE

## Goal
Unblock a Windows link step that fails with `LINK : fatal error LNK1105: cannot close file '<output>'; error code 1224` by releasing or bypassing the lock on the output EXE, so that the same build command links successfully and the freshly linked binary runs and produces the expected output.

## Scope
### In scope
- Windows link failures whose text contains `LNK1105`, `error code 1224`, and `linker command failed with exit code 1105`, produced by `make`, `clang`/`clang++`, or a wrapper build script.
- Cases where the named output file is a project binary (`bin/yggdrasil.exe`, `epilog.exe`, `build/frost_smoke.exe`, `build/tests/test_*.exe`) that a previous run of the same program or a test run left running.
- Recovery actions: terminating the holding process (PowerShell `Stop-Process`, `taskkill`), waiting briefly and relinking, and relinking to a fresh output filename when the holder cannot be stopped.

### Out of scope
- Compilation errors, other link error codes (LNK1104, LNK1181, LNK2019, ...), and non-Windows lock semantics — the trajectory provides no verified experience for them.
- Read-only permission problems, antivirus holds, or locks held by unrelated system processes — no verified evidence exists for these causes.
- Test failures that appear only after the binary links successfully; those are separate problems.

## Inputs
- **Failing build command** — string; source: the failing tool call in the session (e.g. `make 2>&1`, an inline `clang++ ... -o <out>` line, or a PowerShell compile loop); required: yes; constraint: must be the command that produced the LNK1105 text; default: the exact same command is re-run after unblocking.
- **Locked output path/name** — string; source: parsed from `cannot close file '<path>'`; required: yes; constraint: keep the exact spelling (backslashes, `.exe` suffix) because it feeds the kill command and relink; default: none.
- **Process name to terminate** — string; source: the output EXE base name (e.g. `yggdrasil`, `epilog`, `frost_smoke.exe`, `test_indexing.exe`); required: yes when killing; constraint: only project processes that were started by this session's test/run steps; default: base name of the locked EXE.
- **Shell in use** — enum {PowerShell, bash}; source: the tool being used; required: yes; constraint: determines the kill and sleep syntax; default: the shell the failing build already ran in.
- **Wait before retry** — duration; source: agent choice informed by the trajectory; required: no; constraint: short delay only; default: 0.3–1 s (observed: `Start-Sleep -Milliseconds 500`, `-Milliseconds 300`, `-Milliseconds 800`, `sleep 1`, `Start-Sleep -Seconds 1`).
- **Alternate output filename** — string; source: agent choice; required: no; constraint: only used when the holder cannot be stopped; default: same directory, suffixed name (observed `build/tests/test_solver2025.exe`, `build/tests/${t}_final.exe`, `/tmp/dbg2.exe`).

## Outputs
### Artifacts
- Re-linked output EXE at the original path (or at the alternate path when the lock could not be cleared), format: Windows executable produced by the project's link command.
- Build tool output showing a clean link, format: stdout text containing the project's success line (observed `Built: bin/yggdrasil.exe`) or exit status 0 with no `LNK1105`.
- Post-link run output, format: stdout from executing the freshly linked binary (observed REPL banner, fixture transpile output, or a test summary line).

### Success criteria
- The re-run link command emits no `LNK1105` / `error code 1224` and reports success (observed `Built: bin/yggdrasil.exe`, `test_indexing: 0`, `All smoke tests PASSED.`).
- The linked binary is executed afterwards and produces the expected program output or test summary.

### Failure criteria
- LNK1105 repeats after kill + wait + relink, or the holding process cannot be terminated.
- The link succeeds but the binary then fails for a different reason (e.g. crash, failing test) — report it separately; this flow does not cover it.

## Preconditions
- The failing output must contain `LINK : fatal error LNK1105` and `error code 1224`; if the message differs, stop and treat it as a different problem (no evidence in the trajectory for other codes).
- Platform is Windows (the observed sessions ran `make`, `clang`, and PowerShell against `.exe` targets); otherwise stop.
- The locked file path must be readable from the error text so the holder can be identified.
- Permission to terminate the holding process must exist, and the holder must be a process this session's own run/test steps started — if the holder is unknown or not a project process, do not kill it; skip to the alternate-output branch.
- The link command itself must be reproducible (same compiler, flags, object list) so the retry isolates only the lock.

## Procedure
### Step 1: Read the lock signal from the link output
- Actions: locate `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224` in the failing tool result; extract `<path>`; note the wrapper text `linker command failed with exit code 1105`.
- Inputs: failing tool result.
- Outputs: locked file path, EXE base name.
- Cautions: exit code 1105 is the linker's code surfaced by clang; do not treat it as a source or Makefile defect.
- Preserve: the original build command and flags unchanged.
- Next: continue when the path is known; otherwise stop and report that the holder cannot be identified.

### Step 2: Stop the process holding the EXE
- Actions: kill by name — PowerShell `Stop-Process -Name <base> -Force -ErrorAction SilentlyContinue` (observed for `yggdrasil`, `epilog`), bash/MSYS `taskkill /F /IM <name>.exe` (observed for `frost_smoke.exe frost_subsystems.exe frost_bytecode.exe`), or a pattern filter when many test EXEs are held: `Get-Process | Where-Object { $_.Name -like \"*test*\" -or $_.Name -like \"*epilog*\" } | Stop-Process -Force -ErrorAction SilentlyContinue`.
- Inputs: EXE base name(s) from Step 1, shell from the session.
- Outputs: processes terminated (or no-op if none running).
- Cautions: `SilentlyContinue` keeps the script alive when nothing is running; kill only project processes.
- Preserve: all source and build files.
- Next: continue to Step 3; if killing is not permitted, go to Step 4.

### Step 3: Wait briefly, then relink with the identical command
- Actions: insert a short delay before re-running the same link — `Start-Sleep -Seconds 1; make 2>&1`, `Start-Sleep -Milliseconds 500; clang ... -o epilog.exe`, or `taskkill ...; sleep 1; make ...`.
- Inputs: original build command, wait duration (default 0.3–1 s).
- Outputs: new link attempt.
- Cautions: relinking immediately after the kill can still fail with LNK1105; the delay is what made a retry succeed after an instant retry failed.
- Preserve: output path unchanged on this branch.
- Next: continue to Step 5 when the link no longer prints LNK1105; otherwise repeat Step 3 once with a longer delay, then fall back to Step 4.

### Step 4: Bypass the lock with a fresh output filename (only if the holder cannot be stopped)
- Actions: relink to a new name in the same or a temp directory (observed `-o build/tests/test_solver2025.exe`, `-o build/tests/${t}_final.exe`, `-o /tmp/dbg2.exe`) and run that new binary instead.
- Inputs: same objects and flags, changed `-o` target.
- Outputs: freshly linked binary under the new name.
- Cautions: scripts that hard-code the old path must be pointed at the new name; the old path remains locked.
- Preserve: original output path and any build configuration.
- Next: continue to Step 5.

### Step 5: Verify by relinking and running
- Actions: confirm the link output shows the project's success line or exit 0 with no LNK1105; then execute the binary and observe real output (a fixture run, the REPL banner, or the test summary).
- Inputs: freshly linked binary.
- Outputs: build success text plus program/test output.
- Cautions: a clean link does not prove the program behaves correctly — the run step is mandatory.
- Preserve: everything already produced.
- Next: stop when both the link and the run checks pass; otherwise report the remaining failure verbatim.

## Decision Rules
### When the link text is `LNK1105 ... error code 1224`
Treat it as "output file still open", not as a code or Makefile bug: do not edit sources or build files; go straight to kill + short wait + relink.

### When the locked file is a program this session just ran or a test binary from the last suite run
Kill that process first — observed diagnosis "The binary is still running from the previous test. Need to kill the test runner first:" followed by `Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make 2>&1`, which then produced `Built: bin/yggdrasil.exe`.

### When one retry right after the kill fails again with LNK1105
Insert a short sleep and retry once more — the sequence `Stop-Process ...; make` (still LNK1105) followed by `Start-Sleep -Seconds 1; make 2>&1` produced `Built: bin/yggdrasil.exe`.

### When a batch loop links many test EXEs and several report LNK1105
End all of them at once by pattern, then relink — observed `taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make ...` and `Get-Process | Where-Object { $_.Name -like \"*test*\" ... } | Stop-Process -Force ...`.

### When the holding process cannot be terminated
Link to a fresh output filename and run that binary — observed comment "# Link just test_solver and test_indexing (fresh filenames to avoid lock)" with `-o build/tests/test_solver2025.exe`, after which `test_indexing: 0` was reported.

### When the error text is not LNK1105/1224
Stop; this procedure has no evidence behind it for other link errors.

## Invariants
- Never "fix" LNK1105 by editing source files, Makefiles, or build scripts; the fault is the open handle on the output file.
- Never terminate processes outside this project's own program and test binaries.
- Never change compiler flags or the object list while retrying — only the lock state (and, on the fallback branch, the output path) may change.
- Never report success from the link step alone: always execute the freshly linked binary afterwards.
- Never claim the problem is solved if LNK1105 still appears in the latest tool result.
- Never loop kill/retry indefinitely: one kill plus one delayed retry, then fall back to a fresh output name, then stop and report the verbatim error.
- Preserve all previously built artifacts and test outputs; do not delete a locked file by force.

## Common Failures
### Failure: Relink attempted immediately after the kill still fails with LNK1105
- Symptoms: two consecutive tool results both containing `LINK : fatal error LNK1105: cannot close file ... error code 1224`, even though `Stop-Process ...; make` was one command.
- Causes: the file handle was not yet released at the moment of relink (exact OS timing cause not confirmed in the trajectory).
- Recovery: re-run the same link after an explicit delay (`Start-Sleep -Seconds 1; make 2>&1`), which produced `Built: bin/yggdrasil.exe`.

### Failure: Whole test batch fails to relink — several EXEs report LNK1105 in one run
- Symptoms: a loop output shows `COMPILE ERROR: test_parser.cpp`, `LNK1105: cannot close file 'build\tests\test_parser.exe'`, and similar for other suites, with a summary like `=== 2 suite(s) PASSED, 5 FAILED ===`.
- Causes: the previous test round left its binaries running.
- Recovery: terminate every project test/main process (by exact name or name pattern), wait ~0.8 s, relink — afterwards the same runner reported `=== 6 PASSED, 1 FAILED ===` with the remaining failure being a different (crash) problem.

### Failure: Only the main program is killed, test EXEs stay locked
- Symptoms: main binary relinks cleanly but `build\tests\*.exe` still report LNK1105.
- Causes: each test executable is its own process name.
- Recovery: kill per EXE name (`/IM` list or `Get-Process` name filter) before relinking.

### Failure: The holder cannot be stopped
- Symptoms: LNK1105 persists after kill attempts, or the process must keep running.
- Causes: not confirmed in the trajectory.
- Recovery: link to a fresh output filename and run that binary instead; leave the old path alone.

## Verification
Check each item against a fresh tool result (do not mark done based on the plan):
1. The relinked command's output contains no `LNK1105` and no `error code 1224`.
2. The link reports success in the project's own words — observed `Built: bin/yggdrasil.exe`, `test_indexing: 0`, `test_solver: 0`, `All compiled`.
3. The binary is executed after linking and produces real program output — observed `Epilog 0.1  (type 'halt.' to exit, '?- goal.' to query)` after a kill-and-relink cycle, and a transpiled fixture body after `Built: bin/yggdrasil.exe`.
4. If a test suite was the trigger, its summary appears from the freshly linked build — observed `All smoke tests PASSED.` with `Results: 135 passed, 0 failed` after `taskkill ...; sleep 1; make`.
5. The lock source is gone: no project process with the locked EXE's base name remains (re-check with the same kill command or process query).
6. If the fresh-filename branch was used, the new path is the one being executed and the report names it explicitly.

## Examples
### Example 1: Kill the running program, then rebuild the main binary
- Input: `make 2>&1` fails with `LINK : fatal error LNK1105: cannot close file 'bin\yggdrasil.exe'; error code 1224`.
- Procedure: identify the holder from the output path; run `Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make 2>&1`; if LNK1105 repeats, run `Start-Sleep -Seconds 1; make 2>&1`; then run `.\bin\yggdrasil.exe <fixture>`.
- Expected result: link output shows `Built: bin/yggdrasil.exe` and the fixture run prints transpiled JavaScript.
- Parameterized values: `<base name>` = EXE base name without extension; `<fixture>` = any input file the program accepts; `<wait>` = 1 s.

### Example 2: Kill a whole test batch, wait, and rebuild everything
- Input: `make ...` ends with `LINK : fatal error LNK1105: cannot close file 'build\frost_smoke.exe'; error code 1224` and `make: *** [build/frost_smoke.exe] Error 1105`.
- Procedure: `taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make CC=clang AR=llvm-ar OPT="-O0" BUILD=build 2>&1`.
- Expected result: all three EXEs link, then the suites run and print `All smoke tests PASSED.` and `Results: 135 passed, 0 failed`.
- Parameterized values: `<exe list>` = every output EXE named in the failing batch; `<wait>` = 1 s; `<make vars>` = the project's usual make variables.

### Example 3: Relink to a fresh filename when the holder cannot be stopped
- Input: a PowerShell loop fails with `LINK : fatal error LNK1105: cannot close file 'build\tests\test_indexing.exe'; error code 1224` and `test_indexing exit: 1105`.
- Procedure: relink the same objects with `-o build/tests/test_solver2025.exe` and `-o build/tests/test_indexing2025.exe` (comment: "# Link just test_solver and test_indexing (fresh filenames to avoid lock)"), then execute the new binaries.
- Expected result: the tool result prints `test_solver: 0` and `test_indexing: 0`, and the run shows `22/22 tests passed` for test_solver.
- Parameterized values: `<suffix>` = a unique tag such as the year or `_final`; `<dir>` = the project's test binary directory.

## Evidence
Problem:
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-02`, source_index 491, source_part_index 0: "LINK : fatal error LNK1105: cannot close file 'bin\yggdrasil.exe'; error code 1224" — supports: the error signature and the locked output path in the primary case.
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-02`, source_index 370, source_part_index 0: "LINK : fatal error LNK1105: cannot close file 'epilog.exe'; error code 1224" — supports: same signature for a top-level EXE in a different session.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 223, source_part_index 0: "LINK : fatal error LNK1105: cannot close file 'build\tests\test_indexing.exe'; error code 1224" — supports: signature also occurs for individual test executables.
- file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index 575, source_part_index 0: "LINK : fatal error LNK1105: cannot close file 'build\frost_smoke.exe'; error code 1224" — supports: signature in a make-driven C build.

Action (diagnosis + recovery):
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 224, source_part_index 0: "The linker can't overwrite `test_indexing.exe` because it's still running. Let me run solver first, then wait:" — supports: correct root-cause reading (output EXE still running) before acting.
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index 967, source_part_index 0: "The binary is still running from the previous test. Need to kill the test runner first:" — supports: diagnosis that a prior test run holds the lock.
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index 968, source_part_index 0: "Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make 2>&1" — supports: kill-then-rebuild action in PowerShell.
- file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index 577, source_part_index 0: "taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make CC=clang AR=llvm-ar OPT=\"-O0\" BUILD=build 2>&1" — supports: batch kill of several test EXEs plus a 1 s wait before relinking.
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index 1069, source_part_index 0: "Start-Sleep -Seconds 1; make 2>&1" — supports: delayed retry after an immediate retry still failed (preceding event 1068 is another LNK1105 result).
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-02`, source_index 374, source_part_index 0: "Stop-Process -Name epilog -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500; clang -std=c11 -Wall -Wextra -Wpedantic -Iinclude main.c repl.c" — supports: kill plus a 500 ms wait folded into the same rebuild command.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 258, source_part_index 0: "# Link just test_solver and test_indexing (fresh filenames to avoid lock)" — supports: fresh-output-name branch when the holder cannot be stopped.
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index 1193, source_part_index 0: "Get-Process | Where-Object { $_.Name -like \"*test*\" -or $_.Name -like \"*epilog*\" } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800" — supports: pattern-based kill of all test/main processes before relinking.

Verification:
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-02`, source_index 728, source_part_index 0: "Built: bin/yggdrasil.exe" — supports: the relink after unlocking succeeded (same command previously failed at 726).
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index 1070, source_part_index 0: "Built: bin/yggdrasil.exe" — supports: the delayed retry after a failed immediate retry succeeded.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 259, source_part_index 0: "test_indexing: 0" — supports: the fresh-filename relink reported exit 0.
- file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index 580, source_part_index 0: "All smoke tests PASSED." — supports: after the batch kill and relink the binaries linked and ran to completion.
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-03`, source_index 536, source_part_index 0: "Epilog 0.1  (type 'halt.' to exit, '?- goal.' to query)" — supports: the binary relinked after kill-and-wait actually runs.

---
name: unlock-locked-test-exe-before-relink
description: Use when relinking a test binary fails with LNK1105 "cannot close file ... error code 1224" although the sources are unchanged. Helps the agent identify that a still-running test process holds the executable, stop it, and relink successfully. Requires Windows process-management commands and the ability to rerun the test build loop. Do not use when the error is LNK2019/LNK1120 (unresolved symbol), LNK2005 (duplicate), or when no previous run of that binary exists.
---
# Clear LNK1105 "cannot close file" by Stopping Lingering Test Processes

## Goal
Unblock test-binary relinking on Windows by identifying and terminating the process that still holds the previous `test_*.exe`, so the link completes and the suite can run.

## Scope
### In scope
- Link-stage errors of the form `LNK1105: cannot close file '<path>.exe'; error code 1224` produced while rebuilding test executables that were built and launched earlier in the same session.
- Build harnesses that label any non-zero compiler/linker exit as a compile error, so the lock appears mislabelled.
- Recovery by stopping lingering processes (by name or by image name) and relinking, with a short wait before the retry.

### Out of scope
- `LNK2019`/`LNK1120` unresolved-symbol errors, `LNK2005` duplicate definitions — code-level defects.
- Read-only file locks held by antivirus or an editor; not observed in this trace.
- Crashes of the test binary at run time (exit `-1073741571`), which survive the relink.

## Inputs
- **Linker error text** — type: string; source: test build tool result; required: yes; constraints: must contain `LNK1105: cannot close file` and `error code 1224`; default: none.
- **Names of the affected test binaries** — type: list of strings; source: the failing output (observed: `test_parser.exe`, `test_terms.exe`, `test_unifier.exe`, `test_variables.exe`, `test_atoms.exe`); required: yes; constraints: used as process names for termination; default: none.
- **Process-management command** — type: shell command; source: agent (observed: PowerShell `Stop-Process -Name <names> -ErrorAction SilentlyContinue` and `Stop-Process -Force` filtered by name pattern, plus `taskkill /F /IM "<name>.exe"`); required: yes; constraints: must tolerate names with no running process; default: PowerShell `Stop-Process -ErrorAction SilentlyContinue`.
- **Test build/run command** — type: command; source: test harness; required: yes; constraints: must be rerunnable immediately after the processes are stopped; default: none.
- **Settling delay** — type: integer (ms); source: agent; required: recommended; constraints: observed 500–800 ms after stopping processes before relinking; default: `500`.

## Outputs
### Artifacts
- A clean relink log for the previously locked binaries (no `LNK1105`, no `error code 1224`).
- Freshly built `build\tests\*.exe` and their run output.

### Success criteria
- The build loop produces the locked binary again and the linker reports success for it.
- The affected suite starts (it may still fail assertions — that is separate).

### Failure criteria
- `LNK1105`/`error code 1224` persists for a binary after its process was stopped and a settling delay elapsed.
- Source or build files were edited without need while chasing a lock error.

## Preconditions
- The error text contains `LNK1105 ... cannot close file` with `error code 1224`; any other LNK code means a different failure class.
- The failing binaries were built and executed earlier in this session (so a leftover process is possible).
- Permission to terminate processes on the machine, and knowledge that stopping them may discard their in-flight output.
- The exact binary names are known from the error text or the build loop.
- If the same file is locked without any prior run of it (fresh build directory), stop and report — the lock's holder is unknown in that case and this skill does not explain it.

## Procedure
### Step 1: Recognise the lock error behind the harness label
- Actions: read the failing block in the build output; confirm `LNK1105: cannot close file '<path>.exe'; error code 1224`; note which binaries are affected.
- Inputs: build tool result.
- Outputs: list of locked binary names.
- Cautions: the harness prefixes the block with `COMPILE ERROR: <file>.cpp` even though no compiler diagnostic follows — do not start editing that source file.
- Preserve: the raw error text.
- Next: continue only when the LNK1105/1224 signature matches.

### Step 2: Stop the processes holding those binaries
- Actions: terminate by process name with `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue`, then wait briefly (`Start-Sleep -Milliseconds 500`); if a binary is still locked, escalate to `Stop-Process -Force` filtered by name pattern or `taskkill /F /IM "<name>.exe"`.
- Inputs: binary names from Step 1.
- Outputs: stopped processes; short settling delay.
- Cautions: `-ErrorAction SilentlyContinue` (or `2>$null`) is required so a name with no process does not abort the script; stopping processes discards any output they had not flushed.
- Preserve: all source and build files.
- Next: go to Step 3.

### Step 3: Relink immediately and rerun the loop
- Actions: rerun the same build/run loop without changing anything else; check the output for the previously locked binaries.
- Inputs: test build/run command.
- Outputs: per-suite results; absence of `LNK1105` for the unlocked binaries.
- Cautions: one binary may still be locked (observed: `test_atoms` failed once more after the batch stop) — repeat Step 2 targeted at that name, then relink that single binary alone.
- Preserve: the pre-change error log for comparison.
- Next: stop when every affected binary links; run-time results are handled separately.

## Decision Rules
### When the output shows `LNK1105 ... cannot close file ... error code 1224` with no compiler diagnostic
Treat it as a file lock: stop the named test processes, wait, relink — verified branch in this trace (four binaries relinked and ran after a batch `Stop-Process`).

### When one binary is still locked after the batch stop
Repeat the stop targeted at that binary's process (`Stop-Process -Force` on the filtered process, or `taskkill /F /IM "<name>.exe"`), wait again, and relink that binary alone — observed to release the lock (the next link attempt proceeded with a full link instead of LNK1105).

### When the harness labels the block `COMPILE ERROR: <file>.cpp`
Ignore the label: with no compiler diagnostic present, do not modify that source file; the defect is the lock.

### When the relink succeeds but the suite then crashes or fails
The lock is resolved; the run-time symptom belongs to a different failure class and must not trigger more process killing.

### When the same file is locked on a first-ever build with no prior run
Stop and report: no lingering-process explanation is available from this trace.

## Invariants
- Never edit source files, tests, or build configuration to resolve a lock error; the only action is releasing the lock and relinking.
- Stop only processes that correspond to the project's test/program binaries — no broad process termination.
- Keep the build command unchanged between the failing and the succeeding attempt so the comparison is meaningful.
- Do not report the suite as passing because the link succeeded; report only that the binary relinked.
- Do not skip the settling delay after stopping processes; the lock may not be released the instant a process is signalled.
- Preserve the original `LNK1105` output as before-evidence for the after-comparison.

## Common Failures
### Failure: build loop reports LNK1105 for several binaries in one run
- Symptoms: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224` repeated for `test_terms`, `test_unifier`, `test_variables`, each under a harness `COMPILE ERROR:` label.
- Causes: executables from the previous run are still resident and hold the files open; the trace does not show why they lingered.
- Recovery: batch-stop the named test processes, wait ~500 ms, rerun the loop — those four binaries then linked and produced full results (`18/18 tests passed`, `17/17 tests passed`, `15/15 tests passed`, `12/12 tests passed` in the same output).

### Failure: one binary still reports LNK1105 after the batch stop
- Symptoms: the batch stop ran, yet `test_atoms.cpp` still fails with `LNK1105 ... error code 1224`.
- Causes: its process survived the name-based stop (exact reason not shown in the trace).
- Recovery: targeted `Stop-Process -Force`/`taskkill /F /IM` for that image plus a longer delay, then relink that binary alone; the following link attempt completed a full link with no LNK1105.

### Failure: relink succeeds but the binary produces no output
- Symptoms: link is clean, the suite line is blank or the process exits `-1073741571`.
- Causes: a run-time start-up crash of that test binary, unrelated to the lock.
- Recovery: hand it to the startup-crash workflow; do not keep killing processes.

## Verification
Observable checks after stopping processes (none are claims about the current session):

1. The relink log for each previously locked binary contains no `LNK1105` and no `error code 1224`.
2. The compiler/linker invocation exits 0 for that binary, so the harness no longer prints its `COMPILE ERROR:` block for it.
3. The binary file is rewritten: its build timestamp/size changes between the failed and the successful attempt (or the linker reports `performing full link` for it).
4. The suite for that binary prints test result lines (e.g. `18/18 tests passed`) rather than an empty entry in the loop summary.
5. No source file mtime changed between the failing run and the successful run — proving nothing was edited to get past the lock.
6. A repeat of the loop immediately afterwards does not reintroduce `LNK1105` for the same binaries.

## Examples
### Example 1: batch lock across four test binaries
- Input: test build loop output contains, for each of four suites, `COMPILE ERROR: test_parser.cpp` followed by `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224 clang++: error: linker command failed with exit code 1105 (use -v to see invocation)`; no compiler diagnostics appear.
- Procedure: Step 1 confirm the LNK1105/1224 signature and collect names; Step 2 run `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue` followed by `Start-Sleep -Milliseconds 500`; Step 3 rerun the unchanged build/run loop.
- Expected result: those binaries link and run — observed output after the stop listed `12/12 tests passed`, `15/15 tests passed`, `18/18 tests passed` and `17/17 tests passed`, ending `=== 6 PASSED, 1 FAILED ===`.
- Parameterized values: `<names>` = locked test binary names; `<delay-ms>` = 500; `<project-dir>` = project root; `<build-dir>` = `build\tests`.

### Example 2: single binary remains locked
- Input: after the batch stop, the loop still reports `COMPILE ERROR: test_atoms.cpp` with `LINK : fatal error LNK1105: cannot close file 'build\tests\test_atoms.exe'; error code 1224`.
- Procedure: Step 2 targeted escalation — `Get-Process | Where-Object { $_.Name -like "*test*" -or $_.Name -like "*epilog*" } | Stop-Process -Force -ErrorAction SilentlyContinue` (or `taskkill /F /IM "test_atoms.exe"`), wait ~800 ms, then relink only that binary.
- Expected result: the link proceeds (`LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link`) with no LNK1105. If the binary then exits `-1073741571`, that is a separate start-up crash and must be handled by its own workflow.
- Parameterized values: `<name>` = locked binary; `<delay-ms>` = 800.

## Evidence
- problem — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1187, source_part_index: 0, quote: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224`, supports: relinking failed with a file-lock error (repeated for `test_terms.exe`, `test_unifier.exe`, `test_variables.exe` in the same output) even though compilation produced no diagnostics, and the harness labelled the block `COMPILE ERROR: test_parser.cpp`.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1190, source_part_index: 0, quote: `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue`, supports: the recovery action was to stop the test processes by name and wait (`Start-Sleep -Milliseconds 500`) before rebuilding — no source file was changed for this failure.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1191, source_part_index: 0, quote: `18/18 tests passed`, supports: after the batch stop, `test_unifier` (blocked by LNK1105 in the previous run) relinked and ran to completion; the same output shows `15/15 tests passed` and `12/12 tests passed` for `test_terms` and `test_parser`, also previously locked, and only `test_atoms` still reports `LINK : fatal error LNK1105: cannot close file 'build\tests\test_atoms.exe'; error code 1224`.
- action — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1193, source_part_index: 0, quote: `Stop-Process -Force`, supports: for the one binary that stayed locked, the escalation was a forceful name-filtered stop of lingering test/program processes followed by a `Start-Sleep -Milliseconds 800` before relinking that binary alone.
- verification — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1194, source_part_index: 0, quote: `LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link`, supports: the link for the previously locked binary proceeded to a full link with no LNK1105, i.e. the lock was released; the binary's subsequent run-time exit code `-1073741571` shown in the same output is a separate crash, not a lock problem.

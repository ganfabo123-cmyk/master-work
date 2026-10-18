---
name: recover-lnk1105-locked-test-binary
description: Use when relinking a test binary fails with LNK1105 "cannot close file ... error code 1224" while other suites still link fine. Helps the agent identify that a lingering test process holds the executable, terminate it, and re-run the same build script so the previously blocked suites link and run. Requires permission to list and kill processes (Stop-Process/taskkill) and a re-runnable test build script. Do not use when the error is LNK2019 unresolved externals or when the executable keeps failing to relink after the process is gone.
---
# Recover from LNK1105 Locked Test Executable on Windows

## Goal
Unblock relinking of a test executable that fails with LNK1105 "cannot close file ... error code 1224" by terminating the process that still holds it, so the suite links and runs again.

## Scope
### In scope
- Link failures whose text is `LINK : fatal error LNK1105: cannot close file '<path>\<name>.exe'; error code 1224` while other suites in the same run link normally.
- Identifying and terminating lingering test processes (`Stop-Process`, `taskkill`), waiting briefly, then re-running the identical build script.
- Confirming recovery by observing that the previously blocked executables link and their suites print pass counts.

### Out of scope
- LNK2019 unresolved-external failures (fix-lnk2019-extern-global-test-link).
- Suites that link fine but crash with exit -1073741571 (windows-static-fixtures-avoid-stack-overflow).
- Diagnosing why a test process lingers in the first place — the trace never established it (suspected hung/crashed test binaries; unconfirmed).
- Executables that remain locked after termination (no verified further step; see decision rules).

## Inputs
- **Link error output**: string; source = tool result of the test build script; required; must contain `LNK1105: cannot close file` and `error code 1224`; default: none.
- **Blocked executable names**: e.g. `test_parser.exe`, `test_terms.exe`, `test_unifier.exe`, `test_variables.exe`, `test_atoms.exe`; source = parsed from the LNK1105 messages; required; default: none.
- **Process-management rights**: ability to list/kill processes in the shell (`Stop-Process`, `taskkill /F /IM`); source = environment; required; default: none.
- **Original build-and-run script**: the unchanged PowerShell loop that compiles and runs every suite; source = project; required for re-run and verification; default: none.
- **Settle delay**: short pause after killing (trace used `Start-Sleep -Milliseconds 500`); source = trace recipe; optional; default: 500 ms.

## Outputs
### Artifacts
- The set of terminated test processes and the re-run output of the same build script.
- Rebuilt executables for the previously blocked suites.

### Success criteria
- The re-run contains no LNK1105 line for the executables whose processes were killed.
- Those suites print `PASS` lines and `N/N tests passed`, and the final tally counts them as passed.

### Failure criteria
- A previously blocked executable still reports `LNK1105 ... error code 1224` after termination and the settle delay.
- The suite links but produces no output (a different defect, e.g. exit -1073741571).

## Preconditions
- The failing message is specifically `LNK1105: cannot close file` / `error code 1224`, not LNK2019 or a compile error.
- You may list and terminate processes on this machine; if not, stop and report that the executable is locked.
- The source code itself compiles: the same run shows other suites linking, or the blocked suite compiled in a previous run — otherwise a code problem may be hidden behind the lock.
- The original build script can be re-run unchanged for verification.
- You can wait a short settle time after termination before relinking.

## Procedure
### Step 1: Separate the lock errors from code errors
Actions: scan the run output; collect every `LNK1105: cannot close file '<exe>'; error code 1224` entry as locked, and note whether other suites linked and ran in the same run. Inputs: build output. Outputs: list of blocked executables plus evidence that compilation itself is healthy. Cautions: an `COMPILE ERROR:` label in the harness may be printed for a pure link failure — read the underlying message. Preserve: sources unchanged. Next: proceed only if the failures are LNK1105.

### Step 2: Terminate the processes holding those executables
Actions: kill the test binaries by name, e.g. `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500` or `taskkill /F /IM "test_atoms.exe"`. Inputs: blocked executable names. Outputs: processes gone. Cautions: killing unrelated processes is forbidden — restrict the names to the blocked executables. Preserve: editor and build tool processes. Next: Step 3.

### Step 3: Re-run the identical build script
Actions: execute the same compile-and-run loop without modifying flags, source lists, or order. Inputs: build script. Outputs: per-suite compile status and results. Cautions: do not "fix" code in response to an LNK1105 — nothing in the source causes it. Next: Step 4.

### Step 4: Verify per suite and record what remains
Actions: compare with the Step 1 list: each previously blocked executable must now link and its suite must print `N/N tests passed`. Inputs: new run output. Outputs: recovery status per suite. Next: stop when all previously locked executables link; if one is still locked, report it as unresolved.

## Decision Rules
### When the message is LNK1105 "cannot close file ... error code 1224"
The executable is held open by a process; terminate the test processes named in the message, wait briefly, and re-run the same build script — no code change.

### When other suites in the same run link and run normally
Compilation and most of the code are healthy; treat the locked ones as an environment issue, not a source issue.

### When, after termination, a previously blocked suite links and prints its pass count
Recovery is confirmed for that suite; record it and continue with the remaining blocked executables.

### When an executable is still locked after termination
The trace provides no further verified step (`test_atoms.exe` stayed locked through the last captured runs); stop and report the lock rather than editing code.

### When a relinked suite produces no output
The lock is gone but a runtime defect remains; hand the suite to the stack-overflow procedure instead of repeating kills.

## Invariants
- LNK1105 is treated as an environment/lock problem: source files, flags, and the source list are never edited in response to it.
- Only the processes named by the locked executables are terminated; no other processes are killed.
- Verification always re-runs the original build script unchanged, so results stay comparable with the failing run.
- Suites that relink but produce no output are reported as runtime failures, not as successes of this procedure.
- No claim of recovery for an executable that still reports LNK1105 after the kill-and-rerun cycle.

## Common Failures
### Failure: "Fixing" code for a lock error
Symptoms: LNK1105 persists while other suites keep linking fine. Causes: the message describes a file handle, not a code defect; the same run shows healthy compilation elsewhere. Recovery: revert any source edits made for this error, terminate the holding processes, and re-run the script.

### Failure: Killing processes but relinking immediately
Symptoms: LNK1105 recurs on the first retry. Causes: the handle was not yet released; the trace's recipe inserts a pause (`Start-Sleep -Milliseconds 500`) before rebuilding. Recovery: wait briefly and re-run again; if it still fails, report the lock as unresolved.

### Failure: One executable stays locked through every attempt
Symptoms: `test_atoms.exe`-style entries keep reporting LNK1105 after `Stop-Process`/`taskkill`. Causes: unknown — the trace ends without a captured result for the final kill-and-rebuild. Recovery: report the suite as blocked with its exact message; do not mark it passed.

### Failure: Treating a silent, relinked suite as recovered
Symptoms: link succeeds now but the suite prints nothing (e.g. exits -1073741571). Causes: a separate startup defect. Recovery: verify recovery only at the link stage for this skill and route the runtime issue elsewhere.

## Verification
- The re-run of the original build script contains no `LNK1105` / `error code 1224` line for the executables whose processes were terminated.
- Each previously blocked suite now appears in the output with its own section and a `N/N tests passed` line (target state: `test_parser 12/12`, `test_terms 15/15`, `test_unifier 18/18`, `test_variables 17/17`).
- The final tally counts those suites as passed (observed: `=== 6 PASSED, 1 FAILED ===` after the kill-and-rerun, versus `=== 2 suite(s) PASSED, 5 FAILED ===` before, when four suites were lock-blocked).
- Any executable still reporting LNK1105 is listed explicitly as unresolved with its message.

## Examples
### Example 1: Four suites blocked by locks while two already pass
Input: run output where `test_lexer` and `test_solver` pass (`22/22 tests passed`) while `test_parser`, `test_terms`, `test_unifier`, `test_variables` each report `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224`.
Procedure: Step 1 (classify all four as locked; compilation healthy), Step 2 (`Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500`), Step 3 (re-run the same loop), Step 4 (compare).
Expected result: the four executables link and their suites print `12/12`, `15/15`, `18/18`, `17/17` test lines; tally becomes `=== 6 PASSED, 1 FAILED ===`.
Parameterized values: process names = the blocked suite basenames; settle delay 500 ms; build output dir `build\tests`.

### Example 2: One executable remains locked after the kill
Input: re-run output where all previously blocked suites linked except `build\tests\test_atoms.exe`, which still reports `LNK1105 ... error code 1224`.
Procedure: Step 4 only — record the residual lock; then attempt a targeted kill of that single binary and rebuild it alone if permitted.
Expected result: honest status: suites recovered are reported recovered, the locked one is reported blocked with its message; no code edits were made anywhere in this cycle.
Parameterized values: single target `test_atoms.exe`, verification command compiles `tests/test_atoms.cpp` against the full source list.

## Evidence
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1187; source_part_index: 0; quote: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224 clang++: error: linker command failed with exit code 1105 (use -v to see invocation)`; supports: problem — four suites fail to relink with a file-lock error in a run where `test_lexer` and `test_solver` still link and pass (`22/22 tests passed`), showing compilation is healthy.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1189; source_part_index: 0; quote: `The "compile errors" are just file-locked binaries from the previous run still in memory.`; supports: diagnosis (assistant judgement) that the failure is a lock, not source code.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1190; source_part_index: 0; quote: `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500`; supports: action — kill the named test processes and pause before rebuilding.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1191; source_part_index: 0; quote: `PASS  parse simple fact: foo.`; supports: verification — in the very next run `test_parser`, which had been lock-blocked, linked and ran, reporting `12/12 tests passed` (alongside `test_terms 15/15`, `test_unifier 18/18`, `test_variables 17/17`), and the tally became `=== 6 PASSED, 1 FAILED ===`.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original; source_index: 1191; source_part_index: 0; quote: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_atoms.exe'; error code 1224`; supports: limit of the method — one executable remained locked after the kill, so recovery is reported per suite and the residual lock stays unresolved.

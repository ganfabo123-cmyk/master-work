---
name: fix-lnk1105-locked-output-exe
description: Use when clang/clang++ linking on Windows fails with "LINK : fatal error LNK1105: cannot close file '<output.exe>'; error code 1224" and "linker command failed with exit code 1105" while object compilation succeeds. Helps the agent recognize the output binary is held by a still-running process, terminate it, wait for the handle to be released, and re-run the link until it succeeds. Requires a Windows shell with permission to kill processes (PowerShell Stop-Process or taskkill). Do not use when the link fails with a different diagnostic (undefined symbols, LNK2001/LNK2019, LNK1104 with a cause other than a running process) or when object compilation itself fails.
---
# Resolve LNK1105 (exit 1105 / 0x451) Locked-Output Link Failures on Windows

## Goal
Recover a Windows native build whose final link step fails with `LINK : fatal error LNK1105: cannot close file '<output.exe>'; error code 1224` (surfaced by clang/clang++ as "linker command failed with exit code 1105", and by make as `Error 1105`; decimal 1105 = the error key 0x00000451) because the output executable is still held open by a leftover running process, and produce a verified successful relink of that executable at its original output path.

## Scope
### In scope
- Windows hosts where clang/clang++ drives the MSVC linker (link.exe) and the final executable link fails with LNK1105 + error code 1224 while all object-file compilation steps succeed.
- Builds driven by `make`, direct clang/clang++ command loops, or PowerShell/Bash wrapper scripts that relink executables in place (e.g., test binaries under `build\tests\`).
- Terminating the leftover process(es) that hold the output executable (PowerShell `Stop-Process -Name <base> -Force -ErrorAction SilentlyContinue` or `taskkill /F /IM <name>.exe`), waiting briefly, and re-running the exact link command.
- The retry-with-wait branch: when an immediate relink after killing still fails with LNK1105, sleeping (~1 s) and relinking again.

### Out of scope
- Genuine compile or link errors (missing symbols, bad flags, corrupt object files); these need source/build fixes, not process cleanup.
- Permanently changing the project's Makefile or build scripts to avoid the lock (not demonstrated in the evidence).
- Configuring antivirus/real-time scanning exclusions (suspected as possible external lockers but never verified in the evidence).
- Non-Windows platforms; LNK1105 is an MSVC link.exe diagnostic.
- Runtime crashes of the relinked binary (a separate code problem; e.g., a test binary that relinked fine but crashed with a negative exit code still needs a code fix).

## Inputs
- **Failing build/link output** — type: text; source: the shell tool result of the build command (make, clang/clang++, or a wrapper script); required: yes; constraint: must contain `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224` (or the clang wrapper line `linker command failed with exit code 1105`); default: none.
- **Output executable path/name** — type: string; source: the quoted path inside the LNK1105 message (e.g., `bin\yggdrasil.exe`, `build\tests\test_parser.exe`, `epilog.exe`); required: yes; constraint: used to derive the process name to kill (executable base name without extension); default: none.
- **Evidence that compilation succeeded** — type: text; source: the same build output, showing `.o` compile lines and/or `llvm-ar` archive creation completing before the link step; required: yes — without it the failure may not be a lock; default: none.
- **Available shell** — type: enum(PowerShell | Bash); source: the agent's shell tool; required: yes; constraint: PowerShell `Stop-Process` + `Start-Sleep` retries are verified end-to-end in the evidence; Bash `taskkill /F /IM ... ; sleep 1` appears only as an attempted variant with no captured result; default: whichever shell the session already uses (prefer PowerShell for the verified path).
- **Permission to terminate processes** — type: boolean; source: environment; required: yes; constraint: killing processes whose names match the output executables is acceptable in this workspace; default: no — must be confirmed before acting.
- **Retry count/wait time** — type: integer/duration; source: agent choice; required: no; constraint: evidence supports ~500 ms after Stop-Process, or `Start-Sleep -Seconds 1` before a retry relink; default: 500 ms, escalating to 1 s on repeated failure.

## Outputs
### Artifacts
- Relinked executable at the original output path (e.g., `bin\<name>.exe`, `build\tests\<name>.exe`, or `<name>.exe` in the working directory) — format: PE executable produced by the same clang/clang++ link command that previously failed.
- Build command transcript (shell tool result) showing the relink without any LNK1105 line — format: plain text.
- Optionally, the kill-and-retry command line used (kept verbatim in the session transcript for reproducibility).

### Success criteria
- The relink command exits with code 0 and the output contains no `LNK1105` / `exit code 1105` line; the build system prints its success message (e.g., make runs the post-link recipe, or the wrapper prints `Built: <target>`).
- The output executable exists at the original path and can subsequently be launched (e.g., a fixture run or test binary executes against it).

### Failure criteria
- LNK1105 with error code 1224 still appears after kill + wait + relink attempts (lock held by something other than a killable same-named process — unverified cause; escalate/stop and report).
- A new, different linker or compiler error appears after the lock is cleared (now a real code/build problem, out of scope for this skill).
- The relink succeeds but the binary immediately crashes at runtime (link problem solved; a separate defect remains and must not be reported as a full fix).

## Preconditions
- Host is Windows and the toolchain is clang/clang++ invoking the MSVC linker (the diagnostic text contains `LINK : fatal error LNK1105`). If absent, stop — this skill does not apply.
- All object compilation steps in the failing build succeeded and only the final link to the executable failed; if `.o` compilation also fails, fix the compile errors first.
- The locked output is an executable (`.exe`), not a static archive: in the evidence, `llvm-ar rcs build/libfrostcore.a ...` completed fine while only the exe link failed, which is the expected signature.
- You can name the process(es) that could hold the file: the base name of the output exe (e.g., `yggdrasil`, `epilog`, `test_atoms`) and any test binaries run earlier in the same session.
- You have, or can obtain, permission to forcibly terminate processes by name in this workspace. If not permitted, stop and report that the build cannot proceed.
- You have a shell with `Stop-Process`/`Start-Sleep` (PowerShell) or `taskkill`/`sleep` (Bash) available.
- You can re-run the exact failing build command (make target, clang link line, or wrapper script) after killing.

## Procedure
### Step 1: Confirm the lock signature in the build output
- Actions: Read the failing tool result. Check for all three markers: `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224`, `clang++: error: linker command failed with exit code 1105 (use -v to see invocation)`, and make's `*** [<target>] Error 1105`. Confirm the preceding `.c/.cpp` compile commands (or `llvm-ar` archive step) succeeded.
- Inputs: failing build output.
- Outputs: confirmed diagnosis "output exe locked by a running process", plus the exact output path (e.g., `bin\yggdrasil.exe`).
- Cautions: a harness may relabel this as `COMPILE ERROR: <file>.cpp` even though the underlying message is a link lock — read the underlying linker text, not the harness label. Do not start editing source code for this error.
- Preserve: the original failing command, so the retry uses the identical command line.
- Next: proceed if signature matches; otherwise stop and handle as a normal compile/link error.

### Step 2: Identify which process(es) hold the output
- Actions: Derive the process name from the locked exe's base name. Recall which executables were launched earlier in the same session (main program runs, test binaries from a build-and-run loop) — in the evidence the locker was always a leftover instance of the very program or test binary being relinked, launched by the agent's previous run.
- Inputs: output path from Step 1, session history.
- Outputs: list of process names to kill (e.g., `yggdrasil`; or `test_atoms,test_terms,test_unifier,test_variables,test_parser` when a whole test loop ran).
- Cautions: if the same build relinks several test exes, all of them may be locked at different times — plan to kill all of them.
- Preserve: anything unrelated to these executable names.
- Next: proceed with termination.

### Step 3: Kill the holder and wait for the handle to be released
- Actions: PowerShell: `Stop-Process -Name <base> -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500` (use `-Name a,b,c` for multiple). Bash variant (attempted, result not captured): `taskkill /F /IM <name>.exe /IM <other>.exe 2>/dev/null; sleep 1`.
- Inputs: process name list from Step 2.
- Outputs: processes terminated; short wait elapsed.
- Cautions: `-ErrorAction SilentlyContinue` (or `2>/dev/null`) is required so a not-running process does not abort the script before the build runs.
- Preserve: do not kill processes unrelated to the output exe names.
- Next: immediately re-run the build.

### Step 4: Re-run the exact link/build command
- Actions: Execute the same command from Step 1 (e.g., `make 2>&1`, or the clang link line / wrapper script).
- Inputs: original build command.
- Outputs: relink result.
- Cautions: do not pipe the output through filters that drop `LINK` lines — that hides persistent failures.
- Preserve: full unfiltered output.
- Next: if it exits 0 with no LNK1105, go to Step 6; if LNK1105 persists, go to Step 5.

### Step 5: Retry with a longer wait (and broaden the kill) when the first attempt fails
- Actions: One observed case showed LNK1105 persisting even after a kill + immediate relink; the follow-up `Start-Sleep -Seconds 1; make 2>&1` then succeeded, i.e., the file handle is released asynchronously and a plain timed retry can clear it. If the build relinks many test binaries, kill all of them by name (wildcard matching `*test*`/`*<program>*` was used) with ~500–800 ms wait, then relink each failing target.
- Inputs: same failing target(s).
- Outputs: relinked binaries; a leftover crashed/hung test binary may need a second kill before its exe relinks (`LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link` appeared once the lock was gone).
- Cautions: escalating waits are empirical; stop after a few retries and report if the lock never clears.
- Preserve: any real compile errors that surface after the lock is cleared — fix those separately.
- Next: proceed to verification on success.

### Step 6: Verify and continue
- Actions: Confirm exit code 0 and absence of LNK1105; then run the binary once (fixture, smoke test, or single test) to prove it is usable.
- Inputs: relinked binary path.
- Outputs: verified build.
- Cautions: if the binary now crashes at runtime, that is a distinct code defect — report it separately, the link lock is resolved.
- Preserve: the successful command sequence for future re-runs in the same session (kill before every relink of a binary that was just executed).

## Decision Rules
### When object compilation succeeds but only the final exe link fails with LNK1105 / error code 1224
Treat it as an environmental file lock, not a code problem. Do not modify source files, flags, or the Makefile. Go straight to process termination and relink. (In every observed instance the lock came from a still-running instance of the binary itself.)

### When the locked target is a test binary built and run in a loop earlier in the session
Kill all test binaries from the loop by name before relinking (`Stop-Process -Name test_atoms,test_terms,... -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500`), not just the currently failing one — multiple exes fail LNK1105 at different points in the same loop.

### When an immediate relink after a kill still reports LNK1105
Do not conclude the diagnosis was wrong. Wait and retry the identical link (`Start-Sleep -Seconds 1; make 2>&1`); in the evidence this retry succeeded where the kill-then-instant-relink had failed, consistent with the file handle being released asynchronously.

### When a static library step (llvm-ar) succeeds while the exe link fails
The lock is confined to the exe output; the object code and archive are fine. Confirms the environmental-lock diagnosis and narrows the kill target to the exe's process name.

### When the test harness labels the failure `COMPILE ERROR: <file>.cpp`
Read the underlying linker message before acting; if it is LNK1105, treat it as a lock, not a compile error. Suites that "failed" this way can pass on relink without any source change.

### When build output is being piped/filtered in a wrapper
Never filter out `LINK` lines or print an unconditional "All compiled" after the loop. One observed wrapper swallowed LNK1105 this way and masked which binaries were stale. Keep full output and check the link exit code per target.

### When the relink succeeds but the binary crashes on launch
The lock problem is solved; stop applying this skill and switch to debugging the crash (it is a separate defect, unrelated to LNK1105).

## Invariants
- Do not edit source files, compiler flags, or build configuration in response to LNK1105/1224; the failure is a file lock, and the observed resolutions changed no code.
- Do not rename the output or link to a different path as a workaround; relink to the original output path so downstream scripts, test harnesses, and expected-binary locations keep working.
- Do not suppress or filter linker output (e.g., dropping lines matching `^LINK` before checking `$LASTEXITCODE`); report exactly which targets failed to link.
- Do not report the build as successful without a zero-exit link of the specific locked target and an output free of LNK1105.
- Do not report test results for a binary that failed to relink; a stale or absent exe invalidates the suite result.
- Do not kill processes whose names do not correspond to the output executables being rebuilt; limit termination to those names (with `-ErrorAction SilentlyContinue` / `2>/dev/null` so a missing process does not abort the build).
- Do not claim the whole task is fixed when only the link succeeded but the relinked binary crashes at runtime; report the two issues separately.
- Do not treat a failed first retry as disproof of the lock diagnosis; the handle release can lag behind process termination, and a delayed retry is an evidenced successful path.

## Common Failures
### Failure: Relink immediately after killing still fails with LNK1105
- Symptoms: `Stop-Process -Name <base> -Force ...; make` outputs `LINK : fatal error LNK1105: cannot close file '<exe>'; error code 1224` again.
- Causes: the process handle or OS file lock is released asynchronously after termination; an immediate relink can race it. (The exact releasing component was not verified in the evidence.)
- Recovery: do not re-diagnose; run the same link again after a short wait (`Start-Sleep -Seconds 1; make 2>&1`). This sequence produced a clean `Built: <target>` where the instant retry had failed.

### Failure: Lock persists because only one of several test binaries was killed
- Symptoms: each relink attempt fails LNK1105 on a different `build\tests\*.exe` within the same build-and-run loop.
- Causes: the session previously ran many test exes that are each still resident.
- Recovery: kill the full set by name before relinking (`Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500`, or a `Get-Process | Where-Object { $_.Name -like "*test*" -or $_.Name -like "*<program>*" } | Stop-Process -Force` sweep with an ~800 ms wait), then rebuild each previously locked target.

### Failure: One test exe stays locked after the main cleanup
- Symptoms: after the bulk kill, most suites relink and pass but a single exe (e.g., `test_atoms`) still cannot be relinked, or a later relink reports `LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link`.
- Causes: the specific holder of that exe was not covered by the first kill pattern (not verified which process kept the lock).
- Recovery: kill remaining matching processes again (wildcard sweep) and relink that single target; once the lock cleared, the relink completed. A subsequent runtime crash of that binary is a separate code defect, not a lock problem.

### Failure: Wrapper script masks the link failure and declares success
- Symptoms: build output contains `clang++: error: linker command failed with exit code 1105` yet the script prints `All compiled`; stale binaries persist and confuse later runs.
- Causes: piping compiler output through a filter that drops `LINK` lines and not checking per-target exit codes.
- Recovery: rerun the compile/link loop without the filter, capture `$LASTEXITCODE` per target, then apply the kill-and-relink procedure to the targets that actually failed.

### Failure: Harness output mislabels the lock as a compile error
- Symptoms: a test runner prints `COMPILE ERROR: test_parser.cpp` (etc.) followed by the LNK1105 text; suites are counted as FAILED.
- Causes: the harness treats any non-zero link exit as a compile error.
- Recovery: read the underlying linker message; if it is LNK1105/1224, kill the holders and relink — the same suites then pass with no source changes.

## Verification
- The relink command exits with code 0 (make finishes its recipe instead of printing `*** [<target>] Error 1105`; a direct clang link line produces no `error:` output).
- The build transcript contains no `LNK1105`, no `error code 1224`, and no `linker command failed with exit code 1105`.
- The build prints its success marker for the target (observed: `"Built: bin/yggdrasil.exe"` after a successful `make` relink).
- The output exe exists at the same path the failed link named (e.g., `bin\yggdrasil.exe`, `build\tests\test_parser.exe`, `epilog.exe`).
- The binary is runnable: launching it produces normal program output (observed: a fixture transpiled to JavaScript output, or a test suite printing `PASS` lines and `N/N tests passed`).
- A previously lock-failed suite now reports a pass tally (observed pattern: suites that had been counted as `COMPILE ERROR` printed their `PASS` lines and were counted PASSED after kill + relink, with no source changes).
- Remaining failures, if any, are not LNK1105 (e.g., a test binary crashing at startup is tracked as a separate defect).

## Examples
### Example 1: Compiler binary locked by its own previous run
- Input: `make` output ending with `LINK : fatal error LNK1105: cannot close file 'bin\yggdrasil.exe'; error code 1224` and `make: *** [bin/yggdrasil.exe] Error 1105`, while all `-c -o build/*.o` steps succeeded.
- Procedure: Step 1 (confirm signature), Step 2 (holder is the program `yggdrasil` launched by an earlier fixture run), Step 3: `Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make 2>&1`.
- Expected result: link exits 0, output shows the link command plus `"Built: bin/yggdrasil.exe"`, and the binary immediately transpiles a fixture file successfully.
- Parameterized values: program base name `yggdrasil`, output `bin\yggdrasil.exe`, object files `build/codegen.o build/diagnostics.o build/lexer.o build/main.o build/parser.o`.

### Example 2: Kill + instant relink still fails; delayed retry succeeds
- Input: after `Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make`, the result again shows `LINK : fatal error LNK1105: cannot close file 'bin\yggdrasil.exe'; error code 1224`.
- Procedure: Step 5 — do not re-diagnose; run `Start-Sleep -Seconds 1; make 2>&1`.
- Expected result: clean relink (`Built: bin/yggdrasil.exe`) with no source or Makefile changes, demonstrating asynchronous handle release.
- Parameterized values: wait 1 s; same build command; same target.

### Example 3: Bulk cleanup before rebuilding a whole test loop
- Input: a PowerShell loop that compiles and runs ~7 test exes reports some suites as `COMPILE ERROR: test_<x>.cpp` followed by `LINK : fatal error LNK1105: cannot close file 'build\tests\test_<x>.exe'; error code 1224`, and other suites print `PASS` lines normally.
- Procedure: Step 2–4 — kill every test binary from the loop by name, then relink each failing target: `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500`, then recompile each `tests/test_*.cpp` into `build\tests\<name>.exe`.
- Expected result: the previously locked suites build and pass with no source changes (observed: `--- test_parser ---` ... `12/12 tests passed`, `=== 6 PASSED, 1 FAILED ===` with the single remaining failure being an unrelated crash in one binary).
- Parameterized values: test exe directory `build\tests\`, wait 500 ms, C++ standard/flags as configured by the project (e.g., `-std=c++23 -Iinclude -Itests -g -O0`).

### Example 4: Static library fine, exe link locked (diagnostic narrowing)
- Input: `make` output where `llvm-ar rcs build/libfrostcore.a ...` succeeds and only `clang ... -o build/frost_smoke.exe ...` fails with `LINK : fatal error LNK1105: cannot close file 'build\frost_smoke.exe'; error code 1224`.
- Procedure: Step 1 (archive success confirms the lock is on the exe only), Step 3–4: `taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make CC=clang AR=llvm-ar OPT="-O0" BUILD=build`.
- Expected result: the exe relinks; note this Bash/taskkill variant was attempted in the evidence without a captured result, so prefer the verified PowerShell `Stop-Process` + retry path when available.
- Parameterized values: exes `frost_smoke.exe frost_subsystems.exe frost_bytecode.exe`, archive `build/libfrostcore.a`.

## Evidence
Problem:
- file_id: claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original, source_index: 491, source_part_index: 0, quote: "LINK : fatal error LNK1105: cannot close file 'bin\yggdrasil.exe'; error code 1224", supports: the failure signature on a make-driven C++ build where object compilation succeeded.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 370, source_part_index: 0, quote: "LINK : fatal error LNK1105: cannot close file 'epilog.exe'; error code 1224", supports: same signature for a directly-invoked clang link of a C program.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 223, source_part_index: 0, quote: "LINK : fatal error LNK1105: cannot close file 'build\tests\test_indexing.exe'; error code 1224", supports: same signature when relinking a test binary produced by a build-and-run loop.
- file_id: claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__original, source_index: 575, source_part_index: 0, quote: "llvm-ar rcs build/libfrostcore.a build/frostcore.o build/frostcore_subsystems.o build/frost_parse.o build/frost_vm.o build/quickjs.o build/libregexp.o build/libunicode.o build/dtoa.o build/quickjs-libc.o", supports: the archive step succeeding immediately before the exe link failed, narrowing the lock to the exe.
- file_id: claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original, source_index: 1068, source_part_index: 0, quote: "LINK : fatal error LNK1105: cannot close file 'bin\yggdrasil.exe'; error code 1224", supports: an immediate relink after a kill can still fail, motivating the wait-and-retry branch.

Diagnosis (from the trajectory, not assumed):
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 373, source_part_index: 0, quote: "The binary is still running (file locked). Kill it and rebuild:", supports: identifying the locker as the program's own previous instance.
- file_id: claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original, source_index: 967, source_part_index: 0, quote: "The binary is still running from the previous test. Need to kill the test runner first:", supports: the locker was launched by the agent's own earlier test run.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 224, source_part_index: 0, quote: "The linker can't overwrite `test_indexing.exe` because it's still running. Let me run solver first, then wait:", supports: the same diagnosis plus the idea of sequencing runs and waiting.
- file_id: claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__original, source_index: 576, source_part_index: 0, quote: "The library built successfully. The link error is just because the existing test binary is already running/locked. Let me kill any running instances and rebuild:", supports: distinguishing library-build success from the exe-only lock.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 1189, source_part_index: 0, quote: "The \"compile errors\" are just file-locked binaries from the previous run still in memory.", supports: harness "COMPILE ERROR" labels are link locks, not source errors.

Action:
- file_id: claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original, source_index: 968, source_part_index: 0, quote: "Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make 2>&1", supports: the verified kill-then-build command pattern.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 374, source_part_index: 0, quote: "Stop-Process -Name epilog -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500; clang -std=c11", supports: kill + ~500 ms wait + immediate relink in one command.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 1190, source_part_index: 0, quote: "Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500", supports: killing all test binaries by name before relinking a whole suite loop.
- file_id: claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original, source_index: 1069, source_part_index: 0, quote: "Start-Sleep -Seconds 1; make 2>&1", supports: the delayed-retry action that succeeded where the instant retry failed.
- file_id: claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__original, source_index: 577, source_part_index: 0, quote: "taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make CC=clang AR=llvm-ar OPT=\"-O0\" BUILD=build 2>&1", supports: the Bash/taskkill variant (action only; its tool result was not captured in the trace).

Verification:
- file_id: claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original, source_index: 969, source_part_index: 0, quote: "\"Built: bin/yggdrasil.exe\"", supports: kill + make produced a successful relink with the build script's success marker.
- file_id: claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__original, source_index: 1070, source_part_index: 0, quote: "\"Built: bin/yggdrasil.exe\"", supports: the 1-second delayed retry also produced a successful relink; the binary was then run on a fixture in the next step.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 375, source_part_index: 0, quote: "(PowerShell completed with no output)", supports: the kill + 500 ms wait + clang relink of epilog.exe completed with no compiler/linker error output.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 1191, source_part_index: 0, quote: "12/12 tests passed", supports: a suite that had failed as a link-lock now builds and passes after the bulk kill, with no source changes.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original, source_index: 1194, source_part_index: 0, quote: "LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link", supports: once the remaining lock was cleared, the previously stuck exe relinked.

Anti-pattern evidence:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 247, source_part_index: 0, quote: "2>&1 | Where-Object { $_ -notmatch \"^LINK\" }", supports: a wrapper that filtered out linker lines while relinking all test binaries.
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__original, source_index: 248, source_part_index: 0, quote: "clang++: error: linker command failed with exit code 1105 (use -v to see invocation)", supports: the masked failure that still occurred despite the filter, followed by the unconditional "All compiled" message in the same result.

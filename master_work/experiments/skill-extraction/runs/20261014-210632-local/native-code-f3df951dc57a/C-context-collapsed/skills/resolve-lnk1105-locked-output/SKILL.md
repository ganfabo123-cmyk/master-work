---
name: resolve-lnk1105-locked-output
description: Use when the MSVC linker reports `LINK : fatal error LNK1105: cannot close file '<output>.exe'; error code 1224` while object compilation succeeded. Helps the agent release the lock on the link output (kill holders, wait, delete the artifact, or link to a fresh name) and produce a verified relink. Requires Windows, a shell that can stop processes and delete files, and the exact output path from the error. Do not use when compilation itself fails, when other link errors (e.g. unresolved symbols) appear, or on non-Windows toolchains.
---
# Resolve Windows LNK1105 "cannot close file" Link Failures

## Goal
Clear the Windows `LNK1105 ... error code 1224` failure on one specific link output and deliver a freshly linked, runnable binary, without changing sources, build scripts, or compiler flags.

## Scope
### In scope
- Diagnosing an `LNK1105 ... error code 1224` build output as a lock on the link output file (link-only failure while compilation and archiving succeeded).
- Stopping the processes that run binaries produced by the same build (application image and test images), with a short delay before retrying.
- Deleting the locked output artifact and rebuilding.
- Relinking to a fresh output file name as a bypass when verification is blocked.
- Verifying the relink by exit status, success marker, file existence, and actually running the binary.

### Out of scope
- Compile-time errors, include errors, or any failure before the link step.
- Other linker errors (unresolved symbols, LNK2019/LNK1120, incremental-link notices).
- Editing source files, Makefiles, build scripts, or compiler/linker flags to work around a lock.
- Investigating why a relinked program subsequently crashes or fails tests (separate defect; see fix-windows-test-stack-overflow-locals).
- Non-Windows toolchains and non-MSVC linkers.

## Inputs
- **Build log** — string — output of the failing build command — required — must contain `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224`; also used to confirm compilation succeeded — default: 无.
- **Output path** — string — parsed from the LNK1105 line — required — the `.exe` the linker could not close, e.g. `bin\yggdrasil.exe`, `build\frost_smoke.exe`, `D:\DMLS\build\dmls.exe` — default: 无.
- **Image names** — list of strings — derived from the output file names built by the same command — required for the kill step — every binary that command can produce (app plus test images) — default: the file name(s) on the LNK1105 line(s).
- **Shell** — enum: PowerShell or bash on Windows — environment — required — determines whether `Stop-Process`/`Remove-Item` or `taskkill`/`rm` are available — default: the shell that runs the build.
- **Stop/delete permission** — capability — environment — required — the ability to terminate processes and delete files under the build directory; if denied, stop and report — default: 无.
- **Fresh output name** — string — chosen by the agent — optional — alternative `-o` target used only when the lock cannot be cleared quickly — default: 无.
- **Delay budget** — duration — chosen by the agent — optional — observed working range 300 ms to 1 s between kill and relink — default: 1 second.

## Outputs
### Artifacts
- Relinked binary at the original output path (or at the fresh name when that branch was used) — path taken from the build log — format: PE `.exe`.
- Recovery command record — session log — the kill command, delay, delete/relink command and their exit statuses — format: plain text.
- Status note stating whether the lock holder was confirmed or unconfirmed — session log — format: plain text.

### Success criteria
- The relink command exits 0 and its output contains no `LNK1105` line.
- The build prints its success marker (e.g. `Built: bin/yggdrasil.exe`, `[odin] Built build\dmls.exe`).
- The output file exists at the expected path with a modification time later than the relink command, and the binary starts (or its test suite prints pass counts).

### Failure criteria
- `LNK1105 ... error code 1224` repeats after kill + delay + delete.
- Stopping or deleting cannot be performed (no permission), or the output path is unknown.
- The build log shows compile errors as well (wrong skill).
- A fresh output name was required but scripts still require the canonical name.

## Preconditions
- The host is Windows and the failing step is the MSVC link (`LINK :`) invoked through clang/clang++/clang-cl; otherwise this skill does not apply.
- The exact output path appears in the build log as `cannot close file '<path>'; error code 1224`.
- Object files and libraries were produced successfully in the same run, so the failure is link-only; if compilation errors are present, stop and solve those first.
- The agent may terminate processes and delete files under the build directory; if either is denied, stop and report the permission limitation instead of proceeding.
- The image name(s) of the binaries this build produces are known (derived from the output path or the build script).
- If any of these cannot be confirmed, stop and report what is missing; do not improvise against unknown state.

## Procedure
### Step 1: Confirm a link-only lock failure
- Actions: read the whole build output; verify that compilation and archive steps succeeded; extract the output path from `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224`; note that the wrappers restate it as `linker command failed with exit code 1105` and `make: *** [...] Error 1105` — these are the same failure, not new ones.
- Inputs: build log.
- Outputs: output path, image name(s), determination "link-only failure".
- Cautions: do not chase `Error 1105` or `exit code 1105` as separate defects.
- Preserve: sources, build scripts, flags — nothing is edited in this skill.
- Next condition: link-only → Step 2; compile errors present → stop, wrong skill.

### Step 2: Stop the processes that run this build's binaries
- Actions: list candidates first (`Get-Process`, or filter by `Path -like '*<project>*'`), then kill every image this build can produce in a single command — main app and test images together, e.g. `taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe`, or `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue`.
- Inputs: image names from Step 1.
- Outputs: listing result and kill command status.
- Cautions: `-ErrorAction SilentlyContinue` hides "no such process"; a listing that returns nothing means the holder is invisible to that filter — record it, do not assume the lock is gone.
- Preserve: unrelated processes; pattern-based kills (name matches `*test*`/`*epilog*`) are a last resort only.
- Next condition: listing showed candidates → Step 3; listing empty → Step 4.

### Step 3: Wait briefly, then relink
- Actions: sleep between 300 ms and 1 s (`Start-Sleep -Seconds 1`, `Start-Sleep -Milliseconds 500`), then rerun the identical build command.
- Inputs: original build command.
- Outputs: relink result.
- Cautions: one observed sequence still failed on the immediate post-kill build and only succeeded on the next attempt after a 1 s delay — a single attempt is not conclusive.
- Preserve: same output path, same flags.
- Next condition: link exits 0 → Step 6; LNK1105 again → Step 4.

### Step 4: Delete the locked output and rebuild
- Actions: delete only the output artifact and check the result (PowerShell: `Remove-Item -Force <path> -ErrorAction SilentlyContinue` then verify `$?`), then rerun the build.
- Inputs: output path from Step 1.
- Outputs: delete status, relink result.
- Cautions: delete only the link output; keep object files, libraries, and other build products — a failed delete means an active lock, so return to Step 2 with a wider listing.
- Preserve: everything except the output artifact.
- Next condition: rebuild succeeds → Step 6; still locked → Step 5 or stop and report.

### Step 5 (bypass): Link to a fresh output name
- Actions: pass a new `-o` target (e.g. add a suffix) for the binaries that must be produced now, and run them from that path.
- Inputs: same sources/objects, new output name.
- Outputs: freshly named binaries with exit status 0.
- Cautions: scripts referencing the canonical name will not find the new file; record the deviation and clean up later.
- Preserve: the original path expectation is documented, not silently changed.
- Next condition: verification needs the binary now → Step 6; otherwise stay on Steps 2–4 until the canonical path works.

### Step 6: Verify the relink
- Actions: confirm link exit status 0 with no `LNK1105` line; confirm the success marker; confirm the file exists with a fresh timestamp; run the binary or its test suite from that path.
- Inputs: relink output and run output.
- Outputs: verification record (command, exit code, run evidence).
- Cautions: "the kill command printed nothing" is not verification, and a run that fails with a runtime exit code means the lock is resolved but a different defect remains.
- Preserve: report runtime failures as separate issues.
- Next condition: all checks pass → done; otherwise return to the failing step.

## Decision Rules
### When object compilation succeeded and only the final `-o <path>.exe` link failed
Treat it as a lock on that output path; run the kill + delay + relink sequence and leave sources, scripts, and flags untouched.

### When the build produces several binaries and one is locked while others link
Kill all images the same build command produces in one shot rather than one at a time; a single locked test binary among many is enough to fail the run.

### When a kill by image name was issued but the very next link still fails
Do not conclude the kill failed or that the name was wrong: observed sequences showed an immediate post-kill build still failing with 1224 and the next attempt after a 1 s sleep succeeding. Sleep 300 ms–1 s and retry once before escalating.

### When the process listing returns no candidate for the output path
Escalate to deleting the output artifact with `Remove-Item -Force` and rebuilding; this was verified end-to-end. The identity of an invisible holder was never established in the trajectory — report it as unconfirmed.

### When verification is blocked but a binary is needed immediately
Link to a fresh `-o` file name; two freshly named test binaries linked with exit status 0 in one run while the canonical names were locked. Record the new name because build scripts still reference the original.

### When the relink succeeds but the program then fails at runtime
Stop — the lock is resolved. Runtime failures (for example a silent exit -1073741571) are a separate defect and must not be reported as a link problem or as a fixed build.

## Invariants
- Never edit source files, build scripts, makefiles, or compiler/linker flags to work around a file lock.
- Delete only the link output artifact; object files, libraries, and unrelated build products stay intact.
- Kill only processes running binaries produced by this build; broad pattern-based kills are a last resort and must be reported as such.
- Do not treat filtered or suppressed linker output (e.g. dropping lines matching `^LINK`) as a fix — the lock and the missing binary remain.
- Do not report success without a relink that exits 0, an output file that exists, and a run of that file.
- Do not claim the identity of the locking process unless a listing actually showed it; otherwise state that the holder was not confirmed.
- Keep the original output path expectation visible: a fresh-name link is a documented bypass, not a silent rename.

## Common Failures
### Failure: LNK1105 persists after killing by image name
- Symptoms: repeated `LINK : fatal error LNK1105: cannot close file '<path>'; error code 1224` right after `Stop-Process -Name <name> -Force ... ; <build>`.
- Causes: in the observed case a path-filtered process listing returned nothing while the lock stayed, and the actual holder was never identified; whether the name, timing, or an invisible holder was responsible was not established.
- Recovery: delete the output with `Remove-Item -Force` and rebuild (verified: subsequent build reported `[odin] Built build\dmls.exe`), or link to a fresh output name (verified: two fresh-name links exited 0).

### Failure: Immediate relink after a kill still fails once
- Symptoms: first `kill + make` attempt still ends with `Error 1105`.
- Causes: handle-release timing is unconfirmed; the observed sequence failed immediately after the kill and succeeded on the next attempt after `Start-Sleep -Seconds 1`.
- Recovery: add a 300 ms–1 s delay and rerun the same build before escalating to deletion.

### Failure: Linker output suppressed by filtering
- Symptoms: the build looks clean, then running fails with `The term 'build/tests/test_solver.exe' is not recognized as a name of a cmdlet, function, script file, or executable program.`
- Causes: piping the compiler through a filter such as `Where-Object { $_ -notmatch "^LINK" }` hides the lock error and the failed output creation.
- Recovery: stop filtering, rerun the build visibly, then follow this procedure.

### Failure: Lock-inspection tooling unavailable
- Symptoms: `handle64.exe: The term 'handle64.exe' is not recognized as a name of a cmdlet, function, script file, or executable program.`
- Causes: the handle-inspection utility is not installed on the host.
- Recovery: skip identification and go directly to the verified branches — kill with a delay, delete the output, or use a fresh output name.

### Failure: Lock cleared but the program still misbehaves
- Symptoms: link succeeds and the binary runs but exits with a non-zero runtime code (e.g. -1073741571) or prints nothing.
- Causes: the lock and the runtime defect are independent; one session linked successfully after the kill and the binary still crashed on start.
- Recovery: declare the link problem solved, then treat the runtime failure as a separate issue.

## Verification
- Re-running the same build command exits 0 and its output contains no `LNK1105` line and no `Error 1105`.
- The build prints its success marker, e.g. `Built: bin/yggdrasil.exe` or `[odin] Built build\dmls.exe`.
- The output file exists at the expected path with a modification time later than the relink command.
- The binary executes from that path: a previously locked test run now prints suite results (e.g. `=== 6 PASSED, 1 FAILED ===`), or the application starts and logs its own startup output (e.g. `All smoke tests PASSED.`).
- When a fresh output name was used, the run invoked that exact name and the deviation is recorded in the session log.
- A second consecutive build succeeds without repeating the kill, showing the lock is really gone.
- The session diff contains no changes to sources, build scripts, or flags.
- The lock holder is reported as confirmed only if a process listing actually returned it; otherwise the note says "not confirmed".

## Examples
### Example 1: Frozen test binaries block `make` (kill all images + sleep + rebuild)
- Input: `clang ... -o build/frost_smoke.exe ...` ends with `LINK : fatal error LNK1105: cannot close file 'build\frost_smoke.exe'; error code 1224`, while the object compile and `llvm-ar` steps already succeeded.
- Procedure: Step 1 confirms link-only; Step 2 kills every image the makefile builds (`taskkill /F /IM <smoke image> /IM <second image> /IM <third image> 2>/dev/null`); Step 3 waits 1 s and reruns the same `make CC=<cc> AR=<ar> OPT="<opt>" BUILD=<dir>`; Step 6 verifies.
- Expected result: the link completes and the suites run, ending with their pass counts (observed `All smoke tests PASSED.` plus two further suites green).
- Parameterized values: image names come from the makefile's binary targets; delay 1 s; keep `CC`/`AR`/`OPT`/`BUILD` exactly as in the failing command.

### Example 2: Kill by name does not release the lock (delete the output instead)
- Input: `LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224` twice, the second occurrence right after `Stop-Process -Name dmls -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500; ... build.bat run`.
- Procedure: Step 2 lists candidates (`Get-Process | Where-Object {$_.Path -like "*<PROJECT>*"}`) and gets no output; Step 4 runs `Remove-Item -Force D:\DMLS\build\dmls.exe -ErrorAction SilentlyContinue`, confirms success, then reruns the build script; Step 6 verifies.
- Expected result: the build prints `[odin] Built build\dmls.exe` and the program starts normally.
- Parameterized values: project root path, output path, build script name; the holder's identity stays "not confirmed".

### Example 3: Bypass with a fresh output name to keep verification moving
- Input: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_indexing.exe'; error code 1224` while `test_solver.exe` in the same loop links fine.
- Procedure: Step 5 relinks both affected tests to new names (`-o build/tests/<test><suffix>.exe` with a comment marking the fresh filenames); Step 6 runs those binaries directly.
- Expected result: both links exit 0 (`<a>: 0`, `<b>: 0`) and the suites print their results from the fresh paths.
- Parameterized values: suffix chosen per run; the original names remain locked until their holders exit.

## Evidence
- file_id: `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index: 575, source_part_index: 0
  quote: `LINK : fatal error LNK1105: cannot close file 'build\frost_smoke.exe'; error code 1224`
  supports: problem — link-only failure: the same run shows object compiles and `llvm-ar rcs` succeeding before this line.

- file_id: `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index: 577, source_part_index: 0
  quote: `taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1`
  supports: action — one command kills every image the makefile builds, followed by a 1 s delay before rebuilding.

- file_id: `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index: 580, source_part_index: 0
  quote: `All smoke tests PASSED.`
  supports: verification — after the kill+delay the same `make` linked all three binaries and ran the suites to completion.

- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1187, source_part_index: 0
  quote: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224`
  supports: problem — several test binaries locked in one run while other suites linked and printed results.

- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1190, source_part_index: 0
  quote: `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500`
  supports: action — kill all of the build's test images by name with a 500 ms delay before the rebuild loop.

- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1191, source_part_index: 0
  quote: `=== 6 PASSED, 1 FAILED ===`
  supports: verification — the previously locked suites linked and executed; only the binary whose holder was not yet stopped remained failing.

- file_id: `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index: 1068, source_part_index: 0
  quote: `LINK : fatal error LNK1105: cannot close file 'bin\yggdrasil.exe'; error code 1224`
  supports: problem — an immediate post-kill build still failed with 1224, so one kill+build attempt is not conclusive.

- file_id: `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index: 1069, source_part_index: 0
  quote: `Start-Sleep -Seconds 1; make 2>&1`
  supports: action — a 1 s delay before retrying the identical build command.

- file_id: `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index: 1070, source_part_index: 0
  quote: `Built: bin/yggdrasil.exe`
  supports: verification — the delayed retry linked successfully and printed the build's success marker.

- file_id: `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02`, source_index: 456, source_part_index: 0
  quote: `LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224`
  supports: problem — failure persisted after `Stop-Process -Name dmls -Force ... Start-Sleep -Milliseconds 500 ... build.bat run`.

- file_id: `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02`, source_index: 457, source_part_index: 0
  quote: `Get-Process | Where-Object {$_.Path -like "*DMLS*"}`
  supports: action — candidate identification attempt whose result (source_index 458) was empty output, so no holder was confirmed.

- file_id: `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02`, source_index: 461, source_part_index: 0
  quote: `Remove-Item -Force D:\DMLS\build\dmls.exe -ErrorAction SilentlyContinue`
  supports: action — deletion of the locked output artifact as the escalation branch (its result at source_index 462 was `True`).

- file_id: `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02`, source_index: 465, source_part_index: 0
  quote: `[odin] Built build\dmls.exe`
  supports: verification — the rebuild after deleting the artifact produced the binary and the program then started.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 223, source_part_index: 0
  quote: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_indexing.exe'; error code 1224`
  supports: problem — a single locked test binary while `test_solver` in the same loop linked (`test_solver exit: 0`).

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 258, source_part_index: 0
  quote: `# Link just test_solver and test_indexing (fresh filenames to avoid lock)`
  supports: action — bypass branch: relink the locked binaries to new output names.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 259, source_part_index: 0
  quote: `test_indexing: 0`
  supports: verification — both fresh-name links reported exit status 0 while the canonical names stayed locked.

- file_id: `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index: 247, source_part_index: 0
  quote: `Where-Object { $_ -notmatch "^LINK" }`
  supports: problem (anti-pattern) — suppressing LINK output hides the lock error; the subsequent run reported `The term 'build/tests/test_solver.exe' is not recognized as a name of a cmdlet, function, script file, or executable program.` at source_index 252.

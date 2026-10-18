---
name: fix-windows-lnk1105-locked-output-exe
description: Use when a Windows clang/MSVC link step fails with "LINK : fatal error LNK1105 ... error code 1224" or "linker command failed with exit code 1105" while rebuilding an .exe that already exists. Helps the agent release the file lock (kill the holder process, wait, relink) or link to an alternate output path, then prove the binary was produced and runs. Requires a shell (PowerShell or Bash) with permission to terminate session-started processes, plus the original link command. Do not use when the text is a source compile error, an unresolved-symbol LNK2xxx, or a non-Windows linker failure.
triggers:
  - "LNK1105"
  - "error code 1224"
  - "exit code 1105"
  - "cannot close file"
---
# Fix Windows LNK1105 "cannot close file" Link Failures on a Locked Output Executable

## Goal
Restore a successful link of the target Windows executable that fails with LNK1105 / exit code 1105 because the output file is held open by a running process, and prove the fix by relinking cleanly and running the produced binary or test suite.

## Scope
### In scope
- Windows link-stage failures whose text contains `LINK : fatal error LNK1105` with `error code 1224`, or `linker command failed with exit code 1105`, or `make: *** [<target>] Error 1105` when the target is an existing `.exe`.
- Releasing the lock by terminating the process image that matches the output executable (REPL, test binary, debug tool started earlier in the session) and waiting for handle release before relinking.
- Falling back to linking the same objects into a different output path when the canonical path must stay locked.
- Re-running the build/test runner so the produced binary is actually executed.

### Out of scope
- C/C++ compile errors in translation units, and any non-1105 linker diagnostics (e.g. unresolved externals).
- Link failures where the message is `error code` other than 1224, or where no existing output file is involved.
- Source-code or test-failure debugging that remains after the binary links and runs.
- Antivirus/exclusion-list configuration, `make clean`, or deleting build directories — no evidence in the trajectories supports these.
- Non-Windows toolchains.

## Inputs
- Failing build/link output — string — tool result of the build command (Bash/PowerShell/`make`) — required — must contain `LINK : fatal error LNK1105` and `error code 1224`, or `linker command failed with exit code 1105`, or `make: *** [...] Error 1105` — default: 无.
- Original link command — string — the tool_call that produced the failure (its `-o <path>` names the locked file) — required — must be re-runnable verbatim for the retry — default: 无.
- Output executable path — string — parsed from the `-o` argument of the failing link line — required — e.g. `bin/yggdrasil.exe`, `build/tests/test_indexing.exe`, `epilog.exe` — default: 无.
- Holder process name — string — derived from the output path file name (without `.exe` for `Stop-Process -Name`, with `.exe` for `taskkill /IM`), cross-checked against processes started earlier in the session — required for Step 3 — default: base name of the output executable.
- Shell flavour — enum (`PowerShell` | `Bash`) — environment of the failing command — required — selects `Stop-Process`/`Start-Sleep` vs `taskkill`/`sleep` — default: 轨迹未提供, detect from the failing command.
- Wait budget before relink — duration — chosen by the agent — optional — observed working values 300 ms–1 s — default: 1 second.
- Alternate output path — string — chosen by the agent when the canonical path stays locked — optional — must be a fresh file name not currently open (e.g. `build/tests/test_indexing2025.exe`) — default: 无.

## Outputs
### Artifacts
- Relinked executable at the original path (preferred) or at the alternate path — location: the `-o` path from the failing link command — format: Windows PE `.exe`.
- Build/link log for the retry — location: captured tool result — format: plain text containing the link command echo.
- Optional secondary artifact: the alternate-named binary plus a note of its path so later steps do not run a stale binary.

### Success criteria
- The re-run link command exits 0 and its output contains no `LNK1105`, no `error code 1224`, and no `exit code 1105`.
- The output executable exists at the expected path and can be launched.
- Running the binary or its test suite produces real program/test output (e.g. a completed test run), not a "file not found"/"not recognized" error.

### Failure criteria
- LNK1105 recurs after kill + wait + relink and after a longer-wait retry.
- The binary links but the run reports a crash or a failing suite that is unrelated to linking.
- The holder of the lock cannot be identified or is a process the agent is not allowed to terminate.

## Preconditions
- The failing message is the Windows link-stage lock signature (`LINK : fatal error LNK1105` + `error code 1224`, or `linker command failed with exit code 1105`). If the text is a compile diagnostic or a different LNK code, stop and report that this skill does not apply.
- A shell is available in which the original build command can be re-run, and in which processes can be terminated (`Stop-Process`/`taskkill` require adequate rights on the machine). Without kill rights, skip to the alternate-output-path branch or stop and report.
- The output path is known from the failing command, and the file already exists (the lock is on a pre-existing `.exe`, not on a file being created for the first time).
- The candidate holder process belongs to this work session (the REPL/test/debug binary the agent launched). If the only matching processes are unrelated to the project, do not kill them — stop and report the blocker instead.
- No source edits are pending that the agent intends to attribute to this fix: this failure is environmental, so sources and build flags must stay untouched during the recovery.

## Procedure
### Step 1: Confirm the failure signature and extract the output path
- actions: Read the failing build tool result; locate `LINK : fatal error LNK1105` and `error code 1224`, or `linker command failed with exit code 1105`, or `make: *** [<target>] Error 1105`; take the output file from the `-o` argument of the link line that failed.
- inputs: failing tool result, original link command.
- outputs: confirmation flag, output executable path, holder-name candidate.
- cautions: `make` and test runners may re-label the failure (`Error 1105`, `COMPILE ERROR: <file>.cpp`, `Exit code 81/2/127`); those labels do not mean the source failed to compile — the object files usually compiled and only the link step hit the lock. Read the LNK line itself before touching sources.
- preserve: sources, headers, compiler flags, Makefile — unchanged.
- next: signature present → Step 2. Signature absent → stop; use the normal compile/test debugging path instead.

### Step 2: Identify the process holding the output file
- actions: derive the image name from the output path (`bin/yggdrasil.exe` → `yggdrasil` / `yggdrasil.exe`); recall binaries launched earlier in this session (REPL, test executables, debug tools) whose image name matches; if the shell allows, list matching running processes before killing.
- inputs: output executable path, session history of launched programs.
- outputs: ordered list of holder candidates.
- cautions: PowerShell `Stop-Process -Name <base>` takes the name without `.exe`; `taskkill /F /IM <image>` takes the name with `.exe`; `Stop-Process -Name <missing>` fails silently when `-ErrorAction SilentlyContinue` is used, so a no-op kill looks identical to a successful one.
- preserve: processes unrelated to this output binary.
- next: at least one candidate → Step 3. No candidate → Step 4 (alternate output path) and report that the holder was unidentified.

### Step 3: Terminate the holder, wait for handle release, and relink
- actions: PowerShell — `Stop-Process -Name <base> -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500; <original build command>`; Bash — `taskkill /F /IM <base>.exe ...; sleep 1; <original build command>`; capture the full output of the relink.
- inputs: holder name, wait budget, original link command.
- outputs: relink log.
- cautions: chaining kill and link in one command can still fail — in one observed session `Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make 2>&1` still ended with `make: *** [bin/yggdrasil.exe] Error 1105`, while the following `Start-Sleep -Seconds 1; make 2>&1` produced `"Built: bin/yggdrasil.exe"`. Treat the first chained attempt as possibly too early, not as proof that the diagnosis is wrong.
- preserve: the original link command and its flags — retry them unchanged.
- next: clean link (exit 0, no LNK1105) → Step 5. LNK1105 again → Step 4.

### Step 4: Retry with a longer wait, then fall back to an alternate output path
- actions: first rerun the link alone after a longer delay (`Start-Sleep -Seconds 1; make 2>&1`); if it still fails, link the same objects to a fresh file name that is not locked (observed: `-o build/tests/test_indexing2025.exe`, `/tmp/dbg2.exe`) and use that binary for the next step.
- inputs: original link command, alternate output path.
- outputs: binary at the canonical or alternate path.
- cautions: an alternate-path binary is a workaround — record its path, and never report that the canonical `bin/<tool>.exe` was rebuilt when it was not. Do not delete or `make clean` the locked file as a substitute for releasing the lock.
- next: link exits 0 → Step 5.

### Step 5: Verify the binary was produced
- actions: confirm the link command exited 0; confirm its log contains no `LNK1105` / `1105`; confirm the output file exists at the expected path (or at the recorded alternate path).
- inputs: relink log, output path.
- outputs: verification record (path + exit status).
- cautions: an empty log can mean success (a clean `clang` invocation prints nothing) or a command that never ran — check the exit status together with the file's existence; a missing binary surfaces later as `bin/yggdrasil.exe: No such file or directory` or `The term 'build/tests/test_solver.exe' is not recognized as a name of a cmdlet, function, script file, or executable program.`
- preserve: the produced binary.
- next: binary present → Step 6. Missing → back to Step 4.

### Step 6: Run the binary or test suite to prove the fix end to end
- actions: execute the produced executable (REPL smoke input, fixture run, or the test suite) and capture its output and exit code; when a test runner is used, make sure it checks the real exit code of each binary instead of filtering linker output.
- inputs: output executable path.
- outputs: program/test output used as the final evidence.
- cautions: filtering link errors out of the runner output (e.g. `Where-Object { $_ -notmatch "^LINK" }`) hides the failure while the binary stays missing — one session printed `All compiled` and then scored `=== TOTAL: 8 passed, 2 failed ===` with suites that produced no output at all.
- preserve: unrelated test results; do not delete previously passing binaries.
- next: program/test output observed and link errors absent → done. Otherwise report the residual failure separately from this link-lock issue.

## Decision Rules
### When the message is `LINK : fatal error LNK1105` with `error code 1224`
Treat it as an OS sharing violation on the output `.exe`: do not edit sources, headers, flags, or the Makefile. Go straight to identifying and terminating the holder of that file.

### When the output executable was launched earlier in the session (REPL, test run, debug tool)
Kill by image name, wait, then relink: PowerShell `Stop-Process -Name <base> -Force -ErrorAction SilentlyContinue` then `Start-Sleep`; Bash `taskkill /F /IM <base>.exe` then `sleep 1`. Verified outcomes: the FrostCore `make` run after `taskkill ...; sleep 1` completed the build and reported `All smoke tests PASSED.` and `Results: 135 passed, 0 failed`.

### When kill and relink are chained in one command and LNK1105 still appears
Do not abandon the diagnosis; the handle release is asynchronous. Run the link again after an additional delay (`Start-Sleep -Seconds 1; make 2>&1`), which produced `"Built: bin/yggdrasil.exe"` in one session after an immediately-following chained attempt had failed.

### When the canonical output path cannot be freed
Link the same objects into a fresh file name and use that binary. Verified: relinking `tests/test_indexing.cpp` to `build/tests/test_indexing2025.exe` returned `Compile: 0` with `13/13 tests passed`, while the same command targeting the locked `test_indexing.exe` had returned exit `1105`.

### When a build or test runner labels the failure as `COMPILE ERROR` or prints `All compiled` while LNK1105 is in the log
The objects compiled; only the link stage hit the lock. Re-run the link after releasing the lock, and require evidence that the `.exe` exists and runs before reporting the step as complete.

### When the lock holder cannot be identified or is not a session-started process
Stop after the retry-with-longer-wait attempt, report the blocker and the evidence (the LNK1105 line), and use the alternate-output-path branch only if a different path is acceptable for subsequent steps.

## Invariants
- Do not modify source files, headers, compiler flags, or build scripts to resolve an LNK1105 lock — the failure is environmental and all observed recoveries left the code untouched.
- Do not kill processes that do not correspond to the locked output binary or to a program started by this session.
- Do not suppress, filter, or truncate linker output (e.g. dropping lines matching `^LINK`) and then report the build as successful.
- Do not report a successful build without evidence that the link command exited 0 and the output file exists; do not report the canonical binary as rebuilt when only an alternate path was produced.
- Do not skip the final run of the binary/tests: a clean link alone does not show that the program works.
- Do not delete the locked file, run `make clean`, or restart the machine as a first resort; those are out of scope and unverified here.
- Do not attribute the LNK1105 episode to a source-level bug in the final report; keep the environmental fix and any code changes clearly separated.

## Common Failures
### Failure: Relink immediately after kill, with no wait
- symptoms: the chained command `Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make 2>&1` still ends with `make: *** [bin/yggdrasil.exe] Error 1105` and PowerShell reports `clang++: error: linker command failed with exit code 1105 (use -v to see invocation)`.
- causes: the process handle on the image is released asynchronously, so the link can start while the file is still open (observed pattern; exact release timing not measured in the trajectory).
- recovery: sleep and relink by itself (`Start-Sleep -Seconds 1; make 2>&1`), which then produced `"Built: bin/yggdrasil.exe"`.

### Failure: Masking the linker error instead of producing the binary
- symptoms: the runner prints `All compiled` while its log still contains `clang++: error: linker command failed with exit code 1105 (use -v to see invocation)`; later the suite run yields `The term 'build/tests/test_solver.exe' is not recognized as a name of a cmdlet, function, script file, or executable program.` and ends with `=== TOTAL: 8 passed, 2 failed ===`.
- causes: output was filtered (e.g. `Where-Object { $_ -notmatch "^LINK" }`) and the compile step was declared finished without checking that each `.exe` was written.
- recovery: rerun the same link commands without filtering, confirm exit status 0 per binary, then run the suites again.

### Failure: Misreading a link-stage lock as a compile or test failure
- symptoms: a test runner reports `COMPILE ERROR: test_parser.cpp` (and similar for several suites) while the underlying text is `LINK : fatal error LNK1105 ... error code 1224`; suite summary reads `=== 2 suite(s) PASSED, 5 FAILED ===`.
- causes: the runner labels any non-zero compiler-driver exit as a compile error; the driver exit code 1105 comes from the linker, not the compiler.
- recovery: release the lock and relink; after killing the stale test processes before compiling, the same runner reported `=== 6 PASSED, 1 FAILED ===` with the remaining failure unrelated to linking.

### Failure: Holder process name does not match, kill is a no-op
- symptoms: `Stop-Process ... -ErrorAction SilentlyContinue` reports nothing and the same LNK1105 reappears; or only `taskkill /F /IM <name>.exe` (which errors visibly when the image is absent) reveals the name mismatch.
- causes: PowerShell `Stop-Process -Name` expects the name without `.exe` and silently does nothing when it matches nothing; multiple differently named test binaries can hold different outputs.
- recovery: enumerate the candidate images (e.g. filter running processes by name pattern), kill each match with `-Force`, wait, then relink; if none match, switch to the alternate-output-path branch and report the unidentified holder.

## Verification
- Re-run the original link command and observe exit status 0.
- Grep that command's output: no `LNK1105`, no `error code 1224`, no `exit code 1105`, no `Error 1105`.
- Confirm the output file exists at the expected path (or at the recorded alternate path) and that its creation/modification is a result of this link run.
- Launch the produced executable and observe real program output (banner, fixture output, REPL response) rather than `No such file or directory` / `is not recognized as a name of a cmdlet`.
- Run the associated test suite and record the pass/fail summary; each suite's binary must have been produced by a link run that exited 0.
- Confirm that no `COMPILE ERROR:`-style label in the runner output is backed by an LNK1105 line; if one is, the step is not yet verified.
- Confirm sources, flags, and build files are byte-identical to their pre-recovery state (no code change was made for this fix).

## Examples
### Example 1: `make` cannot relink a running REPL binary (PowerShell)
- input: build output containing `LINK : fatal error LNK1105: cannot close file 'epilog.exe'; error code 1224` and `linker command failed with exit code 1105 (use -v to see invocation)`; output path `epilog.exe`.
- procedure: Step 1 (signature + path) → Step 2 (holder = image `epilog`, launched earlier as a REPL) → Step 3 (`Stop-Process -Name epilog -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 300; <clang compile+link command>`) → Step 5 (link produced no error text) → Step 6 (pipe a small Prolog program into `.\epilog.exe`).
- expected result: the link command emits no error and the program answers with its banner (`Epilog 0.1  (type 'halt.' to exit, '?- goal.' to query)`), proving both link and run.
- parameterized values: process base name = `epilog`, output = `epilog.exe`, wait = 300 ms, compile driver = `clang`.

### Example 2: `make` build fails on a smoke-test binary (Bash)
- input: `make` output ending with `make: *** [build/frost_smoke.exe] Error 1105`; outputs `build/frost_smoke.exe`, `build/frost_subsystems.exe`, `build/frost_bytecode.exe`.
- procedure: Step 1–2 (holders = the three test images from earlier runs) → Step 3 (`taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make CC=clang AR=llvm-ar` …) → Step 6 (run the full `make test` output).
- expected result: all three binaries link in the same run and the suites print `All smoke tests PASSED.`, `Results: 135 passed, 0 failed`, `Results: 101 passed, 0 failed`.
- parameterized values: images = one per output `.exe`, wait = 1 s, build command = the session's `make` invocation.

### Example 3: locked test binary, alternate output path
- input: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_indexing.exe'; error code 1224` with `test_indexing exit: 1105`, where the holder could not be freed in time.
- procedure: Step 4 (compile the same objects with `-o build/tests/test_indexing2025.exe`, keeping all flags unchanged) → Step 5 (`Compile: 0`, file present) → Step 6 (run the new binary).
- expected result: `Compile: 0` followed by `13/13 tests passed` and `exit: 0`; the canonical path stays reported as not rebuilt.
- parameterized values: suffix = any unique token, e.g. `<year>`; object list and flags reused verbatim from the failing command.

## Evidence
Problem:
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-02`, source_index 370, source_part_index 0 — quote: `LINK : fatal error LNK1105: cannot close file 'epilog.exe'; error code 1224` — supports: the failure signature is a lock on an existing output `.exe`, with no source involvement.
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-02`, source_index 370, source_part_index 0 — quote: `clang: error: linker command failed with exit code 1105 (use -v to see invocation)` — supports: why the error key is exit status `0x00000451` (1105).
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 252, source_part_index 0 — quote: `The term 'build/tests/test_solver.exe' is not recognized as a name of a cmdlet, function, script file, or executable program.` — supports: downstream symptom when the locked binary was never produced.
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index 1187, source_part_index 0 — quote: `COMPILE ERROR: test_parser.cpp` — supports: test runners mislabel a link-stage lock as a compile error.

Action:
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index 1065, source_part_index 0 — quote: `Stop-Process -Name yggdrasil -Force -ErrorAction SilentlyContinue; make 2>&1` — supports: kill-then-relink as the primary remediation attempt (this chained attempt itself still failed, see 1068).
- file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index 577, source_part_index 0 — quote: `taskkill /F /IM frost_smoke.exe /IM frost_subsystems.exe /IM frost_bytecode.exe 2>/dev/null; sleep 1; make CC=clang AR=llvm-ar` — supports: kill by image name plus an explicit wait before relinking.
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index 1069, source_part_index 0 — quote: `Start-Sleep -Seconds 1; make 2>&1` — supports: an extra delay plus relink when the first chained attempt still hit LNK1105.
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index 1190, source_part_index 0 — quote: `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue` — supports: killing several stale test images before recompiling a whole suite.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 278, source_part_index 0 — quote: `build/tests/test_indexing2025.exe` — supports: the alternate-output-path fallback when the canonical `.exe` stays locked.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 247, source_part_index 0 — quote: `Where-Object { $_ -notmatch "^LINK" }` — supports: the anti-pattern of filtering linker errors out of the runner output.

Verification:
- file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index 580, source_part_index 0 — quote: `All smoke tests PASSED.` — supports: after kill + `sleep 1`, the previously locked binaries linked and ran.
- file_id `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`, source_index 580, source_part_index 0 — quote: `Results: 135 passed, 0 failed` — supports: end-to-end success of the same recovery run.
- file_id `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`, source_index 1070, source_part_index 0 — quote: `"Built: bin/yggdrasil.exe"` — supports: relink succeeded after the additional one-second wait.
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-03`, source_index 534, source_part_index 0 — quote: `(PowerShell completed with no output)` — supports: the kill + 300 ms wait + full `clang` compile/link command completed with no error text.
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-03`, source_index 536, source_part_index 0 — quote: `Epilog 0.1  (type 'halt.' to exit, '?- goal.' to query)` — supports: the relinked binary runs.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 279, source_part_index 0 — quote: `Compile: 0` — supports: the alternate-output-path link succeeded.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 279, source_part_index 0 — quote: `13/13 tests passed` — supports: the alternate binary runs and passes.
- file_id `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`, source_index 252, source_part_index 0 — quote: `=== TOTAL: 8 passed, 2 failed ===` — supports: the filtered-output approach did not produce working binaries.
- file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index 1191, source_part_index 0 — quote: `=== 6 PASSED, 1 FAILED ===` — supports: after killing stale test processes before recompiling, all but one suite relinked and ran.

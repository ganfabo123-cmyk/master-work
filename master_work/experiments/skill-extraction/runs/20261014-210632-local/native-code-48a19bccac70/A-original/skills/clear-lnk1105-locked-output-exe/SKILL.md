---
name: clear-lnk1105-locked-output-exe
description: Use when the MSVC/clang++ linker fails with `LNK1105: cannot close file '<output>.exe'; error code 1224` while rebuilding an executable that a previous run left running. Helps the agent identify the locked output, terminate only the project's lingering processes (exact-name, then wildcard -Force, with a short wait), and relink successfully. Requires the linker output naming the locked file, a shell able to list/kill processes (PowerShell or taskkill), and the original build command. Do not use for LNK2019/LNK1120 unresolved-symbol errors or for binaries that relink but fail at runtime.
---
# Clear MSVC LNK1105 (error code 1224) Caused by a Lingering Process Holding the Output EXE

## Goal
Unblock a Windows link step that fails with `LINK : fatal error LNK1105: cannot close file '<output>.exe'; error code 1224` by terminating the lingering process that still holds the output executable, then rerun the same link command successfully.

## Scope
### In scope
- MSVC/clang-cl linker failures where the error names the project's own output file (`LNK1105: cannot close file 'epilog.exe'; error code 1224`, `LNK1105: cannot close file 'build\tests\test_parser.exe'`) and a previously launched copy of that binary is still running.
- Recovering with shell process management on Windows: PowerShell `Stop-Process -Name <names>`, wildcard `Get-Process | Where-Object { $_.Name -like "*<pattern>*" } | Stop-Process -Force`, `taskkill /F /IM <image>`, each followed by a short sleep before relinking.
- Escalation when a name-scoped kill does not clear the lock: broader wildcard kill with `-Force` and a longer wait.

### Out of scope
- `LNK2019`/`LNK1120` unresolved-external errors (separate skill: fix-lnk1120-header-extern-global).
- `LNK1105` when the file is held by antivirus/indexer or another non-project process — the trajectory never observed this; stop and report if no process of this project holds the file.
- Runtime failures of the freshly linked binary (e.g. exit `-1073741571` observed after a successful relink); relinking is the end of this skill.
- Non-Windows platforms, where output files are not locked this way.

## Inputs
- **Linker error text**: string, from the failing build tool result, required. Must contain `LNK1105`, `cannot close file`, the output path, and `error code 1224`. Default: 无.
- **Output executable identity**: name/path parsed from the error plus the project's binary names (trajectory: `epilog.exe`; test binaries `test_atoms`, `test_terms`, `test_parser`, `test_unifier`, `test_variables`), required. Default: 无.
- **Shell**: process-capable shell (trajectory: PowerShell; `taskkill` also used), required. Default: 无.
- **Original build command**: the exact compile/link invocation to rerun unchanged (trajectory: `clang -std=c11 ... -o epilog.exe` and the PowerShell test loop compiling `tests\test_*.cpp` to `build\tests\*.exe`), required. Default: 无.
- **Wait duration**: milliseconds between kill and relink (trajectory used 300–800 ms; 500 ms worked for `epilog.exe`, 800 ms with `-Force` worked for a stubborn test binary). Default: 500.

## Outputs
### Artifacts
- Killed-process step in the build command (e.g. `Stop-Process -Name <names> -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds <n>` prepended to the link command, or `taskkill /F /IM <image>`).
- Relinked output executable at its original path (trajectory: `epilog.exe`, `build\tests\test_*.exe`).
- Relink tool output log showing completion without `LNK1105`.

### Success criteria
- The relink completes with no `LNK1105` and no `linker command failed with exit code 1105`; the output executable file is written/refreshed.
- The same build command can be run again without the lock error.

### Failure criteria
- `LNK1105 ... error code 1224` still appears after the kill+wait+relink cycle.
- The named/wildcard process list is empty yet the file stays locked — an external holder was not identified; stop and report rather than killing unrelated processes.
- The relink succeeds but the binary fails at runtime; that is out of scope and must be reported separately, not as a failure of this skill.

## Preconditions
- The failing output is `LNK1105` with `error code 1224` naming this project's own executable; if the error is `LNK2019`/`LNK1120`, stop and use the unresolved-external procedure instead.
- Permission to terminate processes of this project (trajectory ran in the project directory and killed only `epilog`/`test_*` images). If only processes outside this project appear to hold the file, stop and report.
- A shell that can list and kill processes (PowerShell `Stop-Process`/`Get-Process`, or `taskkill`) and sleep between kill and relink.
- The original compile/link command is available to rerun unchanged.
- Working directory matches the build's (trajectory: `cd d:\Epilog` before building), otherwise the wrong binary may be targeted.

## Procedure
### Step 1: Identify the locked output and its owning process names
- actions: Read the `LNK1105` line and extract the locked file (trajectory: `'epilog.exe'`, `'build\tests\test_parser.exe'`). Map it to the process image name (strip path and `.exe`: `epilog`, `test_parser`). Cross-check with any prior assistant observation that the binary was left running (trajectory: `The binary is still running (file locked). Kill it and rebuild:`).
- inputs: linker error text, project binary names.
- outputs: target process name(s) and the exact build command to rerun.
- cautions: do not infer a lock from a different error code; `LNK1105` + `1224` is the signal.
- preserve: all sources and build scripts — nothing is edited in this skill.
- next: go to Step 2 with at least one concrete image name.

### Step 2: Kill the lingering project process, wait, and relink
- actions: Prepend a kill and a short sleep to the unchanged build command, e.g. `Stop-Process -Name epilog -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500; clang ... -o epilog.exe` (trajectory pattern; 300–800 ms sleeps were used).
- inputs: process names from Step 1, original build command, wait duration (default 500 ms).
- outputs: relink result.
- cautions: `-ErrorAction SilentlyContinue` tolerates "not running"; a kill that matches nothing leaves the lock in place, so treat a repeated LNK1105 as "process not actually terminated", not as a new problem.
- preserve: compiler flags, output path, sources.
- next: if the link succeeds, go to Step 4; if `LNK1105` repeats, go to Step 3.

### Step 3: Escalate to a wildcard force-kill with a longer wait
- actions: Kill every project-matching process regardless of exact name: `Get-Process | Where-Object { $_.Name -like "*test*" -or $_.Name -like "*epilog*" } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800`, or `taskkill /F /IM "test_atoms.exe"` per image; then rerun the same build command (trajectory: an exact-name `Stop-Process -Name test_atoms,...` run still produced `LNK1105 ... 'build\tests\test_atoms.exe'`, while the wildcard `-Force` + 800 ms retry linked successfully).
- inputs: name patterns scoped to this project, `-Force`, longer sleep.
- outputs: relink result without `LNK1105`.
- cautions: keep the wildcard filter constrained to this project's binaries; do not broaden to all processes.
- preserve: everything except the running processes.
- next: go to Step 4 on a clean link; if still locked, stop and report an unidentified external holder.

### Step 4: Confirm the relink and move on
- actions: Verify the link output has no `LNK1105`/`1105` lines and the executable was produced, then continue with the original build/test plan.
- inputs: relink output.
- outputs: successful link evidence.
- cautions: a subsequent runtime failure of the binary (trajectory saw `exit -1073741571` right after a successful relink) is a separate issue — do not loop back into kill/relink for it.
- preserve: the freshly built binary.
- next: report link success; hand off runtime failures to their own investigation.

## Decision Rules
### When the link error is `LNK1105 ... cannot close file '<output>'; error code 1224`
Treat it as a file lock on this project's own executable: kill the owning process, sleep briefly, rerun the unchanged link command (Step 2). Verified repeatedly — after `Stop-Process -Name epilog ... Start-Sleep -Milliseconds 500` the `clang ... -o epilog.exe` link completed with no output (success) where it had failed with LNK1105.

### When an exact-name kill is followed by another `LNK1105` for the same file
The named kill did not terminate the holder (trajectory: `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser` still left `LNK1105: cannot close file 'build\tests\test_atoms.exe'`). Escalate to the wildcard `-Force` kill plus a longer sleep (Step 3), which then linked cleanly.

### When the project runs several test executables in a loop
Kill all candidate images up front in the same command (`Get-Process | Where-Object { $_.Name -like "*test*" -or $_.Name -like "*epilog*" } | Stop-Process -Force ...; Start-Sleep`) rather than fixing locks one file at a time, so one iteration does not lock the next.

### When the relink succeeds but the binary fails immediately at runtime
Stop: the lock is cleared (e.g. `LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link` with no LNK1105, followed by `exit: -1073741571`). Runtime diagnosis is outside this skill.

### When no process belonging to this project holds the file
Stop and report; the trajectory provides no verified recovery for non-project holders.

## Invariants
- Never edit source files, build scripts, flags, or output paths to work around LNK1105; only processes and a short wait change.
- Kill only processes belonging to this project (bounded name/image patterns such as `epilog`, `test_*`); never a global unscoped kill.
- Rerun the original build command byte-for-byte after clearing the lock, so a successful link is attributable to the unlock.
- Do not skip the wait between kill and relink; the verified recovery always included a sleep (300–800 ms).
- Do not report the build as fixed on the basis of the kill alone — the relink output itself must be free of `LNK1105`.
- Do not chain runtime failures of the relinked binary into this procedure; report link status and runtime status separately.
- Do not claim the root cause of why the processes stayed alive; the trajectory only shows they were "still running (file locked)".

## Common Failures
### Failure: relink fails again with LNK1105 after an exact-name kill
- symptoms: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_atoms.exe'; error code 1224` on the retry even though `Stop-Process -Name test_atoms,... -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500` ran.
- causes: the targeted kill did not actually terminate the holding process; the trajectory does not state why (name mismatch, elevation, or still-exiting process all remain unconfirmed).
- recovery: escalate to `Get-Process | Where-Object { $_.Name -like "*test*" -or $_.Name -like "*epilog*" } | Stop-Process -Force -ErrorAction SilentlyContinue` with `Start-Sleep -Milliseconds 800`, or `taskkill /F /IM "test_atoms.exe"`, then relink; this cleared the lock in the observed case.

### Failure: one locked binary poisons a whole test loop
- symptoms: a multi-suite build reports `COMPILE ERROR` for several suites, each with `LNK1105 ... error code 1224`, while other suites link and run.
- causes: previous iterations left their executables running, so the next loop's relinks hit locked files.
- recovery: kill all project test processes at the top of the loop (Step 3 command) before iterating.

### Failure: file remains locked and no project process matches
- symptoms: LNK1105 persists after scoped kills; process list shows no `epilog`/`test_*` images.
- causes: holder unidentified; the trajectory never observed or resolved this case.
- recovery: stop and report the situation; do not broaden the kill beyond this project.

### Failure: treating a successful relink as a fully working build
- symptoms: LNK1105 is gone, yet the run continues to fail — e.g. the binary exits with `-1073741571` or prints no tests.
- causes: an unrelated runtime defect (in the trajectory, test binaries crashed at startup with exit `-1073741571` after linking).
- recovery: report the link as fixed and hand the runtime failure to a separate diagnosis; do not repeat kill/relink cycles.

## Verification
Check the relink output produced after the kill+wait cycle (each item must be matched in fresh output, not assumed):

1. No `LNK1105` and no `cannot close file` line appears anywhere in the relink output.
2. No `linker command failed with exit code 1105`.
3. The linker reports producing/updating the target (trajectory: `LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link` with no fatal error), and/or the build loop no longer tags that suite as `COMPILE ERROR`.
4. In a multi-target loop, every target that previously failed with LNK1105 now compiles and links in the same run.
5. The previously locked file can be rebuilt a second time without repeating the error.

Report separately: link status (checks 1–4) versus runtime status of the produced binary (trajectory observed `exit: -1073741571` after a clean relink — that does not invalidate checks 1–4, but must be reported as an open runtime issue).

## Examples
### Example 1: relink the main executable after an interactive run left it alive
- input: Build output `LINK : fatal error LNK1105: cannot close file 'epilog.exe'; error code 1224` followed by `clang: error: linker command failed with exit code 1105`; project dir `d:\Epilog`.
- procedure: Step 1 map `epilog.exe` → process `epilog`; Step 2 run `cd d:\Epilog && Stop-Process -Name epilog -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500; clang -std=c11 -Wall -Wextra -Wpedantic -Iinclude main.c repl.c internals/atoms.c internals/variables.c internals/terms.c parser/lexer.c parser/parser.c engine/database.c engine/unifier.c engine/builtins.c engine/solver.c -o epilog.exe 2>&1`; Step 4 inspect the output.
- expected result: the command completes with no output (no LNK1105, no linker error) and `epilog.exe` is written; the identical kill+sleep+link pattern succeeded three separate times in the trajectory (different sleeps: 500/300/400 ms).
- parameterized values: output `epilog.exe`, process `epilog`, sleep 300–500 ms, compiler `clang -std=c11`.

### Example 2: clear multiple locked test binaries before a batch rebuild
- input: A PowerShell loop compiles `tests\test_*.cpp` to `build\tests\*.exe` with `clang++ -std=c++23 -Iinclude -Itests -g -O0`; output contains `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224` (and similar for `test_terms`, `test_unifier`, `test_variables`), while other suites link and run.
- procedure: Step 1 extract each locked image (`test_parser`, `test_terms`, ...); Step 2 first attempt `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500`; when one file is still locked, Step 3 escalate to `Get-Process | Where-Object { $_.Name -like "*test*" -or $_.Name -like "*epilog*" } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800` (or `taskkill /F /IM "test_parser.exe"`) and rerun the unchanged loop.
- expected result: all suites compile and link in one run — trajectory reached `=== 6 PASSED, 1 FAILED ===` with the only remaining failure being a runtime issue on one binary, and no `LNK1105` lines.
- parameterized values: output dir `build\tests`, name patterns `test_*` and `epilog`, sleep 500→800 ms, compiler `clang++ -std=c++23`.

## Evidence
All quotes from file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original`.

- problem — source_index 370, source_part_index 0, quote: `LINK : fatal error LNK1105: cannot close file 'epilog.exe'; error code 1224`, supports: the locked-output failure mode (the same text recurs at source_index 532 and 645, each fixed the same way).

- diagnosis — source_index 373, source_part_index 0, quote: `The binary is still running (file locked). Kill it and rebuild:`, supports: identifying a lingering process as the lock holder.

- action — source_index 374, source_part_index 0, quote: `Stop-Process -Name epilog -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500`, supports: the kill + wait step prepended to the unchanged `clang ... -o epilog.exe` link command in the same event.

- verification — source_index 375, source_part_index 0, quote: `(PowerShell completed with no output)`, supports: the relink that previously failed with LNK1105 completed with no error output; the same kill→relink→no-output pattern verified again at source_index 534 and 647.

- problem (batch case) — source_index 1187, source_part_index 0, quote: `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224 clang++: error: linker command failed with exit code 1105 (use -v to see invocation)`, supports: the same lock error affecting multiple test binaries inside one build loop.

- diagnosis (batch) — source_index 1189, source_part_index 0, quote: `The "compile errors" are just file-locked binaries from the previous run still in memory.`, supports: root cause is executables left running from the previous run.

- partial recovery / escalation trigger — source_index 1191, source_part_index 0, quote: `COMPILE ERROR: test_atoms.cpp`, supports: after an exact-name `Stop-Process -Name test_atoms,... ; Start-Sleep -Milliseconds 500` (source_index 1190), `test_atoms` still failed with `LINK : fatal error LNK1105: cannot close file 'build\tests\test_atoms.exe'; error code 1224` in the same event, showing a name-scoped kill can be insufficient.

- escalation action — source_index 1193, source_part_index 0, quote: `Get-Process | Where-Object { $_.Name -like "*test*" -or $_.Name -like "*epilog*" } | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 800`, supports: wildcard force-kill scoped to the project plus a longer wait before relinking.

- escalation verification — source_index 1194, source_part_index 0, quote: `LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link`, supports: the previously locked `test_atoms.exe` relinked with no `LNK1105` after the wildcard `-Force` kill (the same event's later `exit: -1073741571` is a runtime failure, not a link lock).

- alternate kill form — source_index 1220, source_part_index 0, quote: `taskkill /F /IM "test_atoms.exe"`, supports: per-image force kill as another way to release the lock before relinking.

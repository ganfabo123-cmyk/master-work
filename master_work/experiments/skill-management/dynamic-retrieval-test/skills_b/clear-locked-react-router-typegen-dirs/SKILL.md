---
name: clear-locked-react-router-typegen-dirs
description: Use when `react-router dev` on Windows crashes at startup with `EPERM: operation not permitted, scandir` or `ENOTEMPTY` rmdir on `.react-router/types/**/+types` directories. Helps the agent confirm the symptom, inspect locked dirs, skip deletion tools proven to fail on ACL-less volumes, locate the unconditional typegen cleanup call in the bundled dist, and clear the cache tree with verification. Requires Windows, Bash plus PowerShell tools, and installed `node_modules/@react-router/dev`. Do not use when the dev server boots normally, when the crash path is outside `.react-router/types`, or when no dev-server run can be executed.
triggers:
  - "EPERM: operation not permitted, scandir"
  - "ENOTEMPTY"
  - ".react-router/types"
  - "typesDirectory(ctx)"
---
# Clear Windows-Locked React Router Typegen +types Dirs That Crash the Dev Server with EPERM

## Goal
Diagnose the `EPERM: operation not permitted, scandir` (or `ENOTEMPTY` rmdir) startup crash of `react-router dev` caused by Windows-locked `.react-router/types/**/+types` directories, and reach a verified end state: either the typegen cache tree is deleted (a listing confirms it is gone) or a dev-server boot output shows no EPERM line.

## Scope
### In scope
- Reproducing the crash with a short `npm run dev` run and capturing the exact `EPERM`/`ENOTEMPTY` message.
- Inspecting locked directories with `cmd /c dir /a` when PowerShell and Node cannot read them.
- Recognizing deletion routes that provably fail on volumes without ACL support (`takeown`, `icacls`, `cmd rd`, `rmdir`, `robocopy /MIR`, `node fs.rmSync`, nested `rm -rf` of a subtree).
- Locating the unconditional typegen cleanup call `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` in the bundled `@react-router/dev` dist.
- Two mitigations: appending `.catch(() => {})` to those cleanup calls, and a single-pass Bash wipe of the whole `.react-router` tree.
- Verification of whichever mitigation was applied.

### Out of scope
- Fixing the filesystem, converting the volume, or granting ACLs.
- EPERM failures whose path is outside `.react-router/types` (antivirus locks, other tools).
- React Router application code, routes, or config changes as a "workaround".
- React Router versions whose dist layout differs from `dist/vite.js` + `dist/cli/index.js`.
- Re-running the app after switching frameworks (the trajectory later moved to SolidJS).

## Inputs
- Project directory — path — task environment — required — must contain `node_modules/@react-router/dev/dist/vite.js` and `node_modules/@react-router/dev/dist/cli/index.js`; default: 无
- Dev-server crash output — string — tool result of a short `npm run dev` run — required — must contain `EPERM` with `scandir`, or `ENOTEMPTY` with `rmdir`, pointing into `.react-router/types`; default: 无
- Bash and PowerShell tools — tool capability — agent environment — required — PowerShell for `cmd /c` inspection and Start-Job runs, Bash for `rm -rf` and `ls`; default: 无
- Mitigation choice — enum (`patch-dist` | `wipe-cache`) — agent decision — not required — `patch-dist` keeps the cache dir but makes cleanup non-fatal; `wipe-cache` deletes `.react-router`; default: 无
- Project path and dev command — strings — task environment — required — parameterize all examples; default: `npm run dev`

## Outputs
### Artifacts
- Removed cache tree: `<project>/.react-router` (format: directory absent after a successful wipe).
- Optional patched bundles: `<project>/node_modules/@react-router/dev/dist/vite.js` and `<project>/node_modules/@react-router/dev/dist/cli/index.js` (format: JavaScript with `.catch(() => {})` appended to the three typegen `rm` call sites).
- No report file; findings go into the final message.

### Success criteria
- `rm -rf <project>/.react-router && echo done` prints `done` and a subsequent listing of `<project>` no longer shows `.react-router`; and/or
- a post-change `npm run dev` boot output contains no `Error: EPERM: operation not permitted, scandir` line.

### Failure criteria
- Locked `+types` directories still exist after the single-pass wipe.
- A dev-server boot still prints the EPERM line.
- The dist bundles cannot be edited (read-only `node_modules`) when `patch-dist` was chosen.

## Preconditions
- Windows host with Node/npm installed and `npm install` already completed for the project; otherwise stop and report that the environment cannot reproduce the crash.
- The observed crash path is under `.react-router/types` (for example `types/app/+types` or `types/app/routes/+types`); a crash elsewhere means this skill does not apply.
- Both Bash and PowerShell tools are available: PowerShell for `cmd /c "dir /a ..."` inspection and short Start-Job runs, Bash for `rm -rf` and `ls`.
- Permission to run `npm run dev` briefly and to stop it; no other agent or session may be running the same dev server concurrently, because lingering Node jobs can hold directory handles.
- Permission to edit `node_modules/@react-router/dev/dist/*` if the `patch-dist` mitigation will be attempted; if `node_modules` is read-only, only the `wipe-cache` path is available.

## Procedure
### Step 1: Reproduce and capture the crash
- Actions: in PowerShell run the dev server inside a job with a short wait, e.g. `cd <project>; $job = Start-Job { Set-Location <project>; npm run dev 2>&1 }; Start-Sleep -Seconds 10; Receive-Job $job; Stop-Job $job; Remove-Job $job`, then read the received output.
- Inputs: project path, dev command.
- Outputs: the raw error text.
- Cautions: npm writes warnings to stderr, so PowerShell may wrap output in `NativeCommandError`; judge by the actual `[Error: ...]` line, not the wrapper. The wait must be long enough for typegen to run (~8–12 s worked) and the job must always be stopped.
- Preserve: keep the exact error message for the report.
- Next condition: message contains `EPERM` and `scandir` with a path under `.react-router/types` (or `ENOTEMPTY` + `rmdir` on the same tree) → Step 2; otherwise stop and report that the symptom does not match.

### Step 2: Inspect the locked directories with cmd
- Actions: run `cmd /c "dir /a <project>\.react-router\types\app\routes"` and the sibling `.../app` directory listing; also list the parent tree.
- Inputs: locked paths taken from the error message.
- Outputs: confirmation that `+types` entries exist and whether they contain files.
- Cautions: PowerShell `Get-ChildItem -Recurse` may error or return nothing on this tree, and Node `readdir` fails with `EPERM`; `cmd dir /a` still works. Expect `<DIR> +types` with `0 File(s)` — locked but empty directories.
- Preserve: do not attempt to write inside the locked tree.
- Next condition: directories confirmed present → Step 3.

### Step 3: Rule out deletion routes that provably fail here
- Actions: on a volume where `takeown` reports `there is no support for ACLs.`, do NOT repeat `takeown`/`icacls`, `cmd /c rd /s /q`, `cmd /c rmdir`, `robocopy <empty> <target> /MIR`, `node -e "...fs.rmSync..."`, or nested `rm -rf <tree>/<subdir>`; each was tried once and failed in this trajectory with `Access is denied.`, `exit: 5`, `ERROR 5 (0x00000005) Deleting Extra Directory`, `EPERM ... scandir` at `fixWinEPERMSync`, and `rm: cannot remove ...: Directory not empty` respectively.
- Inputs: Step 2 findings, error text.
- Outputs: decision to go straight to Step 4/5 instead of OS-level reclaim.
- Cautions: `rd /s /q` can exit 0 while still leaving `+types` behind — an exit code alone is not proof of deletion.
- Preserve: the cache tree itself.
- Next condition: proceed to Step 4 (locate crash source) and/or Step 5/6 (mitigation).

### Step 4: Locate the unconditional typegen cleanup call
- Actions: grep `typesDirectory` in `node_modules/@react-router/dev/dist/vite.js`; read the surrounding lines; repeat for `node_modules/@react-router/dev/dist/cli/index.js`.
- Inputs: installed `@react-router/dev` dist files.
- Outputs: the call sites — one inside `async function watch(rootDirectory, { mode, logger, rsc }) {` in `vite.js`, and two in `cli/index.js` (inside `run` and `watch`), all of the form `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`.
- Cautions: the bundled file is generated; line numbers may shift between versions, so match on the code text, not the line number. The crash stack itself may not name this line — treat it as the prime suspect because it unconditionally deletes the tree that contains the locked dirs.
- Preserve: every other line of the dist files.
- Next condition: all call sites identified → Step 5 (patch) or Step 6 (wipe), or both.

### Step 5: Mitigation A — make the cleanup non-fatal (effect unverified in this trajectory)
- Actions: edit each identified call site, appending `.catch(() => {})`, e.g. `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});`.
- Inputs: dist files from Step 4.
- Outputs: written edits (the write results confirmed the files were updated).
- Cautions: in this trajectory the follow-up dev-server run that would have proven the patch was rejected by the user, so the patch's effect on the crash was never observed — do not report it as a working fix until you run Step 7 yourself. A stale `.react-router` tree still exists until Step 6 runs.
- Preserve: the original `rm(...)` arguments; only add error swallowing.
- Next condition: edits written → Step 7 (verify by booting).

### Step 6: Mitigation B — wipe the whole cache tree in one pass
- Actions: ensure no dev-server/npm job is running (Stop-Job/Remove-Job, confirm nothing else runs the project), then in one Bash invocation delete the entire tree including `.react-router`: `rm -rf <files...> .react-router <files...> && echo done`.
- Inputs: project path, list of entries to remove (only what the task authorizes).
- Outputs: `done` on success (the `&&` guarantees `rm` exited 0).
- Cautions: deleting a subtree such as `.react-router/types/app/routes` while its `+types` child is locked fails with `Directory not empty`; a single top-level pass is what succeeded here. The exact reason the lock was gone by this point (stopped jobs vs. transient handles) was not established — do not claim a cause.
- Preserve: files not listed for deletion (in the trajectory: `DESIGN.MD`, `CLAUDE.MD` were kept).
- Next condition: `done` printed → Step 7.

### Step 7: Verify
- Actions: list `<project>` (Bash `ls <project>/` or equivalent) and check for `.react-router`; then run the Step 1 dev-server boot again.
- Inputs: project path.
- Outputs: listing without `.react-router`, and boot output.
- Cautions: a build or typecheck alone does not prove the dev server boots; the EPERM happens at dev startup.
- Preserve: all verification output for the report.
- Next condition: both checks clean → report success; if only the wipe is confirmed, report exactly that and mark the boot check as still to be run.

## Decision Rules
### When the drive reports no ACL support (takeown: `there is no support for ACLs.`)
Skip all ownership/ACL tooling (`takeown`, `icacls`) and mirror deletions (`robocopy /MIR`) for the rest of the session; they cannot work on this volume.

### When PowerShell `Get-ChildItem` errors or returns empty on the locked tree
Use `cmd /c "dir /a <path>"` for inspection, and cross-check with Bash `ls`/`find` before drawing conclusions about directory contents.

### When the crash happens at dev startup before the server binds
Treat typegen cleanup as the suspect: grep `typesDirectory` in `@react-router/dev/dist` and read the code around the match instead of guessing from the truncated stack.

### When deleting a nested subtree returns `Directory not empty`
Stop deleting per-subdirectory; remove the top-level `.react-router` tree in a single `rm -rf` pass after confirming no dev job is running.

### When a mitigation edit was written but no post-edit boot has run
Report the edit as applied and the fix as unverified; the trajectory's post-patch dev run was rejected, so no evidence of success exists yet.

### When an `rd /s /q` command prints errors but exits 0
Treat the exit code as meaningless here; verify with a directory listing instead.

## Invariants
- Do not modify application source, routes, or `react-router.config.ts`; this problem lives in the generated cache tree and the typegen cleanup code only.
- Do not delete anything beyond `.react-router` (and, if authorized, the three dist call sites); never wipe `node_modules` or project files as part of this skill.
- Do not repeat a deletion command that already failed with `Access is denied` / `EPERM` on this volume expecting a different result.
- Do not report the dev server as fixed without a boot output that lacks the `Error: EPERM ... scandir` line.
- Do not infer why a lock was released; when a later wipe succeeds, report only that the wipe succeeded.
- Do not treat `rd /s /q` exit code 0, an empty PowerShell listing, or a passing typecheck as proof that the locked directories are gone.
- Do not claim the `.catch(() => {})` patch works without running the dev server after applying it.

## Common Failures
### Failure: Nested wipe ends with `Directory not empty`
- Symptoms: `rm -rf <project>/.react-router/types/app/routes` returns `rm: cannot remove '<path>': Directory not empty`.
- Causes: the locked `+types` child directory sits under the subtree being removed; the underlying cause of the lock (handle from a prior typegen run vs. filesystem restriction) was not confirmed in the trajectory.
- Recovery: delete the whole `.react-router` tree in one Bash `rm -rf` pass after stopping all dev jobs; confirm with a listing.

### Failure: ACL/ownership tooling refuses to act
- Symptoms: `takeown` prints `ERROR: File ownership cannot be applied on insecure file systems;` followed by `there is no support for ACLs.`; `icacls` prints `Invalid parameter`.
- Causes: the volume does not support ACLs.
- Recovery: abandon OS-level reclaim; use the dist-inspection and single-pass wipe steps instead.

### Failure: `rd`, `rmdir`, and `robocopy /MIR` all deny deletion
- Symptoms: `cmd rd` prints `Access is denied.` for both `+types` paths (sometimes with `exit: 0`); `rmdir` exits `5`; robocopy prints `ERROR 5 (0x00000005) Deleting Extra Directory` and exits 2.
- Causes: the same locked directories on an ACL-less volume; robocopy finishing with a zero-ish exit code after printing errors is a trap.
- Recovery: do not retry; proceed to dist inspection and the single-pass wipe.

### Failure: Node-based deletion crashes the same way
- Symptoms: `node -e "fs.rmSync(...)"` fails with `Error: EPERM: operation not permitted, scandir` and a stack through `fixWinEPERMSync (node:internal/fs/rimraf:305:5)`.
- Causes: Node's rimraf hits the same unreadable directory.
- Recovery: delete from Bash in one top-level pass instead of via Node on this volume.

### Failure: Dev server still prints EPERM after patching dist
- Symptoms: boot output repeats `Error: EPERM: operation not permitted, scandir` for a `.react-router/types` path. Trajectory status: this state was never observed, because the post-patch dev run was rejected by the user.
- Causes: unknown — could be a missed `rm` call site, a stale tree that still must be wiped, or the patched bundle not being the code that loads.
- Recovery: re-run the reproduce step, re-grep the dist for any remaining unconditional `rm` on the types directory, confirm the `.react-router` tree was actually removed, and only then judge the patch.

## Verification
Run these checks and quote their raw output in the final report:
- Wipe check: `rm -rf <project>/.react-router && echo done` prints `done` (the `&&` only fires when `rm` exited 0).
- Absence check: a listing of `<project>` (Bash `ls <project>/`) shows no `.react-router` entry.
- Boot check: the Step 1 Start-Job dev run completes its wait with output that does not contain `EPERM` or `scandir`, and ideally shows typegen completing (the code logs `generated types` after the cleanup call).
- Patch check (only if `patch-dist` was used): grep `dist/vite.js` and `dist/cli/index.js` for `.catch(() => {})` at the `rm(typesDirectory(ctx), ...)` call sites.
- Explicit non-claims: a passing `tsc`/typecheck or a production build does not verify this fix; the failure occurs in the dev-server startup path. In this trajectory no post-fix dev boot was captured, so any success statement must come from a boot you ran yourself.

## Examples
### Example 1: Locked empty `+types` dirs on an ACL-less volume — wipe path
- Input: Windows project at `<project>` (parameterize: project path); `npm run dev` prints `Error: EPERM: operation not permitted, scandir` for `<project>\.react-router\types\app\+types` (parameterize: locked path).
- Procedure: Step 1 (capture), Step 2 (`cmd /c dir /a` shows `+types` with `0 File(s)`), Step 3 (skip ACL tools after `takeown` prints `there is no support for ACLs.`), Step 6 (single Bash `rm -rf ... .react-router ... && echo done`), Step 7.
- Expected result: output `done`, then a listing of `<project>` without `.react-router`, then a dev boot with no EPERM line.
- Parameterized values: project path, locked subpath, list of files to keep, dev command.

### Example 2: Patch-the-cleanup path (must be boot-verified)
- Input: same crash, `node_modules` writable, decision `patch-dist`.
- Procedure: Step 1, Step 4 (grep finds `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` in `dist/vite.js` `watch()` and twice in `dist/cli/index.js`), Step 5 (append `.catch(() => {})` to each), Step 7 boot check; optionally Step 6 afterwards to clear the stale tree.
- Expected result: boot output without `Error: EPERM: operation not permitted, scandir`. Note: in the source trajectory this boot was never run (the tool use was rejected), so the expected result is the acceptance criterion for your own run, not an observed outcome.

## Evidence
- problem — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 97, source_part_index 0, quote `Error: EPERM: operation not permitted, scandir` — supports: the dev server (`npm run dev`) crashes at startup on the typegen types directory; this is the entry symptom.
- problem — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 83, source_part_index 0, quote `Error: ENOTEMPTY: directory not empty, rmdir` — supports: an earlier dev run failed with ENOTEMPTY on the same `.react-router/types` tree, confirming cleanup (rmdir/rm) as the failing operation.
- problem — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 108, source_part_index 0, quote `at fixWinEPERMSync (node:internal/fs/rimraf:305:5)` — supports: Node's own rimraf path hits the lock, so `fs.rmSync`-based deletion fails on this volume.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 111, source_part_index 0, quote `0 File(s)` — supports: `cmd /c dir /a` can inspect the locked tree and shows the `+types` directory exists while being empty, so inspection via cmd works where PowerShell/Node failed.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 105, source_part_index 0, quote `ERROR: File ownership cannot be applied on insecure file systems;` and quote `there is no support for ACLs.` — supports: `takeown`/`icacls` cannot help on this volume; ACL tooling must be skipped.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 125, source_part_index 0, quote `ERROR 5 (0x00000005) Deleting Extra Directory` — supports: `robocopy /MIR` from an empty source also fails to delete the locked `+types` directories.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 155, source_part_index 0, quote `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` — supports: grep of the bundled dist located the unconditional typegen cleanup call that deletes the tree containing the locked directories.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 159, source_part_index 0, quote `async function watch(rootDirectory, { mode, logger, rsc }) {` — supports: the call site sits in the dev watcher function of `dist/vite.js`, i.e. it runs on dev-server startup, matching when the crash occurs.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 160, source_part_index 0, quote `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});` — supports: Mitigation A edit content — the patch was written to `dist/vite.js` (and later to both call sites in `dist/cli/index.js`).
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 189, source_part_index 0, quote `rm -rf Dockerfile README.md app node_modules package-lock.json package.json public react-router.config.ts tsconfig.json vite.config.ts .gitignore .dockerignore .react-router .claude && echo "done"` — supports: Mitigation B — a single-pass Bash wipe that includes the whole `.react-router` tree.
- verification — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 190, source_part_index 0, quote `done` — supports: `rm` exited 0 (the `&& echo` fired), so the previously undeletable `.react-router` tree, including the locked `+types` dirs, was fully removed at that point.
- verification — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 177, source_part_index 0, quote `The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file).` — supports: the post-patch dev-server run never executed, therefore Mitigation A's effect on the EPERM crash is unverified in this trajectory.

---
name: unblock-react-router-typegen-enotempty
description: Use when `react-router dev` or React Router typegen crashes with ENOTEMPTY/EPERM on rmdir/scandir under `.react-router/types` (typically locked `+types` folders) on Windows and the folders cannot be deleted. Helps the agent pinpoint the exact `fs.rm(typesDirectory(...))` cleanup call inside `@react-router/dev` and neutralize its failure instead of fighting the filesystem. Requires a React Router project with `node_modules/@react-router/dev` present and editable. Do not use when the error path is outside `.react-router/types`, when the directory deletes normally, or when no React Router typegen is involved.
triggers:
  - "ENOTEMPTY: directory not empty, rmdir"
  - "EPERM"
  - ".react-router/types"
  - "typesDirectory(ctx)"
---
# Unblock React Router Typegen ENOTEMPTY/EPERM on Windows

## Goal
Stop the React Router dev server / typegen from crashing on Windows with ENOTEMPTY or EPERM on `.react-router/types`, and produce a verified-starting dev run plus a minimal, re-applicable patch to the typegen cleanup call in `node_modules/@react-router/dev`.

## Scope
### In scope
- Confirming the failure signature: Node crash with `ENOTEMPTY` (`syscall: rmdir`) or `EPERM` (`syscall: scandir`) whose `path` is under `<project>/.react-router/types`, including the `+types` subfolders.
- Diagnosing that the folder cannot be removed at the OS level (inspection only; deletion attempts are known-failing on such volumes).
- Locating every `rm(typesDirectory(ctx), ...)` cleanup call in `node_modules/@react-router/dev/dist` and appending error suppression so the awaited cleanup cannot crash the process.
- Bounded re-run of the dev command as the verification step, and documenting that the patch must be re-applied after dependency reinstalls.

### Out of scope
- Fixing or reformatting the underlying Windows volume/filesystem (ACL support, locks, antivirus).
- Patching React Router upstream or contributing a PR.
- Projects where `.react-router/types` deletes normally, or error paths outside `.react-router/types`.
- Application source code, route code, or unrelated `node_modules` packages.
- Reinstalling, upgrading, or swapping dependencies.

## Inputs
- **Crash output**: string, from the tool result of the failing `npm run dev` / `react-router dev` / typegen run; required. Must contain an error `code` (`ENOTEMPTY` or `EPERM`) and a `path` under `<project>/.react-router/types`. Default: 无.
- **Project root**: directory path, from the user or current working directory; required. Must contain `package.json` and `node_modules/@react-router/dev`. Default: 无.
- **Shell in use**: PowerShell / Bash / cmd, from the environment; required, because PowerShell wraps Node stderr in `CategoryInfo` noise and cmd's `dir /a` was the only listing that worked on locked folders. Default: 无.
- **Edit permission on `node_modules`**: boolean, from the environment; required. Without it the patch cannot be applied and the skill must stop. Default: 无.
- **Dependency versions**: strings from `package.json` (evidence environment: `@react-router/dev` dist build containing `typesDirectory`, Node.js v22.20.0); optional, used only to keep grep expectations realistic. Default: 无.

## Outputs
### Artifacts
- Patched `node_modules/@react-router/dev/dist/vite.js` — the `watch()` cleanup line now ends with `.catch(() => {});`.
- Patched `node_modules/@react-router/dev/dist/cli/index.js` — both the `run()` and `watch()` cleanup lines patched the same way.
- A recorded note that the patch lives only in `node_modules` and must be re-applied after any `npm install`.

### Success criteria
- A re-run of the dev command completes its startup window with no `ENOTEMPTY` and no `EPERM` in the captured output, and typegen progresses (e.g. the `generated types` log line).
- Only `node_modules` files were touched; project source and config are unchanged.

### Failure criteria
- The same crash reappears with the same `path`, or a new `EPERM`/`ENOTEMPTY` on a different `.react-router/types` subpath.
- Grep finds no `rm(typesDirectory(` call to patch, or `node_modules` is read-only.
- The verification re-run never executes (rejected, cancelled, or unavailable) — report the state as "patched, unverified" instead of success.

## Preconditions
- The failure occurs on Windows and the crashing `path` is inside `<project>/.react-router/types` (including `+types` subfolders). If the path is elsewhere, stop and handle it as a different problem.
- `node_modules/@react-router/dev/dist/vite.js` and `dist/cli/index.js` exist and are readable; if not, stop — there is nothing to locate or patch.
- The agent may edit files under `node_modules`. If edits are forbidden (read-only install, managed environment), stop and report that no in-scope remedy exists.
- A way to run the project's dev command for a bounded window exists (the evidence used a PowerShell background job with a fixed sleep). If no command execution is available, stop before claiming any fix.
- Baseline crash text has been captured verbatim before changing anything, so before/after can be compared.

## Procedure
### Step 1: Confirm the failure signature
- Actions: read the full crash text; extract `code`, `syscall`, and `path`; verify `path` starts with the project's `.react-router/types`; note the Node version printed in the crash.
- Inputs: baseline crash output.
- Outputs: confirmed `ENOTEMPTY`/`rmdir` or `EPERM`/`scandir` signature under `.react-router/types`.
- Cautions: PowerShell prefixes Node stderr with `CategoryInfo`/`FullyQualifiedErrorId` noise — the real error is the `[Error: ...] { errno, code, syscall, path }` block.
- Preserve: the original crash text for the before/after comparison.
- Next: signature matches → Step 2; otherwise stop and treat as a different problem.

### Step 2: Establish that the folder is locked at the OS level (inspection only)
- Actions: list the folder with `cmd /c "dir /a <path>"` to see whether it is empty; note whether POSIX-style listing reports `Permission denied`.
- Inputs: the `path` from Step 1.
- Outputs: knowledge that the folder may show `0 File(s)` yet be undeletable — which routes the fix to Step 3 instead of deletion.
- Cautions: do NOT spend attempts on `rm -rf`, `Remove-Item -Recurse -Force`, `cmd rd /s /q`, `node fs.rmSync`, `takeown`/`icacls`, or `robocopy /MIR`; the evidence shows every one of them failing on this kind of volume (see Common Failures).
- Preserve: the directory itself — leave it in place; the patched cleanup tolerates it.
- Next: empty-but-locked → Step 3; deletable → delete normally and re-run dev instead (no patch needed).

### Step 3: Locate the cleanup call in `@react-router/dev`
- Actions: grep `typesDirectory` across `node_modules/@react-router/dev/dist`; confirm the awaited cleanup line `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` in `dist/vite.js` (`watch`) and in `dist/cli/index.js` (both `run` and `watch`).
- Inputs: `node_modules/@react-router/dev/dist`.
- Outputs: a file/line list of every occurrence (evidence: one in `vite.js`, two in `cli/index.js`).
- Cautions: `grep` for `EPERM|scandir` finds nothing — the crash comes from Node's `fs/promises.rm`, not from app code; search for `typesDirectory` instead.
- Preserve: do not edit surrounding logic.
- Next: at least one occurrence found → Step 4; none found → stop and report that the source layout differs.

### Step 4: Neutralize the cleanup failure at every occurrence
- Actions: append `.catch(() => {})` to the awaited `rm(...)` call so the cleanup promise can never reject; apply to all occurrences from Step 3.
- Inputs: occurrence list.
- Outputs: patched `dist/vite.js` and `dist/cli/index.js`.
- Cautions: `force: true` does not suppress these errors — do not rely on it; the only change is the appended catch.
- Preserve: every other byte of the files; keep the patch one-line-per-site so it is easy to re-apply.
- Next: Step 5.

### Step 5: Verify with a bounded dev-server run
- Actions: start the project's dev command in a background job, wait a fixed window (evidence: 8–12 seconds), capture output, then stop the job (PowerShell pattern: `Start-Job` → `Start-Sleep` → `Receive-Job` → `Stop-Job`/`Remove-Job`).
- Inputs: patched project.
- Outputs: captured startup log.
- Cautions: a rejected/cancelled tool call means verification did not happen; background-job output mixes npm wrapper noise with the real error — search for `ENOTEMPTY` and `EPERM` explicitly.
- Next: no `ENOTEMPTY`/`EPERM` and typegen progressed → Step 6; crash persists → Common Failures; run never executed → report "patched, unverified".

### Step 6: Record the re-apply requirement
- Actions: state that the patch exists only in `node_modules` and is wiped by any `npm install`; save the exact lines to patch so a future session can redo Step 4 quickly.
- Inputs: patched line list.
- Outputs: re-apply note.
- Cautions: a later full deletion of `.react-router` from Bash did succeed once in the evidence after the earlier failures; the reason the lock cleared is 轨迹未提供 — do not rely on it.
- Next: done.

## Decision Rules
### When the crash `path` is under `.react-router/types` with `syscall: rmdir` or `scandir`
Go straight to source-level handling (Step 3): the failing call is React Router's typegen cleanup, not application code.

### When every deletion tool fails (`Access is denied`, `Directory not empty`, `ERROR 5`)
Stop deleting. The folder can be empty per `cmd dir /a` and still be undeletable; deletion attempts on this class of volume were all failures in the evidence — route to Steps 3–4.

### When `takeown` reports no ACL support
Abandon ownership/ACL fixes entirely (`icacls`, grants, take ownership); the volume reports that ACLs are unsupported, so no permission change will succeed.

### When grep for `typesDirectory` returns multiple `rm(...)` occurrences
Patch all of them: the dev server path goes through `watch()` in `dist/vite.js`, and one-off/CLI typegen goes through `run()` and `watch()` in `dist/cli/index.js`.

### When the verification run is rejected, cancelled, or impossible
Report the outcome as "patched, unverified" and hand over the exact re-run command; never summarize it as fixed.

### When the error path is not under `.react-router/types`, or the directory deletes fine
This skill does not apply — no patch is warranted.

## Invariants
- Only `node_modules/@react-router/dev` files are modified; no project source, route, or config file is changed to work around the crash.
- Nothing outside the `.react-router` cache is deleted, and no deletion at all happens once the OS-level lock is confirmed.
- The patch is additive and minimal — appending `.catch(() => {})` to the cleanup call, changing nothing else — so it can be re-applied identically after a reinstall.
- No success is reported without an observed clean re-run of the dev command; a rejected or missing verification run leaves the state "patched, unverified".
- PowerShell's `NativeCommandError`/`CategoryInfo` wrapper text is treated as noise, not as the error under diagnosis; the `code`/`syscall`/`path` block is the source of truth.
- The locked directory itself is left in place for the patched cleanup to tolerate; it is not renamed, moved, or chown'ed.

## Common Failures
### Failure: recursive deletion of the types cache fails
- Symptoms: `rm: cannot remove '/<path>/.react-router/types/app/routes': Directory not empty`; `cmd rmdir` → `Access is denied`; `robocopy /MIR` → `ERROR 5 (0x00000005) Deleting Extra Directory ... Access is denied`; Node `fs.rmSync` → `EPERM ... scandir`.
- Causes: the `+types` subfolders are empty per `cmd dir /a` yet undeletable on this volume; the exact origin of the lock is 轨迹未提供 (not confirmed in the evidence).
- Recovery: stop deleting (Step 2) and patch the cleanup call (Steps 3–4); the patched cleanup tolerates a leftover folder.

### Failure: ownership/ACL tools refuse to run
- Symptoms: `ERROR: File ownership cannot be applied on insecure file systems;` and `there is no support for ACLs.`; `icacls` parameter errors.
- Causes: the volume does not support ACLs, so no grant/ownership change is possible.
- Recovery: drop `takeown`/`icacls` from the plan; proceed to the source patch.

### Failure: `EPERM scandir` on a second `+types` path after partial cleanup
- Symptoms: after some directories are removed, the next start crashes with `EPERM: operation not permitted, scandir '<...>/types/app/+types'`.
- Causes: more than one locked folder exists; each cleanup attempt surfaces them one at a time.
- Recovery: the same patch covers it — `fs.promises.rm` on the types directory is the single choke point; no per-folder work is needed.

### Failure: the patch silently disappears
- Symptoms: the original `ENOTEMPTY` crash returns after dependency work.
- Causes: `npm install` regenerated `node_modules`, discarding the edited dist files.
- Recovery: re-run Steps 3–4; keep the recorded line list so re-application is mechanical.

### Failure: reported as fixed without a run
- Symptoms: a summary claims the dev server works while the verification tool call was rejected/cancelled, so no post-patch output exists.
- Causes: verification skipped or interrupted.
- Recovery: re-run Step 5 before making any success claim; otherwise state "patched, unverified".

## Verification
Observable checks (do not mark as done unless each has tool output behind it):

- Baseline captured: the pre-fix crash text containing `ENOTEMPTY: directory not empty` or `EPERM: operation not permitted, scandir` with a `path` under `.react-router/types` is saved for comparison.
- Read-back of patched lines: re-read `dist/vite.js` around the `watch()` cleanup and `dist/cli/index.js` around `run()`/`watch()`; every `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true })` line now ends in `.catch(() => {});`.
- Coverage: grep for `rm(typesDirectory` returns only `.catch(() => {});`-terminated lines (count matches the pre-patch occurrence list).
- Bounded dev run: background start + fixed wait + captured output contains neither `ENOTEMPTY` nor `EPERM`, and shows typegen progressing (e.g. `generated types`).
- Blast radius: `git status`/file listing shows changes only under `node_modules/@react-router/dev` — no project source or config edits.
- Re-apply note written, stating the patch is lost on the next `npm install`.

Explicitly NOT established by the source trace: the post-patch dev run was rejected before executing, so in that session only the diagnosis and the edits were verified. Any claim beyond "patched" requires a fresh run of the check above.

## Examples
### Example 1: dev server dies on startup with ENOTEMPTY
- Input: Windows project; `npm run dev` output ends with `Error: ENOTEMPTY: directory not empty, rmdir '<root>\.react-router\types\app\routes'` (Node.js v22.20.0).
- Procedure: Step 1 (signature under `.react-router/types`) → Step 2 (`cmd dir /a` shows the folder empty; deletion ruled out) → Step 3 (grep `typesDirectory` finds the cleanup in `dist/vite.js` watch and `dist/cli/index.js` run/watch) → Step 4 (append `.catch(() => {})` at all three sites) → Step 5 (bounded background dev run) → Step 6 (re-apply note).
- Expected result: the bounded run shows no `ENOTEMPTY`/`EPERM` and typegen proceeds; only the three `node_modules` lines differ from baseline. In the source trace this final run was rejected by the user, so that session's honest status is "patched, unverified".
- Parameterized values: project root (`<root>`), package dist layout (`node_modules/@react-router/dev/dist`), Node version (v22.20.0 in evidence), sleep window (8–12 s).

### Example 2: deletion already ruled out, go straight to the patch
- Input: `cmd /c "dir /a ...+types"` reports `0 File(s)` while `ls` returns `Permission denied` and `robocopy /MIR` exits with `ERROR 5 (0x00000005) Deleting Extra Directory ... Access is denied`.
- Procedure: skip repeated deletion attempts; Step 3 → Step 4 → Step 5.
- Expected result: cleanup call neutralized; the locked folder remains in place and the next start does not crash on it.
- Parameterized values: locked subpaths (`app/+types`, `app/routes/+types`), the exact dist files present in the installed `@react-router/dev` build.

## Evidence
- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 83, source_part_index: 0
  quote: `ENOTEMPTY: directory not empty, rmdir`
  supports: problem — the crash signature on `npm run dev` (`react-router dev`) with `syscall: rmdir` and `path: D:\IceBerg\.react-router\types\app\routes` that triggers this skill.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 97, source_part_index: 0
  quote: `EPERM: operation not permitted, scandir`
  supports: problem — the follow-on symptom after partial deletion attempts, on a different `+types` path, confirming multiple locked folders and the same root call.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 89, source_part_index: 0
  quote: `rm: cannot remove '/d/IceBerg/.react-router/types/app/routes': Directory not empty`
  supports: problem/diagnosis — direct deletion of the crash path fails, which is why the skill routes to a source patch instead of deletion.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 105, source_part_index: 0
  quote: `there is no support for ACLs.`
  supports: problem/condition — `takeown`/`icacls` cannot work on this volume (same result block also shows `ERROR: File ownership cannot be applied on insecure file systems;`), so ownership fixes are excluded.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 125, source_part_index: 0
  quote: `ERROR 5 (0x00000005) Deleting Extra Directory`
  supports: problem/diagnosis — `robocopy /MIR` mirror-wipe also fails with Access denied on the `+types` folders, closing the last deletion-based option.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 159, source_part_index: 0
  quote: `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`
  supports: action — the located root call at `dist/vite.js` line 1344 inside `async function watch(...)`, the line the patch targets.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 167, source_part_index: 0
  quote: `1339:  await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`
  supports: action — the same cleanup exists twice more in `dist/cli/index.js` (lines 1339 and 1348), so all occurrences must be patched.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 160, source_part_index: 0
  quote: `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});`
  supports: action — the applied patch shape (`.catch(() => {})` appended) written to `dist/vite.js`; equivalent edits were written to `dist/cli/index.js` at source_index 170 and 173.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 164, source_part_index: 0
  quote: `The file d:\IceBerg\node_modules\@react-router\dev\dist\vite.js has been updated successfully.`
  supports: action — tool confirmation that the vite.js patch was actually written (not merely proposed).

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 177, source_part_index: 0
  quote: `The tool use was rejected`
  supports: verification (negative) — the post-patch dev-server re-run was rejected before executing, so the fix was never verified in this trace; the skill requires reporting "patched, unverified" until a clean run is observed.

- file_id: `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index: 190, source_part_index: 0
  quote: `done`
  supports: verification (observation) — a later Bash `rm -rf ... .react-router ...` reported success after all earlier deletion failures; the reason the lock had cleared by then is 轨迹未提供, so it is documented only as an observation, not a remedy.

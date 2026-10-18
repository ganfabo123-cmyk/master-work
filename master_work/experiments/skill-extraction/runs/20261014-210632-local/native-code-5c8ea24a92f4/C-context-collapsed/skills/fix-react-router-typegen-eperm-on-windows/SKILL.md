---
name: fix-react-router-typegen-eperm-on-windows
description: Use when `npm run dev` (react-router dev) crashes with EPERM/ENOTEMPTY scandir on locked `+types` directories under `.react-router/types` on Windows. Helps the agent locate the exact `fs.rm` call sites in `@react-router/dev` and patch them to tolerate locked directories, after deletion-based recovery has failed on a filesystem without ACL support. Do not use when the project lives on NTFS and a simple delete/reboot works, or when the failure is a different EPERM cause (e.g. file handles held by another process on an ordinary volume).
---
# Fix React Router Typegen EPERM Crash on Windows Non-ACL Volumes

## Goal
Diagnose why a React Router v7 (framework mode) dev server crashes at startup with `EPERM: operation not permitted, scandir` on the typegen cache directory `.react-router/types/**/+types` on a Windows volume that has no ACL support, and produce either a booting dev server (via a targeted patch of the `@react-router/dev` typegen cleanup calls) or an honest report that deletion is impossible and the workaround is unverified.

## Scope
### In scope
- React Router v7 framework mode (`@react-router/dev`, scaffolded with `create-react-router@7.15.1`) on Windows, where `npm run dev` / typegen crashes with `EPERM` (errno -4048) or `ENOTEMPTY` (errno -4051) on `.react-router/types/app/+types` and `.react-router/types/app/routes/+types`.
- Escalating deletion attempts of `.react-router/types` and recognizing when they are provably futile on a filesystem without ACL support (`takeown`/`icacls` fail).
- Locating the three `fs.rm` call sites inside `node_modules/@react-router/dev/dist/vite.js` and `dist/cli/index.js` that wipe the types directory on every start, and patching them with `.catch(() => {})`.
- Documenting the environment constraints (Windows, Node v22, non-ACL volume) that make this failure reproducible.

### Out of scope
- Upstream fixes to React Router, or reporting the bug to the maintainers.
- EPERM causes unrelated to the typegen cache (AV scanners, other processes holding handles on NTFS, OneDrive/sync locks).
- Linux/macOS EPERM semantics.
- Any alternative framework migration (in the source session the user abandoned Remix for SolidJS; that is a product decision, not a fix).

## Inputs
- **Dev-server error output** — type: string — source: output of `npm run dev` (`react-router dev`) — required: yes — constraints: must contain `EPERM: operation not permitted, scandir` or `ENOTEMPTY: directory not empty, rmdir` plus a path under `.react-router/types` — default: 无.
- **Project root path** — type: string (e.g. `d:\IceBerg`) — source: working directory — required: yes — constraints: the volume's filesystem type matters; on the observed volume ACL operations are unsupported — default: 无.
- **Node.js and npm versions** — type: string — source: `node --version; npm --version` — required: no — constraints: observed v22.20.0 / npm 11.8.0 — default: 轨迹未提供 beyond observed values.
- **`@react-router/dev` installed dist files** — type: files — source: `node_modules/@react-router/dev/dist/vite.js` and `node_modules/@react-router/dev/dist/cli/index.js` — required: yes — constraints: layout observed under create-react-router@7.15.1; bundled (minified-ish) dist with source-line comments — default: 无.
- **Permission to edit `node_modules`** — type: authorization — source: user — required: yes — constraints: edits are wiped by any reinstall — default: 无.

## Outputs
### Artifacts
- Patched `node_modules/@react-router/dev/dist/vite.js` — the `watch()` typegen cleanup line gains `.catch(() => {})`.
- Patched `node_modules/@react-router/dev/dist/cli/index.js` — both the `run()` and `watch()` cleanup lines gain `.catch(() => {})`.
- A short diagnosis report: filesystem constraint observed, deletion methods ruled out, patch applied, verification status.

### Success criteria
- `npm run dev` starts without the EPERM/ENOTEMPTY crash, typegen logs its completion (`generated types`), and the dev server stays up.

### Failure criteria
- Dev server still crashes after patching all three call sites, or verification cannot be executed (e.g. the verification run is rejected/interrupted). In that case report the fix as applied-but-unverified and recommend moving the project to an NTFS volume or rebooting to release directory locks.

## Preconditions
- The project is a React Router v7 framework-mode app whose dev server runs typegen into `<root>/.react-router/types` (confirmed by `typesDirectory` returning `Path.join(ctx.rootDirectory, ".react-router/types")`).
- The failing directory is a `+types` directory under `.react-router/types` and is at minimum locked; `cmd /c "dir /a ..."` can show it is empty, which means typegen only needs to write into it, not replace it.
- The volume does not support ACLs: `takeown` must be confirmed to fail with `ERROR: File ownership cannot be applied on insecure file systems;` / `there is no support for ACLs`. If ACLs are supported, prefer ordinary deletion/reboot instead of this skill.
- The agent has permission to edit files under `node_modules`, and the user understands the patch does not survive `npm install`.
- Do not proceed if the EPERM path is outside `.react-router/types` — that is a different failure with different causes.

## Procedure
### Step 1: Reproduce and characterize the crash
Actions: run `npm run dev` in the project root; capture the full error. Confirm it is `[Error: EPERM: operation not permitted, scandir` with `errno: -4048`, `code: 'EPERM'`, `syscall: 'scandir'` pointing into `.react-router/types/.../+types`, or the precursor `[Error: ENOTEMPTY: directory not empty, rmdir` on the same tree. Note whether the locked dir is empty via `cmd /c "dir /a <path>"`.
Inputs: project root. Outputs: error text, locked path(s). Cautions: on the observed machine there were TWO locked dirs (`app/+types` and `app/routes/+types`) — fixating on one hides the other. Preserve: exact error text for later comparison. Next: proceed to Step 2.

### Step 2: Attempt deletion once, with escalating methods — then stop
Actions: try, in order: Bash `rm -rf` on the types dir; PowerShell `Remove-Item -Recurse -Force`; `cmd /c "rd /s /q <root>\.react-router"`; `takeown /f <root>\.react-router /r /d y` + `icacls` grant + `rd`; `node -e "require('fs').rmSync('<path>', {recursive:true, force:true})"`; `robocopy <empty temp dir> <root>\.react-router /MIR`.
Inputs: locked paths. Outputs: per-method failure signatures. Cautions: expect all of them to fail on a non-ACL volume (`rm: cannot remove ... Directory not empty`, `Access is denied.`, `ERROR 5 (0x00000005) Deleting Extra Directory`, EPERM from rimraf's `fixWinEPERMSync`). Do not loop more attempts after `takeown`/`icacls` prove ACLs unsupported — deletion is impossible while the OS holds the lock. Preserve: the failing output as evidence for the report. Next: proceed to Step 3.

### Step 3: Locate the code that deletes the types directory on startup
Actions: in `node_modules/@react-router/dev/dist/vite.js`, grep for `typesDirectory` and read around the `watch(` function; you are looking for `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` (observed at line ~1344). Then grep the same pattern in `node_modules/@react-router/dev/dist/cli/index.js` — it appears twice (in `run()` and `watch()`, observed at lines ~1339 and ~1348).
Inputs: node_modules dist files. Outputs: three call sites. Cautions: grepping for `EPERM|scandir|rmdir|unlinkSync` finds nothing — the call is `fs/promises.rm`, so grep for `typesDirectory` or `rmSync|rmdir` instead. Preserve: the surrounding function names (`run`, `watch`) so all sites get patched. Next: proceed to Step 4.

### Step 4: Patch all three call sites to tolerate failure
Actions: edit each site so the line ends with `.catch(() => {})`, e.g. `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});`. Patch `vite.js` once and `cli/index.js` twice.
Inputs: the three identified lines. Outputs: three successful file edits. Cautions: typegen regenerates the `.d.ts` files on every run, so swallowing the cleanup error is safe when the locked dirs are empty; stale files may remain if the locked dir is non-empty. Preserve: everything else in these vendor files. Next: proceed to Step 5.

### Step 5: Verify by restarting the dev server
Actions: run `npm run dev` again; watch for typegen's success log (`generated types`) and absence of the EPERM crash; then run the project's typecheck/build to confirm the app still compiles. Re-apply the patch after any `npm install`.
Inputs: patched node_modules. Outputs: boot log or crash log. Cautions: if the verification command is rejected or interrupted before it runs, the fix is NOT verified — say so explicitly. Next: report result; if still crashing, go to Common Failures.

## Decision Rules
### When `takeown`/`icacls` report no ACL support on the volume
Stop all deletion-based recovery (robocopy /MIR, rd /s /q, rmSync all fail with Access denied / ERROR 5 on such volumes). Proceed directly to patching the rm call sites, or recommend relocating the project to an NTFS volume.

### When the locked `+types` directory is empty (`dir /a` shows 0 files)
Patching the `fs.rm` call with `.catch(() => {})` is sufficient: typegen writes fresh files into the existing directory on each run.

### When two different `+types` directories are locked
Patch the shared cleanup code rather than the directories; both crash sites go through the same `typesDirectory(ctx)` rm call, so a single missed call site (e.g. patching `vite.js` but not `cli/index.js`) leaves the crash in one execution path.

### When the verification run is rejected, interrupted, or cannot be executed
Report the fix as "patch applied, runtime effect unverified" — do not claim the dev server works. Preserve the exact verification command so it can be run later.

### When the user will not accept a `node_modules` patch
Fall back to: moving the project to an NTFS volume, or a reboot to release the directory locks, then deleting `.react-router/types` before the next start.

## Invariants
- Never claim the dev server boots without a post-patch startup log showing typegen completing and no EPERM crash.
- Do not modify project source code (routes, config) to work around this crash — the fault is in the vendor cleanup call, not the app.
- Do not loop filesystem deletion attempts indefinitely; after `takeown`/`icacls` fail with no-ACL errors, further deletion attempts are provably futile.
- Do not report `takeown`/`icacls`/robocopy failures as success because the command returned exit code 0 — on the observed machine `cmd /c "rd /s /q ..."` printed `Access is denied.` for each locked dir while echoing `exit: 0`.
- Keep the patch minimal (only the `.catch(() => {})` suffix); do not rewrite vendor files.
- Always state that the patch is lost on `npm install` and name the pinned generator version (create-react-router@7.15.1 on Node v22.20.0 in the observed case).

## Common Failures
### Failure: Endless deletion loop on a locked directory
Symptoms: repeated `Access is denied.`, `rm: cannot remove ... Directory not empty`, robocopy `ERROR 5 (0x00000005) Deleting Extra Directory`, node rimraf EPERM from `fixWinEPERMSync`. Causes: the volume has no ACL support (takeown: `ERROR: File ownership cannot be applied on insecure file systems;`) and the OS holds the `+types` directory lock; the `+` prefix combined with this filesystem makes the dir undeletable while locked. Recovery: stop deleting; patch the `fs.rm` call sites (Step 4) or relocate the project / reboot.

### Failure: Patch applied but crash persists
Symptoms: same EPERM after editing `vite.js`. Causes: a missed call site — `dist/cli/index.js` contains the same rm line in both `run()` and `watch()`; or the user ran the `typegen` CLI path rather than the Vite dev path. Recovery: grep `typesDirectory(ctx)` in both dist files and patch every `rm(...)` occurrence.

### Failure: Fix silently lost
Symptoms: crash returns after some later session. Cause: `npm install` / reinstall replaced `node_modules`, discarding the patch. Recovery: re-apply the patch, or move the project to an NTFS volume so `.react-router/types` can simply be deleted.

### Failure: Reported "fixed" without ever running the dev server
Symptoms: the verification command was rejected or interrupted (in the source session the post-patch restart was rejected by the user) and the agent still summarized the issue as resolved. Cause: claiming success from a completed edit instead of a completed run. Recovery: state explicitly that the patch is applied but runtime-unverified, and provide the exact command to verify later.

## Verification
Run these after patching; each is an observable check, not an assumption:

1. `npm run dev` in the project root: the process must get past typegen — look for the green `generated types` log emitted by the patched `watch()` path — and no `[Error: EPERM: operation not permitted, scandir` may appear.
2. `npm run typecheck` (or the project's `react-router typegen && tsc` script) must exit 0, proving regenerated types are usable.
3. Re-run `npm run dev` a second time: the second run is the one that previously crashed with EPERM (the first run is what creates the locked dirs), so a clean second start is the decisive check.
4. Confirm the patch still exists: grep `catch(() => {})` in `node_modules/@react-router/dev/dist/vite.js` and `dist/cli/index.js` after any dependency operation.
5. If any of these cannot be executed (e.g. the run was rejected), record the fix as unverified rather than passing it.

## Examples
### Example 1: Diagnose a locked `+types` cache and patch typegen
Input: Windows project at `d:\IceBerg`, scaffolded with `create-react-router@7.15.1`, Node v22.20.0; `npm run dev` prints `[Error: EPERM: operation not permitted, scandir '...\.react-router\types\app\+types']` with `errno: -4048`.
Procedure: (1) confirm a second locked dir exists at `.../app/routes/+types`; (2) try `rm -rf`, `Remove-Item -Recurse -Force`, `cmd rd /s /q`, `takeown`+`icacls`, `node fs.rmSync`, `robocopy /MIR` — all fail; takeown reports `ERROR: File ownership cannot be applied on insecure file systems;`; (3) grep `typesDirectory` in `node_modules/@react-router/dev/dist/vite.js` and find `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` in `watch()`; find the same line twice in `dist/cli/index.js`; (4) append `.catch(() => {})` at all three sites; (5) restart `npm run dev` and confirm typegen completes.
Expected result: the dev server boots; typegen regenerates files into the existing locked directories without crashing. If step 5 cannot be run, report "patch applied, unverified."
Parameterized values: project root `d:\IceBerg`; generator `create-react-router@7.15.1`; Node `v22.20.0`; locked dirs `app/+types` and `app/routes/+types` under `.react-router/types`.

## Evidence
All quotes below are from `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01` (full-content slice; all cited events have visible tool-result bodies in this slice).

- **problem** — source_index 97, source_part_index 0 (tool_result of `npm run dev`): quote `[Error: EPERM: operation not permitted, scandir` with `errno: -4048`, `syscall: 'scandir'`, `Node.js v22.20.0`; a second crash site at source_index 122 (tool_result): same quote; precursor at source_index 83: `[Error: ENOTEMPTY: directory not empty, rmdir`. supports: the dev-server startup crash this skill addresses, on two distinct `+types` directories.
- **problem (futility of deletion)** — source_index 89 (tool_result): `rm: cannot remove '/d/IceBerg/.react-router/types/app/routes': Directory not empty`; source_index 93: `ls: cannot open directory '/d/IceBerg/.react-router/types/app/routes/+types/': Permission denied`; source_index 105: `ERROR: File ownership cannot be applied on insecure file systems;` and `there is no support for ACLs.`; source_index 108: `Error: EPERM: operation not permitted, scandir` and `at fixWinEPERMSync (node:internal/fs/rimraf:305:5)`; source_index 125: `ERROR 5 (0x00000005) Deleting Extra Directory` / `Access is denied.`. supports: six escalating deletion methods all fail on this volume, justifying the patch-instead-of-delete decision.
- **action (root cause located)** — source_index 150 (tool_result reading vite.js): `return Path3.join(ctx.rootDirectory, ".react-router/types");`; source_index 155 (tool_result, grep): `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`; source_index 167 (tool_result, grep of cli/index.js): same line, two occurrences. supports: the typegen cleanup call wipes the types dir on every start and is the EPERM source.
- **action (patch)** — source_index 160 (tool_call:Edit on vite.js): new_string contains `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});`; source_index 170 and 173 (Edits on cli/index.js) apply the same suffix; tool results 164, 172, 174 each contain `has been updated successfully`. supports: the workaround was actually written to all three call sites.
- **action (environment pinned)** — source_index 45 (tool_result): `The following package was not found and will be installed: create-react-router@7.15.1`. supports: version context that scopes the dist-file line numbers.
- **verification (gap — the fix is NOT runtime-verified)** — source_index 177 (tool_result of the post-patch `npm run dev` restart): `The user doesn't want to proceed with this tool use. The tool use was rejected`; source_index 159 (tool_result showing the patched `watch()` context): `logger?.info((0, import_picocolors2.green)("generated types")` defines the success log to look for on a future run. supports: in the source session the dev-server restart was never executed, so the skill mandates reporting the fix as applied-but-unverified until a clean second start is observed.

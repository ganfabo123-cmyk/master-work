---
name: fix-react-router-typegen-eperm-windows
description: Use when `react-router dev` on Windows crashes at startup with EPERM errno -4048 on scandir of `.react-router/types/**/+types` directories. Helps the agent confirm the OS-level lock, rule out all deletion-based fixes cheaply, locate the exact fs.rm call in the installed @react-router/dev bundle, and apply a guarded-rm patch. Requires Windows, Node.js, an installed @react-router/dev package, and shell access. Do not use when the EPERM path is not a React Router typegen `+types` directory, when the drive supports ACLs and normal deletion works, or when modifying node_modules is forbidden.
---
# Diagnose and Work Around React Router Typegen EPERM scandir on Windows

## Goal
Unblock a React Router (react-router dev) project on Windows that crashes at startup with `EPERM: operation not permitted, scandir '<project>\.react-router\types\...\+types'` (errno -4048) caused by empty `+types` directories that the OS refuses to list or delete, by producing a working dev-server startup (or an explicit, evidence-backed stop report when the environment forbids the only remaining fix).

## Scope
### In scope
- Windows machines where `npm run dev` / `react-router dev` dies at boot with `EPERM` scandir on `.react-router\types\app\+types` or `.react-router\types\app\routes\+types`.
- Diagnosing whether the `+types` directories are OS-locked and empty, and whether the volume supports ACLs.
- Ruling out (cheaply, in order) deletion-based fixes: `rd /s /q`, `rmdir`, Node `fs.rmSync`, `robocopy /MIR`, `takeown`/`icacls`.
- Locating the exact `fs.promises.rm(typesDirectory(ctx), { recursive: true, force: true })` call sites inside the installed `@react-router/dev` dist bundle.
- Patching those call sites with `.catch(() => {})` so the typegen cleanup failure no longer crashes the dev server.

### Out of scope
- Linux/macOS permission problems, or EPERM on paths unrelated to React Router typegen.
- Fixing the underlying filesystem (repairing/convertng the volume, moving the project, reformatting the drive).
- Permanent or supported configuration fixes: the trace showed no `typegen: false` / custom type-dir option exists in the installed version (grep for `typegen` config returned no matches), and `react-router.config.ts` only exposes `ssr`.
- Making the patch survive `npm install` / `node_modules` reinstall.
- React Router versions other than the one installed in the traced project; line numbers and function names must be re-located per install.

## Inputs
- **Crash output of `react-router dev`** — string, from the failing `npm run dev` run; required. Must contain `EPERM`, `scandir`, and a path under `<project>\.react-router\types`. Default: none.
- **Project root directory** — path (e.g. `d:\IceBerg`), from the shell working directory / user; required. Used to build the cache path `<root>\.react-router`. Default: current working directory of the shell.
- **Installed package location** — path, from `<project>\node_modules\@react-router\dev\dist`; required for the patch step. Contains at least `vite.js` and `cli/index.js`. Default: `<project>\node_modules\@react-router\dev\dist`.
- **Shell** — PowerShell on Windows with `cmd` available; required. The traced environment used PowerShell jobs (`Start-Job`/`Receive-Job`) to run and time-box the dev server. Default: PowerShell.
- **Node.js runtime** — version present on PATH; in the trace `Node.js v22.20.0` produced the `node:internal/fs/rimraf` stack. Required for confirming the failure originates in Node's rimraf, not in shell tooling. Default: whatever `node -v` reports.
- **Permission to edit `node_modules`** — boolean; required for the patch step. If false or the environment rejects the edit/run, the skill stops with a report. Default: assumed granted only after user confirmation.
- **Time-boxed dev-server runner** — command wrapper, e.g. `Start-Job { npm run dev }; Start-Sleep 12; Receive-Job; Stop-Job`; optional but used for verification. Default: the PowerShell job pattern above.

## Outputs
### Artifacts
- Patched `node_modules/@react-router/dev/dist/vite.js` — the `watch()` typegen cleanup call changed from `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` to the same call with `.catch(() => {})` appended.
- Patched `node_modules/@react-router/dev/dist/cli/index.js` — same change in both the `run()` and `watch()` typegen cleanup calls (two occurrences).
- Diagnosis note (chat text): filesystem type, which deletion methods were tried and failed, and the exact crash site located in the dist bundle.

### Success criteria
- `react-router dev` starts without the uncaught `EPERM: operation not permitted, scandir ...+types` exception and reaches the point of serving/typegen logging.

### Failure criteria
- Any of the three `rm(typesDirectory(ctx), ...)` call sites remains unpatched in either dist file.
- The dev server still dies with the same `EPERM` scandir error after patching.
- The edits cannot be applied (no write access to `node_modules`, or the user/environment rejects the edit or the verification run).

## Preconditions
- Windows host with a shell that can run both PowerShell and `cmd` built-ins (`rd`, `rmdir`, `dir`).
- The failing command is `react-router dev` (typically via `npm run dev`) and the error text contains `EPERM`, `errno: -4048`, `syscall: 'scandir'`, and a path ending in `+types` under `.react-router\types`.
- `node_modules/@react-router/dev/dist/` exists and contains `vite.js` and `cli/index.js` (the bundled dist layout; do not assume a source layout).
- Write permission to those dist files. Editing `node_modules` is a local, non-durable workaround — it is wiped by any reinstall; confirm with the user that this trade-off is acceptable before patching.
- If the environment forbids editing `node_modules` or rejects the verification run, stop and report: no supported config option was found in the trace to relocate or disable typegen, so there is no alternative fix to offer.
- Do not assume administrator rights help: in the trace the volume reported "no support for ACLs", making `takeown`/`icacls` useless regardless of privileges.

## Procedure
### Step 1: Confirm the symptom and capture the failing path
- Actions: run the failing command (`npm run dev` → `react-router dev`) time-boxed (e.g. PowerShell `Start-Job`, sleep ~10–12s, `Receive-Job`, `Stop-Job`) and capture stderr. Confirm the error matches `EPERM: operation not permitted, scandir '<root>\.react-router\types\...\+types'` with `errno: -4048`, `code: 'EPERM'`.
- Inputs: project root, shell.
- Outputs: crash text; the exact locked path(s) (the trace showed two: `.react-router\types\app\+types` and `.react-router\types\app\routes\+types`).
- Cautions: PowerShell wraps Node stderr as `NativeCommandError`; read through the wrapper to the `[Error: EPERM ...]` block.
- Next: proceed to Step 2. If the error is not a `+types` scandir EPERM, stop — this skill does not apply.

### Step 2: Inspect the locked directories without deleting
- Actions: list the tree with `cmd /c "dir /a <path>"` (works even when recursive tools fail). Verify the `+types` dirs are empty (`0 File(s)`).
- Inputs: locked paths from Step 1.
- Outputs: confirmation that the targets are empty `<DIR>` entries.
- Cautions: recursive listing from other tools may fail (`ls` returned `Permission denied`; PowerShell `Get-ChildItem -Recurse -Force` returned exit 1) — that itself is evidence of the lock.
- Next: proceed to Step 3.

### Step 3: Establish that deletion and ownership fixes are impossible on this volume
- Actions: try, in order, each time recording the exact failure: `cmd /c "rd /s /q <root>\.react-router"`, `cmd /c "rmdir \"<locked dir>\""`, `node -e "fs.rmSync(root, {recursive:true, force:true})"`, `robocopy <empty tmp dir> <root>\.react-router /MIR`, and `takeown /f <root>\.react-router /r /d y` + `icacls`.
- Inputs: project root, locked paths.
- Outputs: failure record for each method. In the trace all returned `Access is denied` / exit code 5 / `ERROR 5 (0x00000005)`, and `takeown` reported `File ownership cannot be applied on insecure file systems; there is no support for ACLs`.
- Cautions: do not spend more than one attempt per method; these are independent mechanisms, and universal failure indicates an OS/filesystem-level lock, not a tooling problem. `robocopy /MIR` exit codes ≥1 are not automatically success — check for `ERROR 5`.
- Next: proceed to Step 4. Do not keep trying deletion variants.

### Step 4: Locate the crash site in the installed @react-router/dev dist
- Actions: grep the bundled files for the typegen cleanup call: `Grep pattern "rm.*typesDirectory|typesDirectory.*rm" path "<root>\node_modules\@react-router\dev\dist"`; then Read ~20 lines around each hit to confirm the surrounding function.
- Inputs: dist directory (`vite.js`, `cli/index.js`).
- Outputs: the call sites. In the trace: `vite.js` `watch()` (one call, ~line 1344) and `cli/index.js` `run()` and `watch()` (two calls, ~lines 1339 and 1348), all of the form `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`, where `typesDirectory(ctx)` joins the project root with `.react-router/types`.
- Cautions: line numbers shift between package versions — locate by pattern, not by number. The crash stack (`node:internal/fs/rimraf`, `readdirSync`) comes from inside `fs.promises.rm`, so the grep should target `rm`/`typesDirectory`, not `scandir`.
- Next: proceed to Step 5 with every located call site.

### Step 5: Patch every call site to tolerate cleanup failure
- Actions: for each located call, Edit appending `.catch(() => {})`: `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});`. In the trace this was applied to `vite.js` once and `cli/index.js` twice.
- Inputs: the dist files from Step 4.
- Outputs: three patched call sites (one in `vite.js`, two in `cli/index.js`).
- Cautions: patch all occurrences, not just the first — `cli/index.js` has two identical lines in different functions (`run` with `watch: false`, `watch` with `watch: true`); an Edit with `replace_all: false` must be repeated per occurrence with unique surrounding context (the `createContext2({... watch: false })` vs `watch: true` lines disambiguate).
- Preserve: change only the cleanup call; leave the typegen `write()` that follows untouched so types are still regenerated over the stale locked dirs.
- Next: proceed to Step 6.

### Step 6: Verify by starting the dev server again
- Actions: rerun the time-boxed `npm run dev` from Step 1 and inspect output.
- Inputs: patched project.
- Outputs: pass = no `EPERM` scandir crash and the dev server proceeds to normal startup/typegen logging; fail = same crash returns.
- Caution: this step must actually run; a successful file Edit does not prove the fix. In the traced session this verification was interrupted by the user and never executed, so the patch's runtime effect is unconfirmed in that trace.
- Next: on pass, report the caveat that the patch is lost on `npm reinstall` of `@react-router/dev`; on fail, stop and report the residual error verbatim.

## Decision Rules
### When the error is `EPERM ... scandir` on a `.react-router\types\...\+types` path
Treat it as React Router typegen cleanup failing on an OS-locked directory; go straight to the diagnosis procedure (Steps 1–4) instead of debugging the app code, routing config, or `react-router.config.ts`.

### When `takeown` reports the filesystem is insecure / has no ACL support
Abandon all ownership- and ACL-based approaches (`takeown`, `icacls`) permanently for this volume; they cannot work regardless of elevation. Proceed directly to the dist-patch track (Steps 4–6).

### When at least two independent deletion mechanisms fail with `Access is denied` on the same path
Conclude the directory is OS-locked and undeletable from userland; stop trying deletion variants (`rd`, `rmdir`, `rmSync`, `robocopy /MIR` were all tried once in the trace and all failed). Move to Step 4.

### When the locked `+types` directories are confirmed empty (`0 File(s)`)
The stale content is harmless — typegen's `write()` regenerates files into the existing tree. Do not require deletion for success; only the cleanup `rm` call must be made non-fatal.

### When grep of the dist bundle finds no `rm(typesDirectory(...))` call
The installed version differs from the traced one; re-locate by related symbols (`typesDirectory`, `.react-router/types`, `typegen`) before concluding the patch is impossible. Do not invent an unsupported config option — the trace's grep for a `typegen` config toggle returned no matches.

### When the environment rejects editing `node_modules` or rejects the verification run
Stop and report: the only fix evidenced by the trace is the dist patch; no config-based alternative was found. State that moving the project to an NTFS/ACL-capable location or upgrading React Router are untested suggestions, not verified fixes.

## Invariants
- Never claim the EPERM crash is fixed without rerunning the dev server after patching; a successful Edit tool result only proves the file changed, not that the crash is gone.
- Patch only the typegen cleanup `rm` calls; do not disable typegen `write()` — generated types are required by the project's tsconfig (`rootDirs` includes `./.react-router/types`).
- Touch only the two dist files inside `node_modules/@react-router/dev/dist` (`vite.js`, `cli/index.js`); do not modify app source, `react-router.config.ts`, or `tsconfig.json` for this problem.
- Apply `.catch(() => {})` to every located occurrence, not a subset; an unpatched `run()`/`watch()` variant will crash when that code path is used.
- Do not report `robocopy` or `rd` exit code 0 as deletion success when the `+types` paths still print `Access is denied` / `ERROR 5`; verify by listing the directory afterwards.
- Do not present the `node_modules` patch as durable: it is erased by any reinstall of `@react-router/dev`, and that caveat must be stated in the final report.
- Do not invent configuration escapes (e.g. disabling typegen or relocating the types dir) — none were found in the traced version, and unverified suggestions must be labeled as such.

## Common Failures
### Failure: `Access is denied` from every deletion tool
- Symptoms: `rd /s /q`, `rmdir`, `fs.rmSync`, and `robocopy /MIR` all fail on the `+types` paths with `Access is denied` / `ERROR 5 (0x00000005)`; `ls` reports `Permission denied` while `cmd /c dir /a` can still list the (empty) directory.
- Causes: the directories are locked at the OS/filesystem level on a volume that reports no ACL support; not a tooling or quoting problem. (The precise OS-side locker was not identified in the trace — the agent only confirmed it is not fixable from userland.)
- Recovery: skip deletion entirely and patch the typegen cleanup call (Steps 4–6).

### Failure: `takeown` errors with "insecure file systems … no support for ACLs"
- Symptoms: `takeown` refuses ownership; `icacls` rejects the grant syntax; deletion still denied afterwards.
- Causes: the drive's filesystem does not support NTFS ACLs, so ownership-based repair is impossible by definition.
- Recovery: treat ownership repair as a dead end; proceed to the dist patch.

### Failure: patch applied but dev server still crashes with the same EPERM
- Symptoms: identical `[Error: EPERM ... scandir ... +types']` after editing `vite.js`/`cli/index.js`.
- Causes: an occurrence was missed (e.g. only `vite.js` patched while the invoked code path is `cli/index.js`, or only one of the two `cli/index.js` calls patched), or a different installed copy of the package is being executed.
- Recovery: re-grep both dist files for `rm(typesDirectory` and confirm every hit ends with `.catch(() => {})`; confirm there is only one `@react-router/dev` in the dependency tree.

### Failure: patch is lost after dependency reinstall
- Symptoms: the EPERM crash returns after any `npm install`/lockfile refresh.
- Causes: the fix lives in `node_modules`, which reinstalls overwrite.
- Recovery: re-apply the same edits, or relocate the project to a filesystem with working ACL support (untested in the trace).

## Verification
Run these checks after patching; each must be observed in tool output, not inferred from a successful Edit.

1. Re-grep both dist files: `Grep pattern "rm.*typesDirectory|typesDirectory.*rm" path "<root>\node_modules\@react-router\dev\dist"` — expect every hit to be followed by `.catch(() => {})` (one hit in `vite.js`, two in `cli/index.js` in the traced layout).
2. Start the dev server time-boxed (`npm run dev` in a background job, wait ~12s, capture output). Pass: output contains no `[Error: EPERM ... scandir ... +types']` and no `node:internal/fs/rimraf` stack; the server proceeds to normal startup. Fail: the same EPERM block reappears.
3. Confirm the dev server binds/serves as expected for the framework (e.g. shows the dev URL / `generated types` log line) rather than exiting with code 1.
4. Negative check: do not treat a clean exit code alone as success — the pre-patch PowerShell job also returned without a PowerShell-level error while Node printed EPERM to stderr; the stderr text is the pass criterion.

Important evidence caveat: in the source trace the patch edits succeeded, but the post-patch dev-server run was interrupted by the user and never executed, so this skill's fix is verified for *application* (three call sites patched, tool-confirmed) but its *runtime effect* was not observed in that session. Anyone applying this skill must complete check 2 themselves before reporting success.

## Examples
### Example 1: Diagnose a locked `+types` cache on an ACL-less drive
- Input: project root `D:\IceBerg`; `npm run dev` prints `[Error: EPERM: operation not permitted, scandir 'D:\IceBerg\.react-router\types\app\+types'] { errno: -4048, code: 'EPERM', syscall: 'scandir' }`.
- Procedure: Step 1 (capture crash, find both locked paths: `...\types\app\+types` and `...\types\app\routes\+types`); Step 2 (`cmd /c "dir /a"` shows each is an empty `<DIR>`); Step 3 (`rd /s /q`, `rmdir`, `fs.rmSync`, `robocopy /MIR` all fail with `Access is denied`/`ERROR 5`; `takeown` reports "no support for ACLs").
- Expected result: a documented conclusion that the dirs are undeletable on this volume and deletion/ACL approaches are closed; proceed to the patch track without retrying them.
- Parameterized values: project root `<ROOT>`, locked dirs `<ROOT>\.react-router\types\app\+types` and `<ROOT>\.react-router\types\app\routes\+types`, Node `v22.20.0`.

### Example 2: Patch all typegen cleanup call sites
- Input: `Grep "rm.*typesDirectory|typesDirectory.*rm"` over `<ROOT>\node_modules\@react-router\dev\dist` returns three hits: `vite.js` (one, in `watch()`) and `cli/index.js` (two, in `run()` and `watch()`), each `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`.
- Procedure: Step 4 (Read ~15–20 lines around each hit to anchor the enclosing function); Step 5 (Edit each call to append `.catch(() => {})`, using the `watch: false` vs `watch: true` context lines to disambiguate the two identical calls in `cli/index.js`); Step 6 (rerun `npm run dev` time-boxed and inspect stderr).
- Expected result: all three call sites patched (tool-confirmed), and a fresh dev-server run producing no EPERM scandir crash. Note: in the source trace the runtime rerun was interrupted by the user, so only the patch application was tool-confirmed there; Example 2's runtime expectation is what Step 6 must confirm in your own run.
- Parameterized values: files `<ROOT>\node_modules\@react-router\dev\dist\vite.js` and `cli\index.js`; symbol `typesDirectory(ctx)` resolves to `<ROOT>\.react-router\types`.

## Evidence
All quotes are from file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__original`.

Problem:
- source_index 97, part 0 (tool_result, `npm run dev` stderr): `[Error: EPERM: operation not permitted, scandir 'D:\\IceBerg\\.react-router\\types\\app\\+types'] {\r\n  errno: -4048,\r\n  code: 'EPERM',\r\n  syscall: 'scandir',` — supports: the exact crash signature (EPERM, errno -4048, scandir on a `+types` dir) that triggers this skill.
- source_index 93, part 0 (tool_result): `ls: cannot open directory '/d/IceBerg/.react-router/types/app/routes/+types/': Permission denied` — supports: the lock blocks recursive listing even from other shells.
- source_index 108, part 0 (tool_result, `node -e` with `fs.rmSync`): `Error: EPERM: operation not permitted, scandir 'd:\\IceBerg\\.react-router\\types\\app\\routes\\+types'\r\n    at readdirSync (node:fs:1583:26)\r\n    at _rmdirSync (node:internal/fs/rimraf:251:29)` — supports: the crash originates inside Node's rimraf recursion, i.e. framework-triggered recursive deletion, not app code.
- source_index 111, part 0 (tool_result, `dir /a`): ` Directory of d:\\IceBerg\\.react-router\\types\\app\\routes\r\n...\r\n20-05-2026  19:42    <DIR>          +types\r\n               0 File(s)              0 bytes` — supports: the locked dir is empty, so deletion is unnecessary for typegen to rewrite files.

Action (futile deletion matrix, verified negative results):
- source_index 102, part 0 (tool_result, `rd /s /q`): `d:\\IceBerg\\.react-router\\types\\app\\routes\\+types - Access is denied.\r\n` and `d:\\IceBerg\\.react-router\\types\\app\\+types - Access is denied.` — supports: `rd` fails on both locked dirs.
- source_index 105, part 0 (tool_result, `takeown` + `icacls` + `rd`): `takeown : ERROR: File ownership cannot be applied on insecure file systems;` … `       there is no support for ACLs.` — supports: ACL/ownership repair is impossible on this volume.
- source_index 118, part 0 (tool_result, `rmdir`): `Exit code 5\ncmd : Access is denied.` — supports: single-dir `rmdir` also fails.
- source_index 125, part 0 (tool_result, `robocopy /MIR`): `2026/05/20 19:45:25 ERROR 5 (0x00000005) Deleting Extra Directory d:\\IceBerg\\.react-router\\types\\app\\+types\\\r\nAccess is denied.` — supports: robocopy mirroring also fails; four independent mechanisms failing justifies abandoning deletion.

Action (locating and patching the crash site):
- source_index 155, part 0 (tool_result, Grep in `vite.js`): `1344:  await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` — supports: the cleanup call that triggers rimraf over the locked tree.
- source_index 159, part 0 (tool_result, Read around line 1344): `1342\tasync function watch(rootDirectory, { mode, logger, rsc }) {\n1343\t  const ctx = await createContext2({ rootDirectory, mode, rsc, watch: true });\n1344\t  await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` — supports: the call sits in the dev-server `watch()` startup path.
- source_index 148, part 0 (tool_result, Grep): `981:  return Path3.join(ctx.rootDirectory, \".react-router/types\");` — supports: `typesDirectory(ctx)` is exactly `<root>/.react-router/types`.
- source_index 167, part 0 (tool_result, Grep in `cli/index.js`): `1339:  await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });\r\n1348:  await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` — supports: two occurrences in the CLI bundle must both be patched.
- source_index 160, part 0 (tool_call:Edit on `vite.js`): `\"new_string\": \"  await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});\"` — supports: the concrete patch shape (append `.catch(() => {})`).
- source_index 164, part 0 (tool_result): `The file d:\\IceBerg\\node_modules\\@react-router\\dev\\dist\\vite.js has been updated successfully.` — supports: the `vite.js` patch was applied.
- source_index 170, part 0 (tool_call:Edit on `cli/index.js`, `run()` with `watch: false`) and source_index 173, part 0 (Edit, `watch()` with `watch: true`), with results at source_index 172 and 174 (tool_result: `...cli\\\\index.js has been updated successfully.`) — supports: both CLI occurrences were patched using surrounding-function context to disambiguate.

Verification status (explicit gap):
- source_index 176, part 0 (tool_call:PowerShell, post-patch `npm run dev`) met with source_index 177, part 0 (tool_result): `The user doesn't want to proceed with this tool use. The tool use was rejected...` — supports: the post-patch dev-server run never executed in the trace; runtime effectiveness of the patch is unverified and must be re-checked by any agent applying this skill.

---
name: fix-react-router-typegen-enotempty
description: Use when `react-router dev`/`typegen` crashes at startup with ENOTEMPTY rmdir or EPERM scandir inside the project's `.react-router/types` directory on Windows and the directory cannot be removed. Helps the agent pinpoint the cleanup `rm()` call inside `@react-router/dev` dist files and neutralize its failure, or delete the cache once the filesystem allows it. Requires read/grep access to `node_modules`, permission to edit dependency files, and a shell for rerunning the dev server. Do not use when the crash path is outside `.react-router/types`, when the project must keep `node_modules` pristine, or when the crash comes from project source code.
---
# Fix react-router typegen ENOTEMPTY/EPERM crash on an undeletable Windows types directory

## Goal
Stop `react-router dev` from dying at startup with ENOTEMPTY/EPERM against the generated `.react-router/types` directory on Windows, producing either a deletable type-cache directory or patched `@react-router/dev` dist files, confirmed by a rerun of the dev server that starts without the filesystem error.

## Scope
### In scope

- Windows hosts where `npm run dev` → `react-router dev` (or `react-router typegen`) exits immediately with `ENOTEMPTY ... rmdir '<root>\.react-router\types\...'`, later `EPERM ... scandir '<root>\.react-router\types\...\+types'`, or `Access is denied` on those directories.
- Probing whether the typegen cache directory can be deleted once all Node/dev-server processes are stopped, and taking that path when it works.
- Locating the typegen cleanup call by grepping `node_modules/@react-router/dev/dist` for `typesDirectory(ctx)` / `rm(`, reading the hit lines, and appending `.catch(() => {})` to each `await ...rm(typesDirectory(ctx), { recursive: true, force: true });` hit (three call sites were hit in the observed trace: `dist/vite.js` `watch()`, `dist/cli/index.js` `run()`, `dist/cli/index.js` `watch()`).
- Recording the deletion strategies that were verified to fail on this class of filesystem so an agent does not repeat them.

### Out of scope

- TypeScript errors in project source, route/config mistakes, or any crash whose path is not under `.react-router/types`.
- Non-Windows filesystems; no evidence from this trace applies to them.
- Making the patch survive `npm install` / dependency upgrades (trajectory did not provide a solution beyond noting it is lost).
- Fixing React Router itself, upgrading/downgrading `@react-router/dev`, or reinstalling dependencies (no evidence).

## Inputs
1. **Crash output** — type: tool result text from running the project's dev script; source: shell command output; required: yes; constraint: must contain `ENOTEMPTY`/`EPERM`/`Access is denied` with a path under `.react-router/types` plus the Node version line; default: 无.
2. **Project root directory** — type: filesystem path; source: session working directory (e.g. the `cwd` recorded for the shell); required: yes; constraint: must contain `node_modules/@react-router/dev/dist`; default: 无.
3. **Permission to edit `node_modules`** — type: authorization; source: user/policy; required: yes for the patch branch (otherwise only the deletion branch is available and the agent must stop and report); constraint: edits are limited to the matched `rm()` lines; default: 无.
4. **Shell with recursive delete capability** — type: environment (PowerShell / Git Bash `rm` / `cmd`); source: host environment; required: yes; constraint: Windows host observed; behavior on other filesystems unknown; default: 无.
5. **Installed `@react-router/dev` version** — type: version string; source: `package.json` / `node_modules`; required: no; constraint: line numbers and bundle layout vary by version — match on call text, not line number; default: 轨迹未提供 (project used the `create-react-router@7.15.1` scaffold).

## Outputs
### Artifacts

- Patched `node_modules/@react-router/dev/dist/vite.js` (and any other dist file that matched) — each `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` now ends with `.catch(() => {});`. Location: inside the project's `node_modules`; format: edited JavaScript source.
- Patched `node_modules/@react-router/dev/dist/cli/index.js` — same change applied to the `run()` and `watch()` cleanup calls.
- Or: the `.react-router/types` cache directory deleted from the project root (deletion branch), leaving no patch behind.
- Diagnostic note recording which deletion attempts failed and which call sites were patched.

### Success criteria

- Rerunning the dev script produces no `ENOTEMPTY`, no `EPERM`, and no `Access is denied` for any path under `.react-router/types`, and the dev server reaches its normal startup output.
- Every grep hit for the cleanup `rm()` call in `@react-router/dev/dist` carries the appended `.catch(() => {})`.

### Failure criteria

- The rerun still crashes with `ENOTEMPTY`/`EPERM` under `.react-router/types`.
- Grep finds zero cleanup `rm()` hits (version/layout difference) or the agent lacks permission to edit `node_modules` while the directory also cannot be deleted.
- The agent cannot rerun the dev server at all (blocked/interrupted), in which case no success may be claimed.

## Preconditions
- The host is Windows and the crash output shows the failing syscall (`rmdir` or `scandir`) with a path under `.react-router\types` (typically a `+types` subdirectory). If the path is elsewhere, stop — this skill does not apply.
- `node_modules/@react-router/dev/dist` exists and is readable/greppable (the project has `@react-router/dev` installed, i.e. a React Router v7 scaffold).
- Permission to edit files under `node_modules` is granted for the patch branch; if not granted and the directory cannot be deleted, stop and report instead of improvising.
- No dev server or other Node process is still running against the project, so a locked directory is not simply held by a live process.
- A shell is available to rerun the dev script for verification; if reruns are blocked (e.g. the user rejects the command), stop and report the patch as applied-but-unverified rather than claiming success.
- Warn before acting: any patch applied here lives in `node_modules` and is discarded by the next dependency install.

## Procedure
### Step 1: Confirm the error signature

- actions: Run the project's dev script once (e.g. `cd <root>; npm run dev`) and capture the full output; check that the thrown error is `ENOTEMPTY ... rmdir` or `EPERM ... scandir` and that `path` lies under `.react-router/types`.
- inputs: crash output (Inputs #1), project root (Inputs #2).
- outputs: captured error text with `code`, `syscall`, `path`, and the Node.js version line.
- cautions: PowerShell may wrap Node's stderr as `NativeCommandError`; read the `[Error: ...]` block itself, not the wrapper. Do not proceed on unrelated errors.
- preserve: project source files; no edits happen in this step.
- next condition: signature matches → Step 2. Signature does not match → stop and handle the actual error.

### Step 2: Try one clean deletion of the type cache

- actions: Confirm no dev/Node process is running, then attempt a single recursive delete of `<root>/.react-router` (e.g. Bash `rm -rf <root>/.react-router`, or an equivalent recursive remove).
- inputs: project root (Inputs #2), shell (Inputs #4).
- outputs: delete result (success or a concrete error line).
- cautions: Do not chain further deletion tools if this fails — in the observed trace `rm -rf`, `Remove-Item -Recurse -Force`, `cmd /c rd /s /q`, `takeown`+`icacls`, `node fs.rmSync`, and `robocopy /MIR` all failed against the same directories; see Decision Rules and Common Failures.
- preserve: everything outside `.react-router`.
- next condition: delete succeeds → Step 5 (skip patching). Delete fails with `Directory not empty` / `Access is denied` / `EPERM` → Step 3.

### Step 3: Locate the typegen cleanup call in the dist bundle

- actions: Grep `node_modules/@react-router/dev/dist` for `typesDirectory(ctx)` and for `rm(`; open the hit lines with surrounding context; identify every `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });` statement — in the observed bundle these sat in `dist/vite.js` inside `async function watch(...)` (line 1344 there) and in `dist/cli/index.js` inside `async function run(...)` and `async function watch(...)`.
- inputs: readable `node_modules` (Preconditions), grep/read tools.
- outputs: list of files + enclosing functions containing the cleanup `rm()`.
- cautions: Match on the call text, not the line number — bundles are version-specific. If there are zero hits, stop and report a version/layout difference instead of guessing.
- preserve: read-only step; no file changes.
- next condition: at least one hit → Step 4. Zero hits → stop and report.

### Step 4: Append error handling to each cleanup call

- actions: Edit every hit so the statement becomes `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});` (keep the `await`, only add the rejection handler); re-grep to confirm all hits carry the suffix.
- inputs: hit list from Step 3, edit permission (Inputs #3).
- outputs: patched `vite.js` / `cli/index.js`; edit tool confirmations.
- cautions: Change only these statements — the surrounding typegen write logic must stay intact. The patch is per-install; a dependency reinstall reverts it.
- preserve: all other files, including project source and unrelated `node_modules` content.
- next condition: every hit patched → Step 5.

### Step 5: Verify by rerunning

- actions: Rerun the dev script and capture startup output; additionally run the project's typecheck script if it exists (the observed project ran `react-router typegen && tsc`).
- inputs: patched or cleaned project from Steps 2/4.
- outputs: dev-server startup output and typecheck output.
- cautions: The source trace's post-patch rerun was interrupted by the user and never produced output — the rerun is mandatory and must actually be observed; never report success from the edit confirmations alone.
- preserve: stop the dev server after capturing output.
- next condition: no `ENOTEMPTY`/`EPERM`/`Access is denied` under `.react-router/types` and normal startup output → done. Otherwise → return to Step 3 and look for a missed cleanup/scandir call, then stop and report if none is found.

## Decision Rules
### When the crash path is under `.react-router\types` with `ENOTEMPTY`/`rmdir`

Treat it as the typegen cleanup step deleting the whole types directory on (re)start: go to Step 2, then Step 3–4 if the directory cannot be removed.

### When the crash path is under `.react-router\types` with `EPERM`/`scandir` on a `+types` subdirectory

The types directory was partially removed/locked by an earlier run: skip further deletion attempts (they failed in the trace) and go straight to Step 3–4.

### When a recursive delete of `.react-router` succeeds (after all Node processes are stopped)

Skip patching entirely and verify (Step 5). In the observed trace an early `rm -rf` of `.react-router/types/app/routes` failed with `Directory not empty`, while a later full `rm -rf ... .react-router` (run with no dev server active) exited successfully — the cause of the difference was not confirmed, so at most one retry is worth spending here.

### When `takeown` reports `ERROR: File ownership cannot be applied on insecure file systems` / `there is no support for ACLs`

Ownership/ACL tooling cannot help on this volume: do not attempt `icacls` or `takeown`-based recovery; go to Step 3.

### When `rm -rf`, `Remove-Item -Recurse -Force`, `cmd /c rd /s /q`, `node fs.rmSync`, or `robocopy /MIR` each fail with `Directory not empty` / `Access is denied` / `EPERM`

Stop the deletion route (these were all verified failures on this filesystem) and switch to the patch route (Step 3–4).

### When grep over `@react-router/dev/dist` yields no `rm(typesDirectory(...))` hit

Stop and report: the installed version's bundle layout differs from the observed one; do not invent an edit target.

### When editing `node_modules` is not permitted and the directory is undeletable

Stop and report both blocked routes; do not modify project source or config as a substitute (no evidence that `react-router.config.ts` offers an escape — the observed config only contained `ssr: true`).

## Invariants
- Touch only the matched typegen cleanup `rm()` statements (and, on the deletion branch, only `<root>/.react-router`); no project source, route files, or unrelated dependencies are modified.
- Do not change typegen's generation logic, output directory contents, or config files as a workaround — the observed config offered no switch for this, and no such fix was verified.
- Do not claim the dev server is fixed from edit confirmations alone; the only acceptable proof is an observed rerun without the filesystem error.
- Do not present the cause of the locked `+types` directories as established — the trace showed the symptom and the failing tools, not a confirmed root cause.
- Keep the `await` on the cleanup call; swallowing the rejection must not make cleanup fire-and-forget in a way that changes ordering beyond error handling.
- Acknowledge that the patch is local to `node_modules` and disappears on reinstall; never report it as a permanent project fix.
- Never skip Step 5 verification, and never label an interrupted or rejected rerun as success.

## Common Failures
### Failure: Every deletion tool fails on the same `+types` directories

- symptoms: `rm: cannot remove '/d/<root>/.react-router/types/app/routes': Directory not empty`; `cmd : d:\<root>\.react-router\types\app\routes\+types - Access is denied.`; `Access is denied.` from `cmd /c rmdir`; `EPERM: operation not permitted, scandir` from `node fs.rmSync`; `ERROR 5 (0x00000005) Deleting Extra Directory ... Access is denied.` from `robocopy /MIR`.
- causes: the exact mechanism was not confirmed in the trace; the only related fact is that `takeown` reported the volume has no ACL support (`ERROR: File ownership cannot be applied on insecure file systems` / `there is no support for ACLs`), and directory listings showed the target directories existing yet empty (0 files).
- recovery: stop deleting; take the patch route (Step 3–4) and verify by rerun.

### Failure: Dev server crashes again with `EPERM: operation not permitted, scandir ... \+types` after partial cleanup

- symptoms: the first run died with `ENOTEMPTY ... rmdir`, a later run dies with `EPERM ... scandir` on `.\+types`, so the visible error code changes between runs.
- causes: an earlier run removed part of the tree and left `+types` entries that subsequent scans cannot read; not further diagnosed in the trace.
- recovery: do not chase the changing code — treat both codes as the same cleanup/scan failure and go to Step 3–4.

### Failure: Patch applied but rerun never observed

- symptoms: edit tools report the dist files updated, but the verification command is rejected/interrupted, so there is no startup output to judge.
- causes: user interruption or blocked command; unknown whether the patch suffices (the source trace ends this thread here).
- recovery: report the state as "patch applied, unverified", rerun the dev script as soon as execution is allowed, and only then claim success or look for missed call sites.

### Failure: Patch disappears after reinstalling dependencies

- symptoms: the same `ENOTEMPTY` crash returns after `npm install`/`npm ci` or a dependency upgrade.
- causes: the edit lives in `node_modules`, which installs overwrite.
- recovery: reapply Step 4 (verify call sites again — line numbers may have moved); long-term handling was not provided in the trace.

## Verification
- Rerun the project's dev script and capture output: it must contain no `ENOTEMPTY`, no `EPERM`, no `Access is denied`, and no `directory not empty` line referencing `.react-router`, and it must show the dev server's normal startup/banner output.
- Grep `node_modules/@react-router/dev/dist` for `rm(typesDirectory(ctx)` and confirm every hit is followed by `.catch(() => {})` (expected hit count in the observed bundle: three — `dist/vite.js` `watch()`, `dist/cli/index.js` `run()`, `dist/cli/index.js` `watch()`).
- If a typecheck script exists (observed: `react-router typegen && tsc`), run it after the rerun and confirm it exits clean.
- Confirm `.react-router/types` regenerates typegen output (e.g. `+types` files reappear) rather than being permanently absent, showing cleanup no longer aborts startup.
- On the deletion branch: confirm `<root>/.react-router` is gone (`ls <root>` shows no `.react-router`) and the rerun passes as above.
- Record explicitly whether the rerun was actually observed: in the source trace the post-patch rerun was rejected by the user, so the edit confirmations alone proved only that the patch was written, not that the crash is gone.

## Examples
### Example 1: ENOTEMPTY on `react-router dev`, directory undeletable → patch route

- input: `npm run dev` output containing `[Error: ENOTEMPTY: directory not empty, rmdir 'D:\IceBerg\.react-router\types\app\routes'] {` with `errno: -4051` on Node.js v22.20.0; `rm -rf /d/IceBerg/.react-router/types/app/routes` returning `rm: cannot remove ... Directory not empty`.
- procedure: Step 1 (signature confirmed) → Step 2 (delete fails) → Step 3 (grep `dist` for `typesDirectory(ctx)`, find the `rm()` in `dist/vite.js` `watch()` and two more in `dist/cli/index.js`) → Step 4 (append `.catch(() => {})` to all three) → Step 5 (rerun and observe).
- expected result: all three cleanup calls patched; the rerun starts with no filesystem error. In the source trace Steps 1–4 completed with edit confirmations, but the Step 5 rerun was interrupted, so end-to-end success must be re-established by the executing agent.
- parameterized values: project root → `D:\IceBerg` (replace with `<root>`); dist line number → 1344 in that bundle (match on call text instead); volume with no ACL support → any Windows volume where `takeown` prints `there is no support for ACLs`.

### Example 2: cache directory deletes cleanly → no patch

- input: same `ENOTEMPTY ... rmdir` signature, but no dev/Node process is running and a recursive delete of `<root>/.react-router` exits 0.
- procedure: Step 1 → Step 2 (success) → Step 5.
- expected result: no `node_modules` edits at all; rerun starts clean and typegen regenerates `.react-router/types`.
- parameterized values: delete command → `rm -rf <root>/.react-router` on Bash or an equivalent recursive remove in PowerShell; verification command → the project's dev script.

### Example 3: patch blocked by policy → stop and report

- input: undeletable `.react-router/types` (per Example 1's failures) plus a policy forbidding edits under `node_modules`.
- procedure: Step 1 → Step 2 (fails) → Decision Rule "editing `node_modules` is not permitted".
- expected result: an explicit report that both routes are blocked (no deletion possible, no patch allowed), with the captured error lines as evidence; no edits to project source or config, and no claim of a fix.

## Evidence
All entries reference file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__original`.

**problem**

- source_index: 83, source_part_index: 0, quote: `[Error: ENOTEMPTY: directory not empty, rmdir 'D:\IceBerg\.react-router\types\app\routes'] {`, supports: the original failing run — `react-router dev` aborts on `rmdir` of the generated types directory (error key ENOTEMPTY), Node.js v22.20.0.
- source_index: 97, source_part_index: 0, quote: `[Error: EPERM: operation not permitted, scandir 'D:\IceBerg\.react-router\types\app\+types'] {`, supports: after partial deletion the same startup crashes switch to `EPERM`/`scandir` on `+types`, so the code changes between runs while the location stays under `.react-router/types`.
- source_index: 89, source_part_index: 0, quote: `rm: cannot remove '/d/IceBerg/.react-router/types/app/routes': Directory not empty`, supports: Git Bash `rm -rf` failed against the cache directory — verified failure of the first deletion strategy.
- source_index: 102, source_part_index: 0, quote: `d:\IceBerg\.react-router\types\app\routes\+types - Access is denied.`, supports: `cmd /c rd /s /q` also failed (verified failure), including on a `+types` directory.
- source_index: 105, source_part_index: 0, quote: `takeown : ERROR: File ownership cannot be applied on insecure file systems;`, supports: ownership/ACL repair is unavailable on this volume (`there is no support for ACLs` in the same result), so `takeown`/`icacls` recovery is a dead end here.
- source_index: 108, source_part_index: 0, quote: `Error: EPERM: operation not permitted, scandir 'd:\IceBerg\.react-router\types\app\routes\+types'`, supports: `node fs.rmSync` deletion attempt failed with the same `scandir` EPERM, matching the crash stack (`node:internal/fs/rimraf`).
- source_index: 125, source_part_index: 0, quote: `ERROR 5 (0x00000005) Deleting Extra Directory`, supports: `robocopy /MIR` mirror-wipe failed with access denied — the last deletion strategy tried, also verified as failure.

**action**

- source_index: 148, source_part_index: 0, quote: `return Path3.join(ctx.rootDirectory, ".react-router/types");`, supports: grep located the types-directory helper inside `@react-router/dev/dist`, anchoring the search for the cleanup call.
- source_index: 159, source_part_index: 0, quote: `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`, supports: reading `dist/vite.js` exposed the exact cleanup statement inside `async function watch(...)` (line 1344 in that bundle) that performs the fatal recursive delete on startup.
- source_index: 160, source_part_index: 0, quote: `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});`, supports: the patch applied to `dist/vite.js` — appending a rejection handler to the cleanup `rm()` is the core corrective action.
- source_index: 170, source_part_index: 0, quote: `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});`, supports: the same patch was applied to the `run()` path in `dist/cli/index.js`, showing the cleanup exists in more than one dist file.
- source_index: 173, source_part_index: 0, quote: `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});`, supports: the `watch()` path in `dist/cli/index.js` was patched too — three call sites total in the observed bundle.

**verification**

- source_index: 164, source_part_index: 0, quote: `has been updated successfully. (file state is current in your context — no need to Read it back)`, supports: edit confirmation for `dist/vite.js` — proves only that the patch was written, not that the crash is gone.
- source_index: 174, source_part_index: 0, quote: `has been updated successfully. (file state is current in your context — no need to Read it back)`, supports: edit confirmation for `dist/cli/index.js` (second call site), same partial scope of proof.
- source_index: 79, source_part_index: 0, quote: `> react-router typegen && tsc`, supports: before the crash, `react-router typegen && tsc` ran clean, isolating the failure to the dev server's cleanup step rather than type generation or type checking.
- source_index: 177, source_part_index: 0, quote: `The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file).`, supports: the post-patch rerun of `npm run dev` was rejected, so end-to-end success was never observed in this trace and must be established by the executing agent (this is why Step 5 is mandatory and no success may be claimed otherwise).
- source_index: 190, source_part_index: 0, quote: `done`, supports: a later full `rm -rf ... .react-router` (with no dev server running) echoed `done`, i.e. deletion eventually succeeded once — supporting the "one retry after processes exit" rule, with the cause explicitly unconfirmed.

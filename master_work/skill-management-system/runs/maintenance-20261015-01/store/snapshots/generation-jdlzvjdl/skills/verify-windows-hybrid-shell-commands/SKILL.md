---
name: verify-windows-hybrid-shell-commands
description: Use when working in a Windows agent environment that exposes both Bash and PowerShell and command results look empty, failed, or misleading. Helps the agent pick the right shell and path syntax, avoid GNU/cmd utilities that do not exist in the other shell, interpret npm stderr noise that PowerShell wraps as `NativeCommandError`, and judge scaffold or setup outcomes by a file listing instead of an exit code. Requires both Bash and PowerShell tools on a Windows host. Do not use on single-shell or non-Windows hosts, or when the command output is already unambiguous.
triggers:
  - "NativeCommandError"
  - "Select-Object -First"
  - "(PowerShell completed with no output)"
---
# Read Windows Hybrid-Shell Command Results Correctly and Verify Outcomes by Filesystem State

## Goal
Interpret command results correctly in a Windows agent shell that mixes Bash, PowerShell, and cmd so that setup or scaffold outcomes are decided by filesystem evidence rather than by misleading exit codes, wrong path syntax, or empty output.

## Scope
### In scope
- Choosing path syntax per shell: Bash uses `/d/...`, PowerShell uses `d:\...`; cmd syntax only under `cmd /c`.
- Substituting missing utilities: no `head` (and other GNU names) in PowerShell — use `Select-Object -First N`; use Bash `find`/`ls` for recursive listings.
- Reading npm/npx output where stderr warnings (`npm warn exec ...`, deprecation notices) make PowerShell surface `NativeCommandError` and a non-zero exit code even when the tool succeeded.
- Cross-checking suspicious "(PowerShell completed with no output)" results with the other shell.
- Verifying scaffold/setup claims with a directory listing (e.g. Bash `find`) before reporting success or failure.

### Out of scope
- Linux/macOS hosts or environments with only one shell.
- Fixing npm, PowerShell, or the scaffolder itself.
- Deciding what the correct project contents should be (that belongs to the specific scaffold skill).
- Application-level verification (install/build/typecheck) beyond using it as the follow-up after the outcome verdict.

## Inputs
- Shell tool selection — enum (`Bash` | `PowerShell` | `cmd`) — agent decision — required — PowerShell for Windows-native cmdlets and `cmd /c`, Bash for GNU tools and `/d/` paths; default: PowerShell for native ops, Bash for listings/deletions
- Command under test — string — task step — required — e.g. an `npx`/`npm create` scaffold invocation; default: 无
- Expected filesystem markers — list of paths — derived from the command's purpose — required for verification — e.g. `package.json`, `app/root.tsx` after a React Router scaffold; default: 无
- Cross-check shell — enum — agent decision — required when output looks empty or contradictory — the shell other than the one that produced the result; default: 无
- Project path — string — task environment — required — parameterize per host (drive letter may differ); default: 无

## Outputs
### Artifacts
- No files are written by this skill; the artifact is a verdict (success/failure/indeterminate) plus the listing evidence quoted in the final message.
- If a command must be retried with corrected syntax, the retry itself is the only side effect.

### Success criteria
- A verdict is reported together with a filesystem listing that shows (or shows the absence of) the expected markers.
- Corrected-syntax retries complete without shell-level errors (`head` not found, positional parameter errors, `cannot access` path errors).
- npm exit codes are reported alongside the actual output text, never alone.

### Failure criteria
- A success or failure claim is made without a listing cross-check when the original output was noisy, empty, or contradictory.
- An empty PowerShell listing is treated as "no files exist" without a second-shell check.

## Preconditions
- Both Bash and PowerShell tools are available in the agent environment; if only one shell exists, the cross-check steps degrade to re-running with corrected syntax in that shell.
- The host is Windows with drive letters mappable into the Bash tool's path space (observed: `d:` ↔ `/d/`).
- The command being judged has known expected outputs (file paths) that can be listed afterwards; without such markers, no verdict can be given — report indeterminate.
- Permission to list the target directory (read access is enough; this skill never modifies files).

## Procedure
### Step 1: Choose shell and path syntax before running
- Actions: decide the shell for the command — Bash gets MSYS-style paths (`/d/IceBerg`), PowerShell gets Windows paths (`d:\IceBerg`), cmd flags (`/s /b`, `rd /s /q`) only run under `cmd /c "..."`.
- Inputs: project path, command purpose.
- Outputs: a first attempt written with matching syntax.
- Cautions: running `ls d:\IceBerg` in Bash mangles the path into `d:IceBerg`; running cmd-style arguments directly in PowerShell feeds them to `Get-ChildItem`.
- Preserve: the original command intent — only syntax changes.
- Next condition: command returns output without shell syntax errors → Step 3; a path/parameter error → Step 2.

### Step 2: Repair shell-specific errors and retry once
- Actions: replace Bash-on-Windows-path failures with either Bash `/d/...` or PowerShell `Get-ChildItem d:\...`; replace `head` with `Select-Object -First N`; wrap cmd flags in `cmd /c`.
- Inputs: the error text from Step 1.
- Outputs: a corrected retry.
- Cautions: each repair changes only the invocation layer, never the underlying operation; do not retry the identical broken form.
- Preserve: both error and retry outputs for the report.
- Next condition: corrected command runs → Step 3.

### Step 3: Read the output text, not just the exit code
- Actions: separate three signals — the exit code, PowerShell's wrapper (`NativeCommandError`, `CategoryInfo` blocks), and the actual message lines (e.g. `npm warn exec The following package was not found and will be installed: ...`, deprecation notices, the tool's own output).
- Inputs: raw command result.
- Outputs: an interim interpretation ("completed with warnings", "tool-reported error", "shell-level failure").
- Cautions: npm writes warnings to stderr, which PowerShell surfaces as an error-looking wrapper even when `is_error` is false or the tool did its job; deprecation warnings (`inflight@1.0.6`, `glob@7.2.3`) are unrelated to success.
- Preserve: exact message lines to quote later.
- Next condition: interpretation still ambiguous (non-zero exit but plausible success, or vice versa) → Step 4; clear result → Step 5.

### Step 4: Cross-check against the filesystem with the other shell
- Actions: list the directory with the other shell — Bash `find /d/<project> -maxdepth 3` or `ls /d/<project>/` when PowerShell output is empty or suspicious; PowerShell `Get-ChildItem` when Bash cannot express the path. Compare against the expected markers for that command.
- Inputs: expected marker list (e.g. `package.json`, `app/root.tsx`, `vite.config.ts`).
- Outputs: presence/absence evidence.
- Cautions: `(PowerShell completed with no output)` was observed for listings that Bash then showed to contain a full project — never equate empty output with an empty directory. A recursive `Get-ChildItem` can fail (exit 1) on locked subtrees while `cmd /c dir /a` works.
- Preserve: quote the listing lines used for the verdict.
- Next condition: markers found or definitively absent → Step 5.

### Step 5: Issue the verdict with both signals
- Actions: state success, failure, or indeterminate; include the exit code/wrapper observation AND the listing evidence; if markers are absent but the tool printed no error, report indeterminate and escalate rather than guessing.
- Inputs: Steps 3–4 results.
- Outputs: final verdict in the response message.
- Cautions: causes that were not confirmed (e.g. why `npx` exited 1) must be labeled unknown rather than asserted.
- Preserve: nothing to write; this skill modifies no files.
- Next condition: verdict delivered; downstream skills (install/build/typecheck) then provide application-level verification.

## Decision Rules
### When Bash reports `ls: cannot access 'd:IceBerg': No such file or directory`
The backslash path was consumed by the Bash tool — rerun with `/d/IceBerg` in Bash or the same path in PowerShell (`Get-ChildItem d:\IceBerg` worked in the trajectory).

### When PowerShell says `The term 'head' is not recognized ...`
GNU coreutils are not available in PowerShell — use `Select-Object -First N`; never pipe to `head`, `tail`, or `grep` there.

### When a cmd-style invocation errors with `A positional parameter cannot be found that accepts argument '/b'.`
The command landed in a cmdlet — wrap it: `cmd /c "dir /s /b ..."`.

### When a listing returns `(PowerShell completed with no output)` while the directory is believed non-empty
Cross-check with Bash `ls`/`find` before concluding anything; in the trajectory the same directory listed fine from Bash.

### When `npm`/`npx` exits 1 whose message lines are only `npm warn exec ...`, deprecation notices, or ANSI spinner text
Treat as "completed with stderr noise" and verify by listing expected files; in the trajectory a React Router scaffold exited 1 yet `find` showed `app/root.tsx`, `package.json`, `vite.config.ts` and friends — the exit code cause was never confirmed, so say so.

### When stderr noise appears but `is_error` is false
No retry needed; proceed to the filesystem cross-check for the real verdict.

## Invariants
- Never report success or failure of a file-creating command without a directory listing that shows or refutes the expected files.
- Never retry a command with identical syntax after a shell-level syntax/path error; change only the invocation layer.
- Never treat PowerShell's `NativeCommandError` wrapper or npm stderr warnings as the tool's verdict.
- Never treat `(PowerShell completed with no output)` as evidence that a directory is empty — cross-check with the other shell.
- Never assert an unconfirmed cause for a non-zero exit code; report the observation and mark the cause unknown.
- Do not modify, clean, or "fix" any files while verifying an outcome.
- Quote raw output lines verbatim in the verdict.

## Common Failures
### Failure: Bash given a Windows backslash path
- Symptoms: `ls: cannot access 'd:IceBerg': No such file or directory` with exit code 2.
- Causes: the Bash tool interprets `d:\IceBerg` as a literal relative name (backslashes consumed/escaped).
- Recovery: rerun as `ls /d/IceBerg/` in Bash or `Get-ChildItem d:\IceBerg` in PowerShell; both worked in the trajectory.

### Failure: GNU utility invoked in PowerShell
- Symptoms: `The term 'head' is not recognized as the name of a cmdlet, function, script file, or operable program.` with exit code 1.
- Causes: PowerShell has no coreutils.
- Recovery: `Select-Object -First N`; keep GNU pipelines inside Bash.

### Failure: cmd syntax fed to PowerShell
- Symptoms: `A positional parameter cannot be found that accepts argument '/b'.` — `dir d:\IceBerg /s /b` was routed into `Get-ChildItem`.
- Causes: `dir` is a cmdlet alias in PowerShell; `/s /b` are not its parameters.
- Recovery: `cmd /c "dir /s /b ..."` (the trajectory instead used Bash `find`, which also worked).

### Failure: Scaffold wrongly declared failed
- Symptoms: `Exit code 1` plus `npm warn exec The following package was not found and will be installed: create-react-router@7.15.1` and ANSI progress text, yet the directory contains the full scaffold (`app/root.tsx`, `package.json`, `vite.config.ts`, `node_modules/...`).
- Causes: npm stderr noise surfaced by PowerShell; possibly the pre-existing files in the directory — the true cause of exit 1 was not confirmed.
- Recovery: run the Step 4 listing, report "scaffold files present despite exit 1", and continue; do not delete or re-scaffold based on the exit code alone.

### Failure: Empty listing mistaken for empty directory
- Symptoms: `Get-ChildItem ... -Recurse -Force | Select-Object FullName` returns `(PowerShell completed with no output)` (observed multiple times, including on a directory Bash later showed to be populated).
- Causes: unknown — the PowerShell pipeline produced nothing in these runs.
- Recovery: cross-check with Bash `find /d/<project> -maxdepth 3`; only trust the shell that actually returned content.

## Verification
Concretely observable checks for the verdict:
- A listing from the cross-check shell contains the expected markers (for a scaffold: a top-level manifest such as `/d/IceBerg/package.json` and framework entry files such as `/d/IceBerg/app/root.tsx`).
- A corrected-syntax retry produces no shell-level error (`head`/positional-parameter/`cannot access` messages gone) and returns real content.
- The final verdict quotes both the original result (exit code and message lines) and the listing lines that support it.
- When output was empty, the verdict names which second-shell command produced the contradicting or confirming evidence.
- When the exit-code cause is unknown (as with the `Exit code 1` scaffold), the report says the cause was not confirmed instead of inventing one.
- Downstream application checks (install/build/typecheck) are run separately — this skill's verdict only establishes what exists on disk.

## Examples
### Example 1: Scaffold exits 1 but actually succeeded
- Input: `npx create-react-router@latest . --yes` run in PowerShell, returning `Exit code 1` with `npm warn exec The following package was not found and will be installed: create-react-router@7.15.1` and spinner text; expected markers: `package.json`, `app/root.tsx`, `vite.config.ts`.
- Procedure: Step 3 (separate wrapper from message lines) → Step 4 (Bash `find /d/<project> -maxdepth 3`) → Step 5 (verdict).
- Expected result: listing shows `/d/IceBerg/package.json` and `/d/IceBerg/app/root.tsx`; verdict = "scaffold present despite exit 1; exit-code cause unconfirmed", and work continues without re-scaffolding.
- Parameterized values: project path, template/flags, marker list.

### Example 2: Empty PowerShell listing on a populated directory
- Input: `Get-ChildItem <path> -Force | ...` returning `(PowerShell completed with no output)` for a directory believed to hold a project.
- Procedure: Step 4 cross-check with Bash `ls /d/<project>/`.
- Expected result: the Bash listing returns the real file names (trajectory: `CLAUDE.MD`, `DESIGN.MD`, `Dockerfile`, `README.md`, `app`, `node_modules`, ...), so the verdict is "directory populated; PowerShell output unreliable", not "empty directory".
- Parameterized values: drive letter, directory, marker list.

## Evidence
- problem — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 15, source_part_index 0, quote `ls: cannot access 'd:IceBerg': No such file or directory` — supports: the Bash tool cannot take a backslash Windows path; path syntax must be chosen per shell.
- problem — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 52, source_part_index 0, quote `The term 'head' is not recognized as the name of a cmdlet, function, script file, or operable program.` — supports: GNU utilities do not exist in PowerShell; use `Select-Object -First N` instead.
- problem — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 57, source_part_index 0, quote `A positional parameter cannot be found that accepts argument '/b'.` — supports: cmd flags must be wrapped in `cmd /c`, otherwise PowerShell routes them into `Get-ChildItem`.
- problem — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 45, source_part_index 0, quote `npm warn exec The following package was not found and will be installed: create-react-router@7.15.1` — supports: an npx scaffold reported `Exit code 1` whose visible message lines are npm stderr noise plus progress text — exactly the situation where the exit code alone misleads.
- problem — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 54, source_part_index 0, quote `(PowerShell completed with no output)` — supports: PowerShell listings can come back empty for populated directories, requiring a second-shell cross-check.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 17, source_part_index 0, quote `Get-ChildItem d:\IceBerg` — supports: the same directory lists correctly from PowerShell when given Windows path syntax, showing the fix is syntax-level.
- action — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 42, source_part_index 0, quote `npm warn exec The following package was not found and will be installed: create-remix@2.17.4` — supports: npm stderr warnings appear even in results flagged `is_error: false`, proving noise ≠ failure.
- verification — file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`, source_index 59, source_part_index 0, quote `/d/IceBerg/package.json` — supports: Bash `find` showed the complete scaffold (manifest, `app/`, `react-router.config.ts`, `node_modules/...`) despite the earlier `Exit code 1`, so the filesystem listing — not the exit code — established that the scaffold succeeded.

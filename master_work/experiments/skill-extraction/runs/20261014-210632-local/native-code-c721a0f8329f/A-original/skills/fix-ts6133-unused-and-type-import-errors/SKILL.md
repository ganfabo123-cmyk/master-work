---
name: fix-ts6133-unused-and-type-import-errors
description: Use when `tsc --noEmit` reports TS6133 'declared but its value is never read' errors (often alongside TS1484 type-only-import and TS2554 wrong-argument-count errors) in a TypeScript project whose tsconfig enables strict unused/type-import checking. Helps the agent apply minimal, per-error edits (trim imports, delete unused locals/constants/state, prefix `type` on type-only imports, give useRef an explicit undefined initial value) and re-run the typecheck until the output is empty. Requires a runnable TypeScript toolchain (e.g. `npx tsc --noEmit` from the project directory) and permission to edit the reported source files. Do not use when the errors are runtime, bundler, or lint failures that `tsc --noEmit` does not report, or when unused-symbol errors are intentionally tolerated by the project config.
---
# Fix TS6133 Unused Declaration Errors (with Companion TS1484/TS2554) and Re-verify With tsc --noEmit

## Goal
Eliminate all TS6133 "declared but its value is never read" errors (and any TS1484/TS2554 errors reported in the same `tsc --noEmit` run) from a TypeScript/React codebase with minimal, behavior-preserving edits, and prove the fix by re-running `npx tsc --noEmit` until it produces no output.

## Scope
### In scope
- TS6133 errors from `tsc --noEmit` under strict compiler options (`noUnusedLocals` / `noUnusedParameters`), for: unused named imports, unused local constants, unused `useState` value slots, unused destructured context values, and unused router hook results.
- Companion errors that appear in the same typecheck report and block a clean run: TS1484 (type-only import required when `verbatimModuleSyntax` is on) and TS2554 (function called with wrong argument count, e.g. `useRef<T>()` with no initial value).
- Verification by re-running the exact same `tsc --noEmit` command and confirming empty output.

### Out of scope
- Runtime behavior, rendering, API, or build/bundle validation (the trajectory verified only the TypeScript check; `vite build`, dev-server, and tests were not run after these edits).
- Lint/format fixes (`eslint`, `prettier`) and test updates.
- Disabling compiler options (`noUnusedLocals: false`, `// @ts-ignore`, `@ts-expect-error`) to silence errors — the trajectory never did this and it is not a validated approach here.
- Refactoring "unused" code that is actually needed (e.g. wiring up a feature that uses the variable); the trajectory removed dead code only.
- Backend (JavaScript/Node) code, which is not typechecked by `tsc`.

## Inputs
- **Typecheck error report**: string. Source: output of running `npx tsc --noEmit` in the TypeScript project directory (one line per error: `path(line,col): error TSNNNN: message`). Required: yes. Constraint: capture the full report (the trajectory piped through `head -60`, which is acceptable only while the report is shorter than the cap). Default: none.
- **Project directory**: path. Source: the TypeScript package root containing `tsconfig.json` (e.g. `<project>/frontend`). Required: yes. Constraint: must contain `tsconfig.json` and a local `typescript` install usable via `npx tsc`. Default: none.
- **Source files named in the error report**: file contents. Source: the agent's context or a Read tool call on the specific file. Required: yes, for each file being edited. Constraint: the `old_string` used for edits must match the current file text exactly. Default: none.
- **Edit capability**: tool. Source: agent environment (e.g. Edit/Write tool). Required: yes. Constraint: edits must be limited to files/lines referenced by the errors. Default: none.
- **Compiler configuration**: object. Source: `tsconfig.json`. Required: no (diagnostic only). Constraint: the trajectory's config had `verbatimModuleSyntax` and unused-symbol checking enabled (evidenced by TS1484/TS6133 errors); do not modify it. Default: none.

## Outputs
### Artifacts
- Edited source files (in place): the `.tsx`/`.ts` files named in the error report, each with only the minimal change required by its errors.
- Verification record: the terminal output of the re-run `npx tsc --noEmit` command; success is indicated by empty output (the trajectory's result was "(Bash completed with no output)").

### Success criteria
- Re-running the same `npx tsc --noEmit` command from the same directory exits with no error lines at all — not merely fewer errors. The trajectory confirmed this once for the whole batch.
- Every TS6133, TS1484, and TS2554 line from the initial report is gone.
- No file outside the error report was modified.

### Failure criteria
- Any error line remains in the re-run output.
- The re-run was never executed, or was piped/truncated such that remaining errors could be hidden.
- Edits changed runtime behavior beyond removing genuinely dead code (e.g. deleting a used state setter, or removing a hook call that had side effects).

## Preconditions
- `tsconfig.json` exists in the project directory and `npx tsc --noEmit` is runnable there (a local TypeScript install is present; the trajectory's frontend used `typescript ^6.0.2` via npm). If `tsc` cannot run, stop and report.
- The error report has been captured in full, or the truncation limit (e.g. `| head -60`) is larger than the report length. If the report may be truncated, re-run with a larger cap before editing.
- The agent may edit the specific files named in the error report, and only those.
- `tsconfig.json` and other configuration files will NOT be modified as part of this fix; if the only viable fix would be to change compiler options, stop and ask instead.
- Each `old_string` for an edit is taken from the current file content (read from context or via Read) so the edit can apply exactly once.

## Procedure
### Step 1: Capture the full typecheck report
- Actions: from the TypeScript project directory, run `npx tsc --noEmit 2>&1 | head -60` (or without `head` if the report may be long; raise the cap if the output ends mid-list). Record every `file(line,col): error TSNNNN` line.
- Inputs: project directory.
- Outputs: error report string listing TS6133 / TS1484 / TS2554 (and any other) errors.
- Cautions: the trajectory's project root for typechecking was the `frontend` directory, not the repo root — run `tsc` where `tsconfig.json` lives.
- Preserve: the exact command form, so the verification run is identical.
- Next: proceed to Step 2 once the report is complete (no cut-off at the tail).

### Step 2: Fix TS1484 type-only imports (do these first)
- Actions: for each `error TS1484: 'X' is a type and must be imported using a type-only import`, edit that file's import statement to prefix each offending name with `type` (e.g. `import { type CSSProperties, type ReactNode, ... } from 'react'`), keeping value imports un-prefixed.
- Inputs: error lines naming file, column, and symbol; current import statement text.
- Outputs: updated import lines.
- Cautions: only mark the symbols named by TS1484; leave other specifiers untouched.
- Preserve: import ordering and the module specifier (e.g. `'react'`).
- Next: continue with the remaining TS1484 lines, then Step 3.

### Step 3: Remove unused imports (TS6133 on import columns)
- Actions: for each TS6133 whose column points into an import statement, delete that specifier from the import list. If the specifier is the only one, remove the whole import line. Observed cases: removing `Outlet` from `import { HeadContent, Outlet, Scripts, createRootRoute } from '@tanstack/react-router'`, removing `Select` from a component import, removing `Link` from `import { createFileRoute, Link } from '@tanstack/react-router'`.
- Inputs: TS6133 lines with file/line/column; current import text.
- Outputs: trimmed import statements.
- Cautions: confirm the symbol truly has no other reference in the file before removing (the compiler already guarantees this, but check you are editing the file the error names).
- Preserve: the remaining specifiers and module specifier.
- Next: go to Step 4.

### Step 4: Remove unused locals and hook results (TS6133 on declarations)
- Actions, by declaration kind as seen in the report:
  - Unused module-level constant: delete the declaration line(s), e.g. `const BASE_URL = 'http://localhost:5000'`.
  - Unused destructured value from a hook that must still be called for its side effects: keep the call, drop the destructuring, e.g. replace `const { user } = useAuth()` with `useAuth()`. Only do this when the hook call itself matters; if the whole call is dead, remove the line entirely.
  - Unused `useState` value slot where only the setter is used: delete the entire `const [value, setValue] = useState(...)` line AND every remaining `setValue(...)` call site (the trajectory removed both `const [applied, setApplied] = useState(false)` and the later `setApplied(true)`).
  - Unused router hook result: delete the line, e.g. `const navigate = Route.useNavigate()`.
- Inputs: TS6133 lines; a Read of each affected file region to see all usages before deleting setters.
- Outputs: files with the dead declarations (and orphaned setter calls) removed.
- Cautions: deleting only the declaration while leaving `setValue(...)` calls produces new errors; delete both. Do not remove a hook call that performs required side effects — prefer dropping just the unused binding.
- Preserve: all code that was not part of the reported dead declaration.
- Next: go to Step 5.

### Step 5: Fix companion argument-count errors (TS2554)
- Actions: if the same report contains TS2554 such as `Expected 1 arguments, but got 0` on a `useRef<T>()` call, supply the explicit initial value: `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)` (widen the type with `| undefined` when the ref is later assigned or cleared).
- Inputs: the TS2554 line and the call site text.
- Outputs: corrected call.
- Cautions: pass an initial value rather than casting, to keep the ref's assignable type honest.
- Preserve: the ref's name and its usages elsewhere.
- Next: go to Step 6.

### Step 6: Re-run the identical typecheck and confirm empty output
- Actions: run the exact same command from Step 1 (e.g. `npx tsc --noEmit 2>&1 | head -40`).
- Inputs: unchanged project directory.
- Outputs: tool result; success = "(Bash completed with no output)" or an empty error list.
- Cautions: do not claim success from a truncated pipe without checking the tail; do not treat a build (`vite build`) as a substitute — the trajectory verified with `tsc --noEmit` only.
- Preserve: all Step 2–5 edits; if errors remain, return to Step 2 for the new report and iterate.
- Next: stop when output is empty and report the result.

## Decision Rules
### When the TS6133 column points into an import statement
Remove only that specifier from the import list (drop the whole line if it was the last specifier). Do not touch value imports the compiler did not flag.

### When the TS6133 declaration is a `useState` value that is never read but the setter is used
Delete the entire state declaration line and all remaining `setValue(...)` call sites in that file, then continue; leaving orphaned setter calls guarantees new errors.

### When the TS6133 declaration destructures a hook result (`const { x } = useSomeHook()`) and the hook call has side effects
Keep the bare hook call (`useSomeHook()`) and remove only the destructuring. Remove the entire line only when the hook call itself is dead.

### When the TS6133 declaration is a plain unused constant or hook result with no side effects
Delete the declaration line entirely.

### When the same report contains TS1484 for a file you must edit anyway
Prefix the flagged names with `type` in that import statement (inline `type X` form), keeping value specifiers unchanged.

### When the report contains TS2554 "Expected 1 arguments, but got 0" on `useRef<T>()`
Pass an explicit initial value, widening the generic with `| undefined` if the ref can be unassigned.

### When the verification run still prints any error line
Re-read the new report and repeat Steps 2–5 for the remaining errors; never report success on a partially clean run.

### When `tsc --noEmit` output is truncated by `head` and may hide remaining errors
Stop and re-run with a larger (or no) truncation cap before claiming the report is complete.

## Invariants
- Modify only the files (and, where possible, only the lines) named in the error report; no unrelated files, configs, or package manifests are touched.
- Never weaken compiler checking to make errors disappear: no changes to `tsconfig.json`, no `@ts-ignore`/`@ts-expect-error`, no disabling `noUnusedLocals`/`noUnusedParameters`/`verbatimModuleSyntax`.
- Every claim of success is backed by a re-run of `tsc --noEmit` showing no error lines; an empty-but-truncated or un-run check is not success.
- Removals are limited to code the compiler proved unread: no behavioral "cleanup" beyond the flagged declarations and their orphaned setter calls.
- Do not mix in unrelated refactors, formatting passes, or feature changes while fixing the report, so that any new error can be attributed to the type-fix edits.
- The verification command must be the same command, run from the same directory, as the diagnostic command.

## Common Failures
### Failure: Removing a `useState` declaration but leaving its setter calls
- Symptoms: after the edit, new errors such as `TS2554`/`TS2304` (cannot find name `setApplied`) appear at the setter call sites.
- Causes: the state value was unread but the setter was still invoked elsewhere in the file.
- Recovery: delete every remaining `setValue(...)` call in the file together with the declaration, then re-run `tsc --noEmit`. (The trajectory avoided this by editing both sites: removing `const [applied, setApplied] = useState(false)` and the later `setApplied(true)` line.)

### Failure: Claiming success from a truncated typecheck output
- Symptoms: the re-run was piped through a small `head -N`; errors beyond the cap are silently hidden, or the initial report itself was cut off mid-list.
- Causes: a fixed-size truncation smaller than the report.
- Recovery: re-run without `head`, or with a cap larger than the longest observed report, and compare the full output.

### Failure: Silencing errors by changing compiler options instead of code
- Symptoms: `tsconfig.json` gains `noUnusedLocals: false`, `verbatimModuleSyntax: false`, or source lines gain `@ts-ignore`.
- Causes: treating the diagnostic as the problem rather than the dead code.
- Recovery: revert the config/ignore changes and apply the import/declaration edits from the Procedure; the compiler settings are the contract being met.

### Failure: Deleting a binding whose hook call had side effects
- Symptoms: typecheck passes but runtime behavior regresses (e.g. auth context no longer initialized/refreshed).
- Causes: removing `const { user } = useAuth()` as a whole line instead of keeping `useAuth()`. In the trajectory the side-effect-preserving form `useAuth()` was used; whether the bare call was actually required was not runtime-verified, so prefer keeping the call when the hook provably has effects and flag the uncertainty.
- Recovery: restore the bare hook call and re-run `tsc --noEmit`.

### Failure: Fixing errors one file at a time and stopping early
- Symptoms: the assistant reports "fixed" while the report still lists other files (TS6133 across several route files plus TS1484/TS2554 in the same run).
- Causes: verifying after a subset of edits without re-running the full check.
- Recovery: treat the whole report as one batch, apply all fixes, and verify once with the full `tsc --noEmit` run (the trajectory edited 7 files — including two edits to `post-job.tsx`, three to `jobs/$id.tsx`, and three to `jobs/index.tsx` — before getting a single clean run).

## Verification
Re-run the identical typecheck from the project directory and check the observable output:

- Command: `npx tsc --noEmit 2>&1 | head -40` (same directory, same form as the diagnostic run; use a cap larger than the original report).
- Pass condition: the tool result contains no `error TS` lines. The trajectory's passing result was exactly "(Bash completed with no output)".
- Cross-check each originally reported error is absent, by file and position, e.g.:
  - `src/routes/__root.tsx(1,23)` no longer reports TS6133 for `Outlet`.
  - `src/routes/jobs/$id.tsx(9,7)` no longer reports TS6133 for `BASE_URL`.
  - `src/routes/jobs/index.tsx(44,23)` no longer reports TS2554.
- Confirm no new `TS2304` (cannot find name) or `TS2554` lines were introduced by the deletions — the re-run covers this because it is a full project check.
- Confirm the edit count is bounded: `git diff --stat` (if a git repo is available) should list only the files named in the error report; this check was not performed in the trajectory and is optional.
- Out-of-scope note: passing `tsc --noEmit` proves type-level correctness only. It does not prove the app builds (`vite build`), starts, or renders; do not claim runtime success from this check alone.

## Examples
### Example 1: Batch-fix a mixed TS6133/TS1484/TS2554 report until `tsc --noEmit` is silent
- Input: `tsc --noEmit` report (parameterized as `<report>`) containing, among others:
  - `src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.` (and 4 more TS1484 in the same import, plus one in `src/context/auth.tsx`)
  - `src/routes/__root.tsx(1,23): error TS6133: 'Outlet' is declared but its value is never read.`
  - `src/routes/auth/register.tsx(4,42): error TS6133: 'Select' is declared but its value is never read.`
  - `src/routes/employer/post-job.tsx(31,9): error TS6133: 'user' is declared but its value is never read.`
  - `src/routes/jobs/$id.tsx(9,7): error TS6133: 'BASE_URL' is declared but its value is never read.` and `(19,10)` for `'applied'`
  - `src/routes/jobs/index.tsx(1,27): error TS6133: 'Link' ...`, `(28,9)` for `'navigate'`, `(44,23): error TS2554: Expected 1 arguments, but got 0.`
- Procedure:
  1. Run `npx tsc --noEmit 2>&1 | head -60` from `<project>/frontend` and capture the full report.
  2. TS1484: rewrite `import { CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from 'react'` as `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'`; similarly `import { createContext, useContext, useState, useEffect, ReactNode } from 'react'` → add `type` before `ReactNode`.
  3. TS6133 imports: `import { HeadContent, Outlet, Scripts, createRootRoute } from '@tanstack/react-router'` → `import { HeadContent, Scripts, createRootRoute } from '@tanstack/react-router'`; `import { Button, TextField, Alert, Card, Select } from '#/components/ui'` → drop `Select`; `import { createFileRoute, Link } from '@tanstack/react-router'` → `import { createFileRoute } from '@tanstack/react-router'`.
  4. TS6133 locals: delete `const BASE_URL = 'http://localhost:5000'`; replace `const { user } = useAuth()` with `useAuth()`; delete `const [applied, setApplied] = useState(false)` together with the `setApplied(true)` line; delete `const navigate = Route.useNavigate()`.
  5. TS2554: `const debounceRef = useRef<ReturnType<typeof setTimeout>>()` → `const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`.
  6. Re-run `npx tsc --noEmit 2>&1 | head -40`.
- Expected result: the second run returns no output ("Bash completed with no output"), i.e. zero `error TS` lines across the whole project.
- Parameterized values: `<project>` = the frontend package root; file paths, symbol names, and line/column numbers come from your own `<report>`.

### Example 2: State value unused but setter still called
- Input: TS6133 line `src/routes/jobs/$id.tsx(19,10): error TS6133: 'applied' is declared but its value is never read.` with file content containing `const [applied, setApplied] = useState(false)` and, further down, `setApplied(true)` after a successful submit.
- Procedure: Read the file region to locate all `setApplied` usages; delete the state declaration line; delete the `setApplied(true)` statement (keeping the surrounding success handling, e.g. `setApplySuccess(true)`); re-run `tsc --noEmit`.
- Expected result: no TS6133 for `applied`, and no new `TS2304: Cannot find name 'setApplied'`.
- Parameterized values: state name, setter name, and the retained sibling state (e.g. `applySuccess`) vary per project.

## Evidence
All from file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__original`.

Problem:
- source_index 216, source_part_index 0 (tool_call:Bash): `cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -60` — supports: the diagnostic command and project directory used.
- source_index 217, source_part_index 0 (tool_result): `src/routes/__root.tsx(1,23): error TS6133: 'Outlet' is declared but its value is never read.`; also `src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.` and TS6133 lines for `'Select'`, `'user'`, `'BASE_URL'`, `'applied'`, `'Link'`, `'navigate'`, plus TS1484 lines for `'CSSProperties'` and `'ReactNode'` — supports: the mixed error report and each reported symbol.

Actions:
- source_index 218, source_part_index 0 (tool_call:Edit): `"new_string": "import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'"` — supports: inline `type` prefix fix for TS1484.
- source_index 221, source_part_index 0 (tool_call:Edit): `"new_string": "import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'"` — supports: same fix pattern in a second file.
- source_index 223, source_part_index 0 (tool_call:Edit): `"old_string": "import { HeadContent, Outlet, Scripts, createRootRoute } from '@tanstack/react-router'", "new_string": "import { HeadContent, Scripts, createRootRoute } from '@tanstack/react-router'"` — supports: removing an unused import specifier for TS6133.
- source_index 227, source_part_index 0 (tool_call:Edit): `"old_string": "import { Button, TextField, Alert, Card, Select } from '#/components/ui'", "new_string": "import { Button, TextField, Alert, Card } from '#/components/ui'"` — supports: removing unused `Select` import.
- source_index 231–232, source_part_index 0 (tool_call:Read / tool_result): Read of `post-job.tsx` offset 27, limit 10, returning lines `31	  const { user } = useAuth()` and `32	  const router = useRouter()` — supports: reading the declaration region before editing.
- source_index 233, source_part_index 0 (tool_call:Edit): `"old_string": "  const { user } = useAuth()\n  const router = useRouter()", "new_string": "  useAuth()\n  const router = useRouter()"` — supports: keeping the hook call while dropping the unused destructured binding.
- source_index 237, source_part_index 0 (tool_call:Edit): `"old_string": "const BASE_URL = 'http://localhost:5000'\n\nfunction JobDetailPage() {", "new_string": "function JobDetailPage() {"` — supports: deleting an unused module constant.
- source_index 239, source_part_index 0 (tool_call:Edit): `"old_string": "  const [applied, setApplied] = useState(false)\n  const [applying, setApplying] = useState(false)", "new_string": "  const [applying, setApplying] = useState(false)"` — supports: removing the unused state declaration.
- source_index 241, source_part_index 0 (tool_call:Edit): `"old_string": "      await api.apply(fd)\n      setApplied(true)\n      setApplySuccess(true)", "new_string": "      await api.apply(fd)\n      setApplySuccess(true)"` — supports: also removing the orphaned setter call in the same file.
- source_index 244–245, source_part_index 0 (tool_call:Read / tool_result): Read of `jobs/index.tsx` returning lines `1	import { createFileRoute, Link } from '@tanstack/react-router'` and `28	  const navigate = Route.useNavigate()` — supports: inspecting the file before import/local removal.
- source_index 247, source_part_index 0 (tool_call:Edit): `"old_string": "import { createFileRoute, Link } from '@tanstack/react-router'", "new_string": "import { createFileRoute } from '@tanstack/react-router'"` — supports: removing unused `Link` import.
- source_index 249, source_part_index 0 (tool_call:Edit): `"old_string": "  const search = Route.useSearch()\n  const navigate = Route.useNavigate()", "new_string": "  const search = Route.useSearch()"` — supports: removing unused router hook result.
- source_index 252, source_part_index 0 (tool_call:Edit): `"old_string": "  const debounceRef = useRef<ReturnType<typeof setTimeout>>()", "new_string": "  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)"` — supports: TS2554 fix by supplying an explicit `undefined` initial value with a widened generic.

Verification:
- source_index 254, source_part_index 0 (tool_call:Bash): `cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -40` with description `TypeScript check after fixes` — supports: re-running the identical check after the batch of edits.
- source_index 255, source_part_index 0 (tool_result): `(Bash completed with no output)` — supports: the full project typecheck produced zero error lines, i.e. every TS6133/TS1484/TS2554 from the initial report was resolved.
- source_index 256, source_part_index 0 (assistant_text): `TypeScript passes with no errors. Now write the startup instructions file:` — supports: the agent's own conclusion tied to the empty re-run output (note: no build, dev-server, or test run followed these edits, so runtime success is unverified).

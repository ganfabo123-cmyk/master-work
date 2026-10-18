---
name: fix-strict-tsc-noemit-errors
description: Use when a TypeScript project with verbatimModuleSyntax and noUnusedLocals reports a batch of tsc --noEmit errors (TS1484 type-only imports, TS6133 unused declarations, TS2554 useRef without an argument). Helps the agent clear the entire error list with minimal, targeted edits and verify by rerunning the same typecheck. Requires a working tsc in the project (npx tsc --noEmit) and file-editing access. Do not use when errors are runtime, bundler, or lint errors, or when no rerun of the typecheck is possible.
---
# Fix TS1484/TS6133/TS2554 Errors from a tsc --noEmit Run

## Goal
Resolve every error reported by a single `tsc --noEmit` run (TS1484 type-only import violations, TS6133 unused declarations, TS2554 useRef called with 0 arguments) via minimal source edits, and confirm the fix by rerunning the identical typecheck until it produces no error output.

## Scope
### In scope
- Projects whose tsconfig enables `verbatimModuleSyntax` (triggers TS1484) and `noUnusedLocals` (triggers TS6133), typically modern React 19 / TanStack Start templates.
- Converting value imports used only as types to inline `type` modifiers (TS1484).
- Removing unused imports, unused destructured values, unused state bindings, and unused module constants flagged by TS6133, including removing dependent setter calls when a state binding is deleted.
- Fixing TS2554 on `useRef<T>()` with no argument (React 19 types require an initial value) by supplying an explicit `undefined` initial value.
- Verification by rerunning the exact same `npx tsc --noEmit` command.

### Out of scope
- Runtime bugs, bundler/build errors, ESLint issues, or errors not present in the typecheck output.
- Changing tsconfig flags (e.g., disabling `verbatimModuleSyntax` or `noUnusedLocals`) to silence errors.
- Refactoring behavior of components; only compile-safety edits are in scope.
- Backend (non-TypeScript) code.

## Inputs
- **tsc error list**: string; source: output of `npx tsc --noEmit` run in the project directory; required: yes; constraint: each line has the form `path(line,col): error TSnnnn: message`; default: 无.
- **Project root**: path; source: agent environment (e.g., the frontend directory containing `tsconfig.json`); required: yes; constraint: must contain tsconfig with `verbatimModuleSyntax` and `noUnusedLocals` enabled; default: 无.
- **Source files referenced by errors**: file contents; source: project files (read on demand before editing); required: yes; constraint: edit only files named in the error list; default: 无.
- **File-editing tool access**: capability; source: agent toolset; required: yes; constraint: ability to apply precise string replacements to source files; default: 无.
- **npx availability**: environment; source: project node_modules / PATH; required: yes; constraint: `npx tsc` must resolve the project's TypeScript; default: 无.

## Outputs
### Artifacts
- Edited source files (in place) at the paths named in the tsc error list: imports rewritten with inline `type` modifiers, unused declarations removed, `useRef` initialized with `undefined`.
- Verification record: output of the rerun `npx tsc --noEmit` command (expected: empty output).

### Success criteria
- Rerunning the identical `npx tsc --noEmit` command produces no error lines (empty output).
- Every error code from the original list (TS1484, TS6133, TS2554 in the observed run) is gone; no new errors were introduced.

### Failure criteria
- The rerun still reports any error from the original list or reports new errors introduced by the edits.
- The typecheck could not be rerun, so fixes remain unverified.

## Preconditions
- The project's TypeScript toolchain works: `npx tsc --noEmit` runs from the project directory (the observed project used `typescript ^6.0.2` with React 19 and TanStack Router).
- Generated route/type files (e.g., TanStack Router's `routeTree.gen.ts`) are already up to date; in the observed run `npx tsr generate` was executed before the typecheck. If route files are stale, regenerate them first, otherwise stop and report.
- The tsconfig genuinely enables `verbatimModuleSyntax` / `noUnusedLocals` (or equivalent strict unused checks); if the flags are absent, the error-driven procedure still applies but the preconditions should be re-checked.
- You have edit access to every file named in the error list.
- If any precondition fails (e.g., tsc cannot run), stop and report instead of editing blindly.

## Procedure
### Step 1: Run the typecheck and capture the full error list
- Actions: from the project directory run `npx tsc --noEmit` (optionally piped through `head -60` for readability, but treat the full list as the work queue).
- Inputs: project root.
- Outputs: ordered list of `path(line,col): error TSnnnn` lines.
- Cautions: do not start editing from memory of earlier runs; always work from a fresh capture.
- Preserve: the exact command, so verification reruns the identical command.
- Next: proceed to Step 2 grouped by error code.

### Step 2: Fix TS1484 by adding inline `type` modifiers
- Actions: for each TS1484 line, open the import and prefix each flagged identifier with `type `, keeping value imports untouched. Example applied: `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'`.
- Inputs: TS1484 error lines; file contents at the reported line/column.
- Outputs: edited import statements.
- Cautions: only identifiers named in the error are types; do not convert imports that are used as values in the same file.
- Preserve: import order and all value imports.
- Next: after all TS1484 lines are handled, continue within this step or move to Step 3.

### Step 3: Fix TS6133 by removing the unused declaration and its dependents
- Actions: for each TS6133 line, remove exactly the flagged declaration:
  - Unused named import: delete the identifier from the import list (e.g., remove `Outlet` from the TanStack Router import; remove `Select` from the component import; remove `Link` from `createFileRoute, Link`).
  - Unused hook result: replace `const navigate = Route.useNavigate()` with nothing when unused; replace `const { user } = useAuth()` with a bare `useAuth()` statement when the destructured `user` is never read (the observed post-job page called `useAuth()` without destructuring).
  - Unused module constant: delete the whole `const BASE_URL = 'http://localhost:5000'` declaration.
  - Unused state binding: delete the entire `const [applied, setApplied] = useState(false)` line AND its dependent call `setApplied(true)` elsewhere in the same function.
- Inputs: TS6133 error lines; file contents.
- Outputs: files with the flagged declarations removed.
- Cautions: when the error names one half of a `[value, setValue]` pair, grep the file for the setter before deleting; leaving `setApplied(true)` after removing the state causes a new TS2554/TS2304 error. When a destructure is flagged but the hook call itself may still matter for effects, keep the bare call rather than deleting it.
- Preserve: all code that still references remaining bindings; do not reformat untouched lines.
- Next: when the observed file context is unclear, read the file region (e.g., Read with offset/limit around the reported line) before editing; then proceed to Step 4.

### Step 4: Fix TS2554 on zero-argument useRef
- Actions: for `const debounceRef = useRef<ReturnType<typeof setTimeout>>()` reported as `Expected 1 arguments, but got 0`, change it to `const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`.
- Inputs: TS2554 error line; file contents.
- Outputs: initialized ref declaration.
- Cautions: keep the timer type in the generic; adding `| undefined` and passing `undefined` is required together under React 19 types.
- Preserve: the ref's name and all usage sites (`debounceRef.current` assignments/comparisons).
- Next: once every error line has a corresponding edit, go to Step 5.

### Step 5: Rerun the identical typecheck and confirm clean output
- Actions: rerun `npx tsc --noEmit` from the same directory.
- Inputs: same project root.
- Outputs: command result.
- Cautions: empty output is the pass signal; any output means iterate back to the specific new/remaining error line.
- Preserve: all edits from Steps 2-4 unless the rerun proves one introduced an error.
- Next: stop when output is empty; otherwise repeat Step 3/4 for the new error lines.

## Decision Rules
### When error is TS1484 ("is a type and must be imported using a type-only import")
Edit the named import to add inline `type ` before each flagged identifier. Keep any value imports in the same statement as plain identifiers. Do not split into a separate `import type` line unless the style requires it; inline modifiers were sufficient in the verified run.

### When error is TS6133 on a named import (e.g., 'Outlet', 'Select', 'Link')
Remove only that identifier from the import list.

### When error is TS6133 on a destructured hook value (e.g., 'user', 'navigate')
Remove the binding: drop `= Route.useNavigate()` (delete the statement if unused), or convert `const { user } = useAuth()` into a bare `useAuth()` call when the hook call must be preserved but the value is unused.

### When error is TS6133 on a state binding (e.g., 'applied')
Delete the `useState` line and search the same file for the paired setter; remove setter call sites too before rerunning.

### When error is TS6133 on a module-level constant (e.g., 'BASE_URL')
Delete the constant declaration entirely; do not rename or export it to silence the check.

### When error is TS2554 "Expected 1 arguments, but got 0" on useRef
Supply an explicit initial value of `undefined` and widen the generic with `| undefined`. Do not use a non-null assertion or cast to bypass the arity check.

### When the reported line/column does not match file contents (file changed since the run)
Re-run the typecheck to refresh positions instead of guessing the edit location.

## Invariants
- Edit only files and declarations named in the current tsc error list; unrelated files, formatting, and tsconfig flags stay untouched.
- Never disable or weaken compiler options (`verbatimModuleSyntax`, `noUnusedLocals`, etc.) to make errors disappear.
- Every deleted binding's dependent references (setter calls, JSX usages) are removed in the same pass, so no new undefined-identifier errors are introduced.
- The verification command is the same command that produced the errors (`npx tsc --noEmit` from the same directory); a build, dev-server start, or partial check does not count.
- No success is reported until the rerun output is observed to be empty; unverified or truncated runs are reported as such.
- Do not convert imports to `type` that are demonstrably used as values in the same file.

## Common Failures
### Failure: Editing an unused state binding without removing its setter call
- Symptoms: TS6133 for 'applied' persists as a new error (`setApplied` is not defined / TS2554) after deleting `const [applied, setApplied] = useState(false)`.
- Causes: the setter is referenced elsewhere in the same component (e.g., inside the submit handler).
- Recovery: grep the file for the setter name and delete those call sites, then rerun the typecheck.

### Failure: Treating a destructured-but-unused value as fully removable
- Symptoms: deleting `const { user } = useAuth()` outright would drop a hook call whose side effects may matter, or leaves the file without the import.
- Causes: the error flags only the unused binding, not the hook call itself.
- Recovery: in the verified run the fix was to keep a bare `useAuth()` statement; apply the same minimal change unless removing the call is provably safe.

### Failure: Declaring the fix done after the first typecheck without rerunning
- Symptoms: reported "fixed" while the rerun still shows remaining or newly introduced errors; cause is unverified claim.
- Causes: skipping Step 5.
- Recovery: always rerun the identical `npx tsc --noEmit` and iterate until empty output is observed.

### Failure: Line/column mismatch after earlier edits shift positions
- Symptoms: an Edit fails or targets the wrong line because prior removals changed line numbers.
- Causes: stale positions from the original error output.
- Recovery: apply edits by unique string content (old_string anchors) rather than raw line numbers, or re-run tsc to refresh positions.

## Verification
- Rerun `npx tsc --noEmit` from the same project directory after all edits; the pass signal is empty command output (in the verified run the rerun returned "(Bash completed with no output)").
- Cross-check that every error code from the original list is absent in the rerun: no TS1484, no TS6133, no TS2554 lines appear.
- Spot-check one edited import: identifiers used only as types carry inline `type ` modifiers, value imports do not.
- Spot-check the state-removal file: no references to the removed setter remain (search the file for the setter name).
- Spot-check the ref fix: declaration reads `useRef<T | undefined>(undefined)` and existing `debounceRef.current` usages are intact.
- If any check fails or the command cannot be executed, report the run as unverified rather than passing.

## Examples
### Example 1: Clear a full tsc batch in a TanStack Start + React 19 frontend
- Input: `npx tsc --noEmit` output listing TS1484 for five React type imports in `src/components/ui.tsx` and one in `src/context/auth.tsx`; TS6133 for `Outlet` in `src/routes/__root.tsx`, `Select` in `src/routes/auth/register.tsx`, `user` in `src/routes/employer/post-job.tsx`, `BASE_URL` and `applied` in `src/routes/jobs/$id.tsx`, `Link` and `navigate` in `src/routes/jobs/index.tsx`; TS2554 at `src/routes/jobs/index.tsx(44,23)`.
- Procedure: (1) add inline `type ` modifiers to the flagged React imports; (2) remove `Outlet`, `Select`, `Link` from their import lists; (3) replace `const { user } = useAuth()` with bare `useAuth()` in post-job; (4) delete `const BASE_URL = 'http://localhost:5000'`; (5) delete the `applied` state line plus the `setApplied(true)` call; (6) drop `const navigate = Route.useNavigate()`; (7) change `useRef<ReturnType<typeof setTimeout>>()` to `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`; (8) rerun the identical command.
- Expected result: the rerun produces no output, meaning zero errors; parameterize file paths, identifier names, and the ref's generic type to the actual project.
- Parameterized values observed: TypeScript ^6.0.2, React ^19.2.0, @tanstack/react-router latest, `verbatimModuleSyntax` + unused-locals checks enabled.

### Example 2: Minimal edit for an unused destructured auth value
- Input: TS6133 `src/routes/employer/post-job.tsx(31,9): error TS6133: 'user' is declared but its value is never read.` while the file begins the component with `const { user } = useAuth()`.
- Procedure: read the component region to confirm `user` is unused, then replace the destructure with a bare `useAuth()` statement, keeping the `useAuth` import.
- Expected result: TS6133 for `user` disappears on rerun without introducing TS2304/unused-import errors; the hook call itself is preserved as in the verified run.

## Evidence
- problem: A single typecheck surfaces the mixed error batch (TS1484, TS6133, TS2554) — file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 217, source_part_index: 0, quote: "src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.", supports: TS1484 under verbatimModuleSyntax; same result also contains "src/routes/__root.tsx(1,23): error TS6133: 'Outlet' is declared but its value is never read." and "src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0." — the batch scope of the skill.
- action (TS1484): inline type modifiers — file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 218, source_part_index: 0, quote: "import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'", supports: the exact fix form for TS1484.
- action (TS6133 unused import): remove identifier — file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 223, source_part_index: 0, quote: "import { HeadContent, Scripts, createRootRoute } from '@tanstack/react-router'", supports: dropping `Outlet` from the root route import.
- action (TS6133 unused destructured hook value): keep bare call — file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 233, source_part_index: 0, quote: "useAuth()", supports: converting `const { user } = useAuth()` to a bare call when `user` is unused.
- action (TS6133 unused state plus dependent setter): delete both — file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 239, source_part_index: 0, quote: "  const [applying, setApplying] = useState(false)", supports: the `applied` state line was removed leaving only the `applying` state; and source_index: 241, source_part_index: 0, quote: "      await api.apply(fd)", supports: the `setApplied(true)` line between `api.apply` and `setApplySuccess(true)` was removed in the same pass.
- action (TS2554 useRef arity): explicit undefined — file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 252, source_part_index: 0, quote: "  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)", supports: the verified fix form for zero-argument useRef under React 19 types.
- verification: rerun of the identical typecheck is clean — file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 254, source_part_index: 0, quote: "cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -40", supports: the verification command matches the original check; source_index: 255, source_part_index: 0, quote: "(Bash completed with no output)", supports: observed clean output proving all listed errors were resolved.

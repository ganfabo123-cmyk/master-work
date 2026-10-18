---
name: fix-ts6133-unused-and-related-tsc-errors
description: Use when a TypeScript check of a freshly scaffolded TanStack Start / React 19 frontend reports TS6133 unused declarations, often alongside TS1484 type-only import errors and a TS2554 useRef arity error. Helps the agent classify each error, apply the minimal edit per class (inline type imports, remove unused bindings, supply useRef's required initial value), and re-run the check until it is clean. Requires a project with npx tsc --noEmit available and the tsconfig enabling verbatimModuleSyntax and noUnusedLocals. Do not use for runtime bugs, build failures, or type errors that are not in these three classes.
triggers:
  - "TS6133"
  - "noUnusedLocals"
  - "TS1484"
  - "TS2554"
---
# Fix TS6133 Unused-Declaration Errors (and Sibling TS1484/TS2554) in a TanStack Start React Project

## Goal
Clear the TS6133 "declared but never read" errors that a `tsc --noEmit` check reports in a freshly scaffolded TanStack Start / React 19 frontend, along with the TS1484 type-only-import errors and TS2554 useRef arity error that appeared in the same check run, and end with a clean type check.

## Scope
### In scope
- Running `tsc --noEmit` on a TanStack Start (file-based routing) + React 19 + TypeScript project and fixing the error classes observed in that run:
  - TS6133: unused imports, unused destructured variables, unused local constants and unused `useState` values.
  - TS1484: type-only import required when `verbatimModuleSyntax` is enabled.
  - TS2554: `useRef()` called with no argument, which React 19 types forbid.
- Removing a `useState` pair (value and setter) or a route hook call when the value is never read.
- Regenerating the TanStack route tree (`tsr generate`) after adding route files so the type check sees all routes.

### Out of scope
- Runtime behavior, dev-server startup, production builds, or lint/format checks.
- Errors in other TypeScript classes (module resolution, JSX typing, Mongoose/Express backend code).
- Changing `tsconfig.json` to relax `noUnusedLocals`, `noUnusedParameters`, or `verbatimModuleSyntax`.
- Fixing the Node/Express backend, which is plain JavaScript in this project.

## Inputs
- **Frontend project root**: directory path (e.g. `<project>/frontend`); required; must contain `package.json` and `tsconfig.json`; source: shell environment / agent state; default: none.
- **`tsc` availability**: the project must have TypeScript installed so `npx tsc --noEmit` runs locally; required; source: project `devDependencies` (observed `typescript` in `devDependencies`); default: `npx tsc --noEmit`.
- **`tsconfig.json` settings**: enables `verbatimModuleSyntax` and unused-symbol checking (`noUnusedLocals`/`noUnusedParameters` implied by TS6133 being reported); required to know which fixes apply; source: project config; default: none.
- **Type-check error list**: full output of `npx tsc --noEmit`; required; source: Bash tool result; default: none.
- **React version**: React 19 types, which make `useRef()` with zero arguments a TS2554 error; required to choose the correct useRef fix; source: `package.json` (`react ^19.2.0`); default: none.
- **Route tree generator**: `tsr` CLI available via `npx tsr generate`; needed only when new route files were added since the last generation; source: project `devDependencies` (`@tanstack/router-cli`); default: none.

## Outputs
### Artifacts
- Edited source files under `<frontend>/src` (imports, unused bindings, `useRef` call), location per the `file(path, line, column)` reported by `tsc`; format: TypeScript/TSX source with minimal diffs.
- Regenerated `<frontend>/src/routeTree.gen.ts` via `tsr generate` when new route files exist.
- Final type-check result: `npx tsc --noEmit` run producing no error lines.

### Success criteria
- `npx tsc --noEmit` in the frontend directory completes with no output (no TS6133, TS1484, or TS2554, and no newly introduced errors).
- Every edited file still compiles in context: no symbol removed is referenced elsewhere.

### Failure criteria
- `tsc --noEmit` still reports any error after the edits.
- An edit removes a symbol that other code still uses, producing new TS errors.
- The check cannot run at all (tsc not installed / wrong directory).

## Preconditions
- `npx tsc --noEmit` must run inside the frontend project root and exit without crashing; if tsc is not installed (`npx` prompts to install or fails), install project dependencies first (`npm install` in that directory) and stop until it works.
- `tsconfig.json` must actually enable the strictness behind these errors (`verbatimModuleSyntax` for TS1484, unused-symbol checking for TS6133); if the config differs, re-classify the errors before applying these fixes.
- The full error list must be captured before editing; do not start fixing from a truncated list that hides files beyond the head limit — re-run without the limit or with a larger one when needed.
- New route files (e.g. `routes/jobs/$id.tsx`, `routes/employer/dashboard.tsx`) must have been generated into `routeTree.gen.ts` (run `npx tsr generate`) before the check, otherwise route-related type errors will mix with the unused-symbol errors.
- No runtime verification environment (MongoDB, SMTP, dev server) is required for this skill; if one is expected, that is out of scope here.

## Procedure
### Step 1: Regenerate the route tree (only if route files changed)
- Actions: from the frontend root, run `npx tsr generate`. If it prints nothing and exits 0, the generated `src/routeTree.gen.ts` now includes every route file.
- Inputs: `src/routes/**` files, `tsr` CLI.
- Outputs: updated `src/routeTree.gen.ts`.
- Cautions: only do this when new/renamed route files exist; a silent run is the normal success signal.
- Preserve: never hand-edit `routeTree.gen.ts`.
- Next: proceed to Step 2.

### Step 2: Capture the full type-check error list
- Actions: run `npx tsc --noEmit` (optionally piped through `head` for a first glance, but re-run unpiped if the list was truncated). Read the whole output before editing.
- Inputs: project root, tsc.
- Outputs: list of `file(line,col): error TSxxxx: message` lines.
- Cautions: one file can produce several independent errors (e.g. five TS1484 on one import line plus TS6133 elsewhere); fix by class, not by file.
- Preserve: keep the raw output for comparison in Step 5.
- Next: classify each error per Decision Rules and proceed to Step 3.

### Step 3: Fix TS1484 (type-only imports) first
- Actions: for each TS1484, edit the import so every type-only specifier carries the inline `type` modifier, e.g. `import { type CSSProperties, type ReactNode } from 'react'`. Mixed imports keep value specifiers without `type`.
- Inputs: error list lines with TS1484.
- Outputs: updated import statements.
- Cautions: apply the `type` modifier inline per specifier rather than converting to a separate `import type` block, so value imports on the same line keep working.
- Preserve: import order and all value imports.
- Next: continue with remaining TS1484 lines, then Step 4.

### Step 4: Fix TS6133 (unused declarations)
- Actions: for each TS6133, pick the branch in Decision Rules and edit exactly that file: remove unused import specifiers, replace a destructured-but-unused variable with a bare hook call (e.g. `const { user } = useAuth()` → `useAuth()` when `user` is unread but the call must stay), delete an unused local constant, delete an unread `useState` pair together with its setter call sites, or delete an unused route-hook call (`Route.useNavigate()`).
- Inputs: error list lines with TS6133; the file content around the reported line (Read the file region first when unsure whether the symbol is referenced elsewhere).
- Outputs: minimal diffs to the named files.
- Cautions: when removing a `useState` value like `applied`, also remove every `setApplied(...)` call, or TS6133/TS6133-adjacent errors persist; grep the file for the symbol before deleting.
- Preserve: state that is actually read (e.g. `applySuccess`, `applying`) and any setter that is called.
- Next: proceed to Step 5.

### Step 5: Fix TS2554 (useRef arity) and re-check
- Actions: replace `useRef<ReturnType<typeof setTimeout>>()` with `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`; then re-run `npx tsc --noEmit` and confirm it prints nothing.
- Inputs: error list lines with TS2554; project root.
- Outputs: edited file; empty tsc output.
- Cautions: React 19's types require the initial-value argument; passing `undefined` with the widened type parameter keeps later `x = useRef<T>()`-style usage type-safe.
- Preserve: the ref's usage sites (`clearTimeout(debounceRef.current)` etc.).
- Next: if tsc is clean, stop; otherwise repeat Steps 3–4 for any remaining or newly surfaced errors.

## Decision Rules
### When the error is TS1484 on a mixed import line
Add the inline `type` modifier to each type-only specifier on that line; keep value specifiers unchanged. Observed fix: `import { CSSProperties, ReactNode, InputHTMLAttributes, ... } from 'react'` → `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, ... } from 'react'`.

### When TS6133 names an imported component/value that no JSX or code uses
Remove just that specifier from the import list (e.g. drop `Outlet` from the `@tanstack/react-router` import in the root route; drop `Select` from the `#/components/ui` import in the register page; drop `Link` from the jobs-list page). Do not delete the whole import if other specifiers are used.

### When TS6133 names a destructured variable from a hook call that was kept for other reasons
Keep the hook call, drop only the destructuring: `const { user } = useAuth()` → `useAuth()`. Use this when you are not willing to remove the hook side effects, and the variable is genuinely unread in that component. (If the hook call itself is pointless, removing it entirely is also acceptable — choose one and verify with tsc.)

### When TS6133 names an unused module-level constant
Delete the constant declaration (e.g. `const BASE_URL = 'http://localhost:5000'` in the job-detail page, where resume links were built elsewhere). Grep the file first to confirm there is no other reference.

### When TS6133 names a `useState` value that is never read but whose setter is called
Delete the entire state pair and the setter calls together: `const [applied, setApplied] = useState(false)` plus `setApplied(true)` are removed in favor of an existing `applySuccess` state that is actually rendered. If no alternate state exists, either read the value in the UI or remove the whole mechanism; do not leave the setter call behind.

### When TS6133 names an unused route hook call
Delete the call, e.g. `const navigate = Route.useNavigate()` in a component that only reads search state. Keep `Route.useSearch()` if it is used.

### When the error is TS2554 at a `useRef<T>()` call with no arguments (React 19 types)
Provide the required initial value: `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`. Do not add `// @ts-ignore` or loosen tsconfig.

### When new route files exist but route links report unknown paths
Run `npx tsr generate` before (or as part of) the check cycle; the generation run completes silently on success.

## Invariants
- Do not modify `tsconfig.json` (or add `@ts-ignore`/`@ts-expect-error`) to silence these errors; fix the source instead.
- Do not touch files or lines not named by an error, except the paired setter calls of a state you delete.
- Do not hand-edit the generated `routeTree.gen.ts`; regenerate it with the CLI.
- Do not report success until `npx tsc --noEmit` has been re-run after the last edit and produced no error output.
- Do not delete a `useState` value while leaving its setter calls, and do not delete a setter call while leaving the state; the pair moves together.
- Do not widen a type to `any` to remove an error; the useRef fix keeps the specific timer type plus `undefined`.
- Do not claim runtime behavior (server start, login flow, application submission) is verified — this skill only establishes type-check cleanliness.

## Common Failures
### Failure: TS6133 persists after editing because a setter call was left behind
- Symptoms: `tsc --noEmit` still reports `TS6133: 'applied' is declared but its value is never read` (or TS6133-style complaints on the sibling) after removing only the `useState` line, or a new TS error appears for an undefined `setApplied`.
- Causes: state pair and its call sites were not removed together; the code path that set the value was still present.
- Recovery: search the file for every occurrence of the value and setter, delete all of them in one pass, then re-run tsc. Confirmed in this session only in its successful form: both `const [applied, setApplied] = useState(false)` and `setApplied(true)` were removed together.

### Failure: removing an import breaks another reference
- Symptoms: new `TS2304 Cannot find name` or `TS2551` errors after pruning an import specifier.
- Causes: the symbol was used in a part of the file not inspected before deletion.
- Recovery: restore the specifier, re-read the whole file, and choose the correct branch (keep the import, remove the actual unused one).

### Failure: tsc still reports TS2554 after "fixing" useRef
- Symptoms: `Expected 1 arguments, but got 0` remains.
- Causes: the argument was added without widening the type parameter, or a different zero-argument call site exists.
- Recovery: use `useRef<T | undefined>(undefined)` at the reported line and re-check for additional zero-argument `useRef` calls.

### Failure: fixing errors before regenerating the route tree
- Symptoms: errors reference stale routes, or newly added route files are not visible to the checker at all.
- Causes: `routeTree.gen.ts` is generated output and only updated by `tsr generate`.
- Recovery: run `npx tsr generate` in the frontend root, then re-run `tsc --noEmit` before making further edits.

### Failure: truncated error list leads to partial fixes
- Symptoms: after one round of fixes and re-running tsc, more TS6133/TS1484 errors appear from files never seen.
- Causes: the first run was piped through `head`, cutting off the list.
- Recovery: re-run `npx tsc --noEmit` without truncation (or with a larger limit) until the output is empty; the fix loop is not done until a full run is clean.

## Verification
- Run `npx tsc --noEmit` from the frontend project root after all edits; success is an empty output stream and zero exit status (the observed clean run printed only "(Bash completed with no output)").
- Confirm the error count went from the full classified list (TS1484 + TS6133 + TS2554 lines) to zero in a single un-truncated run, not merely fewer lines under `head`.
- Spot-check each edited file compiles in context by re-reading the edited import/binding lines and confirming no remaining reference to a removed symbol (grep for the symbol name within the file).
- Confirm `tsr generate` ran successfully (silent, exit 0) before the final check when route files were added in the same session.
- Do not treat a passing `tsc` as evidence that the app runs; runtime, build, and backend checks are separate and were not performed by this skill.

## Examples
### Example 1: Clear a mixed TS6133 / TS1484 / TS2554 report in a TanStack Start frontend
- Input: `npx tsc --noEmit` in the frontend root reports (among others): `src/routes/__root.tsx(1,23): error TS6133: 'Outlet' is declared but its value is never read.`, `src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.`, and `src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.` React is v19; `verbatimModuleSyntax` is on.
- Procedure: (1) ensure `npx tsr generate` has run because new route files (`routes/jobs/$id.tsx`, `routes/employer/dashboard.tsx`, `routes/candidate/dashboard.tsx`, `routes/auth/*`) were added; (2) convert the React type imports to inline type modifiers; (3) remove `Outlet`, `Select`, `Link`, `BASE_URL`, the unread `applied` state with its `setApplied(true)` call, the unread destructured `user` from `useAuth()`, and the unused `Route.useNavigate()` call; (4) change `useRef<ReturnType<typeof setTimeout>>()` to `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`; (5) re-run `npx tsc --noEmit`.
- Expected result: the second `npx tsc --noEmit` produces no output, i.e. zero remaining errors.
- Parameterized values: frontend root `<project>/frontend`; timer type `ReturnType<typeof setTimeout>`; token names `Outlet`, `Select`, `Link`, `BASE_URL`, `applied`, `user`, `navigate`; error codes TS6133, TS1484, TS2554.

### Example 2: Remove an unread state pair cleanly
- Input: job-detail page where `const [applied, setApplied] = useState(false)` exists but the UI reads a separate `applySuccess` boolean; tsc reports `TS6133: 'applied' is declared but its value is never read`.
- Procedure: read the file, locate every `setApplied` call (one in the apply handler's success branch), delete the `useState` line and the `setApplied(true)` statement, keeping `setApplySuccess(true)`.
- Expected result: the TS6133 line disappears and no new undefined-identifier error appears; the page still distinguishes success via `applySuccess`.
- Parameterized values: removed symbol `applied`; kept symbol `applySuccess`; call site inside `handleApply`'s `try` block.

## Evidence
- problem: file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`, source_index 217, source_part_index 0 — the type check surfaced the TS6133 errors targeted by this skill together with TS1484 and TS2554 in the same run. quote: "src/routes/__root.tsx(1,23): error TS6133: 'Outlet' is declared but its value is never read.\nsrc/routes/auth/register.tsx(4,42): error TS6133: 'Select' is declared but its value is never read.\nsrc/routes/employer/post-job.tsx(31,9): error TS6133: 'user' is declared but its value is never read.\nsrc/routes/jobs/$id.tsx(9,7): error TS6133: 'BASE_URL' is declared but its value is never read.\nsrc/routes/jobs/$id.tsx(19,10): error TS6133: 'applied' is declared but its value is never read.\nsrc/routes/jobs/index.tsx(1,27): error TS6133: 'Link' is declared but its value is never read.\nsrc/routes/jobs/index.tsx(28,9): error TS6133: 'navigate' is declared but its value is never read.\nsrc/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0." supports: confirms the exact error classes (TS6133 unused declarations, TS1484 type-only imports, TS2554 useRef arity) that the procedure fixes, and their per-file/per-line locations.

- problem: file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`, source_index 216, source_part_index 0 — the check command used to obtain the error list. quote: "cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -60" supports: shows the verification command is `npx tsc --noEmit` run from the frontend project root (and that piping through `head` risks truncation).

- action: file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`, source_index 218, source_part_index 0 — the TS1484 fix applied inline type modifiers on the existing import line. quote: "import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'" supports: demonstrates the per-specifier `type` modifier edit that clears TS1484 under `verbatimModuleSyntax`.

- action: file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`, source_index 223, source_part_index 0 — the unused `Outlet` import was pruned while keeping other specifiers. quote: "import { HeadContent, Scripts, createRootRoute } from '@tanstack/react-router'" supports: shows the minimal-import-removal pattern for TS6133 on an imported symbol (old string was "import { HeadContent, Outlet, Scripts, createRootRoute } from '@tanstack/react-router'").

- action: file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`, source_index 233, source_part_index 0 — the unread destructured `user` was replaced by a bare `useAuth()` call. quote: "useAuth()\n  const router = useRouter()" supports: demonstrates keeping the hook call while dropping the unused binding (old string was "const { user } = useAuth()\n  const router = useRouter()").

- action: file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`, source_index 239 and 241, source_part_index 0 — the unread `applied` state pair was removed together with its setter call. quote: "const [applying, setApplying] = useState(false)" supports: after the edit the `applied` useState declaration was gone (old string included "const [applied, setApplied] = useState(false)"); source_index 241's edit removed "setApplied(true)" from the apply handler, confirming the state-and-setter move together.

- action: file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`, source_index 252, source_part_index 0 — the TS2554 useRef fix supplied the required initial value. quote: "const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)" supports: demonstrates the React 19 useRef arity fix (old string was "const debounceRef = useRef<ReturnType<typeof setTimeout>>()").

- action: file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`, source_index 212, source_part_index 0 — route tree regeneration before the check. quote: "cd d:/CODSOFT/JOB_BOARD/frontend && npx tsr generate 2>&1" supports: shows regenerating the TanStack route tree after adding route files so the type checker sees all routes.

- verification: file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`, source_index 254, source_part_index 0 — the post-fix re-check command. quote: "cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -40" supports: the same type check was re-run after all edits.

- verification: file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`, source_index 255, source_part_index 0 — the re-check result: no errors remained. quote: "(Bash completed with no output)" supports: empty tsc output verifies that all TS6133, TS1484, and TS2554 errors were cleared by the edits; this is type-check-only evidence, not runtime verification.

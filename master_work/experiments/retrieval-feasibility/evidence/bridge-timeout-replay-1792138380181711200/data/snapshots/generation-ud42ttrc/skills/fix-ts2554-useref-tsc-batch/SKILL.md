---
name: fix-ts2554-useref-tsc-batch
description: Use when `npx tsc --noEmit` reports TS2554 "Expected 1 arguments, but got 0" on a zero-argument `useRef<T>()` call together with TS1484 type-only-import and TS6133 unused-declaration errors in a TypeScript project. Helps the agent give the ref an explicit initializer, mark type imports with `type`, remove the exact unused bindings, and re-run the typecheck until it prints nothing. Requires a tsconfig-based project where `npx tsc --noEmit` runs and edit access to the reported files. Do not use when TS2554 points at a function other than `useRef`, or when the errors are type mismatches, missing modules, or build/runtime failures.
triggers:
  - "TS2554"
  - "Expected 1 arguments, but got 0"
  - "TS6133"
  - "TS1484"
---
# Fix TS2554 useRef initializer and clear the accompanying tsc --noEmit batch

## Goal
Eliminate the `TS2554: Expected 1 arguments, but got 0` error raised at a zero-argument `useRef<T>()` call, together with the TS1484 and TS6133 errors reported in the same `tsc --noEmit` run, so that a repeat typecheck of the project produces no output and no compiler configuration is changed.

## Scope
### In scope

- TS2554 raised at a zero-argument `useRef<T>()` call in a React project (observed with react / @types/react ^19.2.0 and typescript ^6.0.2).
- TS1484 messages ("is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled") for individual import specifiers.
- TS6133 messages ("is declared but its value is never read") for unused import specifiers, unused locals, and unread state bindings, reported in the same batch.
- Batch-fixing these in one pass and gating on a single re-run of `npx tsc --noEmit` that prints nothing.

### Out of scope

- TypeScript codes other than TS2554, TS1484, TS6133 — the trajectory provides no evidence for fixing them.
- Changing tsconfig or package versions to silence errors (never done or verified in the trajectory).
- `vite build`, lint/format, tests, dev-server startup, and runtime behavior: only `tsc --noEmit` was verified in the trajectory, so no claims about those.

## Inputs
1. **tsc --noEmit output** — Type: text, one `path(line,col): error TSxxxx: message` per line. Source: Bash tool result. Required: yes. Constraints: run from the TypeScript project root (trajectory: `cd <project>/frontend && npx tsc --noEmit 2>&1 | head -60`); a `head -N` pipe truncates, so confirm the output was not cut off before editing. Default: 无.
2. **Source context at each reported position** — Type: numbered source text. Source: Read tool result. Required: yes. Constraints: read around the reported line/column before deleting or rewriting anything; TS6133 symbols must be checked for every read/write in the file. Default: 无.
3. **Project compiler configuration** — Type: tsconfig plus installed package versions. Source: project files. Required: yes. Constraints: the TS1484 rule form (`import { type X }`) applies only when `verbatimModuleSyntax` is enabled, which the error text itself states; observed versions: react ^19.2.0, @types/react ^19.2.0, typescript ^6.0.2. Default: 无.
4. **Edit access to the reported files** — Type: file edit tool. Source: agent toolset. Required: yes. Constraints: in-place edits to exactly the files and symbols the compiler named; no config files. Default: 无.

## Outputs
### Artifacts

- Edited source files in place, e.g. `<project>/frontend/src/components/ui.tsx`, `<project>/frontend/src/context/auth.tsx`, `<project>/frontend/src/routes/**.tsx` — format: TS/TSX with `type` modifiers on type-only import specifiers, unused bindings removed, and the `useRef` call carrying an explicit initializer (trajectory edit: `  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`).
- Typecheck transcript: the stdout of `npx tsc --noEmit` re-run after the edits (expected: empty).

### Success criteria

- The re-run prints no diagnostics at all (trajectory result: `(Bash completed with no output)`), i.e. no line containing `error TS2554`, `error TS1484`, or `error TS6133`.
- The fix required no tsconfig or dependency-version changes.

### Failure criteria

- Any error line remains in the re-run output.
- Errors were "fixed" by loosening compiler options (not performed in the trajectory and not acceptable).
- The re-run was never executed, or its output was truncated so a clean result cannot be concluded — then the batch is unverified.

## Preconditions
- A directory holding a tsconfig-based TypeScript project where `npx tsc --noEmit` runs with the local toolchain (trajectory: the frontend app of a job-board repository, npm available, typescript ^6.0.2, react / @types/react ^19.2.0).
- A completed compiler run whose output includes TS2554 at a `useRef` call site and/or TS1484 and TS6133 messages. If TS2554 names a different function, stop: the initializer rule in this skill does not apply, and that function's signature must be analyzed instead.
- Evidence that `verbatimModuleSyntax` is enabled — supplied by the TS1484 message text itself; without it, the `import { type X }` rewrite is the wrong form.
- Read access to the reported files (to inspect line context) and edit access to them.
- If any of these cannot be confirmed, report the gap and stop instead of guessing a fix.

## Procedure
### Step 1: Capture the full error batch

- actions: From the project directory run `npx tsc --noEmit` and keep the complete output (trajectory: `cd <project>/frontend && npx tsc --noEmit 2>&1 | head -60`), listing every `file(line,col): error TSxxxx`.
- inputs: project directory; local TypeScript install.
- outputs: grouped error list (TS2554 / TS1484 / TS6133).
- cautions: a `head -N` pipe truncates; if more lines are plausible than the limit, re-run with a larger limit before editing.
- preserve: do not touch tsconfig or package versions.
- next condition: proceed when each error has file, line, column, and code.

### Step 2: Read the source at each reported position

- actions: Read each file around the reported line — the trajectory read `src/routes/jobs/index.tsx` (offset 1, limit 50) and confirmed line 44 is `const debounceRef = useRef<ReturnType<typeof setTimeout>>()`.
- inputs: file paths and line numbers from Step 1.
- outputs: confirmed meaning of each flagged symbol.
- cautions: for TS6133 "declared but its value is never read", search the file for both reads and writes before deleting; state can be written but never read.
- preserve: surrounding logic and unflagged code.
- next condition: every error site is understood.

### Step 3: Fix TS2554 by giving `useRef` an explicit initial value

- actions: replace the zero-argument call with one that passes an initializer and widens the type parameter so `undefined` is assignable: old `  const debounceRef = useRef<ReturnType<typeof setTimeout>>()` → new `  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`.
- inputs: the TS2554 line plus its Step 2 context.
- outputs: updated `useRef` call.
- cautions: the `| undefined` widening is part of the fix — passing `undefined` while the parameter type excludes it leaves an assignability problem; code that reads `ref.current` must tolerate `undefined` (the trajectory's `clearTimeout(debounceRef.current)` does).
- preserve: the ref's role and all its call sites.
- next condition: this site is addressed; TS2554 is only claimed fixed after Step 6.

### Step 4: Fix TS1484 by making type imports type-only

- actions: for every specifier named in a TS1484 message add the `type` modifier, e.g. `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'` and `import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`.
- inputs: TS1484 lines and the import declarations.
- outputs: updated import declarations.
- cautions: convert only specifiers the compiler named; value imports (hooks, components) must stay unmodified or a new error appears.
- preserve: module specifiers and import order.
- next condition: all TS1484 specifiers carry `type`.

### Step 5: Fix TS6133 by removing the named unused bindings and their dependents

- actions: remove exactly what the compiler named — an unused import specifier (`Outlet` from `@tanstack/react-router`, `Select` from the shared UI module, `Link` from the router import), an unused local (`BASE_URL`, `navigate`), a hook-destructured binding that is never read (`const { user } = useAuth()` → `useAuth()`, keeping the hook call), and an unread state binding together with its setter call sites (`applied` removed together with `setApplied(true)`).
- inputs: TS6133 lines plus Step 2 context.
- outputs: files with the flagged bindings deleted.
- cautions: never remove the hook call itself; remove every write of a deleted state variable in the same edit, otherwise the setter becomes the next TS6133.
- preserve: everything the compiler did not flag.
- next condition: all TS6133 names addressed.

### Step 6: Re-run the typecheck and stop on a clean result

- actions: re-run the same command (trajectory: `cd <project>/frontend && npx tsc --noEmit 2>&1 | head -40`).
- inputs: project directory.
- outputs: empty output means done (trajectory: `(Bash completed with no output)`).
- cautions: this run verifies the batch as a whole; it does not attribute any individual edit.
- preserve: no configuration changes.
- next/stop condition: stop when the output is empty; if any error line remains, return to Step 2 with the new output.

## Decision Rules
### When TS2554 lands on a zero-argument `useRef<T>()` call

Pass an explicit initializer and widen the parameter type: `useRef<T | undefined>(undefined)`.

### When TS1484 names a specific import specifier

Add the `type` keyword to that specifier only; leave value specifiers untouched.

### When TS6133 names an imported binding

Delete that specifier from the import list, or the whole declaration if it becomes empty.

### When TS6133 names a binding destructured from a hook

Keep the hook call, drop only the binding: `const { user } = useAuth()` → `useAuth()`.

### When TS6133 names state that is written but never read

Delete the state declaration and all of its setter call sites in the same edit.

### When the run mixes several codes

Apply the fixes as one batch and gate on a single re-run of `tsc --noEmit` (the trajectory pattern); do not attribute the clean result to any single edit.

## Invariants
- Never modify tsconfig or compiler options to make errors disappear.
- Only remove identifiers the compiler explicitly named as unread; leave all other code untouched.
- Keep required hook calls in place; only their unused destructured bindings may be removed.
- Do not skip the `tsc --noEmit` re-run after the edits — it is the only accepted proof for this skill.
- Do not report the typecheck as passing without the observed empty output.
- Do not claim build, dev-server, or runtime success: only the typecheck was verified in the trajectory.
- Do not attribute the final clean run to one edit when several edits landed before it.

## Common Failures
### Failure: `useRef` initializer added without widening the type parameter

- symptoms: an assignability error appears for `undefined`, or TS2554 persists.
- causes: `undefined` was passed while the type argument still excludes it — the reason the applied fix writes `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`; the narrower form was not attempted in the trajectory, so this cause is inferred from the fix shape.
- recovery: widen the parameter to `T | undefined` and re-run the typecheck.

### Failure: state binding deleted but its setter call kept

- symptoms: the next run reports a new TS6133 naming `setXxx`.
- causes: partial removal of an unread state variable; the trajectory avoided this by removing `applied` and `setApplied(true)` in one edit, so the failure itself was not observed.
- recovery: delete every setter call site together with the state declaration.

### Failure: truncated typecheck output mistaken for a clean run

- symptoms: remaining errors exist below the `head -N` cutoff while the visible portion looks short.
- causes: piping `tsc --noEmit` through `head` with too small a limit (the trajectory used `head -60` then `head -40`); not observed to cause a wrong conclusion here.
- recovery: re-run without truncation or with a larger limit and confirm there are zero lines before declaring success.

## Verification
Checks to run after the batch of edits (do not mark as done without observing them):

- Re-run `npx tsc --noEmit` from the same project directory used in Step 1; a pass is empty stdout (trajectory observed `(Bash completed with no output)`).
- Grep the re-run output: no line contains `error TS2554`, `error TS1484`, or `error TS6133`; ideally the output has no lines at all.
- Inspect the former TS2554 site: it now reads `const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`.
- Inspect former TS1484 imports: the named specifiers carry `type` (e.g. `import { type CSSProperties, type ReactNode, ... } from 'react'`).
- Confirm tsconfig and compiler-related package versions are unchanged.
- Scope note: these checks prove typecheck only; build, dev server, and runtime were not verified in the trajectory, so none of them may be reported as passing on this evidence.

## Examples
### Example 1: debounce timer ref throwing TS2554 on a jobs route

- input: a line from `npx tsc --noEmit` — `src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.`
- procedure: Step 1 capture the run; Step 2 read the file and find `const debounceRef = useRef<ReturnType<typeof setTimeout>>()`; Step 3 replace it with `const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`; Step 6 re-run the typecheck.
- expected result: the TS2554 line is gone; once the rest of the batch is fixed too, the re-run prints nothing.
- parameterized values: project dir `<project>/frontend`, route file `<route-file>.tsx`, ref name `<refName>`, type argument `ReturnType<typeof setTimeout>` (or any timer/handle type).

### Example 2: mixed TS1484 + TS6133 batch in shared modules

- input: error lines such as `src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.` and `src/routes/__root.tsx(1,23): error TS6133: 'Outlet' is declared but its value is never read.`
- procedure: Step 4 add `type` to every TS1484 specifier across the affected files; Step 5 delete each TS6133-named binding (unused import specifiers, unused locals, unread destructured state, plus its setter calls); Step 6 re-run once.
- expected result: no TS1484 or TS6133 lines remain and the single re-run output is empty, verifying the batch as a whole.
- parameterized values: shared UI file `<shared-ui-file>.tsx`, context file `<context-file>.tsx`, route files under `<routes-dir>/`, specifier names as reported by the compiler.

## Evidence
- problem | file_id `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01` | source_index 217 | source_part_index 0 | quote: `src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.` | supports: the TS2554 symptom this skill targets, produced by `npx tsc --noEmit`.
- problem | same file_id | source_index 217 | source_part_index 0 | quote: `src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.` | supports: the TS1484 companion errors and the `verbatimModuleSyntax` precondition stated by the compiler itself.
- problem | same file_id | source_index 217 | source_part_index 0 | quote: `src/routes/__root.tsx(1,23): error TS6133: 'Outlet' is declared but its value is never read.` | supports: the TS6133 companion errors in the same batch.
- context | same file_id | source_index 245 | source_part_index 0 | quote: `const debounceRef = useRef<ReturnType<typeof setTimeout>>()` | supports: the offending zero-argument `useRef` call at line 44, read before fixing.
- action | same file_id | source_index 252 | source_part_index 0 | quote: `  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)` | supports: the TS2554 fix (Edit new_string) — explicit initializer plus `| undefined` widening.
- action | same file_id | source_index 218 | source_part_index 0 | quote: `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'` | supports: the TS1484 fix form — `type` modifiers on the named specifiers.
- action | same file_id | source_index 223 | source_part_index 0 | quote: `import { HeadContent, Scripts, createRootRoute } from '@tanstack/react-router'` | supports: the TS6133 fix form — removal of the unused `Outlet` specifier while keeping value imports.
- action | same file_id | source_index 241 | source_part_index 0 | quote: `await api.apply(fd)` | supports: removing the setter write (`setApplied(true)`) together with the unread `applied` state in one edit.
- verification | same file_id | source_index 254 | source_part_index 0 | quote: `cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -40` | supports: the verification command re-run after the batch of edits.
- verification | same file_id | source_index 255 | source_part_index 0 | quote: `(Bash completed with no output)` | supports: the re-run printed no diagnostics, i.e. the whole batch (TS2554 + TS1484 + TS6133) passed typecheck; this single run verifies the batch as a whole, not each edit individually.

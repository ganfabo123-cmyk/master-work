---
name: fix-ts2554-useref-initial-value
description: Use when tsc reports TS2554 "Expected 1 arguments, but got 0" on a zero-argument useRef call in a project with @types/react 19+. Helps the agent supply an explicit initial value (e.g. undefined with a union type) so the type check passes. Do not use when the TS2554 error points at a different function whose call signature was not changed by dependency upgrades.
---
# Fix TS2554 Expected 1 arguments in useRef Calls Under React 19 Typings

## Goal
Eliminate the TypeScript error TS2554 "Expected 1 arguments, but got 0" raised on zero-argument `useRef` calls in a React 19 project, so that `tsc --noEmit` completes with no errors for the affected file.

## Scope
### In scope
- TS2554 errors located on a `useRef(...)` call with no arguments in `.tsx`/`.ts` files of a React project whose `@types/react` is version 19 or newer.
- Passing an explicit initial value to `useRef`, including the `undefined` + union-type pattern for timer/timeout refs.
- Re-running the TypeScript check to confirm the specific error is resolved.

### Out of scope
- TS2554 errors on other functions whose arity differs for reasons unrelated to React 19 typings.
- Other errors reported by the same tsc run (e.g., TS1484, TS6133); fix them separately.
- Runtime behavior changes beyond the ref's initial value; no refactoring of the logic that consumes the ref.

## Inputs
- **Type check output**: string — produced by running `tsc --noEmit` (or the project's equivalent) in the frontend project; required. Must contain the full `file(line,col): error TS2554: ...` message.
- **Target source file path**: string — taken from the TS2554 error message's file/line/column prefix; required.
- **@types/react version**: string — read from the project's `package.json` devDependencies (e.g., `"@types/react": "^19.2.0"`); required to confirm the React 19 cause. Constraint: 19.x or newer triggers the one-argument requirement.
- **tsconfig.json**: JSON/text — project TypeScript configuration; optional, used only to confirm strictness settings. Default: 轨迹未提供 (not read in the trace).
- **Ref type**: string — the type parameter of the `useRef` call (e.g., `ReturnType<typeof setTimeout>`); required to construct the fix. Default: 无.

## Outputs
### Artifacts
- Edited source file where the zero-argument `useRef` call now passes an explicit initial value (same file path as input).
- Clean `tsc --noEmit` output for the project (no TS2554 lines).

### Success criteria
- The TS2554 error no longer appears at the reported location, and a re-run of `tsc --noEmit` reports no errors (in the observed case the command produced no output at all).

### Failure criteria
- TS2554 persists at the same location after the edit, or the edit introduces new type errors.
- The re-run of `tsc --noEmit` is not performed, leaving the fix unverified.

## Preconditions
- The frontend project's dependencies are installed (node_modules present) so `npx tsc --noEmit` can run.
- The exact TS2554 message with file, line, and column has been captured from a real type-check run.
- `package.json` confirms `@types/react` at 19.x or newer; if it is 18.x, the zero-argument `useRef` overload exists and the error has a different cause — stop and report instead of applying this fix.
- The agent has write access to the reported source file.
If any of these cannot be confirmed, stop and report the gap rather than editing blindly.

## Procedure
### Step 1: Capture the TS2554 error from a type check
- Actions: run the project's TypeScript check, e.g. `npx tsc --noEmit`, from the frontend project root. Locate lines matching `error TS2554: Expected 1 arguments, but got 0`.
- Inputs: project root with installed dependencies.
- Outputs: the error list including `file(line,col)` prefixes.
- Cautions: do not fix errors you cannot reproduce from a fresh check run.
- Preserve: the full raw output for later comparison.
- Next: proceed when at least one TS2554 line points at a `useRef` call.

### Step 2: Confirm the React 19 cause
- Actions: read the erroring file to confirm the call site is `useRef<...>()` with no arguments; check `package.json` for `@types/react` >= 19.
- Inputs: source file, `package.json`.
- Outputs: confirmation that the error is the React 19 arity change (the no-argument `useRef` overload was removed in @types/react 19).
- Cautions: if the symbol at the error location is not `useRef`, or `@types/react` is 18.x, this skill does not apply.
- Preserve: all other reported errors (they belong to separate fixes).
- Next: proceed to edit only when both checks pass.

### Step 3: Supply an explicit initial value
- Actions: edit the `useRef` call to pass an initial value. For a mutable timeout ref, widen the type to include `undefined` and pass `undefined`: `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`.
- Inputs: the `useRef` call and its existing type parameter.
- Outputs: the updated one-line call.
- Cautions: keep the existing type parameter in the union; removing it changes what consumers of the ref may access.
- Preserve: every other line in the file; use a minimal targeted edit.
- Next: re-run the type check.

### Step 4: Re-run the type check and compare
- Actions: run `npx tsc --noEmit` again. Confirm the TS2554 line is gone and no new errors appeared (in the observed trace the re-run produced no output).
- Inputs: edited project.
- Outputs: clean or reduced error output.
- Cautions: a clean check on this error does not verify runtime behavior; the ref consumer still needs the `undefined` guard it already has via `clearTimeout`.
- Preserve: the verification output as evidence.
- Next: done when the TS2554 error is absent; otherwise return to Step 2 with the new output.

## Decision Rules
### When @types/react is 19+ and the error is on a zero-argument useRef call
Pass an explicit initial value. For timer refs use `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`; for value refs pass the typed default (e.g., `useRef<HTMLDivElement | null>(null)`).

### When the same tsc run reports other error codes (TS1484, TS6133, etc.)
Fix TS2554 with the minimal useRef edit and handle each other error code with its own targeted fix; do not mix unrelated changes into one edit. In the observed trace, all fixes were applied as separate minimal edits before a single re-check.

### When TS2554 points at a non-useRef function
Do not apply this skill. Investigate that function's actual call signature (overloads, dependency version changes) instead.

### When the re-check still reports TS2554 at the same location
Re-read the call site; the likely causes are an edit that did not land on the reported line, or a second zero-argument useRef in the same file. Re-apply and re-check.

## Invariants
- Only change the reported `useRef` call (and, if needed, its type parameter); do not touch unrelated files or logic.
- Do not disable the error by loosening tsconfig settings (e.g., turning off strict or noUnusedLocals) or adding `@ts-ignore`.
- Do not claim success without a post-edit `tsc --noEmit` run showing the TS2554 line is gone.
- Do not report the project as fully type-clean based only on this fix if other errors were present in the original run and not addressed.
- Preserve the existing ref semantics: the ref must still be usable with the same narrowing the code already performs at use sites.

## Common Failures
### Failure: TS2554 persists after adding undefined
- Symptoms: re-run of `tsc --noEmit` still reports `Expected 1 arguments, but got 0` at the same or a nearby location.
- Causes: the edit missed the actual call site (file has multiple useRef calls), or the edit changed a different line. 轨迹未提供 evidence of other causes in this session.
- Recovery: re-read the exact line from the error message, apply the edit at that line, and re-run the check.

### Failure: New null-safety errors appear after the fix
- Symptoms: downstream code that reads `ref.current` now errors because the type includes `undefined`.
- Causes: the widened union type (`| undefined`) was not anticipated by consumers. This was avoided in the trace because the consumer already cleared the timeout without dereferencing it beyond `clearTimeout(debounceRef.current)`.
- Recovery: keep the union and guard at the use site (e.g., `if (ref.current) clearTimeout(ref.current)`), rather than removing the `undefined` from the type.

### Failure: Error assumed to be the React 19 arity change but @types/react is 18.x
- Symptoms: the prescribed edit either doesn't compile or the original zero-argument call was legal.
- Causes: misreading dependency versions.
- Recovery: revert the edit and investigate the actual call signature of the function at the error location.

## Verification
- Run `npx tsc --noEmit` from the frontend project root after the edit; expect no output (no errors), matching the observed clean re-check.
- Grep the fresh check output for `TS2554`; expect zero matches at the previously reported file and line.
- Confirm no new error codes appear that were not present in the pre-fix run.
- Confirm `package.json` still lists `@types/react` at 19.x after the fix (no accidental dependency changes).
Note: a clean type check verifies compilation only; it does not verify that the debounced search still behaves correctly at runtime — that would require exercising the UI, which was not done in the trace.

## Examples
### Example 1: Debounce timer ref in a TanStack Router jobs page
- Input: `tsc --noEmit` output containing `src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.` in a Vite + React 19 (`@types/react` ^19.2.0) frontend; the file declares `const debounceRef = useRef<ReturnType<typeof setTimeout>>()` used to debounce a search request.
- Procedure: Steps 1–4 — confirm the call is a zero-argument `useRef` and `@types/react` is 19+; replace the declaration with `const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`; re-run `npx tsc --noEmit`.
- Expected result: the re-run produces no output; the TS2554 line is gone and the existing `clearTimeout(debounceRef.current)` call remains valid.
- Parameterized values: file path (`src/routes/jobs/index.tsx`), ref type (`ReturnType<typeof setTimeout>`), debounce delay (300 ms in the original code) are project-specific; the fix pattern is the same.

## Evidence
- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 217, source_part_index: 0
  quote: "src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0."
  supports: problem — the TS2554 error appears at line 44 of the jobs listing route in the `tsc --noEmit` output (tool_result for the TypeScript check command).

- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 252, source_part_index: 0
  quote: "  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)"
  supports: action — the Edit call replaced the zero-argument `useRef<ReturnType<typeof setTimeout>>()` declaration with an explicit `undefined` initial value and a widened union type (new_string of the edit; the old_string in the same event was `  const debounceRef = useRef<ReturnType<typeof setTimeout>>()`).

- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 30, source_part_index: 0
  quote: "\\\"@types/react\\\": \\\"^19.2.0\\\""
  supports: precondition — the frontend `package.json` devDependencies confirm @types/react 19.x, the version line whose typings removed the zero-argument `useRef` overload (visible in the tool_result showing the package.json contents).

- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 254, source_part_index: 0
  quote: "cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -40"
  supports: verification action — the TypeScript check was re-run after the edits.

- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 255, source_part_index: 0
  quote: "(Bash completed with no output)"
  supports: verification — the re-run of `npx tsc --noEmit` after the useRef fix (and the companion TS1484/TS6133 fixes) produced no errors, confirming the TS2554 error was resolved.

---
name: fix-react19-useref-ts2554-no-default
description: Use when React 19 type definitions report TS2554 'Expected 1 arguments, but got 0' on a useRef() call with no initial value. Helps the agent add an explicit undefined initial argument and widen the ref type. Requires @types/react v19 and a runnable tsc. Do not use for older React types that allow zero-argument useRef, or for TS2554 errors on functions other than useRef.
triggers:
  - "TS2554"
  - "Expected 1 arguments, but got 0"
  - "useRef"
---
# Fix React 19 TS2554 on Zero-Argument useRef

## Goal
Resolve the React 19 TypeScript error TS2554 ('Expected 1 arguments, but got 0') on a zero-argument `useRef()` call by supplying an explicit initial value and widening the ref type, so that `tsc --noEmit` reports no error at that call site.

## Scope
### In scope
- TS2554 errors reported by `tsc` specifically at a `useRef()` call site invoked with no arguments under React 19 type definitions, where the generic type argument does not include `undefined` (or `null`).
- Fixing by widening the ref's generic to include `undefined` and passing `undefined` as the explicit initial value: `useRef<T | undefined>(undefined)`.
- Re-running `tsc --noEmit` to confirm the error at that call site is resolved.

### Out of scope
- TS2554 errors on functions or hooks other than `useRef`.
- React versions whose type definitions permit zero-argument `useRef`; this skill is grounded in the React 19 (`@types/react` ^19) behavior.
- Refactoring the surrounding logic, renaming the ref, or changing how the ref value is consumed downstream.
- Suppressing the error via tsconfig changes, type assertions, or `@ts-ignore`/`@ts-expect-error`.
- Choosing a meaningful non-`undefined` default value when one is clearly appropriate; this skill covers the `undefined`-initial pattern only.

## Inputs
1. **tsc error output** — Type: text (compiler diagnostics). Source: result of running `tsc --noEmit` (in evidence: `npx tsc --noEmit 2>&1 | head -60`). Required: yes. Constraints: a line reads `path(line,col): error TS2554: Expected 1 arguments, but got 0.` pointing at the `useRef` call. Default: none.

2. **Target source file** — Type: TypeScript/TSX file. Source: the path prefix of the TS2554 line (in evidence: `src/routes/jobs/index.tsx`). Required: yes. Constraints: must be readable and contain the `useRef` call at the reported line/column. Default: none.

3. **The `useRef` call site** — Type: line of TypeScript code. Source: the reported location. Required: yes. Constraints: of the form `const xRef = useRef<T>()` with no second argument, where `T` does not include `undefined`. Default: none.

4. **React version context** — Type: dependency metadata. Source: `package.json` (in evidence: `react` and `@types/react` at `^19.2.0`). Required: yes. Constraints: React 19 typings require an explicit initial argument to `useRef` when the type excludes `undefined`. Default: none.

5. **Project root / working directory** — Type: filesystem path. Source: the directory the `tsc` command is run from. Required: yes. Constraints: `npx tsc --noEmit` must resolve the project's tsconfig and dependencies from here. Default: none.

6. **Edit tool (file editor)** — Type: tool. Source: agent environment. Required: yes. Constraints: must apply an exact-string edit to the `useRef` call line. Default: none.

## Outputs
### Artifacts
- An edited `useRef` call where the generic type includes `undefined` and `undefined` is passed as the explicit initial value (e.g. `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`).
- A verification command result from re-running `tsc --noEmit` after the edit.

### Success criteria
- Re-running `tsc --noEmit` from the project root no longer reports TS2554 at the edited call site (in evidence, the whole run produced no output at all).
- The ref still holds the intended base type plus `undefined`, so downstream reads that already guard for unset values remain valid.
- No new errors are introduced by the edit.

### Failure criteria
- TS2554 remains at the call site.
- The edit changes the ref's base type (other than adding `| undefined`) or alters downstream usage.
- The verification command was not re-run, or its output was not inspected.

## Preconditions
1. **React 19 type definitions are in use** (`@types/react` ^19). The zero-argument `useRef` error is specific to these typings; under older typings a bare `useRef<T>()` is valid and this skill does not apply.

2. **The error is TS2554 at a `useRef` call**, not at some other function. Confirm the diagnostic line points at `useRef`.

3. **`tsc` is runnable from the project root** (in evidence, `npx tsc --noEmit` from the `frontend` directory). If the compiler cannot run, stop and report that verification is impossible.

4. **The call site is readable and editable**, and the current generic type argument `T` is identifiable.

5. **The ref is genuinely optional** — it is legitimately unset before an effect or callback assigns it, so `undefined` is an accurate initial value. If a meaningful default exists, prefer that instead.

If any of these preconditions cannot be met, stop and report the specific blocker rather than making speculative edits.

## Procedure
### Step 1: Confirm the error is TS2554 at a `useRef` call
- Actions: Run `tsc --noEmit` from the project root (in evidence: `npx tsc --noEmit 2>&1 | head -60`). Locate the line `... error TS2554: Expected 1 arguments, but got 0.` and confirm the reported column points at a `useRef(` call invoked with no arguments.
- Inputs: tsc output.
- Outputs: the file, line, and column of the offending `useRef` call.
- Cautions: TS2554 can be raised for many functions; only proceed if the callee is `useRef`. If another function is at fault, this skill does not apply.
- Preserve: other error codes in the same output (e.g. TS1484, TS6133); handle them separately.
- Next condition: proceed when a zero-argument `useRef` call is confirmed.

### Step 2: Read the call site and its current generic type
- Actions: Read the reported line. Identify the existing type argument `T` (in evidence: `ReturnType<typeof setTimeout>` in `const debounceRef = useRef<ReturnType<typeof setTimeout>>()`).
- Inputs: the source file.
- Outputs: the exact current call text and the base type `T`.
- Cautions: Note whether the surrounding code already treats the ref as possibly-unset (e.g. reads guarded by a truthiness check). That determines whether `undefined` is a safe initial value.
- Preserve: the variable name and the base type `T`.
- Next condition: proceed to edit once `T` is known.

### Step 3: Widen the generic and pass `undefined` as the initial value
- Actions: Edit the call so the generic includes `undefined` and `undefined` is passed explicitly: `useRef<T>()` becomes `useRef<T | undefined>(undefined)` (in evidence: `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`).
- Inputs: the current call text.
- Outputs: the edited call text.
- Cautions: Both changes are required together. Passing `undefined` without widening the generic leaves the type mismatch; widening without passing an argument still fails the arity check. Do not substitute `null` unless the surrounding code specifically expects `null`.
- Preserve: the base type `T` (only add `| undefined`) and the variable name.
- Next condition: proceed to verification after the edit.

### Step 4: Re-run `tsc --noEmit` and confirm the error is gone
- Actions: Run the same type-check command again from the same directory (in evidence: `npx tsc --noEmit 2>&1 | head -40`). Confirm TS2554 no longer appears at that call site, and that no new error is introduced.
- Inputs: the edited project.
- Outputs: the new tsc output.
- Cautions: An empty output means success; do not assume success without seeing the command re-run and return clean. If downstream reads now complain about `undefined`, guard them rather than reverting the widening.
- Preserve: all edits; do not revert.
- Next condition: stop when the error is resolved; if it persists, return to Step 2 to re-check the call.

## Decision Rules
### When the ref is genuinely optional and unset before an effect/callback assigns it
- Use `undefined` as the initial value and widen the generic: `useRef<T | undefined>(undefined)`. This is the pattern verified in evidence for a debounce-timer ref.

### When the surrounding code already reads the ref behind a guard
- Widening to `T | undefined` is safe; the guard already accounts for the unset state, so no downstream change is needed.

### When downstream code would newly break on `undefined`
- Add a guard at the read site (e.g. check before use) rather than reverting the widening. Do not remove `| undefined` to silence the downstream error.

### When a meaningful default value is clearly available
- Prefer passing that real default over `undefined` (out of scope for this skill's `undefined` pattern, but the better engineering choice when applicable).

### When the error persists after the edit
- Re-check that both changes were applied together (generic widened AND argument supplied) and that the edit targeted the correct `useRef` call.

### When the tsc run is clean but other error codes remain
- Report those separately; they are outside this skill and must not be conflated with the TS2554 fix.

## Invariants
- Preserve the ref's base type `T`; only add `| undefined` (do not substitute a different type or drop the original type argument).
- Preserve the ref variable name and all downstream usage except where a guard is strictly required for the newly-possible `undefined`.
- Never change tsconfig, add type assertions, or use `@ts-ignore`/`@ts-expect-error` to suppress TS2554.
- Never apply this pattern to non-`useRef` TS2554 errors or to React versions whose typings allow zero-argument `useRef`.
- Never report success without re-running `tsc --noEmit` and observing that the TS2554 diagnostic at the call site is gone.
- Never treat an empty or truncated command result as proof of success unless the verification command was actually executed and returned clean.
- Do not assume the ref must always hold a value; the whole point of the `undefined` initial is that it may legitimately be unset.

## Common Failures
### Failure: Supplied `undefined` but did not widen the generic
- Symptoms: TS2554 is replaced by a type-argument mismatch (the `undefined` value is not assignable to `T`).
- Causes: the edit passed `undefined` while leaving the generic as `useRef<T>(undefined)`.
- Recovery: widen the generic to `T | undefined` so the `undefined` argument type-checks, then re-run `tsc --noEmit`.

### Failure: Widened the generic but did not pass an argument
- Symptoms: TS2554 persists at the call site.
- Causes: the edit produced `useRef<T | undefined>()` with no initial value, still failing the arity check under React 19 typings.
- Recovery: pass `undefined` explicitly as the second piece of the fix, then re-verify.

### Failure: Downstream code newly rejects `undefined`
- Symptoms: after the edit, reads of the ref report that `undefined` is not assignable / possibly-undefined.
- Causes: the ref was previously assumed to always hold a value; widening surfaced that assumption.
- Recovery: add a guard at the read site (check before use) rather than reverting the widening; this is the expected consequence of an optional ref.

### Failure: Wrong error code or non-`useRef` target
- Symptoms: the edit does not clear the reported error, or a different function's TS2554 remains.
- Causes: TS2554 was raised for a function other than `useRef`, or the project is not on React 19 typings.
- Recovery: confirm the callee is `useRef` and that `@types/react` is v19; otherwise stop, as this skill does not apply.

### Failure: Claimed success without a clean re-run
- Symptoms: the fix looks correct but the error is still present, or a later step fails on the same line.
- Causes: `tsc --noEmit` was not re-run, or its output was truncated/not inspected.
- Recovery: always re-run the type check and confirm the TS2554 diagnostic at the call site is gone before reporting done.

### Failure: Cause not confirmed
- Symptoms: uncertain whether the edit actually addressed TS2554 or masked something else.
- Causes: multiple simultaneous edits or unrelated changes in the same batch.
- Recovery: isolate the `useRef` edit, re-run tsc, and confirm the specific diagnostic cleared.

## Verification
1. **Re-run the type check** from the project root with the same command used to discover the error (in evidence: `npx tsc --noEmit 2>&1 | head -40`). Observable check: the output contains no `error TS2554` line for the edited `useRef` call; an entirely empty output indicates a fully clean check.

2. **Confirm the edited call matches the intended form** by reading the line. Observable check: the statement is now of the shape `useRef<T | undefined>(undefined)` (in evidence: `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`).

3. **Confirm both changes are present together**: the generic includes `| undefined` AND `undefined` is passed as the argument. Observable check: neither `useRef<T | undefined>()` nor `useRef<T>(undefined)` remains.

4. **Confirm no new errors were introduced** at the call site or its downstream reads. Observable check: the post-edit tsc output has no new diagnostic pointing at the ref variable; if a downstream read complains about `undefined`, a guard was added rather than the widening being reverted.

5. **Do not rely on build or dev-server success as a substitute** for the type check unless those are also known to run `tsc`; a clean `tsc --noEmit` is the direct evidence for TS2554 resolution.

## Examples
### Example 1: Optional debounce-timer ref with no initial value
- input: `tsc --noEmit` reports `src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.` The offending line reads: `const debounceRef = useRef<ReturnType<typeof setTimeout>>()`.
- procedure: Follow Steps 1–4. Confirm the callee is `useRef`, note the base type `ReturnType<typeof setTimeout>`, widen the generic to include `undefined`, and pass `undefined` as the explicit initial value.
- expected result: The line becomes `const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`, and re-running `npx tsc --noEmit` no longer reports TS2554 at that location (in evidence the whole run produced no output).
- parameterized values: file path `src/routes/jobs/index.tsx`; ref variable `debounceRef`; base type `ReturnType<typeof setTimeout>`; verification command `npx tsc --noEmit 2>&1 | head -40`; clean result `(Bash completed with no output)`.

### Example 2: Guarded optional ref read downstream
- input: A `useRef<HTMLDivElement>()` (or similar) is declared with no initial value and later read only inside a conditional guard. `tsc --noEmit` reports TS2554 at the declaration.
- procedure: Follow Steps 1–4. Since the ref is genuinely optional and its reads are already guarded, widen to `| undefined` and pass `undefined`; leave the guarded reads unchanged.
- expected result: The declaration becomes `useRef<T | undefined>(undefined)`, the guard continues to satisfy the compiler, and no new downstream error appears.
- parameterized values: file path `<route-or-component>.tsx`; ref variable `<name>Ref`; base type `T` (e.g. `HTMLDivElement`); initial argument `undefined`; verification command `npx tsc --noEmit`.

## Evidence
file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01

- kind: problem
  source_index: 217
  source_part_index: 0
  quote: "src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0."
  supports: Establishes the problem signature — TS2554 at a call site expecting one argument; combined with the React 19 (`@types/react` ^19.2.0, source_index 30) dependency this is the zero-argument `useRef` arity error.

- kind: context
  source_index: 245
  source_part_index: 0
  quote: "44\t  const debounceRef = useRef<ReturnType<typeof setTimeout>>()"
  supports: Shows the offending call site before the fix — a `useRef` invoked with no initial argument and generic type `ReturnType<typeof setTimeout>` that excludes `undefined`.

- kind: action
  source_index: 252
  source_part_index: 0
  quote: "  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)"
  supports: Demonstrates the fix — the generic widened to include `undefined` AND `undefined` passed as the explicit initial value, both applied together.

- kind: verification
  source_index: 254
  source_part_index: 0
  quote: "cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -40"
  supports: The verification command re-run after the edits (description: "TypeScript check after fixes"), matching the discovery command used at source_index 216.

- kind: verification
  source_index: 255
  source_part_index: 0
  quote: "(Bash completed with no output)"
  supports: The post-fix `tsc --noEmit` returned empty output, directly evidencing that the TS2554 diagnostic (and the other errors in the batch) were resolved; the assistant then stated "TypeScript passes with no errors." (source_index 256).

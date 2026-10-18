---
name: fix-ts2554-use-ref-initial-value
description: Use when TypeScript reports TS2554 "Expected 1 arguments, but got 0" on a React `useRef` call that passes no initial value under @types/react 19. Helps the agent add an explicit undefined-inclusive initial argument and re-run `npx tsc --noEmit` until the diagnostic disappears. Requires a TypeScript project where `npx tsc --noEmit` can be run and the package.json dependency versions can be read. Do not use when TS2554 points at a different function, when the project's @types/react is major 18 (the zero-argument useRef overload still exists there), or when the type check cannot be executed.
---
# Fix TS2554 on useRef Calls That Omit the Initial Argument

## Goal
Eliminate the TypeScript error TS2554 "Expected 1 arguments, but got 0" raised on a zero-argument `useRef<T>()` call in a React 19 project, so that a project-wide `npx tsc --noEmit` type check runs with no reported errors.

## Scope
### In scope
- TS2554 diagnostics whose reported position lands on a `useRef(...)` call made with no arguments, in a project whose `@types/react` is major version 19 (where the zero-argument `useRef()` overload was removed).
- Editing the specific `useRef` call site to pass an explicit initial value that preserves the original "possibly unset" semantics.
- Re-running the project type check (`npx tsc --noEmit`) from the package root to confirm the diagnostic is gone.

### Out of scope
- TS2554 errors on functions other than React hooks (API calls, helpers, constructors) — those require checking the callee's signature, not this pattern.
- Other diagnostics that may appear in the same type-check output (e.g. TS1484 type-only import errors, TS6133 unused-variable errors); they are fixed separately and only affect this skill in that the final type check must be run after all edits.
- Changing `tsconfig.json` options, downgrading `@types/react`, or adding `@ts-expect-error`/`@ts-ignore` to silence the error.
- Runtime behavior verification (dev server, tests, production build) — the trace only verified a clean type check.

## Inputs
- **TS2554 diagnostic line** — Type: text from compiler output. Source: `npx tsc --noEmit` (or equivalent `tsc --noEmit`) run output. Required: yes. Constraint: must read `error TS2554: Expected 1 arguments, but got 0.` and include `file(line,col)` pointing at the suspect call. Default: 无.
- **Reported source file and line** — Type: file path plus line/column. Source: the diagnostic line's `file(line,col)` position. Required: yes. Constraint: file must be readable so the exact call site can be inspected before editing. Default: 无.
- **Project `package.json`** — Type: JSON file at the frontend/package root. Source: repository. Required: yes. Constraint: must show the installed `@types/react` major version (the trace had `"@types/react": "^19.2.0"` with `"react": "^19.2.0"`); used to confirm the zero-argument `useRef()` overload is absent. Default: 无.
- **Working directory for the type check** — Type: directory path. Source: the package root containing `package.json` and `tsconfig.json` (trace used the `frontend` directory). Required: yes. Constraint: `npx tsc --noEmit` must resolve the project's tsconfig from it. Default: 无.
- **Edit capability on the source file** — Type: tool access. Source: agent environment. Required: yes. Constraint: exact-string edit of the `useRef` line; do not rewrite unrelated code. Default: 无.

## Outputs
### Artifacts
- **Edited source file** — Location: the file named in the TS2554 diagnostic (trace: `frontend/src/routes/jobs/index.tsx`). Format: TypeScript/TSX source where the `useRef` line now passes an explicit initial `undefined` with the value type widened to include `undefined`.
- **Verification command output** — Location: terminal/tool result. Format: output of `npx tsc --noEmit` executed from the package root (trace: empty output).

### Success criteria
- The TS2554 diagnostic for the reported `file(line,col)` no longer appears in a fresh `npx tsc --noEmit` run.
- The edited line preserves the original semantics: the ref's value type includes `undefined` and the initial value is explicitly `undefined`, so no downstream usage needs retyping.

### Failure criteria
- TS2554 still appears at the same position after the edit.
- The type check fails with new or remaining diagnostics (the trace's final check had to be clean of all errors, including TS1484/TS6133 fixed separately, before it passed with no output).
- The `@types/react` major version cannot be confirmed as 19, or `tsc` cannot be run from the package root.

## Preconditions
- A TypeScript package with `typescript` installed and a resolvable `tsconfig.json`; `npx tsc --noEmit` must be runnable from the package root. If the type check cannot run (missing tsc, broken tsconfig), stop and report — the fix cannot be verified.
- `package.json` is readable and shows `@types/react` at major version 19 (the trace: `"@types/react": "^19.2.0"`). If the project uses `@types/react` 18, where a zero-argument `useRef<T>()` overload exists, this pattern does not apply — stop and re-diagnose the actual callee signature instead.
- The TS2554 diagnostic has been reproduced at least once and its exact `file(line,col)` is known (trace baseline: `npx tsc --noEmit` output listing `src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.`).
- The reported source line has been read and confirmed to be a `useRef<...>()` call with no argument. If the position points at any other function, do not apply this skill.
- Edit permission on the reported file only; no tsconfig or dependency changes are authorized.

## Procedure
### Step 1: Reproduce and capture the diagnostic
- Actions: From the package root run the type check, e.g. `npx tsc --noEmit 2>&1 | head -40` (trace: `cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -60`). Locate the `error TS2554: Expected 1 arguments, but got 0.` line and its `file(line,col)`.
- Inputs: package root directory.
- Outputs: baseline error list including the TS2554 position.
- Cautions: the same output may contain unrelated diagnostics (TS1484, TS6133 in the trace) — record them but do not conflate them with TS2554; this run is the baseline, not verification.
- Preserve: full diagnostic text for later comparison.
- Next: proceed when the TS2554 line and its exact position are known.

### Step 2: Read the reported call site
- Actions: Read the reported file around the reported line (trace: `Read` of `frontend/src/routes/jobs/index.tsx` with offset 1, limit 50, showing line 44 as `const debounceRef = useRef<ReturnType<typeof setTimeout>>()`). Confirm the call is `useRef<...>()` with zero arguments.
- Inputs: file path and line from Step 1.
- Outputs: the exact original line to be edited.
- Cautions: if the position is not a zero-argument `useRef`, stop — the TS2554 has a different cause and needs the callee's signature checked.
- Preserve: the original generic type argument (here `ReturnType<typeof setTimeout>`), which expresses what the ref will hold.
- Next: proceed when the line is confirmed to be a zero-argument `useRef<T>()`.

### Step 3: Add an explicit initial value, widening the type with `| undefined`
- Actions: Edit the line so the type parameter includes `undefined` and an initial `undefined` is passed:
  `const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`
- Inputs: original line from Step 2.
- Outputs: edited source file; the edit tool reports the file updated successfully.
- Cautions: do not pass `null` unless the ref is meant to hold `null` — the pattern verified in the trace pairs `| undefined` in the type with `undefined` as the initial value; do not use `!` non-null assertions or `@ts-ignore` to bypass the error; other unused-import/unused-variable errors in the same file (TS6133 in the trace) must not be "fixed" by this step.
- Preserve: all other code in the file, including consumers of the ref (`debounceRef.current` usage, cleanup timers).
- Next: proceed to re-running the type check.

### Step 4: Re-run the type check and confirm it is clean
- Actions: Run the same command as Step 1 (trace: `cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -40`).
- Inputs: package root.
- Outputs: tool result — in the trace, `(Bash completed with no output)`.
- Cautions: any remaining diagnostic means the overall check is not clean; the TS2554 fix alone does not clear unrelated errors (TS1484 type-only imports and TS6133 unused variables were fixed in the same session before the clean run).
- Preserve: nothing else is changed in this step.
- Next: stop when the command outputs no errors; if TS2554 reappears at the same position, return to Step 2 and re-inspect the call site.

## Decision Rules
### When the TS2554 position is a zero-argument `useRef<T>()` and `@types/react` is major 19
Apply the verified fix: widen the type parameter to `T | undefined` and pass `undefined` as the first argument — `useRef<ReturnType<typeof setTimeout> | undefined>(undefined)` — then re-run the type check.

### When the TS2554 position is any other function call
Do not apply this skill. Read the callee's declaration and pass the argument(s) it actually requires; a `useRef`-shaped fix cannot resolve an arbitrary arity mismatch.

### When the project's `@types/react` is major 18 (or unconfirmed)
Do not apply this skill as written: the zero-argument overload may legitimately exist, so the error has a different origin. Confirm the installed version from `package.json`/lockfile first; if it cannot be confirmed, stop and report.

### When the baseline type check also lists other diagnostics (TS1484, TS6133, …)
Fix them by their own mechanisms in the same editing pass, then treat the single clean re-run of `npx tsc --noEmit` as the verification for the whole pass. Do not report the TS2554 fix as verified from a run that still prints errors.

### When TS2554 persists after the edit at the same position
The edit did not land or the diagnosis was wrong: re-read the reported line, confirm the tool reported the file updated successfully, and re-check whether the call truly had zero arguments. Do not escalate to tsconfig changes or dependency downgrades.

## Invariants
- Edit only the reported call site (and, when present in the same pass, each error's own minimal fix); do not rewrite unrelated files, routes, or components.
- Do not modify `tsconfig.json`, `package.json` dependency versions, or generated route files to suppress the diagnostic.
- Preserve runtime semantics: the ref must still start unset, expressed as an explicit `undefined` initial value with `| undefined` in the type — never replace it with a fabricated default (e.g. `0`, `''`) that changes behavior.
- Do not skip the final `npx tsc --noEmit` re-run, and do not report success from the edit tool's "updated successfully" message alone — that only proves the write, not the type check.
- Do not report a clean type check as a build, test, or runtime verification: only the type check was executed.
- Do not attribute the clean final run solely to this fix when other diagnostics were fixed in the same pass; report the pass as a whole.
- Keep the original generic type (`ReturnType<typeof setTimeout>` in the trace) intact when widening with `| undefined`; do not collapse it to `any`.

## Common Failures
### Failure: TS2554 remains after editing the line
- Symptoms: the re-run still prints `error TS2554: Expected 1 arguments, but got 0.` at the same `file(line,col)`.
- Causes: the edit did not actually change the reported position (wrong line, stale buffer, or the Read view predated another edit), or the position is not the zero-argument `useRef` the agent assumed. The trace did not exhibit this failure after its fix, so no further cause is confirmed.
- Recovery: re-read the reported line from disk, confirm the exact current text, re-apply the minimal edit, and re-run the type check. If the line is correct and the error persists, inspect the callee declaration before any config change.

### Failure: type check stays red because other diagnostics remain
- Symptoms: the TS2554 line is gone but `npx tsc --noEmit` still prints errors such as `error TS1484 ... type-only import` or `error TS6133 ... declared but its value is never read`.
- Causes: a pre-existing error batch was present at baseline; the useRef fix never claimed to cover them (the baseline run in the trace listed 14 errors across TS1484, TS6133, and TS2554).
- Recovery: fix each remaining diagnostic by its own mechanism (add `type` modifiers to type-only imports; remove genuinely unused declarations), then re-run the type check until it produces no output.

### Failure: `@types/react` version mismatch makes the diagnosis invalid
- Symptoms: a zero-argument `useRef<T>()` compiles in this project, or the dependency cannot be located.
- Causes: the project is on `@types/react` 18 or the version was never confirmed.
- Recovery: read `package.json`/lockfile to establish the installed major version; if it is not 19, abandon this pattern and diagnose the actual callee signature at the reported position.

## Verification
- Run `npx tsc --noEmit` from the package root after the edit; the observable pass condition is output containing no `error TS2554` for the reported `file(line,col)` (in the trace the command returned `(Bash completed with no output)`, i.e. no errors at all).
- Compare against the baseline output captured before editing: every baseline line must be absent from the new output, not just the TS2554 line.
- Grep/search the edited file to confirm the line now reads `useRef<... | undefined>(undefined)` and no zero-argument `useRef<...>()` remains in the file.
- Confirm the edit tool result for the target file reported a successful update before trusting the type-check delta.
- Confirm `package.json` still shows the original `@types/react` (trace: `"@types/react": "^19.2.0"`) and `tsconfig.json` is untouched, proving no suppression was used.
- Do not treat this as verified for runtime behavior: no dev server, test run, or production build was executed in the trace after the fix; if runtime confirmation is required, it must be run separately and is outside this skill's verified scope.

## Examples
### Example 1: debounce timer ref in a TanStack Router route
- Input: baseline type-check output line `src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.` from `npx tsc --noEmit` in a frontend package using `react` / `@types/react` `^19.2.0`.
- Procedure:
  1. Read `src/routes/jobs/index.tsx` and observe line 44: `const debounceRef = useRef<ReturnType<typeof setTimeout>>()`.
  2. Edit that line to `const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`.
  3. Re-run `npx tsc --noEmit` from the package root.
- Expected result: the TS2554 line no longer appears; in the trace the re-run completed with no output (no errors). The ref still starts as `undefined`, so existing `debounceRef.current` guards and `clearTimeout` cleanup behave exactly as before.
- Parameterized values: file = the reported `.tsx` path; generic type = whatever the original call passed (here `ReturnType<typeof setTimeout>`); ref name = the existing identifier (here `debounceRef`); initial value = `undefined` paired with `| undefined` in the type.

### Example 2: same pass also clears unrelated baseline errors
- Input: baseline output containing the TS2554 line plus other diagnostics in the same run, e.g. `src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.` and `src/routes/jobs/index.tsx(1,27): error TS6133: 'Link' is declared but its value is never read.`
- Procedure:
  1. Fix each diagnostic by its own mechanism (inline `type` modifiers on type-only imports; delete unused declarations/imports), including the Step 3 `useRef` edit for the TS2554.
  2. Run one final `npx tsc --noEmit` covering the whole package.
- Expected result: the command produces no output, i.e. the entire baseline list — TS1484, TS6133, and TS2554 — is gone (this is what the trace's final check showed). Report the outcome as "type check clean after a batch of fixes," not as the `useRef` edit alone carrying the result.
- Parameterized values: error codes present in the batch; file paths; the specific unused symbols and type-only imports named in the output.

## Evidence
- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__original; source_index: 217; source_part_index: 0; quote: `src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.`; supports: problem — the TS2554 diagnostic in the baseline `tsc --noEmit` output, with the exact position later targeted.
- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__original; source_index: 30; source_part_index: 0; quote: `"@types/react": "^19.2.0",`; supports: precondition — the project is on React 19 type definitions, where a zero-argument `useRef()` call is rejected.
- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__original; source_index: 245; source_part_index: 0; quote: `const debounceRef = useRef<ReturnType<typeof setTimeout>>()`; supports: problem context — the reported line read back before editing, showing a `useRef` generic call with no argument.
- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__original; source_index: 251; source_part_index: 0; quote: `Now fix the `useRef` type error (no default argument):`; supports: diagnosis — the agent identified the TS2554 as a `useRef` call missing a default argument.
- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__original; source_index: 252; source_part_index: 0; quote: `const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)`; supports: action — the exact edit applied: type widened with `| undefined` and explicit `undefined` passed as the first argument.
- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__original; source_index: 254; source_part_index: 0; quote: `npx tsc --noEmit 2>&1 | head -40`; supports: verification method — the type check re-run after the fix.
- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__original; source_index: 255; source_part_index: 0; quote: `(Bash completed with no output)`; supports: verification result — the post-fix type check printed no errors, so the TS2554 (and the session's other baseline diagnostics) were gone. Note: TS1484/TS6133 fixes at source_index 218–249 happened in the same pass, so the clean run verifies the batch; the TS2554-specific change is the edit at source_index 252.
- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__original; source_index: 216; source_part_index: 0; quote: `cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -60`; supports: procedure step 1 — how the baseline diagnostics were produced from the package root.

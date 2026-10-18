---
name: fix-ts1484-type-only-imports
description: Use when tsc reports TS1484 "'X' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled" for symbols imported from React or other libraries. Helps the agent convert the offending named imports to inline `type` specifiers and re-verify with a clean type check. Do not use when the project does not enable verbatimModuleSyntax/importsNotUsedAsValues, or when the imported symbol is used as a runtime value.
---
# Fix TS1484 Type-Only Import Errors When verbatimModuleSyntax Is Enabled

## Goal
Eliminate TypeScript TS1484 errors ("'X' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled") by converting the offending named imports to inline `type` specifiers, so `tsc --noEmit` completes without those errors.

## Scope
### In scope
- TS1484 errors on named imports of type-only symbols (e.g., React's `CSSProperties`, `ReactNode`, `InputHTMLAttributes`, `TextareaHTMLAttributes`, `SelectHTMLAttributes`) in projects with `verbatimModuleSyntax` enabled.
- Converting individual named specifiers to inline `type` specifiers (`import { type X, Y } from '...'`) or to a separate `import type` statement.
- Re-running the type check to confirm the TS1484 errors are gone.

### Out of scope
- Removing unused value imports reported as TS6133; those are deleted, not converted.
- Changing tsconfig options to disable `verbatimModuleSyntax`.
- Modules where the symbol is used at runtime; converting those imports would break the build.

## Inputs
- **Type check output**: string — produced by `tsc --noEmit`; required. Must contain lines of the form `file(line,col): error TS1484: 'X' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.`
- **Import statement location**: file path + line number — derived from the TS1484 error's `(line,col)` prefix; required.
- **Current import statement**: string — read from the source file (e.g., `import { CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from 'react'`); required to build the replacement.
- **Usage check**: boolean per symbol — whether the symbol is used only in type positions in that file; required before conversion (in the trace, all flagged React symbols were pure types).
- Default values: 无.

## Outputs
### Artifacts
- Edited source file(s) whose flagged import statements now use inline `type` specifiers for the type-only symbols.
- Clean `tsc --noEmit` output (no TS1484 lines) after the edits.

### Success criteria
- A re-run of `tsc --noEmit` reports zero TS1484 errors for the edited files; in the observed trace the entire re-check produced no output.
- Value imports in the same statement remain value imports and still resolve.

### Failure criteria
- TS1484 persists, or new errors (e.g., runtime import failures or TS2305) appear after the change.
- The re-check was not run, leaving the fix unverified.

## Preconditions
- The project enables `verbatimModuleSyntax` (or equivalent type-only import enforcement) in its tsconfig; this is confirmed indirectly by the TS1484 message text itself.
- Dependencies are installed so `npx tsc --noEmit` can run.
- The exact TS1484 messages with file, line, and column have been captured from a real type-check run.
- Each flagged symbol has been confirmed to appear only in type positions in the file being edited.
- The agent has write access to the flagged files.
If the symbol is also used at runtime in the file, stop: converting it would break the import; report the conflict instead.

## Procedure
### Step 1: Collect all TS1484 errors from a type check
- Actions: run `npx tsc --noEmit` in the project root and extract every line containing `error TS1484`, noting file, line, column, and symbol name.
- Inputs: installed project.
- Outputs: a grouped list of files and their flagged symbols (e.g., `src/components/ui.tsx` → `CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes`; `src/context/auth.tsx` → `ReactNode`).
- Cautions: multiple files may be affected; fix all before the final verification, or verify each incrementally.
- Preserve: the original raw output for comparison.
- Next: proceed to inspect each flagged import statement.

### Step 2: Rewrite each import with inline type specifiers
- Actions: for each flagged import statement, prefix only the type-only symbols with `type`. Example: `import { CSSProperties, ReactNode, ... } from 'react'` becomes `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'`. A statement whose symbols are all types may instead become `import type { ... } from 'react'`; the observed fix used inline specifiers.
- Inputs: the original import statement text.
- Outputs: the updated import statement.
- Cautions: do not add `type` to symbols used as values in the same file; keep value specifiers untouched.
- Preserve: import order, the module specifier, and any other specifiers in the statement.
- Next: after all flagged statements are updated, re-run the type check.

### Step 3: Re-run the type check
- Actions: run `npx tsc --noEmit` again and confirm no TS1484 lines remain (in the observed trace the re-run produced no output, i.e., the whole check was clean).
- Inputs: the edited project.
- Outputs: clean or reduced error output.
- Cautions: a clean type check proves compilation only, not runtime behavior of the affected components.
- Preserve: the verification output as evidence.
- Next: done when TS1484 is absent; otherwise return to Step 2 with the new output.

## Decision Rules
### When a flagged symbol is used only in type positions in the file
Add the inline `type` prefix to that specifier (chosen style in the trace), or move it to a separate `import type` statement if the whole import is type-only.

### When the same import statement mixes type-only and value symbols
Keep the value specifiers unchanged and prefix only the type ones, e.g. `import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`.

### When the TS1484 run also reports TS6133 (declared but never read)
Remove the unused import or binding entirely instead of converting it; TS6133 and TS1484 have different remedies. In the trace, unused `Outlet`, `Select`, `Link`, `navigate`, `BASE_URL`, `applied`, and `user` were deleted, not typed.

### When re-check still reports TS1484 on the same line
The edit likely missed the reported statement or the file has a second import of the same symbol; re-read the exact line and re-apply.

## Invariants
- Only modify the import statements flagged by TS1484 (plus verified-unused imports flagged by TS6133); do not change component logic or other files.
- Never convert a symbol to a type import if it is used at runtime in that file (e.g., React itself, component functions).
- Do not disable `verbatimModuleSyntax` or weaken tsconfig to silence the error.
- Do not claim success without a post-edit `tsc --noEmit` run showing no TS1484 lines.
- Preserve import ordering and module specifiers; the change is limited to adding/removing the `type` keyword on individual specifiers.

## Common Failures
### Failure: TS1484 still reported after adding type keywords
- Symptoms: the re-check lists TS1484 on the same file/line.
- Causes: the edit did not match the actual import statement text, or the file imports the symbol twice. 轨迹未提供 an instance of this in the session.
- Recovery: re-read the import line, apply the edit verbatim, re-run `tsc --noEmit`.

### Failure: Runtime break after converting a value import
- Symptoms: the type check passes but the app fails at runtime or build with a missing export / undefined component.
- Causes: a symbol used at runtime was wrongly converted to a type-only import.
- Recovery: revert that specifier to a value import; keep `type` only on symbols proven type-only in that file.

### Failure: Mass-converting an entire barrel import
- Symptoms: bundle or runtime errors after rewriting a whole-module import.
- Causes: converting `import ... from 'lib'` wholesale when some imports are values. The trace's import style (explicit named specifiers, e.g., from 'react' and '#/components/ui') avoids this.
- Recovery: revert and prefix only the individual type-only specifiers.

## Verification
- Run `npx tsc --noEmit` from the project root after all import edits; expect no output (the observed post-fix re-check completed with no output).
- Grep the fresh output for `TS1484`; expect zero matches for the previously flagged files (e.g., `src/components/ui.tsx`, `src/context/auth.tsx`).
- Confirm no new error codes appear relative to the pre-fix run.
- Optionally re-open an edited import statement and confirm type-only specifiers carry the `type` keyword while value specifiers do not.
Note: this verifies compilation only; runtime rendering of the affected components was not exercised in the trace.

## Examples
### Example 1: UI kit module with five React type imports
- Input: `tsc --noEmit` reports five TS1484 errors on line 1 of `src/components/ui.tsx` for `CSSProperties`, `ReactNode`, `InputHTMLAttributes`, `TextareaHTMLAttributes`, `SelectHTMLAttributes`, imported via `import { CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from 'react'`.
- Procedure: Step 2 edit — replace the statement with `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'`; then Step 3 re-check.
- Expected result: the TS1484 lines for this file disappear; the file's components still compile because all five symbols are used only in type positions.
- Parameterized values: module (`react`), symbol set, and file path vary per project; the prefix-only-types rule is constant.

### Example 2: Mixed value and type imports in an auth context
- Input: `src/context/auth.tsx` line 1 imports `createContext, useContext, useState, useEffect, ReactNode` from `react`, with only `ReactNode` flagged by TS1484.
- Procedure: keep the four value imports unchanged and add `type` to the last: `import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`.
- Expected result: TS1484 for `ReactNode` is resolved while `createContext` and hooks continue to work at runtime.
- Parameterized values: value symbols here (`createContext`, hooks) are runtime React APIs; in other files substitute the actual value imports.

## Evidence
- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 217, source_part_index: 0
  quote: "src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled."
  supports: problem — the first of five TS1484 errors on the UI module's import line in the `tsc --noEmit` output; the same tool_result also lists TS1484 for `ReactNode`, `InputHTMLAttributes`, `TextareaHTMLAttributes`, `SelectHTMLAttributes` in this file and for `ReactNode` in `src/context/auth.tsx(1,58)`.

- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 218, source_part_index: 0
  quote: "import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'"
  supports: action — the new_string of the Edit that converted all five flagged specifiers to inline type imports (old_string in the same event was `import { CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from 'react'`).

- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 221, source_part_index: 0
  quote: "import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'"
  supports: action — the mixed-import fix: value specifiers unchanged, only `ReactNode` converted to a type specifier (Edit new_string; the auth context file had one TS1484 error on `ReactNode`).

- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 254, source_part_index: 0
  quote: "cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -40"
  supports: verification action — the type check was re-run after the import edits.

- file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01, source_index: 255, source_part_index: 0
  quote: "(Bash completed with no output)"
  supports: verification — the post-fix `tsc --noEmit` run produced no output, confirming the TS1484 errors (along with the TS2554 and TS6133 fixes) were fully resolved.

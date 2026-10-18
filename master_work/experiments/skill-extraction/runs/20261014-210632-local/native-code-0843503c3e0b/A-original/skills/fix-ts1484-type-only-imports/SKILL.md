---
name: fix-ts1484-type-only-imports
description: Use when `tsc --noEmit` reports TS1484 errors that type names are imported with value-only import syntax while `verbatimModuleSyntax` is enabled. Helps the agent convert only the offending specifiers to inline `type` modifiers and re-verify with a clean typecheck. Requires a TypeScript project with `npx tsc --noEmit` available. Do not use when the errors are TS6133 unused declarations, TS2554 argument-count mismatches, or other non-TS1484 diagnostics, or when the user asks to disable `verbatimModuleSyntax` instead.
---
# Fix TS1484 Type-Only Import Errors under verbatimModuleSyntax

## Goal
Eliminate every TS1484 error ("'X' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled") in a TypeScript project by converting the offending import specifiers to type-only syntax, and produce a typecheck run whose output contains no TS1484 diagnostics.

## Scope
### In scope
- TS1484 errors reported by `tsc --noEmit` in `.ts`/`.tsx` files where a named import specifier refers only to a type (interface, type alias, type-only React attribute types such as `CSSProperties`, `ReactNode`, `InputHTMLAttributes`).
- Rewriting the import statement so type-only specifiers carry the inline `type` modifier (e.g. `import { type ReactNode } from 'react'`) while value specifiers in the same statement stay unmodified.
- Re-running the typecheck to confirm no TS1484 diagnostics remain.

### Out of scope
- Other diagnostics that may appear in the same typecheck output (TS6133 unused declarations, TS2554 argument-count errors, etc.); fix those separately with their own evidence and verification.
- Changing `tsconfig.json` (e.g. disabling `verbatimModuleSyntax`) instead of fixing imports — the trajectory did not do this and it is not verified here.
- Converting entire import statements to `import type { ... }` when the statement mixes value and type specifiers (that would drop the value imports).
- Runtime testing, builds beyond typechecking, lint autofixes.

## Inputs
- **Typecheck output**: string, source: result of running `tsc --noEmit` in the project directory; required. Must list one or more `error TS1484` lines in the form `path(line,col): error TS1484: 'Name' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.`
- **Project root / working directory**: string, source: user request or repo layout (trajectory used `<project>/frontend`); required. Default: repository root containing `tsconfig.json`.
- **tsconfig with `verbatimModuleSyntax` enabled**: config, source: project's `tsconfig.json`; required to be present and unchanged. Default: whatever the project already has; do not modify it.
- **TypeScript availability**: `npx tsc` resolvable via local `typescript` dependency; required. No default.
- **File paths from error lines**: relative paths as printed by `tsc` (e.g. `src/components/ui.tsx`), resolved against the project root; required per error.
- **Optional edit tool or text editor**: means of applying precise import-line edits; required in effect (any editing mechanism works).

## Outputs
### Artifacts
- Edited source files with type-only import specifiers marked `type` (e.g. `src/components/ui.tsx`, `src/context/auth.tsx` in the trajectory); location: same file paths reported by `tsc`; format: modified `.ts`/`.tsx` source.
- Post-fix typecheck transcript: output of re-running `npx tsc --noEmit` in the project directory; format: shell output.

### Success criteria
- A re-run of the same typecheck command produces no `error TS1484` lines (in the observed case, the re-run produced no output at all).
- Import statements that mix value and type specifiers keep their value specifiers as plain runtime imports.

### Failure criteria
- TS1484 errors still appear after the edits, or new TS1484 errors appear in other files.
- An edit accidentally removed or changed a value import, breaking runtime code (would surface as new errors or later runtime failures).
- The typecheck command cannot run (TypeScript not installed / wrong directory).

## Preconditions
- The project's `tsconfig.json` (or an extended config) enables `verbatimModuleSyntax`; do not proceed by silencing the flag — if the user explicitly wants the flag removed, stop and confirm, since that changes emit semantics.
- `npx tsc --noEmit` runs successfully from the project directory (TypeScript installed locally; no compile-blocking install errors). Verify by running it once before editing.
- Node/npm (or the project's package manager) is available in the environment; the trajectory ran on Windows paths (`d:/CODSOFT/JOB_BOARD/frontend`) with `2>&1 | head -N` to cap output.
- Each file named in the TS1484 errors exists and is readable at the path printed by `tsc`.
- If prerequisites fail (missing tsconfig, tsc unavailable, unreadable files), stop and report the specific failure instead of making blind edits.

## Procedure
### Step 1: Capture the full TS1484 list
- Actions: from the project directory, run the typecheck capturing stderr, e.g. `npx tsc --noEmit 2>&1 | head -60`. Collect every `error TS1484` line: file path, line, column, and the offending type name in quotes.
- Inputs: project root.
- Outputs: list of `(file, specifier)` pairs to fix.
- Cautions: pipe through `head` only for display; the same command must be re-run later for verification. Note that the same output may contain unrelated errors (TS6133, TS2554) — do not conflate them with this task.
- Preserve: do not change `tsconfig.json` or run autofixers.
- Next: proceed when at least one TS1484 line is present; otherwise stop (nothing to fix).

### Step 2: Read each import statement and mark type-only specifiers
- Actions: for each file, open the import line indicated by the error (e.g. column positions map into the specifier list). For each flagged specifier, confirm it is used only in type positions in that file (type annotations, generic constraints, React prop/attribute types like `CSSProperties`, `ReactNode`, `InputHTMLAttributes`, `TextareaHTMLAttributes`, `SelectHTMLAttributes`).
- Inputs: file paths and specifier names from Step 1.
- Outputs: per-file edit plan: which specifiers get `type`, which stay plain.
- Cautions: a specifier flagged by TS1484 is by definition type-only under this flag, but double-check before deleting anything; never convert value imports.
- Preserve: value specifiers in the same statement (e.g. `createContext`, `useContext`, `useState`, `useEffect`) remain unmodified.
- Next: proceed to edits once the plan covers every TS1484 line.

### Step 3: Apply inline `type` modifiers
- Actions: rewrite each flagged import so type-only specifiers carry the inline modifier, keeping one statement per import line. Trajectory examples:
  - `import { CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from 'react'` → `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'`
  - `import { createContext, useContext, useState, useEffect, ReactNode } from 'react'` → `import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`
- Inputs: edit plan from Step 2.
- Outputs: edited files.
- Cautions: prefer the inline `type` modifier over `import type { ... }` when the statement mixes value and type specifiers. Do not reformat unrelated code in the file.
- Preserve: import order, module specifiers ('react', '@tanstack/react-router', '#/components/ui'), and all non-flagged lines.
- Next: once every flagged specifier in every listed file is edited, proceed to verification.

### Step 4: Re-run the typecheck and confirm TS1484 is gone
- Actions: re-run the exact command from Step 1 (trajectory: `npx tsc --noEmit 2>&1 | head -40`).
- Inputs: same project directory.
- Outputs: verification transcript.
- Cautions: an empty result means the whole check passed; non-empty output must be scanned — remaining TS1484 lines mean back to Step 2 for those files; other error codes are out of scope for this fix and should be reported separately.
- Next: stop when no TS1484 lines remain; otherwise iterate.

## Decision Rules
### When the flagged import statement contains only type specifiers
Convert the whole statement with the inline modifier on each specifier (as observed) or equivalently `import type { ... }`; the trajectory used inline `type` on every specifier.

### When the flagged import statement mixes value and type specifiers
Add `type` only to the flagged specifiers and leave value specifiers untouched (e.g. keep `createContext, useContext, useState, useEffect` plain, mark only `ReactNode`).

### When the same file has multiple TS1484 lines
They usually point to different columns of one import statement; fix the whole statement in a single edit rather than one specifier at a time (trajectory fixed five specifiers of `src/components/ui.tsx` line 1 in one edit).

### When the typecheck output also contains non-TS1484 errors
Fix only TS1484 in this pass; report the remaining codes (TS6133, TS2554 in the trajectory) as separate issues requiring their own fixes and verification.

### When the user wants `verbatimModuleSyntax` disabled instead
Stop; that changes emitted JS semantics and was not performed or verified in the trajectory.

## Invariants
- Do not modify `tsconfig.json` or any config to suppress TS1484; fix the imports.
- Do not change value imports or module specifiers; only add `type` modifiers to type-only specifiers.
- Do not touch unrelated files or unrelated errors in the same typecheck output.
- Do not delete imports as a shortcut for "unused"; TS6133-style cleanup is a separate concern with separate verification.
- Do not report success without re-running the typecheck after the edits.
- Do not assume a fix applied to one file covers others; every file listed in the TS1484 output must be edited and re-checked.

## Common Failures
### Failure: Only some TS1484 files edited, re-check still fails
- Symptoms: re-run of `tsc --noEmit` still prints TS1484 for a file that was not edited.
- Causes: multiple files flagged (trajectory had `src/components/ui.tsx` and `src/context/auth.tsx`); partial fix pass.
- Recovery: re-run Step 1, collect all remaining TS1484 lines, apply Step 3 to each, re-verify.

### Failure: Value import accidentally marked or removed
- Symptoms: new errors such as "X is not a value" / runtime module missing after the edit.
- Causes: converting a mixed statement wholesale with `import type { ... }` instead of inline modifiers.
- Recovery: restore the statement, re-apply inline `type` only to flagged specifiers (trajectory's mixed example: `createContext, useContext, useState, useEffect` stayed plain).

### Failure: Typecheck output truncated by `head` hides errors
- Symptoms: "no output" claim based on a truncated or different command, or TS1484 lines beyond the head limit.
- Causes: piping through `head -N` when many errors exist.
- Recovery: re-run without truncation or with a larger limit; compare error codes, not just line counts.

### Failure: Edits applied in the wrong project directory
- Symptoms: tsc reports the same errors or the file paths don't resolve.
- Causes: running `npx tsc` outside the directory containing `tsconfig.json` (trajectory cd'd into `<project>/frontend` first).
- Recovery: re-run from the directory that holds the tsconfig covering the reported files.

## Verification
- Re-run the identical typecheck from the project directory: `npx tsc --noEmit 2>&1` (trajectory used `npx tsc --noEmit 2>&1 | head -40`).
- Observe: zero lines containing `error TS1484`. In the trajectory the verification run returned "(Bash completed with no output)", i.e. the entire typecheck was clean.
- If any output remains, grep it for `TS1484`: remaining occurrences mean the fix is incomplete; other error codes are out of scope for this skill and should be listed separately rather than counted as failure of the TS1484 fix.
- Spot-check one edited file (e.g. `src/components/ui.tsx` line 1) to confirm every previously flagged specifier now reads `type <Name>` and no value specifier was altered.
- Do not treat an edit tool's "has been updated successfully" message as verification; only the fresh typecheck output counts.

## Examples
### Example 1: Mixed React import in a UI module
- Input: `npx tsc --noEmit` reports five TS1484 errors on `src/components/ui.tsx(1,10/25/36/57/81)` for `CSSProperties`, `ReactNode`, `InputHTMLAttributes`, `TextareaHTMLAttributes`, `SelectHTMLAttributes`.
- Procedure: Step 1 captured the errors; Step 3 edited line 1 in one Edit call.
- Expected result: line 1 becomes `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'`; subsequent typecheck shows no TS1484 for this file.
- Parameterized values: file `src/components/ui.tsx`; module `'react'`; the five specifier names; column offsets from the error lines.

### Example 2: Single type specifier among value imports
- Input: `src/context/auth.tsx(1,58): error TS1484: 'ReactNode' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.`
- Procedure: keep `createContext, useContext, useState, useEffect` as values; add `type` only to `ReactNode`.
- Expected result: `import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`.
- Parameterized values: file `src/context/auth.tsx`; value specifiers and module name vary by project.

### Example 3: Batch fix verified by a clean typecheck
- Input: six TS1484 errors across two files plus unrelated TS6133/TS2554 errors in the same output.
- Procedure: fix both files' imports (Example 1 and 2), leave the unrelated errors to a separate pass, then re-run `npx tsc --noEmit 2>&1 | head -40`.
- Expected result: verification output contains no TS1484 lines (trajectory observed empty output, meaning all diagnostics were resolved in the combined fix pass).
- Parameterized values: command, `head` limit, and file set come from the actual project.

## Evidence
file_id: `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__original`

Problem:
- source_index 217, source_part_index 0, category tool_result: "src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.\r\nsrc/components/ui.tsx(1,25): error TS1484: 'ReactNode' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.\r\nsrc/components/ui.tsx(1,36): error TS1484: 'InputHTMLAttributes' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.\r\nsrc/components/ui.tsx(1,57): error TS1484: 'TextareaHTMLAttributes' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.\r\nsrc/components/ui.tsx(1,81): error TS1484: 'SelectHTMLAttributes' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.\r\nsrc/context/auth.tsx(1,58): error TS1484: 'ReactNode' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled." — supports: the error format, multi-file/multi-specifier scope, and that unrelated error codes (TS6133, TS2554) share the same output.
- source_index 216, source_part_index 0, category tool_call:Bash: "cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -60" — supports: the diagnostic command and working directory.

Action:
- source_index 218, source_part_index 0, category tool_call:Edit: "old_string": "import { CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from 'react'", "new_string": "import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'" — supports: inline `type` modifiers fix five specifiers of one statement in a single edit.
- source_index 221, source_part_index 0, category tool_call:Edit: "old_string": "import { createContext, useContext, useState, useEffect, ReactNode } from 'react'", "new_string": "import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'" — supports: mixed value/type statements keep value specifiers plain; only the flagged specifier gets `type`.
- source_index 219 and 222, source_part_index 0, category tool_result: "The file d:/CODSOFT/JOB_BOARD/frontend/src/components/ui.tsx has been updated successfully. (file state is current in your context — no need to Read it back)" / "The file d:/CODSOFT/JOB_BOARD/frontend/src/context/auth.tsx has been updated successfully. (file state is current in your context — no need to Read it back)" — supports: both edits were applied; the edits alone are not proof of success.

Verification:
- source_index 254, source_part_index 0, category tool_call:Bash: "cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -40" with description "TypeScript check after fixes" — supports: verification is a re-run of the same typecheck after editing.
- source_index 255, source_part_index 0, category tool_result: "(Bash completed with no output)" with "is_error": false — supports: the post-fix typecheck produced no diagnostics, so no TS1484 errors remained.

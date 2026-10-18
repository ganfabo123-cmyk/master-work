---
name: fix-ts1484-type-only-imports
description: Use when TypeScript reports TS1484 errors ('X is a type and must be imported using a type-only import when verbatimModuleSyntax is enabled') on named imports. Helps the agent convert those imports to inline type modifiers without breaking value imports. Requires a TypeScript project with verbatimModuleSyntax enabled and a runnable tsc. Do not use when verbatimModuleSyntax is not enabled, or for other error codes in the same tsc output.
triggers:
  - "TS1484"
  - "must be imported using a type-only import"
  - "verbatimModuleSyntax"
---
# Fix TS1484 Type-Only Import Errors Under verbatimModuleSyntax

## Goal
Resolve TypeScript error TS1484 ('X' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled) so that `tsc --noEmit` reports no TS1484 errors, by converting the offending named imports to type-only form without breaking any runtime value imports.

## Scope
### In scope
- TS1484 errors reported by `tsc` for named imports of type-only symbols when `verbatimModuleSyntax` is enabled in tsconfig.
- Two import shapes observed in evidence: (a) imports where every named specifier is a type, and (b) mixed imports where only some specifiers are types and the rest are runtime values.
- Converting a type-only named specifier to the inline `type` modifier form (`import { type X, ... } from '...'`), which keeps the import a runtime import while marking individual specifiers as types.
- Re-running `tsc --noEmit` to confirm the TS1484 errors are gone.

### Out of scope
- Changing `verbatimModuleSyntax` (or any tsconfig setting) to suppress the error.
- Rewriting a whole import to `import type { ... } from '...'` when the import also carries runtime value specifiers, which would break the value bindings.
- Other error codes that may appear in the same `tsc` output (TS6133 unused declarations, TS2554 argument-count, etc.); handle each with its own targeted fix.
- Runtime behavior changes: this skill only adjusts import syntax and must not alter what a module exports or how it is used.
- Non-TypeScript concerns (lint, formatting, build tooling) unless they are part of the verification command.

## Inputs
1. **tsc error output** — Type: text (compiler diagnostics). Source: result of running `tsc --noEmit` (in evidence: `npx tsc --noEmit 2>&1 | head -60`). Required: yes. Constraints: each line is `path(line,col): error TS1484: 'Name' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.` The `Name` in quotes identifies the offending specifier. Default: none.

2. **Target source file** — Type: TypeScript/TSX file. Source: the path prefix of each TS1484 line (in evidence: `src/components/ui.tsx`, `src/context/auth.tsx`). Required: yes. Constraints: must be readable and contain the import statement on the reported line. Default: none.

3. **tsconfig with verbatimModuleSyntax** — Type: JSON config. Source: project `tsconfig.json`. Required: yes (as a precondition, not an input to edit). Constraints: `verbatimModuleSyntax` is enabled, which is why TS1484 is raised. Do not modify it. Default: none.

4. **Project root / working directory** — Type: filesystem path. Source: the directory the `tsc` command is run from (in evidence: the `frontend` subdirectory). Required: yes. Constraints: `npx tsc --noEmit` must resolve the project's tsconfig and dependencies from here. Default: none.

5. **Edit tool (file editor)** — Type: tool. Source: agent environment. Required: yes. Constraints: must apply exact-string edits to the import line. Default: none.

## Outputs
### Artifacts
- Edited import statements in the reported files, where each type-only named specifier is prefixed with the inline `type` modifier (e.g. `import { type CSSProperties, type ReactNode, ... } from 'react'`), while value specifiers are left unchanged.
- A verification command result from re-running `tsc --noEmit` after the edits.

### Success criteria
- Re-running `tsc --noEmit` from the project root produces no TS1484 diagnostics for the files that were edited (in evidence, the whole run produced no output at all).
- Every specifier named in a TS1484 message now appears with the inline `type` modifier in its import.
- No new errors are introduced by the edits.

### Failure criteria
- TS1484 diagnostics remain after the edits.
- A value specifier was wrongly converted to a type-only specifier, producing new errors (e.g. "used as a value") or breaking a runtime import.
- The verification command was not re-run, or its output was not inspected.

## Preconditions
1. **verbatimModuleSyntax is enabled** in the project's effective tsconfig. TS1484 is only raised under this setting; if it is off, this skill does not apply. Confirm via the tsconfig or by the presence of the TS1484 message itself.

2. **`tsc` is runnable from the project root** (in evidence, `npx tsc --noEmit` from the `frontend` directory). If the compiler cannot run or cannot resolve the tsconfig, stop and report that verification is impossible.

3. **The reported files are readable and editable**, and the import statement can be located at the reported line.

4. **The specifier roles are known**: for each flagged specifier, confirm it is used only as a type (annotations, generics, JSX type positions) and not as a runtime value, so you do not accidentally convert a value import.

5. **The scope is limited to import syntax**. Do not proceed if resolving the error would require changing tsconfig flags, runtime logic, or module resolution.

If any of these preconditions cannot be met, stop and report the specific blocker rather than making speculative edits.

## Procedure
### Step 1: Collect the TS1484 diagnostics
- Actions: Run `tsc --noEmit` from the project root (in evidence: `npx tsc --noEmit 2>&1 | head -60`). Grep or read the output for `error TS1484`. For each line, record the file path, the reported line/column, and the specifier name in quotes.
- Inputs: tsc output.
- Outputs: a list of (file, specifier) pairs to fix.
- Cautions: The same import line can produce multiple TS1484 lines, one per type specifier (in evidence, `src/components/ui.tsx` line 1 produced five). Group them by file and line so you edit each import once.
- Preserve: other error codes (TS6133, TS2554, ...) in the same output; handle them separately, not here.
- Next condition: proceed when at least one TS1484 line is present; otherwise this skill is not needed.

### Step 2: Read each flagged import and classify its specifiers
- Actions: Read the reported line in each file. For each specifier in that import, determine whether it is used only as a type or also as a runtime value. A specifier flagged by TS1484 is by definition being imported as a value binding that is actually only a type.
- Inputs: the source file.
- Outputs: the exact import statement and the set of specifiers that need the `type` modifier.
- Cautions: Do not convert the entire import to `import type { ... }` when the statement also imports runtime values — that would strip the value bindings and break the module. Inline `type` on individual specifiers is the safe form.
- Preserve: value specifiers exactly as they are.
- Next condition: proceed to edit once each flagged specifier is identified.

### Step 3: Apply inline `type` modifiers to the flagged specifiers
- Actions: Edit the import so every TS1484-flagged specifier is prefixed with `type `. For an all-type import (in evidence, `ui.tsx`): `import { CSSProperties, ReactNode, ... } from 'react'` becomes `import { type CSSProperties, type ReactNode, ... } from 'react'`. For a mixed import (in evidence, `auth.tsx`): `import { createContext, useContext, useState, useEffect, ReactNode } from 'react'` becomes `import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`.
- Inputs: the original import statement.
- Outputs: the edited import statement.
- Cautions: Keep the module specifier string (`'react'`, `@tanstack/react-router`, `#/components/ui`, ...) unchanged. Only insert `type ` before the flagged names; leave value names untouched.
- Preserve: import order, other specifiers, and the surrounding file.
- Next condition: proceed to verification after all flagged imports in the batch are edited.

### Step 4: Re-run `tsc --noEmit` and confirm the errors are gone
- Actions: Run the same type-check command again from the same directory (in evidence: `npx tsc --noEmit 2>&1 | head -40`). Confirm no TS1484 lines remain for the edited files, and ideally that the run is clean.
- Inputs: the edited project.
- Outputs: the new tsc output.
- Cautions: An empty output means success; do not assume success without seeing the command re-run and return clean. If other error codes remain, they are out of scope for this skill but should be reported.
- Preserve: all edits; do not revert.
- Next condition: stop when TS1484 is resolved; if it persists, return to Step 2 for the missed specifier.

## Decision Rules
### When every specifier in the flagged import is a type
- Apply the inline `type` modifier to each specifier. Example: `import { CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from 'react'` → `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'`.

### When the flagged import mixes value and type specifiers
- Apply `type` only to the specifiers named in the TS1484 diagnostics and leave the value specifiers unchanged. Example: `import { createContext, useContext, useState, useEffect, ReactNode } from 'react'` → `import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`. Do not convert the whole statement to `import type { ... }`.

### When a flagged name is also imported from a local alias path (e.g. `#/components/ui`)
- The same inline-`type` edit applies; only the specifier syntax changes, not the module specifier string.

### When the same file reports multiple TS1484 lines on one import line
- Treat them as one edit: add `type` to every flagged specifier in that single import statement in one pass.

### When the tsc output still shows TS1484 after editing
- Re-read the exact import line and check for a specifier you missed (including specifiers at a different column on the same line), then edit and re-verify.

### When resolving TS1484 would require changing a value import or tsconfig
- Stop; that is out of scope. Inline `type` on individual specifiers never requires changing values or compiler flags.

## Invariants
- Change only import syntax; never alter the module specifier string, the set of imported names, or runtime logic.
- Never convert an import that also carries value specifiers into a whole-statement `import type { ... }`; use inline `type` on individual specifiers only.
- Never change tsconfig (including `verbatimModuleSyntax`) to make the error disappear.
- Never modify unrelated files or unrelated error codes in the same tsc run under this skill.
- Never report success without re-running `tsc --noEmit` and observing that the TS1484 diagnostics for the edited files are gone.
- Never treat an empty or truncated command result as proof of success unless the verification command was actually executed and returned clean.
- Do not infer that a specifier is a value solely because it is imported without `type`; the TS1484 diagnostic itself establishes it is type-only.

## Common Failures
### Failure: Converted a whole import to `import type` and broke value imports
- Symptoms: after the edit, code that used a value from that import fails to compile or fails at runtime (the binding is now type-only); new errors appear at usage sites.
- Causes: the import statement mixed value and type specifiers, but the entire statement was rewritten to `import type { ... }`, erasing the value bindings.
- Recovery: revert to a value import and apply the inline `type` modifier only to the specifiers named in the TS1484 diagnostics, then re-run `tsc --noEmit`.

### Failure: Missed a specifier on a multi-error import line
- Symptoms: some TS1484 lines clear but others on the same file/line persist after the edit.
- Causes: one import line produced several TS1484 diagnostics (one per type specifier) and only some specifiers were prefixed.
- Recovery: re-read the import, add `type` to every remaining flagged specifier in one edit, and re-verify.

### Failure: Edited the wrong import or file
- Symptoms: TS1484 remains at the original path/line after editing.
- Causes: the diagnostic path or line was misread, or a similarly named file/import was changed instead.
- Recovery: re-read the exact path and line/column from the tsc output and apply the edit to the correct statement.

### Failure: Claimed success without a clean re-run
- Symptoms: the fix looks correct but errors are still present, or a downstream step fails on the same code.
- Causes: `tsc --noEmit` was not re-run, or its output was truncated/not inspected.
- Recovery: always re-run the type check and confirm no TS1484 remains before reporting done.

### Failure: Cause not confirmed
- Symptoms: uncertain whether an edit actually addressed TS1484 or masked something else.
- Causes: multiple simultaneous edits or unrelated changes in the same batch.
- Recovery: isolate the import edit, re-run tsc, and confirm the specific diagnostic cleared.

## Verification
1. **Re-run the type check** from the project root with the same command used to discover the error (in evidence: `npx tsc --noEmit 2>&1 | head -40`). Observable check: the output contains no `error TS1484` lines for the edited files; an entirely empty output indicates a fully clean check.

2. **Confirm each flagged specifier now carries the inline `type` modifier** by reading the edited import lines. Observable check: names such as `CSSProperties`, `ReactNode`, `InputHTMLAttributes`, `TextareaHTMLAttributes`, `SelectHTMLAttributes` appear as `type CSSProperties`, `type ReactNode`, etc.

3. **Confirm value specifiers were left intact** in mixed imports. Observable check: names such as `createContext`, `useContext`, `useState`, `useEffect` still appear without `type`.

4. **Confirm no new errors were introduced** by comparing the post-edit tsc output to the pre-edit output. Observable check: the TS1484 count drops to zero and no new diagnostic appears at the edited lines.

5. **Do not rely on build success as a substitute** for the type check unless the build is also known to run `tsc`; a clean `tsc --noEmit` is the direct evidence for TS1484 resolution.

## Examples
### Example 1: All-type import from a package
- input: `tsc --noEmit` reports `src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.` (and analogous lines for `ReactNode`, `InputHTMLAttributes`, `TextareaHTMLAttributes`, `SelectHTMLAttributes` on the same line). The import reads: `import { CSSProperties, ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from 'react'`.
- procedure: Follow Steps 1–4. Because every specifier on the line is a type, apply the inline `type` modifier to each.
- expected result: The import becomes `import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'`, and re-running `npx tsc --noEmit` produces no TS1484 lines for this file.
- parameterized values: file path `src/components/ui.tsx`; module specifier `'react'`; type specifiers `CSSProperties`, `ReactNode`, `InputHTMLAttributes`, `TextareaHTMLAttributes`, `SelectHTMLAttributes`; verification command `npx tsc --noEmit 2>&1 | head -40`; clean result `(Bash completed with no output)`.

### Example 2: Mixed value/type import from a package
- input: `tsc --noEmit` reports `src/context/auth.tsx(1,58): error TS1484: 'ReactNode' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled.` The import reads: `import { createContext, useContext, useState, useEffect, ReactNode } from 'react'`.
- procedure: Follow Steps 1–4. Only `ReactNode` is a type; `createContext`, `useContext`, `useState`, `useEffect` are runtime values and must be preserved. Apply `type` to `ReactNode` only.
- expected result: The import becomes `import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'`, value bindings remain intact, and re-running `npx tsc --noEmit` produces no TS1484 lines for this file.
- parameterized values: file path `src/context/auth.tsx`; module specifier `'react'`; value specifiers `createContext`, `useContext`, `useState`, `useEffect`; type specifier `ReactNode`; verification command `npx tsc --noEmit 2>&1 | head -40`; clean result `(Bash completed with no output)`.

## Evidence
file_id: claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01

- kind: problem
  source_index: 217
  source_part_index: 0
  quote: "src/components/ui.tsx(1,10): error TS1484: 'CSSProperties' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled."
  supports: Establishes the problem signature — TS1484 on a named type imported without the type-only form when verbatimModuleSyntax is enabled; the same line set also flags ReactNode, InputHTMLAttributes, TextareaHTMLAttributes, and SelectHTMLAttributes in ui.tsx.

- kind: problem
  source_index: 217
  source_part_index: 0
  quote: "src/context/auth.tsx(1,58): error TS1484: 'ReactNode' is a type and must be imported using a type-only import when 'verbatimModuleSyntax' is enabled."
  supports: Establishes that TS1484 also arises in a mixed import (values plus one type), which is the case where whole-statement `import type` must be avoided.

- kind: action
  source_index: 218
  source_part_index: 0
  quote: "import { type CSSProperties, type ReactNode, type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes } from 'react'"
  supports: Demonstrates the fix for an all-type import — inline `type` modifier applied to every specifier in the ui.tsx import.

- kind: action
  source_index: 221
  source_part_index: 0
  quote: "import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'"
  supports: Demonstrates the fix for a mixed import — inline `type` applied only to the type specifier (ReactNode) while value specifiers (createContext, useContext, useState, useEffect) are preserved, showing whole-statement `import type` is not used.

- kind: verification
  source_index: 254
  source_part_index: 0
  quote: "cd d:/CODSOFT/JOB_BOARD/frontend && npx tsc --noEmit 2>&1 | head -40"
  supports: The verification command re-run after the edits (description: "TypeScript check after fixes"), matching the discovery command used at source_index 216.

- kind: verification
  source_index: 255
  source_part_index: 0
  quote: "(Bash completed with no output)"
  supports: The post-fix `tsc --noEmit` returned empty output, directly evidencing that the TS1484 (and other) diagnostics were resolved; the assistant then stated "TypeScript passes with no errors." (source_index 256).

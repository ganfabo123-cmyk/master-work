---
name: preserve-separator-space-in-concatenated-prolog-fixture-strings
description: Use when a Prolog-style lexer tokenizes '.' as an operator instead of a clause terminator, producing parse errors like "expected '.', got operator '.'", typically when C/C++ adjacent string literals concatenate clauses into '....).fact(...' with no space after the dot. Helps the agent fix the fixture string literals (or lexer) and verify with the test suite. Requires the project's lexer/parser test harness to verify. Do not use when the lexer documents dot-followed-by-non-space as a valid operator and the failing input has no adjacent-string concatenation.
triggers:
  - "expected '.', got operator '.'"
  - "TOK_DOT"
---
# Keep separator space after terminating dots in concatenated Prolog fixture strings

## Goal
Fix Prolog-style lexer/parser failures where '.' is tokenized as an operator instead of a clause terminator, so that fixture sources built from adjacent C/C++ string literals load fully and queries against them succeed.

## Scope
### In scope
- Parse errors of the form `expected '.', got operator '.'` (or an equivalent "unexpected operator" at a clause boundary) when loading multi-clause source strings.
- The lexer rule that emits TOK_DOT only when '.' is at end-of-input or followed by whitespace, and TOK_OP otherwise.
- Fixing the fixture strings (adding a trailing space to each concatenated clause literal) and auditing all other fixtures with the same pattern.
- Verifying with the full test suite.

### Out of scope
- Changing the lexer's dot rule itself (in the trace this ambiguity is deliberate: `...` style operators and `.` inside atoms rely on it).
- Operator-precedence parsing and other lexer token classes.

## Inputs
- Parse/lex error output (string): required; must contain `expected '.', got operator '.'` or show the lexer emitting an operator token for '.'.
- The lexer's dot-handling rule (source snippet): required; confirms '.' requires following whitespace or end-of-input to be a terminator.
- Test/fixture files containing multi-clause source literals built by adjacent string concatenation (e.g. `ctx.load("parent(alice, bob). parent(bob, carol)." "gp(X,Y) :- ...")`; required.
- The test build-and-run command; required; no default.
- No defaults for the above.

## Outputs
### Artifacts
- Edited fixture strings in the affected test file(s): every clause-ending literal now ends with `". "` (a space after the terminating dot) before an adjacent literal continues the source.
- Audit result: no remaining adjacent-literal concatenation where a `."` is directly followed by `"` .

### Success criteria
- The loader function no longer reports the dot parse error, loads the expected clause count, and the previously failing query tests pass in the suite run.

### Failure criteria
- Any remaining fixture where `."` is immediately followed by `"` in a concatenated source.
- Suite tests still failing with the same parse error.

## Preconditions
- The lexer really distinguishes the cases: read its dot-handling code and confirm `.` followed by a non-space character is lexed as an operator (otherwise this skill does not apply).
- The failing loader's error message identifies the clause boundary and the offending token (in the trace: `parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'`).
- You can rebuild and rerun the test suite to verify.
- Isolation is available: a minimal program loading just the failing source passes, showing the problem is the input string, not the engine.

## Procedure
### Step 1: Reproduce with a minimal load and read the lexer rule
- Actions: Build a tiny program that loads the exact failing source string and prints the parse error; read the lexer's '.' branch to confirm the whitespace requirement.
- Inputs: failing fixture string, lexer source.
- Outputs: confirmed mechanism (the '.' after `)` followed directly by a letter lexes as TOK_OP).
- Cautions: do not change the lexer; the ambiguity is intentional for other tokens.
- Preserve: engine code untouched.
- Next: proceed to Step 2.

### Step 2: Locate every concatenation boundary that drops the separator
- Actions: Grep the fixture file for string literals ending in `."` and check whether the next character in the source is another quote (implicit concatenation). In the trace this affected the two-body rule, recursive ancestor, reachable-path, and cut fixtures.
- Inputs: test file, grep.
- Outputs: list of offending literals.
- Cautions: single-string fixtures with internal spaces (e.g. `"parent(alice, bob). parent(bob, carol). grandparent(...)."`) are already fine; only the join points matter.
- Preserve: the clause text itself.
- Next: proceed to Step 3.

### Step 3: Add the trailing space at each join
- Actions: Change each affected literal to end with `". "` — e.g. `"parent(alice, bob). parent(bob, carol). "` followed by `"gp(X,Y) :- parent(X,Z), parent(Z,Y)."`; also fix single-line loads where the last clause lacks a trailing space only if needed by the same rule.
- Inputs: the offending literals.
- Outputs: edited fixtures.
- Cautions: the edit tool may report "string not found" if whitespace differs; re-read the exact lines before editing rather than guessing.
- Preserve: predicate names, arity, and clause order.
- Next: rebuild and rerun the suite.

### Step 4: Verify with the full suite
- Actions: Rebuild the test binaries and run them; confirm the previously failing tests now pass (in the trace the solver suite went from 18/22 to 22/22).
- Inputs: build/run command.
- Outputs: per-suite pass counts.
- Cautions: if a suite's binary cannot be overwritten (`LNK1105`), kill lingering test processes and rerun; do not count an environmental lock as a test result.
- Next: stop when the affected suites pass and no offending concatenations remain (grep again).

## Decision Rules
### When the parse error names the terminator itself (`expected '.', got operator '.'`)
The '.' was followed by a non-space character. Check for adjacent string-literal concatenation first; add the missing space in the fixture rather than modifying the lexer.

### When the same loader call passes in isolation but fails inside a test using concatenated literals
The test's literal differs from the isolated one — compare them character by character; the missing trailing space is usually at the join.

### When the lexer rule requires whitespace after '.' by design (operators like `...`, dots inside quoted atoms)
Do not relax the lexer to accept `).fact` as a clause boundary; fix inputs instead, because changing the rule would break the operator/atom cases.

### When only the final clause of a fixture lacks a trailing dot-space but no error occurs
Leave it: end-of-input also satisfies the terminator rule; only mid-source joins are defective.

## Invariants
- The lexer and parser are not modified; only fixture inputs change.
- Predicate names, arities, and clause ordering in fixtures are unchanged — only separator whitespace is added.
- Every adjacent-literal join in fixture sources keeps at least one whitespace character after a terminating dot.
- Success is claimed only from a full suite run showing the previously failing tests passing.

## Common Failures
### Failure: parse error at the second or third clause of a multi-literal load
- Symptoms: `[load] parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'`, and the loader returns -1 with earlier clauses already stored (so downstream counts look corrupted, e.g. `db.clause_count=1` with `arena.count=6`).
- Causes: implicit concatenation produced `carol).gp(...)`, and the lexer lexes '.' followed by a letter as TOK_OP.
- Recovery: add the trailing space to the preceding literal; re-run.

### Failure: edit does not apply ("String to replace not found")
- Symptoms: the Edit tool cannot find the expected literal.
- Causes: the file's actual whitespace differs from the assumed version (the debug prints added earlier also shifted context).
- Recovery: grep/read the exact lines and redo the edit against the real text.

### Failure: only some tests were fixed and suite still red
- Symptoms: one fixture fixed, others (`ancestor`, `reachable`, cut test) still fail.
- Causes: the same concatenation pattern appears in several tests; a single fix is not representative.
- Recovery: grep for all `."`-ending literals followed immediately by `"` and fix every join.

## Verification
- The failing loader now reports the full expected clause count (e.g. 3 clauses for two facts plus one rule) instead of -1.
- The previously failing tests pass: in the trace the solver suite reported 22/22 including `two-body rule resolves via conjunction`, `recursive rule — ancestor`, and `backtracking finds second solution after first fails`.
- A grep over the fixture file finds no literal ending in `."` immediately followed by `"` .
- No lexer/parser source file is modified by the change (diff review).

## Examples
### Example 1: two-body rule fixture
- Input: `ctx.load("parent(alice, bob). parent(bob, carol)." "gp(X,Y) :- parent(X,Z), parent(Z,Y).");` producing `parse error after 1 clauses: ... expected '.', got operator '.'`.
- Procedure: Step 3 — change the first literal to `"parent(alice, bob). parent(bob, carol). "` (trailing space), rebuild, rerun the solver suite.
- Expected result: `?- gp(alice, carol).` returns 1 solution and the suite reaches 22/22.
- Parameterized values: predicates `parent/2`, `gp/2`, load-then-query harness.

### Example 2: multi-clause recursive fixture with several joins
- Input: three concatenated literals `"parent(alice, bob). parent(bob, carol). parent(carol, dave)."` + `"ancestor(X,Y) :- parent(X,Y)."` + `"ancestor(X,Y) :- parent(X,Z), ancestor(Z,Y)."` with no spaces at the joins.
- Procedure: Step 2 audit + Step 3 — append a space to each of the first two literals; rerun.
- Expected result: `?- ancestor(alice, dave).` succeeds and `?- ancestor(dave, alice).` fails as asserted.
- Parameterized values: recursive predicate `ancestor/2`, three-clause fixture.

## Evidence
- problem — file_id `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index 1127, source_part_index 0, quote: "parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'", supports: instrumented loader output pinpointed the '.' -as-operator failure at a clause boundary, occurring after one clause had already been stored.
- problem — same file_id, source_index 1113, source_part_index 0, quote: "[DEBUG two-body] loaded=-1 db.clause_count=1 db.pred_count=1 arena.count=6", supports: the load aborted mid-way (returned -1) while partial state showed earlier clauses stored, the signature of a mid-source lexing failure rather than an engine bug.
- action — same file_id, source_index 1136, source_part_index 0, quote: "        \"parent(alice, bob). parent(bob, carol). \"\n        \"gp(X,Y) :- parent(X,Z), parent(Z,Y).\"", supports: the fix adds the missing separator space at the adjacent-literal join; the same pattern was applied to the ancestor (1147) and reachable (1152) fixtures.
- verification — same file_id, source_index 1191, source_part_index 0, quote: "  PASS  two-body rule resolves via conjunction   PASS  recursive rule — ancestor   PASS  multiple clauses — correct solution count   PASS  backtracking finds second solution after first fails", supports: after the separator fixes the previously failing solver tests all pass and the suite reports 22/22 in the same run.

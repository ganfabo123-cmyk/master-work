---
name: space-after-dot-in-prolog-source-strings
description: Use when a Prolog-style loader reports a parse failure like "expected '.', got operator '.'" or a load helper returns -1 while only part of the source was asserted. Helps the agent recognize that a '.' immediately followed by a letter (from joining adjacent string literals) is lexed as an operator instead of a clause terminator, and fix the source literals by adding a trailing space. Requires the failing loader's error message or loaded-count diagnostic. Do not use when the parser error names a different token or the source strings already end each clause with whitespace.
---
# Put Whitespace After '.' When Concatenating Prolog Source Strings

## Goal
Diagnose and fix Prolog-style source loaders that fail with "expected '.', got operator '.'" (or return -1 after asserting only part of the input) by finding '.' characters that are immediately followed by a letter because adjacent string literals were concatenated without whitespace, and correcting the literals so every clause terminator is followed by whitespace.

## Scope
### In scope
- Loader/parser failures whose message names the '.' itself as the wrong token (`expected '.', got operator '.'`), or a load helper that returns -1 with a partial clause count while the source text looks well-formed.
- Source strings assembled from adjacent C/C++ literals (`"....carol)."` + `"gp(X,Y) :- ..."`) where the join produces `).gp(`.
- The lexer rule that '.' is a clause terminator only when followed by whitespace or end-of-input, otherwise an operator token.
- Fixing the string literals (trailing space at each join) and confirming with the affected suites.

### Out of scope
- Parser/grammar changes: the '.'-needs-layout rule matches standard Prolog tokenization and was not changed.
- Parse errors naming any other token, lex errors, or capacity overflows.
- Test assertions unrelated to loading (assert-via-query semantics, etc.) that fail alongside these.

## Inputs
1. **Loader error message or diagnostic** — type: tool result; source: parser error string or a temporary `fprintf` in the load helper; required: yes; constraint: must show '.' treated as an operator or a load returning -1 partway (e.g. after 1 clause); default: 无.
2. **The source literals being concatenated** — type: test/fixture source; required: yes; constraint: must be able to see where one literal ends with '.' and the next begins with a letter; default: 无.
3. **Lexer rule for '.'** — type: source; required: yes; constraint: confirms terminator vs operator decision is layout-sensitive; default: 无.
4. **Failing test cases** — type: test suite; required: yes; constraint: queries whose expectations depend on the mis-joined clauses; default: the project's suite.

## Outputs
### Artifacts
- Edited source literals: a whitespace character added after the '.' at each concatenation point (same files, no behavior changes elsewhere).
- Optionally a temporary load diagnostic (loaded-count / parse-error print) added during diagnosis and removed afterwards.

### Success criteria
- The load helper reports the full expected clause count instead of -1.
- Every previously failing test that depends on those sources passes (observed: `22/22 tests passed` for the solver suite).

### Failure criteria
- Error message still names '.' as an operator, or load still stops partway.
- A different token now fails — the problem is elsewhere; do not keep adding spaces.

## Preconditions
- You have the actual parser/loader error text (or can add a diagnostic that prints the parser's `error_msg` and the number of clauses asserted before failure). Symptom-only "test fails" is not enough.
- You can inspect the raw string literals, including adjacent-literal joins, in the failing test or fixture.
- The lexer's '.' handling is readable and shows whether layout decides terminator vs operator; if the grammar says otherwise, stop and re-diagnose.
- The failing cases can be re-run after a one-character source change.
- If any precondition is missing, gather it before editing — do not apply blind whitespace changes across the file.

## Procedure
### Step 1: Capture the exact failure text
- Actions: run the failing suite/test; if the load helper swallows the error, temporarily print the parser's `error_msg` and the clause count asserted before failure; record the message and how many clauses made it in.
- Inputs: failing test name.
- Outputs: e.g. `parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'` or a debug line showing `loaded=-1 ... arena.count=6`.
- Cautions: a clause count of 1–2 with a full arena means parsing died mid-source, not at the first token; a crash instead of an error message is a different problem (stack overflow).
- Next: go to Step 2 if the message names '.' as an operator.

### Step 2: Read the lexer rule for '.'
- Actions: locate the '.' branch; confirm it emits the terminator token only when the next character is whitespace or end-of-input, else emits an operator token.
- Outputs: confirmed layout sensitivity.
- Cautions: do not "fix" this by changing the lexer unless the project's grammar says otherwise — the rule matches standard Prolog tokenization.
- Next: go to Step 3.

### Step 3: Inspect the source literals at the reported position
- Actions: open the failing test/fixture; reconstruct the concatenated string and find joins where a literal ends in '.' and the next begins with a letter (e.g. `"...carol)."` immediately followed by `"gp(X,Y) :- ..."` → `carol).gp(X,Y)`).
- Outputs: the exact join(s) producing `.<letter>`.
- Cautions: C/C++ adjacent literals concatenate with no separator — the join is invisible when reading line by line.
- Next: go to Step 4.

### Step 4: Add whitespace at each join
- Actions: append a space (or newline) to the literal that ends with '.' so the merged text reads `carol). gp(X,Y)`; apply to every join in the same fixture, not only the reported one.
- Inputs: the literals from Step 3.
- Outputs: edited test/fixture source.
- Cautions: keep clause text otherwise byte-identical; this is not the place to rename predicates or reorder tests.
- Preserve: test names, expectations, and all other assertions.
- Next: go to Step 5.

### Step 5: Re-run and confirm the full load
- Actions: rerun the affected suite; if a diagnostic was added, verify the clause count now equals the number of clauses in the source; then run the whole suite.
- Outputs: pass tallies.
- Cautions: if a test still fails but loading succeeds, the remaining failure is unrelated (e.g. an assertion exercising assert-via-query semantics) — report it separately instead of adding more whitespace.
- Next: stop when all suites pass; remove any temporary diagnostics.

## Decision Rules
### When the parser error says `expected '.', got operator '.'`
The '.' in the source was lexed as an operator; find the character immediately after it and fix the source text, not the parser.

### When load returns -1 with a partial clause count
Treat as a mid-source parse stop; go straight to the literals' concatenation points around the reported position.

### When the offending character after '.' is a letter produced by joining string literals
Add a space at the end of the first literal; check every adjacent-literal join in that fixture, since the same pattern is usually repeated.

### When the error names a different token
Stop: this skill does not apply; diagnose grammar/input issues normally.

### When loading now succeeds but a test still fails
Split the cases — verify load counts first; residual assertion failures belong to a different root cause and must not be folded into this fix.

## Invariants
- Only whitespace is added to source literals; no predicate names, clause bodies, or assertions change as part of this fix.
- The lexer/parser grammar is not modified — the layout-sensitive '.' rule stays as-is.
- Temporary diagnostics introduced for diagnosis are removed (or kept only if the project already logs loads) before reporting done.
- All other suites keep their pass counts; a fix that requires rewriting unrelated tests is not this fix.
- The claim of resolution rests on the re-run output of the previously failing suite, not on the edit itself.

## Common Failures
### Failure: fix applied only at the reported join, other tests still fail
- Symptoms: one test now loads, but sibling tests with the same concatenation pattern still return -1.
- Causes: the pattern (`"...)."` + `"pred(...)"`) was copy-pasted across the fixture.
- Recovery: grep all adjacent-literal joins in the fixture and add the space at each; rerun the suite.

### Failure: message `expected '.', got operator '.'` but the source looks fine on screen
- Symptoms: eyeballing the string shows `carol).` followed by a newline in the source code.
- Causes: the newline is between two C++ literals, not inside the string — concatenation yields `carol).gp(...)` with no space.
- Recovery: examine the literal boundaries (paste the merged string or print it from the diagnostic) rather than the formatted code.

### Failure: still failing after adding spaces
- Symptoms: same error or a new token in the message.
- Causes: a genuinely malformed clause, or the '.' was in a quoted atom / the real stop is elsewhere than assumed.
- Recovery: re-read the message and the printed clause count; if the error names a different token, abandon this fix and re-diagnose.

### Failure: suite passes only because the failing test was changed wholesale
- Symptoms: the suite is green but a test's mechanism was replaced (e.g. assert-via-query rewritten to load-then-query).
- Causes: a second, unrelated defect hidden in the same test.
- Recovery: keep the whitespace fix for the load problem and record the mechanism change as a separate, separately-verified edit.

## Verification
Observable checks:

1. The load path reports success for the full source: previously `loaded=-1` with a partial database (one clause in, arena holding the two facts before the stop), now the loader returns the expected clause count and no parse-error line is printed.
2. The suite that encoded the mis-joined sources flips from `18/22 tests passed` to `22/22 tests passed`.
3. The specific tests that failed on the join now report PASS (e.g. `two-body rule resolves via conjunction`, `recursive rule — ancestor`, `backtracking finds second solution after first fails`).
4. No other suite's tally changes.
5. Rerun any temporarily added diagnostics' suites after removing the diagnostics; if a relink error (`LINK : fatal error LNK1105: cannot close file`) blocks a suite, rebuild and rerun it before counting a pass or failure.

## Examples
### Example 1: Adjacent literals join `).` with a predicate name
- Input: fixture containing
  `ctx.load("parent(alice, bob). parent(bob, carol)." "gp(X,Y) :- parent(X,Z), parent(Z,Y).");`
  which merges to `...carol).gp(X,Y)...`; the suite reports `parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'` and `18/22 tests passed`.
- Procedure: Step 1 capture the message → Step 2 confirm the lexer's `if (i+1U >= len || is_space(src[i+1U]))` terminator rule → Step 3 find the literal boundary → Step 4 edit so the first literal ends `parent(bob, carol). ` → Step 5 rerun.
- Expected result: loads complete; suite prints `22/22 tests passed`.
- Parameterized values: the fixture string and predicate names; the fix is a single whitespace character per join.

### Example 2: Silent partial load in a diagnostic-enabled helper
- Input: load helper augmented with an error print; debug line shows `[DEBUG two-body] loaded=-1 db.clause_count=1 db.pred_count=1 arena.count=6`.
- Procedure: partial clause count + arena showing exactly the pre-join facts ⇒ go directly to the literals around clause 2 (Step 3), apply the space, rerun, then remove the temporary diagnostic.
- Expected result: `loaded` equals the clause count in the source; the dependent query tests pass.
- Parameterized values: any loader that concatenates source fragments in fixtures or documentation examples.

## Evidence
problem:
- file_id: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index: 166, source_part_index: 0, quote: "parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'", supports: the signature error — the parser expected a terminator while the lexer had produced '.' as an operator.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1113, source_part_index: 0, quote: "[DEBUG two-body] loaded=-1 db.clause_count=1 db.pred_count=1 arena.count=6", supports: partial load (one clause stored, arena holding only the pre-join facts) confirming a mid-source parse stop rather than a logic failure.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-05, source_index: 820, source_part_index: 0, quote: "if (i+1U >= len || is_space(src[i+1U]))", supports: the lexer's layout rule that makes '.' immediately followed by a letter an operator token, i.e. the mechanism behind the failure.

action:
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1129, source_part_index: 0, quote: "parent(alice, bob). parent(bob, carol). ", supports: the actual fix — a space appended after the '.' inside the first literal so the adjacent-literal join yields `carol). gp(X,Y)`.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1136, source_part_index: 0, quote: "parent(alice, bob). parent(bob, carol). ", supports: the same correction applied to the second test using the identical concatenation pattern (all joins in the fixture addressed, not just the reported one).

verification:
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1048, source_part_index: 0, quote: "18/22 tests passed", supports: the pre-fix solver-suite state with the four load-dependent failures.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1187, source_part_index: 0, quote: "22/22 tests passed", supports: the post-fix solver suite passing after the string-literal space edits (with an unrelated test-mechanism edit in the same window, recorded separately).
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1187, source_part_index: 0, quote: "two-body rule resolves via conjunction", supports: one of the previously failing tests now passing, tied to the join that was corrected.
- file_id: claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index: 1187, source_part_index: 0, quote: "LINK : fatal error LNK1105: cannot close file", supports: the caveat that file locks made other suites unrunnable in that pass and had to be rebuilt before counting results.

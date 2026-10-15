---
name: fix-concatenated-clause-strings-missing-separator
description: Use when a parser rejects a multi-clause source string built from adjacent C++ string literals with 'expected '.', got operator '.''. Helps the agent locate the literal boundary that swallowed the clause terminator and repair every occurrence in the test inputs. Requires a harness that can print the parser's error message and a rebuild of one test suite. Do not use when the lexer itself must change or when the failure is a link or startup crash.
triggers:
  - "expected '.', got operator '.'"
  - "parse error after"
---
# Fix Parse Errors from Adjacent String Literals That Drop Whitespace

## Goal
Repair multi-clause source strings whose adjacent C++ literal concatenation glued a clause-terminating dot to the next clause's first character, so the loader parses every clause and the previously failing tests pass.

## Scope
### In scope
- Test/helper code that assembles several clauses from adjacent string literals (`"....carol)."` + `"gp(X,Y) :- ..."`).
- Diagnosing with a temporary harness print of the parser's `error_msg`, then reading it.
- Inserting whitespace at the literal boundaries and sweeping for every other occurrence of the same pattern.

### Out of scope
- Changing the lexer's rule for tokenising `.` (left untouched in the trace — the language rule `.` followed by whitespace is a terminator, otherwise an operator, stayed as is).
- Engine/solver bugs, link errors, and startup crashes (covered elsewhere).
- Parser grammar changes.

## Inputs
1. **Suite failure output** — type: text tool result; source: running the built test binary; required: yes; constraint: shows which assertions fail (e.g. `FAIL  two-body rule resolves via conjunction`); default: 无.
2. **Parser error message from a diagnostic build** — type: text tool result; required: yes; constraint: must come from a temporary `fprintf(stderr, ...)` the harness prints with `p.error_msg` (trace: `parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'`); default: 无.
3. **Test source with concatenated literals** — type: source (`tests/test_solver.cpp`); required: yes; constraint: only the input strings may be edited; default: 无.
4. **Build command** — type: shell/PowerShell script; required: yes; constraint: recompiles the single suite (trace: `clang++ -std=c++23 -Iinclude -Itests -g -O0 <shared sources> tests/test_solver.cpp -o <bin>`); default: 无.
5. **Lexer rule for `.`** — type: source (`parser/lexer.cpp`); required: no; constraint: in the trace the rule was described from the assistant's memory, not from a tool read — verify it yourself if you need it; default: 无.

## Outputs
### Artifacts
- Edited test input strings with a trailing space before every closing quote that ends a non-final clause (trace: four `load(...)` call sites in `tests/test_solver.cpp`).
- The same file with the temporary diagnostic prints removed.
- Rebuilt suite binary.

### Success criteria
- The previously failing tests pass: the solver suite prints `22/22 tests passed` and its run shows `PASS  two-body rule resolves via conjunction`.
- No output contains `expected '.', got operator '.'`.
- No debug prints remain in the committed test source.

### Failure criteria
- Any parse error remains in the suite output.
- A different clause in another literal still lacks a separator (only some sites fixed).

## Preconditions
- The failure is a parse error from the test's own input string, not a link error or startup crash — confirm the suite at least runs.
- The harness can be modified temporarily to print the parser's `error_msg` (the trace's `load()` helper had access to `p.error_msg`).
- Permission to edit the test input strings only; the lexer/parser sources stay unchanged.
- Ability to rebuild and rerun the single affected suite after the edit.

## Procedure
### Step 1: Surface the real error instead of theorising
- actions: add a temporary diagnostic in the harness's load/parse path that prints, for each failure branch, the stage, the parser's `error_msg`, and how many clauses loaded; rebuild the suite and run it.
- inputs: test harness (`SolverCtx::load` in the trace); build command.
- outputs: one line per failure, e.g. `[load] parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'`.
- cautions: without this print the suite only reports `FAIL` on the assertion, which invites speculation about shared state or engine bugs — in the trace several rounds of such speculation preceded the print.
- preserve: the failing tests themselves (do not weaken assertions yet).
- next: read the message (Step 2); remove the diagnostics in Step 5.

### Step 2: Read the parser message literally
- actions: map `expected '.', got operator '.'` to the tokenisation: the terminating `.` was emitted as an operator token rather than a terminator token.
- inputs: the diagnostic line.
- outputs: the conclusion that the character following `.` was not whitespace (the lexer's dot rule, as described in the trace: terminator only when the dot is at end or followed by space).
- cautions: this rule description came from the assistant's message, not from a tool read of `parser/lexer.cpp` — confirm in the source if you rely on it.
- next: go to Step 3.

### Step 3: Inspect the literal boundaries in the failing input
- actions: read the `load(...)`/string arguments of the failing tests; look for a string ending in `.` immediately adjacent to a string starting with the next clause, e.g. `"parent(alice, bob). parent(bob, carol)."` concatenated with `"gp(X,Y) :- parent(X,Z), parent(Z,Y)."` → `...carol).gp(...)`.
- inputs: test source lines of the failing cases.
- outputs: identified sites where C++ literal concatenation removed the whitespace after the terminating dot.
- cautions: the concatenation is invisible in the rendered prose — check the closing quote of each literal, not the spacing you *think* is there; an isolated repro may pass simply because it was written with a space the real test lacks.
- preserve: clause text otherwise byte-identical.
- next: go to Step 4.

### Step 4: Insert the separator everywhere, not just in the failing case
- actions: add a trailing space before the closing quote of every non-final clause literal; then grep the file for other line ends matching a terminating `."` pattern and fix each (trace: four sites fixed — the two-body, ancestor, reachable, and cut tests).
- inputs: test file.
- outputs: every concatenated clause sequence now has whitespace after each embedded `.`.
- cautions: fixing only the first failing test leaves the same class of failure elsewhere in the suite.
- next: rebuild and run.

### Step 5: Verify, then remove the diagnostics
- actions: rebuild the suite, run it, confirm the previously failing tests pass; delete the temporary `fprintf` diagnostics and rebuild once more.
- inputs: unchanged build command.
- outputs: `22/22 tests passed`, no `expected '.', got operator '.'` anywhere.
- cautions: do not leave debug output in the test source.
- next: stop when the suite is green with diagnostics removed.

## Decision Rules
### When the parser reports `expected '.', got operator '.'` on a multi-clause input
Inspect the boundary between adjacent string literals: a literal ending in `.` that is immediately followed by another literal starting with a letter makes the dot non-final, so it is tokenised as an operator. Insert whitespace before the closing quote.

### When several tests fail but an isolated repro of the same scenario passes
Diff the repro's input string against the failing test's input before theorising about shared state — in this trace the repro had a space that the real test lacked, and the whole "cross-test contamination" investigation was unnecessary.

### When one fixed site still leaves failures
Sweep the file for the same literal pattern; the class of bug repeats at every concatenated clause boundary (trace: one grep-like read found the remaining sites).

## Invariants
- Do not modify the lexer, parser, or engine to accommodate a malformed test input.
- Keep the clause text itself unchanged — only whitespace at literal boundaries may be added.
- Do not weaken or delete failing assertions to get a green suite; in this trace the assertion changes made elsewhere were for different, separately justified reasons.
- Remove all temporary diagnostics before finishing.

## Common Failures
### Failure: only the first offending literal is fixed
- symptoms: the test you noticed still fails, or other cases in the same suite fail with `expected '.', got operator '.'` — in the trace four solver tests failed from the same pattern at once.
- causes: every concatenated clause boundary without trailing whitespace has the same defect (`...carol).` + `gp(...)`, `...dave).` + `ancestor(...)`, `...path(a, c).` + `reachable(...)`, `member(c).` + end-of-string boundary).
- recovery: after the first fix, read every remaining failing case's input and fix each boundary in the same sweep (trace fixed four sites before the verifying run).

### Failure: long detour theorising about shared state
- symptoms: several rounds of speculation about cross-test contamination while an isolated repro of the scenario passes.
- causes: the isolated repro silently differed from the real test input (it had a space the test lacked), so nothing reproduced.
- recovery: add one temporary `fprintf` that prints the harness's real error and rerun; the trace went from speculation to root cause in a single run once the parser message was printed.

## Verification
- Rebuild and run the affected suite: it prints `22/22 tests passed` and the run output contains `PASS  two-body rule resolves via conjunction` plus `PASS  recursive rule — ancestor` and `PASS  backtracking finds second solution after first fails`.
- No run output contains `expected '.', got operator '.'`.
- Read every `load(...)` input string in the file: each clause except the last is followed by whitespace before the closing quote.
- Grep the test file for the removed diagnostic (`[load]`) — no hits; the temporary prints are gone.

## Examples
### Example 1: `gp/2` two-body rule test fails with a dot parse error
- input: `ctx.load("parent(alice, bob). parent(bob, carol). " "gp(X,Y) :- parent(X,Z), parent(Z,Y).")` — originally written without the space after `carol).`; the suite reports `FAIL  two-body rule resolves via conjunction`.
- procedure: Step 1 add a temporary `fprintf` printing `p.error_msg`; rebuild; read `parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'`; Step 3 inspect the literal boundary (the joined text is `...carol).gp(X,Y)...`, so the dot is followed by a letter); Step 4 add a trailing space: `"parent(alice, bob). parent(bob, carol). "`; rebuild and run; Step 5 remove the diagnostic.
- expected result: all three clauses load, `?- gp(alice, carol).` succeeds, and the suite reports `22/22 tests passed`.
- parameterized values: clause text, suite `tests/test_solver.cpp`, compiler `clang++ -std=c++23 -Iinclude -Itests -g -O0`.

### Example 2: sweeping the remaining boundaries
- input: after fixing the first site, three more tests fail from the same class (`recursive rule — ancestor`, `backtracking finds second solution`, `cut stops backtracking`).
- procedure: read each failing test's input string; append a space before the closing quote of every non-final clause (`"parent(carol, dave). "`, `"ancestor(X,Y) :- parent(X,Y). "`, `"path(a, b). path(b, c). path(a, c). "`, `"...member(c). "`); rebuild and run once.
- expected result: every previously failing case passes in a single run; no parse-error text remains.
- parameterized values: the four call sites, suite binary path `build\tests\test_solver.exe`.

## Evidence
**Problem**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1083, source_part_index: 0, quote: `FAIL  two-body rule resolves via conjunction`, supports: the solver suite failed four tests from the same class while neighbouring cases passed, so the defect was in those tests' inputs rather than in the engine.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1136, source_part_index: 0, quote: `"parent(alice, bob). parent(bob, carol)."`, supports: the first literal ends with the clause terminator `.` and no trailing whitespace, and (per the same edit's `old_string`) is immediately concatenated with the next literal.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1136, source_part_index: 0, quote: `"gp(X,Y) :- parent(X,Z), parent(Z,Y)."`, supports: the second literal starts with a letter, so the joined text is `...carol).gp(...)`, putting a non-space character right after the terminating dot.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1127, source_part_index: 0, quote: `parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'`, supports: the temporary harness diagnostic pinpointed the failure — exactly one clause loaded, then the terminator was tokenised as an operator.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1128, source_part_index: 0, quote: `the lexer is tokenizing `.` as `TOK_OP` instead of `TOK_DOT`. This happens when the character after `.` is NOT whitespace.`, supports: the assistant's root-cause reading of the message (lexer rule itself was not read from source in this trace).

**Action**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1136, source_part_index: 0, quote: `"parent(alice, bob). parent(bob, carol). "`, supports: the repair — a space was inserted before the closing quote so the concatenated text keeps whitespace after the terminator; the same edit pattern was applied at three more sites (events 1147, 1152, 1164).

**Verification**
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1187, source_part_index: 0, quote: `PASS  two-body rule resolves via conjunction`, supports: after the separator fixes the previously failing test passes, along with the other three failures of the same class.
- file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1187, source_part_index: 0, quote: `22/22 tests passed`, supports: the whole solver suite now passes with no parse error remaining (reconfirmed by the later run reporting `=== 6 PASSED, 1 FAILED ===`, the single failure being an unrelated file lock).

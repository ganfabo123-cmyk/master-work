# Skill extraction

本次提取的 Skill 总数：5

- Reuse an existing serialization boundary for portable parse-once/run-many bytecode — 来源 Session `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833`
- Make Windows PowerShell 5.1 build and test scripts parse-compatible — 来源 Session `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6`
- Make an eager JSX lexer own its mode transitions — 来源 Session `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6`
- Preserve request data across allocator cleanup and dispatch — 来源 Session `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa`
- Keep large fixed-capacity test state off the stack and avoid accidental copies — 来源 Session `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e`, `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd`

# Reuse an existing serialization boundary for portable parse-once/run-many bytecode

```yaml
---
name: reuse-existing-serialization-boundary
description: >
  Use when a requested parser/runtime split must produce portable compiled data,
  but the codebase already has a tested compile-only and serialization API.
  Helps implement parse-once/run-many loading without exposing AST or runtime
  pointers. Requires an existing serializer/deserializer whose ownership and
  lifetime can be audited. Do not use when the existing format is not portable,
  is undocumented, or cannot be independently destroyed and loaded.
---
```

## Goal

Expose an owning bytecode handle that can be created without the execution runtime, loaded into another runtime, evaluated repeatedly, and destroyed independently.

## Scope

### In scope

- Audit the requested architectural boundary against the actual compiler/runtime internals.
- Reuse an existing compile-only plus serialization format when it already carries the required portable state.
- Add parse, load, evaluate-loaded, and destroy APIs with explicit ownership.
- Test cross-runtime loading and repeated evaluation.

### Out of scope

- Rewriting a monolithic parser/code generator solely to match an ideal physical file split.
- Exposing AST nodes, adding JIT, module resolution, or changing GC behavior.

## Inputs

- Source text: required string accepted by the existing compile-only path.
- Runtime handle: required only for load/evaluation.
- Existing serializer/deserializer flags and ownership rules: required and must be verified in the source.

## Outputs

- Owning opaque bytecode handle and parse/load/evaluate/destroy functions.
- Success means the serialized blob remains valid after the scratch compile runtime is destroyed and can be loaded into multiple runtimes.
- Failure must report compile, serialization, load, or evaluation errors without claiming a source-level parser split.

## Preconditions

1. Confirm that compile-only evaluation returns a compiled object without executing user code.
2. Confirm that serialization produces a blob with no runtime pointers and that the blob can be copied into independent storage.
3. Confirm how loaded function handles are retained and released by the runtime.

If any ownership or portability condition is unknown, stop and report it.

## Procedure

### Step 1: Audit the real boundary

- Inspect the compiler entry point, serializer flags, deserializer, and execution entry point before creating new parser internals.
- Compare the requested architecture with the actual code; record which requested pieces already exist through serialization.

### Step 2: Implement parse ownership

- Create a scratch runtime, compile with the existing compile-only flag, serialize the compiled object, copy the bytes into owned storage, and destroy the scratch runtime.
- Return an opaque handle that owns only the copied blob.

### Step 3: Implement load and repeated evaluation

- Deserialize the blob into the target runtime and retain the loaded function handle.
- Duplicate the retained handle for each evaluation when required by the runtime so the stored handle survives repeated calls.
- Replace an existing loaded handle only after releasing the previous one.

### Step 4: Verify lifecycle boundaries

- Test parse failure, null arguments, destroy-null, load-before-eval errors, loading into several runtimes, repeated evaluation, and blob use after scratch runtime destruction.

## Decision Rules

### When the existing serialized format is self-contained

Execute:

1. Use it as the portable IR boundary.
2. Keep the physical parser/VM split as a deferred architectural change.
3. Document the mapping from requested API to the existing compile/serialize/load/eval pipeline.

### When serialization retains runtime pointers or its ownership is unclear

- Do not expose it as portable bytecode.
- Report the missing invariant and stop before adding an API that only appears independent.

## Invariants

Execution must preserve:

- The bytecode handle owns its bytes independently of the scratch runtime.
- Loading does not require the parser runtime to remain alive.
- Repeated evaluation does not consume or invalidate the retained loaded handle.
- Null and pre-load calls return explicit errors.
- No AST or runtime pointer is exposed through the public boundary.

## Common Failures

### Failure: Treating an ideal file split as already present

Symptoms:

- The requested parser/VM separation would require rewriting a large monolithic compiler.

Cause:

- The actual implementation interleaves parsing and code generation even though it already has serialization helpers.

Recovery:

1. Audit the existing serializer/deserializer and compile-only path.
2. Verify the bytecode lifecycle tests before deciding whether a physical split is necessary.

## Verification

- [x] Parse success and parse failure are covered.
- [x] The blob survives destruction of the scratch runtime.
- [x] One parsed blob loads into five runtimes and supports repeated evaluation.
- [x] Null-argument, destroy-null, load-before-eval, and replacement cases are checked.
- [x] The recorded result was Stage 1 smoke passed with zero leaks, Stage 2 135/135, and Stage 3 bytecode 101/101.

## Examples

### Example 1: Existing compile-only runtime

输入：

An engine exposing compile-only evaluation, bytecode serialization, deserialization, and function evaluation.

处理：

Compile in a scratch runtime, serialize with the bytecode flag, copy the bytes, destroy the scratch runtime, then deserialize and evaluate in each target runtime while duplicating the retained function handle for execution.

预期结果：

The parse-once/run-many tests pass and the bytecode remains valid after the scratch runtime is gone.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | segment-03 events 30, 38, 53 | Audit found the requested physical split did not exist; existing `JS_WriteObject`/`JS_ReadObject` provided the portable boundary. |
| 关键处理动作 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | segment-03 events 53, 62, 72, 78, 100, 109 | Implemented compile-only serialization, parse/load/eval APIs, retained loaded function state, and bytecode tests. |
| 对应验证结果 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | segment-03 event 175 | Reported Stage 1 smoke, Stage 2 135/135, and Stage 3 bytecode 101/101 passing. |

# Make Windows PowerShell 5.1 build and test scripts parse-compatible

```yaml
---
name: make-powershell-51-scripts-parse-compatible
description: >
  Use when a build or test script must run under Windows PowerShell 5.1.
  Helps identify syntax and character incompatibilities before invoking the
  script. Requires the script path and a PowerShell parser available on the
  target machine. Do not use it as proof that the underlying program or tests
  pass; parser success only proves script syntax is accepted.
---
```

## Goal

Make a PowerShell build/test script parse and run under the supported Windows PowerShell version, with a separate syntax preflight.

## Scope

### In scope

- Replace syntax unavailable in PowerShell 5.1 with equivalent control flow.
- Replace problematic non-ASCII punctuation in string literals when it causes parser failures.
- Parse-check every changed script before running the build or tests.

### Out of scope

- Assuming a successful parse proves compiler, fixture, or runtime correctness.
- Rewriting unrelated shell scripts or changing the supported PowerShell version without evidence.

## Inputs

- `build.ps1` and/or test runner path.
- Target PowerShell version, especially Windows PowerShell 5.1.
- The parser diagnostics and the command used to invoke the script.

## Outputs

- Scripts that pass the PowerShell parser preflight.
- A report separating syntax success from later build/test results.

## Preconditions

1. Confirm the target is Windows PowerShell 5.1 or another version with the relevant syntax limitations.
2. Read the exact parser error and locate the reported construct.
3. Preserve the script's exit-code behavior while changing only incompatible syntax.

## Procedure

### Step 1: Identify version-specific syntax

- Check for PowerShell 7-only ternary expressions and non-ASCII characters inside quoted strings when the parser reports an unterminated string or missing brace.

### Step 2: Replace with compatible equivalents

- Replace `condition ? a : b` with an `if/else` that calls the same exit codes.
- Replace the problematic punctuation with plain ASCII when the diagnostic shows it is confusing the string parser.
- Apply the same fix to companion runners that share the pattern.

### Step 3: Parse before execution

- Call `[System.Management.Automation.Language.Parser]::ParseFile` for each script.
- Continue only when every script reports no parse errors; then run the build/test command separately.

## Decision Rules

### When the parser reports a missing quote or brace near a ternary/Unicode string

Execute:

1. Read the full script around the diagnostic.
2. Replace only the incompatible expression/character.
3. Re-run the parser preflight.

### When the parser is clean but the build/test command fails

- Stop treating it as a script-syntax problem.
- Diagnose the invoked compiler, runner, fixture, or application separately.

## Invariants

- Preserve original exit status semantics.
- Keep the parser preflight distinct from runtime verification.
- Do not report tests as passing solely because scripts parse.
- Do not alter unrelated build logic.

## Common Failures

### Failure: PowerShell 7 ternary syntax on Windows PowerShell 5.1

Symptoms:

- Parse errors report missing terminators or closing braces around a script containing `? :`.

Cause:

- The target shell does not support the ternary operator.

Recovery:

1. Replace it with `if/else`.
2. Parse-check both the build script and test runner again.

## Verification

- [x] Both `build.ps1` and `run_tests.ps1` were parsed successfully after the edits.
- [x] Later fixture execution reached the runner; the final Yggdrasil stage report recorded 48/48 fixture tests and 17/17 batch tests passing.
- [ ] Parser success alone is not used as evidence of compiler correctness.

## Examples

### Example 1: Build and runner scripts

输入：

Windows PowerShell 5.1 reports a missing string terminator and missing closing braces in two scripts.

处理：

Replace the ternary exit expression with `if/else`, replace the parser-confusing em dash with ASCII `-`, then run `ParseFile` on both scripts before invoking tests.

预期结果：

Both scripts parse cleanly; subsequent test results are reported independently.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | segment-02 events 295, 297, 302 | Windows PowerShell reported missing terminators/closing braces; the trace identified the ternary and em dash incompatibilities. |
| 关键处理动作 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | segment-02 events 303, 305, 312, 318 | Replaced both constructs and parser-checked both scripts with `Parser.ParseFile`. |
| 对应验证结果 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | segment-02 event 320; segment-04 events 529, 548 | Both scripts parsed cleanly; final Stage 3 report recorded 48/48 plus 17/17 tests. |

# Make an eager JSX lexer own its mode transitions

```yaml
---
name: make-eager-jsx-lexer-own-mode-transitions
description: >
  Use when tokenization is eager and the parser cannot change lexer mode after
  all tokens have already been produced, especially for JSX tag, child, and
  closing-tag punctuation. Helps prevent compound tokens such as `/>` from
  being split or parsed in the wrong context. Requires an observable token
  stream and a lexer with explicit mode/state handling. Do not use when lexing
  is genuinely parser-driven and tokens are requested lazily.
---
```

## Goal

Ensure an eager lexer emits JSX tokens according to its own current lexical state so the parser receives correct tag, child, closing-tag, and compound punctuation tokens.

## Scope

### In scope

- Auditing whether parser mode calls can affect an already-eager tokenization pass.
- Making the tokenizer push/pop JSX states while scanning.
- Tracking closing-tag state explicitly rather than inferring it from ambiguous last-token kinds.
- Verifying representative JSX fixtures and non-JSX regression cases.

### Out of scope

- Adding unrelated JSX syntax or changing code generation semantics.
- Relying on parser-side mode calls when tokenization has already completed.

## Inputs

- Source text containing self-closing tags, attributes, closing tags, and JSX children.
- Lexer token dump or parser diagnostic for the failing fixture.
- Existing positive, error, and non-JSX fixtures.

## Outputs

- A token stream in which JSX punctuation is represented by the intended compound tokens.
- Parser/codegen results that match expected fixtures.

## Preconditions

1. Confirm whether tokenization is eager and completes before parsing begins.
2. Identify the lexical states needed for JavaScript, JSX tag, and JSX child text.
3. Preserve a regression fixture for `<` used as a normal relational operator.

## Procedure

### Step 1: Inspect the token boundary

- Reproduce the smallest failure, such as `<input disabled />`.
- Dump token kinds and compare the expected `JSXSlashGreater` with the actual separate `Slash` and `Greater` tokens.

### Step 2: Move state transitions into tokenization

- Push JSX tag state after emitting an opening JSX-less token.
- Switch to JSX children after an opening tag closes.
- Enter closing-tag state after JSX-less-slash and return to children/JavaScript after the closing greater token.
- Track `inClosingTag` explicitly so an opening tag ending in an identifier is not confused with a closing tag.

### Step 3: Verify boundaries

- Rebuild, rerun the original boolean-attribute fixture, then run the full positive/error/non-JSX fixture suite.

## Decision Rules

### When the parser asks for mode changes but tokenization is eager

Execute:

1. Treat parser mode calls as too late to control tokenization.
2. Make the lexer state machine self-manage during its scan.
3. Use token dumps to validate each state transition.

### When a token is wrong but the mode is correct

- Inspect punctuation scanning and compound-token recognition before changing parser grammar.

## Invariants

- `/>` is emitted as one JSX self-closing token in JSX tag state.
- Closing-tag detection is explicit and cannot be inferred from an identifier alone.
- Normal JavaScript `<` expressions remain non-JSX.
- The fix is validated by fixture output, not only by a clean compile.

## Common Failures

### Failure: JSX self-closing slash is parsed as an attribute

Symptoms:

- The parser reports `Expected attribute name, got '/'` for `<input disabled />`.

Cause:

- The eager lexer never actually entered JSX tag mode, so it emitted separate slash and greater tokens.

Recovery:

1. Add lexer-owned mode transitions and an explicit closing-tag flag.
2. Dump tokens for the minimal fixture.
3. Rerun the complete fixture suite.

## Verification

- [x] The original boolean-attribute failure was reduced to an incorrect token stream.
- [x] The lexer rewrite built cleanly.
- [x] Stage 1 and Stage 2 fixture reports recorded 48/48 passing after subsequent fixes.
- [x] Non-JSX and error fixtures remained part of the final suite.

## Examples

### Example 1: Self-closing JSX tag

输入：

`<input disabled />` in an eager tokenizer.

处理：

Enter JSX tag state after `<`, scan `disabled`, recognize `/>` as a compound token, and leave the parser to consume the already-correct token stream.

预期结果：

The parser accepts the fixture and the complete fixture suite passes.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | segment-02 events 348, 352, 355, 360 | Failure occurred on `<input disabled />`; trace identified eager tokenization and missing lexer mode transitions. |
| 关键处理动作 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | segment-02 events 361, 366, 374, 389, 393 | Lexer state stack and explicit `inClosingTag` handling were added; token dump was used to inspect slash/greater emission. |
| 对应验证结果 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | segment-04 events 295, 305 | Final Stage 2 report recorded 48/48 passing after JSX hardening. |

# Preserve request data across allocator cleanup and dispatch

```yaml
---
name: preserve-request-data-across-dispatch-cleanup
description: >
  Use when a request parser allocates slices or strings in a temporary
  allocator and a dispatcher routes using those fields. Helps prevent routing
  failures caused by freeing the allocator before dispatch has consumed the
  request. Requires a traceable allocator owner and a handler call boundary.
  Do not use as a substitute for a full ownership audit when data escapes the
  handler or is shared across threads.
---
```

## Goal

Keep parsed request fields valid until routing and handler execution finish, while still releasing temporary allocations at a safe boundary.

## Scope

### In scope

- Trace which allocator owns parsed path/header strings.
- Identify cleanup that runs before routing.
- Move cleanup to the end of dispatch or copy data into a longer-lived owner.
- Verify the route over the actual network boundary.

### Out of scope

- General concurrency redesign, protocol expansion, or replacing the allocator.

## Inputs

- Request parser and dispatcher code.
- Allocator used by `strings.clone` or equivalent request-field construction.
- A reproducible route request and expected status/body.

## Outputs

- A dispatcher that compares valid request fields and returns the intended route response.
- Failure must distinguish parse failure, freed request data, and handler blocking.

## Preconditions

1. Confirm whether request fields are borrowed slices or allocator-owned copies.
2. Locate every `free_all`/reset call on the path from parse to route.
3. Ensure cleanup at function exit occurs after the handler has consumed the request.

## Procedure

### Step 1: Trace the request lifetime

- Follow raw socket bytes through line/field splitting, cloning, dispatch, and response generation.
- Record the allocator owner for `req.path` and other fields.

### Step 2: Remove premature cleanup

- If dispatch begins by freeing the allocator that owns `req.path`, remove that early cleanup.
- Keep cleanup in a deferred/end-of-dispatch position, after route matching and response creation.

### Step 3: Verify on the live boundary

- Rebuild, start the server, send `GET /api/status`, and check for HTTP 200 plus the expected JSON body.

## Decision Rules

### When the route field is allocated on the dispatch allocator

Execute:

1. Keep the field alive through route matching and handler execution.
2. Free only after the response has been formed or copied.

### When the field must outlive dispatch

- Copy it into an explicitly longer-lived request/session owner before cleanup; do not rely on a temporary slice.

## Invariants

- A route comparison never reads memory after its allocator has been freed.
- Response generation completes before request-owned temporary storage is reclaimed.
- A successful HTTP status is checked together with the response body.
- A routing fix is not claimed from static inspection alone.

## Common Failures

### Failure: Every request falls through to 404 despite correct route code

Symptoms:

- The server listens, but `/api/status` returns the not-found route.

Cause:

- `free_all(context.temp_allocator)` runs at the beginning of dispatch and invalidates the cloned path before comparison.

Recovery:

1. Remove the early reset and retain end-of-dispatch cleanup.
2. Rebuild and request `/api/status` again.

## Verification

- [x] The route diagnosis was tied to allocator ownership rather than guessed string parsing.
- [x] After the fix, the trace recorded `GET /api/status` returning HTTP 200 with JSON.
- [x] The final evidence is limited to that route and startup state; it does not prove every endpoint or long-running concurrency path.

## Examples

### Example 1: API status route

输入：

An HTTP parser clones `/api/status` into a temporary allocator and the dispatcher frees that allocator before its switch.

处理：

Remove the initial reset, retain cleanup at dispatch exit, rebuild, and issue the status request.

预期结果：

The status endpoint returns HTTP 200 and JSON containing the initial simulation snapshot.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa` | segment-04 events 0, 21, 24 | Trace identified `req.path` as allocator-owned data freed at the start of `api_dispatch`. |
| 关键处理动作 | `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa` | segment-04 events 21, 24, 45 | Removed premature cleanup and rebuilt/tested the server route. |
| 对应验证结果 | `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa` | segment-04 event 94 | Recorded HTTP 200 with JSON from `GET /api/status`. |

# Keep large fixed-capacity test state off the stack and avoid accidental copies

```yaml
---
name: keep-large-fixed-test-state-off-stack
description: >
  Use when fixed-capacity C or C++ tables, arenas, databases, or solver stacks
  cause startup crashes or stack-overflow exits in tests. Helps place large
  state in static/heap storage and bind helper-returned objects by reference.
  Requires measured object sizes or a reproducible stack-overflow code. Do not
  use to hide arbitrary ownership bugs; verify state reset and test isolation
  after moving storage.
---
```

## Goal

Prevent stack overflow and accidental megabyte-scale copies while preserving test isolation and repeatability.

## Scope

### In scope

- Measure large fixed-capacity members such as atom tables, arenas, choice stacks, and databases.
- Move long-lived test fixtures or local solver stacks to static or heap storage as appropriate.
- Replace `LargeType value = helperReturningReference()` with `LargeType& value = ...` when a reference is intended.
- Reset shared state explicitly between tests.

### Out of scope

- Increasing stack limits as the primary fix.
- Sharing mutable state without a reset protocol.
- Treating a clean compile as proof that stack usage is safe.

## Inputs

- Reproducible crash/exit code and the test source.
- Size estimates or `sizeof` measurements for large fixed-capacity objects.
- Test fixture lifetime and reset requirements.

## Outputs

- Tests that start without stack overflow and still pass their semantic assertions.
- Explicit evidence that state resets between sequential tests.

## Preconditions

1. Confirm the failure is a stack overflow or value copy, not a logic assertion.
2. Identify every large local object and helper-return copy in the failing test.
3. Decide whether the object is per-test resettable static state or needs heap ownership.

## Procedure

### Step 1: Quantify the stack use

- Sum the dominant fixed arrays, for example a choice stack containing hundreds of kilobytes or an atom table around a megabyte.
- Check both the test body and called functions for additional large locals.

### Step 2: Change storage without changing semantics

- Move non-reentrant solver scratch stacks to static or heap storage.
- Make shared fixture members static only with an explicit constructor/reset that clears all dependent arenas, registries, and databases.
- Bind helper-returned static objects by reference so a large copy is not placed on the local stack.

### Step 3: Run sequential tests

- Rebuild all suites, run the previously crashing suite alone, then run the full suite in declaration order.
- If a later test fails, inspect stale arena/database state before changing solver logic.

## Decision Rules

### When the crash occurs before the first test body

Execute:

1. Search for large locals and by-value helper copies.
2. Reproduce with a minimal test binary to separate framework startup from fixture construction.
3. Change the smallest confirmed stack allocation and rerun.

### When moving state makes sequential tests fail

- Add/reset explicit arena, registry, and database state; do not assume static storage is automatically isolated.

## Invariants

- No large fixed-capacity object is copied onto a test function's stack unintentionally.
- Static/heap state is reset before each test that depends on a fresh context.
- A crash fix must be followed by semantic suite results.
- Existing preconditions and test assertions remain unchanged unless the trace proves the assertion itself is invalid.

## Common Failures

### Failure: Windows test process exits with stack overflow before output

Symptoms:

- Exit code `0xC00000FD` or no test output.

Cause:

- Large fixed arrays are local, or a reference-return helper is assigned by value.

Recovery:

1. Move the object to static/heap storage or bind by reference.
2. Rebuild and run the isolated suite, then all suites.

### Failure: Sequential tests observe stale arena/database state

Symptoms:

- An isolated test passes but the same test fails after earlier tests.

Cause:

- Shared static storage was introduced without resetting all dependent state.

Recovery:

1. Reset the database, term arenas, registries, and test-local scratch state together.
2. Re-run in sequence and inspect the first failing test.

## Verification

- [x] The Epilog trace diagnosed large `ChoiceStack`, `TermArena`, and `Database` storage and ultimately reported 10/10 suites, 144/144 tests passing.
- [x] The trace also fixed a by-value `AtomTable` helper result by changing it to a reference; all 17 atom tests then passed.
- [x] The C++ conversion/test trace recorded the same class of stack issue and resolved it before the full suite.
- [x] The evidence supports stack safety and test execution, not a general memory-safety guarantee.

## Examples

### Example 1: Large atom table helper

输入：

`make_table()` returns a static `AtomTable&`, but a test declares `AtomTable t = make_table()`.

处理：

Change the declaration to `AtomTable& t = make_table()`, then rebuild the atom suite and the complete suite.

预期结果：

The startup stack overflow disappears and the atom tests execute; the final complete report is 10/10 suites and 144/144 tests.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e` | segment-03 events 62, 65, 145 | Stack overflow was tied to large `ChoiceStack`, `TermArena`, `Database`, and indexing context objects. |
| 关键处理动作 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e`; `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd` | segment-03 events 68, 72, 145, 202; segment-03 event 357 | Large solver scratch state moved off the stack; indexing context became static; by-value `AtomTable` helper use changed to a reference. |
| 对应验证结果 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e`; `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd` | segment-03 event 212; segment-03 event 209 | Final Epilog report recorded 10/10 suites and 144/144 tests; atom tests passed after the reference fix. |

## 未保留的主要候选

- **Detached long-running server threads**：轨迹识别了 `thread.destroy` 可能等待永久 accept 循环，但选中切片在修复后停留在文件锁/重建阶段，没有足够的最终启动验证，因此未提取。
- **Windows Makefile shell dispatch as a standalone Skill**：轨迹确实发现了 `cmd.exe` 与 Bash 语法不兼容，并使测试命令进入 PowerShell runner，但后续仍暴露了编译器/fixture 失败；证据更适合作为 PowerShell Skill 的相邻步骤，单独提取会扩大“已解决”范围。
- **Epilog variable-binding redesign**：轨迹包含多次失败假设、调试和中途重构；虽然部分规则最终通过，但没有在同一选中切片中形成足够清晰、独立、可复用的完整模板证据，因此未保留为独立 Skill。
- **DMLS window startup / missing DLL diagnosis**：缺失 DLL 的原因被定位并修复，但后续图形窗口与线程生命周期仍有未完成验证；不能把局部启动诊断扩大为完整 GUI 启动 Skill。

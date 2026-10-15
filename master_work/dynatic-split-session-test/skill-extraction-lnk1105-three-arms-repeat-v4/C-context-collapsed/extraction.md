# Skill 提取结果

本次提取的 Skill 总数：6。

| Skill 标题 | 来源 Session ID |
| --- | --- |
| 在既有引擎能力上建立阶段边界适配层 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 |
| 为可选运行时子系统建立显式注册与依赖反馈 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 |
| 为 C 运行时封装建立分配器、生命周期和隔离验证 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 |
| 为跨平台原生测试修复 Shell、编码和退出码差异 | claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6 |
| 为按首参数索引的子句建立两遍构建并验证回溯正确性 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e |
| 识别并修复原生测试中的大对象栈溢出 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e |

---

# 在既有引擎能力上建立阶段边界适配层

```yaml
---
name: adapt-stage-boundaries-to-existing-engine-apis
description: >
  Use when a staged architecture plan assumes a new parser, VM, or IR boundary
  but the existing engine already exposes a serialization or compilation API.
  Helps the agent deliver the requested boundary with a thin adapter while
  preserving the existing implementation. Requires an auditable source/API
  audit and an executable end-to-end test. Do not use when the requested
  physical split is itself the explicitly authorized deliverable.
---
```

## Goal

Deliver a usable stage boundary over verified existing APIs, while explicitly deferring a physical rewrite that the current architecture cannot support without changing the scope.

## Scope

### In scope

- Audit the actual engine implementation and public API before coding.
- Reuse an existing compile/serialize/deserialize path as the boundary when it has the required semantics.
- Add the smallest public wrapper, ownership rules, and tests needed for parse-once/run-many behavior.

### Out of scope

- Claiming that a monolithic parser has been physically split when it has not.
- Rewriting a large upstream engine solely to match an aspirational stage document.
- Adding unrelated loader, JIT, threading, or language binding work.

## Inputs

- `stage specification`: required; states the intended boundary and explicit exclusions.
- `engine source and headers`: required; must be read to confirm actual coupling and available APIs.
- `build/test entry point`: required; must be able to exercise the adapter.

## Outputs

- `<public boundary>`: an owning opaque API over the verified existing mechanism.
- `<tests>`: checks parse/load/execute lifecycle and ownership.
- Success standard: the requested boundary behavior is observable and the deferred physical rewrite is documented as deferred.
- Failure standard: if the existing API cannot provide the semantics, stop and report the architectural mismatch rather than silently widening scope.

## Preconditions

执行前必须确认：

1. The current engine and headers are accessible and can be audited.
2. The candidate existing API's ownership and runtime dependencies are known.
3. A build can compile the adapter and its tests.

前置条件不满足时，停止并报告具体原因。

## Procedure

### Step 1: Audit the assumed boundary

- Read the relevant engine internals and public declarations.
- Record which parts are actually entangled and which existing APIs already provide a portable or reusable representation.

### Step 2: Compare the plan with the evidence

- If an existing API already produces a self-contained representation, choose it as the stage boundary.
- State precisely which requested physical split remains deferred and why.

### Step 3: Implement the thinnest adapter

- Add an opaque handle and explicit create/load/execute/destroy operations.
- Ensure the serialized representation does not retain pointers into the scratch runtime.
- Keep the upstream engine unchanged unless the adapter cannot function without a narrowly justified change.

### Step 4: Verify the lifecycle

- Build the library and run tests for parse success/failure, load, execution, repeated execution, multiple runtimes, and destruction.
- Report the tested boundary rather than the larger aspirational architecture.

## Decision Rules

### When an existing API already serializes a self-contained representation

执行：

1. Use that representation as the intermediate boundary.
2. Expose ownership and load/execute operations around it.
3. Test that it survives destruction of the scratch runtime and can run in multiple target runtimes.

### When the plan requires a physical split that the audit shows is not present

- Do not claim the split is complete.
- Deliver the compatible adapter only if it satisfies the current behavior, and document the physical rewrite as deferred.

### When ownership or pointer independence cannot be established

- Do not expose the adapter as complete.
- Report the missing ownership evidence and stop before presenting success.

## Invariants

执行过程中必须保持：

- The public handle remains independent of scratch-runtime pointers.
- Parse/load/execute/destroy ownership is explicit.
- No unrelated upstream architectural rewrite is introduced.
- The result is reported only to the verified boundary.

## Common Failures

### Failure: The stage document assumes a split that does not exist in the engine

症状：

- Parser and code generation remain interleaved in the upstream monolith.

原因：

- The requested architecture was aspirational and did not match the audited implementation.

恢复：

1. Use the existing compile/serialization API as the boundary when it is self-contained.
2. Add tests for independent load and repeated execution, and mark physical separation deferred.

## Verification

完成后必须检查：

- [x] The existing engine API and coupling were audited before implementation.
- [x] The adapter stores an owning, runtime-independent representation.
- [x] Load and execution work after the scratch runtime is gone.
- [x] Parse-once/run-many and null/error paths are tested.
- [x] The report distinguishes the adapter from the deferred physical split.

## Examples

### Example 1: Compile-once, run-many boundary

输入：

An engine whose compile-only evaluation can be serialized with `JS_WriteObject` and loaded with `JS_ReadObject`.

处理：

Compile in a scratch runtime, serialize and copy the blob, destroy the scratch runtime, then load the blob into each target runtime and execute through an opaque bytecode handle.

预期结果：

The trace reports 101/101 Stage 3 tests passing, including blob independence, five target runtimes, load replacement, and eval-before-load errors. This supports the adapter behavior only.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | segment-03 source_index 433-444 | Stage 3 request followed by audit finding that physical parser/VM separation was not present and serialization already provided the boundary. |
| 关键处理动作 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | segment-03 source_index 456-559 | Implemented compile-only → serialize → load → execute wrapper and updated the build. |
| 对应验证结果 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | segment-03 source_index 574-595 | Stage 1, Stage 2 (135/135), and Stage 3 (101/101) suites passed. |

---

# 为可选运行时子系统建立显式注册与依赖反馈

```yaml
---
name: register-optional-runtime-subsystems-explicitly
description: >
  Use when a runtime currently initializes standard-library capabilities
  implicitly and a stage requires a bare core plus opt-in subsystems. Helps
  expose explicit registration functions with dependency checks and clean
  failures. Requires an engine with separable intrinsic/helper initialization.
  Do not use for changing the VM or garbage collector algorithm.
---
```

## Goal

Start a runtime with only the core execution path, register standard-library groups explicitly, and return actionable dependency errors for invalid registration order.

## Scope

### In scope

- Audit intrinsic and helper initialization calls.
- Define subsystem bitmasks and registration functions.
- Track registered state and validate prerequisites.
- Test both successful registration and clean rejection of missing dependencies.

### Out of scope

- Parser or bytecode modularization.
- GC replacement, scheduler, or unrelated embedding layers.

## Inputs

- `runtime initialization source`: required; identifies raw context and intrinsic calls.
- `subsystem groups`: required; derived from audited initialization dependencies.
- `registration test matrix`: required; includes bare, valid, and invalid orderings.

## Outputs

- `<bare runtime API>` and `<register_* API>`: explicit C-level lifecycle.
- `<registered state>`: bitmask or equivalent state used for dependency checks.
- Success standard: bare and selectively registered runtimes behave as tested; invalid order returns a nonzero result and reason.
- Failure standard: missing dependency or failed build/test is reported with the specific subsystem and reason.

## Preconditions

执行前必须确认：

1. Raw runtime/context construction is available or can be isolated.
2. Intrinsic/helper dependencies have been audited from source.
3. The build can include the relevant runtime and helper sources.

前置条件不满足时，停止并报告具体原因。

## Procedure

### Step 1: Audit initialization

- Locate raw context creation, intrinsic registration, and external helper registration.
- Group them by domain and record prerequisite relationships.

### Step 2: Add explicit state and APIs

- Add a bare constructor and a registered-subsystem bitmask.
- Implement one registration function per audited group.
- Check prerequisites before mutating state and return an explanatory error string.

### Step 3: Cover platform build requirements

- Put platform-specific compile definitions in the build file when the issue is external to the engine source.
- Rebuild from a clean build directory.

### Step 4: Verify behavior

- Test basic VM operation on a bare runtime.
- Test every valid registration path and every dependency rejection in the matrix.
- Record the exact pass/fail counts.

## Decision Rules

### When an intrinsic/helper has a clear prerequisite

执行：

1. Encode the prerequisite in the registration function.
2. Return a reason containing the missing subsystem.
3. Verify the error before proceeding to later registrations.

### When a helper is outside the engine intrinsic chain

- Keep it as a separate subsystem registration path; do not pretend it is part of the bare engine.

### When a platform collision is caused by headers or compiler flags

- Fix the build definition locally (for example, compile definitions) and avoid modifying unrelated upstream source solely for that platform workaround.

## Invariants

- Bare construction does not silently register the optional groups.
- Registration is explicit and dependency-checked.
- Error reasons are returned through the formal API.
- A clean rebuild is used after build-system changes.

## Common Failures

### Failure: Bare C evaluation fails because the eval hook is disabled

症状：

- Basic VM tests report `eval is not supported` on a raw context.

原因：

- The low-level eval hook was not enabled even though full base objects were intentionally omitted.

恢复：

1. Enable the low-level eval path without registering the full global object set.
2. Re-run the bare-runtime tests.

### Failure: Dependency reason appears missing in a combined test expression

症状：

- A dependency check sees a null error pointer despite the registration function setting it.

原因：

- The test passed a pointer in a function-call expression whose argument evaluation order obscured the updated value.

恢复：

1. Split registration and error assertion into separate statements.
2. Re-run the dependency tests and inspect the actual returned reason.

## Verification

- [x] Intrinsic and helper dependencies were audited.
- [x] Bare runtime and explicit registration APIs exist.
- [x] Dependency failures include the missing prerequisite.
- [x] Clean rebuild succeeds after platform compile definitions are applied.
- [x] The final subsystem suite reports 135/135 passing.

## Examples

### Example 1: Bare then selective registration

输入：

An engine exposing raw context creation and intrinsic registration calls.

处理：

Map core, collections, async, time, and I/O groups; create a bare runtime; register groups only after their prerequisite bits are present; test invalid calls separately.

预期结果：

The trace reports 135 passed and 0 failed, with bare evaluation, dependency errors, and subsystem behavior covered.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | segment-01 source_index 214-248 | Stage 2 request and audit identifying raw context, 11 intrinsic calls, and separate libc helpers. |
| 关键处理动作 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | segment-02 source_index 253-320 | Added bare runtime, registry bitmask, registration implementations, and build definitions for Windows headers. |
| 对应验证结果 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | segment-03 source_index 324-370 | Diagnosed eval/dependency test issues, fixed them, and reached 135 passed, 0 failed. |

---

# 为 C 运行时封装建立分配器、生命周期和隔离验证

```yaml
---
name: wrap-c-runtime-with-explicit-allocator-lifecycle
description: >
  Use when embedding a C runtime requires caller-supplied allocation hooks,
  explicit create/destroy functions, and multiple isolated runtime instances.
  Helps build a thin wrapper and smoke test ownership, errors, isolation, and
  leak accounting. Requires a runtime API that accepts allocator callbacks.
  Do not use as a justification for changing the runtime GC algorithm.
---
```

## Goal

Provide a pure C embedding boundary with per-runtime allocator userdata, explicit lifecycle, minimal evaluation, and evidence that multiple runtimes do not contaminate one another.

## Scope

### In scope

- Adapt callback signatures with small thunks.
- Expose create, destroy, and minimal eval operations.
- Build a smoke test with multiple runtimes, errors, isolation, and allocation accounting.

### Out of scope

- C++ wrappers, schedulers, module loaders, or GC algorithm changes.
- Modifying upstream runtime files when existing allocator hooks are sufficient.

## Inputs

- `allocator vtable`: alloc/free/realloc and opaque userdata.
- `runtime constructor/destructor`: required.
- `minimal eval API`: required for smoke tests.
- `C build toolchain`: required for library and test binary.

## Outputs

- `<C header and wrapper>`: opaque runtime handle and explicit lifecycle.
- `<smoke test>`: multiple-runtime and accounting checks.
- Success standard: all runtimes evaluate independently, expected errors are returned, and counted allocations equal frees for the tested lifecycle.
- Failure standard: any build failure, isolation leak, or accounting mismatch is reported.

## Preconditions

执行前必须确认：

1. The engine exposes allocator callbacks or a constructor accepting them.
2. Callback ownership and userdata lifetime are understood.
3. The selected compiler and archive tool can build the wrapper.

前置条件不满足时，停止并报告具体原因。

## Procedure

### Step 1: Inspect the runtime hook

- Read the constructor signature and allocator callback layout.
- Identify argument-order differences between the public wrapper and engine hook.

### Step 2: Add a thin C boundary

- Define an opaque runtime handle and allocator vtable.
- Use static adapter thunks to translate callback signatures and userdata.
- Keep create/destroy/eval operations explicit and free error strings according to the documented ownership.

### Step 3: Build the isolation smoke test

- Create at least three runtimes with distinct allocator configurations.
- Evaluate successful expressions and syntax/reference/throw errors.
- Set a sentinel in one runtime and verify it is absent from another.
- Count allocations and frees over the full lifecycle.

### Step 4: Rebuild and run

- Build from clean outputs, then run the smoke test.
- Report observed pass counts and allocation totals.

## Decision Rules

### When the engine already accepts allocator callbacks

执行：

1. Wrap the existing hook instead of editing allocator internals.
2. Bridge only signature/order differences.
3. Validate isolation and accounting at the wrapper boundary.

### When the allocator userdata is shared unintentionally

- Stop and fix ownership before claiming per-runtime isolation.

### When only compile success is available

- Report the wrapper as built but unverified; compile success does not prove lifecycle or isolation.

## Invariants

- Each runtime carries its own allocator userdata.
- Runtime creation and destruction have no hidden globals.
- Error reporting is explicit and testable.
- Upstream source is left unchanged when the existing hook is sufficient.

## Common Failures

### Failure: Callback signatures do not match

症状：

- The engine callback places opaque userdata first, while the wrapper places it last.

原因：

- The two APIs use different calling conventions.

恢复：

1. Add static adapter thunks with the engine signature.
2. Pass the wrapper allocator and userdata through the thunk and rerun the smoke test.

### Failure: Build uses the wrong compiler/generator

症状：

- The configured build selects MSVC or an unintended generator instead of clang.

原因：

- The initial generator/toolchain selection did not match the requested toolchain.

恢复：

1. Clean the generated build directory.
2. Force the intended generator/compiler and rebuild.

## Verification

- [x] Public C boundary and adapter thunks compile.
- [x] Three simultaneous runtimes are exercised.
- [x] Seven successful eval expressions and three error cases are checked.
- [x] Cross-runtime sentinel isolation is checked.
- [x] Allocation accounting reaches 1246 allocs and 1246 frees in the trace.

## Examples

### Example 1: Three isolated runtimes

输入：

Three runtimes using distinct allocator configurations and a minimal eval entry point.

处理：

Create them simultaneously, evaluate independent expressions, set a sentinel in one, destroy all, and compare allocation/free counters.

预期结果：

The trace reports all smoke tests passing, `allocs=1246`, `frees=1246`, and a reference error when the second runtime reads the first runtime's sentinel.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | segment-01 source_index 2-7 | Stage 1 explicitly requires allocator injection, lifecycle API, minimal eval, and 3+ runtime isolation. |
| 关键处理动作 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | segment-01 source_index 89-124 | Audited `JSMallocFunctions`, added adapter thunks, C wrapper, smoke test, and build scripts. |
| 对应验证结果 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | segment-01 source_index 129-150, 211 | Clean build and smoke test passed with 3 runtimes and equal allocation/free counts. |

---

# 为跨平台原生测试修复 Shell、编码和退出码差异

```yaml
---
name: repair-cross-platform-native-test-harness
description: >
  Use when a native project builds on Windows and Unix-like environments but
  its test target fails because it assumes a shell, PowerShell version,
  encoding, or stderr/exit-code behavior. Helps isolate the platform boundary
  in the build/test harness and verify the real binary behavior. Requires a
  reproducible failing command and a test runner under source control. Do not
  use to mask a genuine compiler or parser failure.
---
```

## Goal

Make the native test target invoke the correct platform runner and report process results reliably across the supported shells.

## Scope

### In scope

- Identify shell-specific syntax in Makefile and PowerShell scripts.
- Replace unsupported syntax with version-compatible forms.
- Preserve native process exit codes when stderr is emitted.
- Re-run the complete fixture suite.

### Out of scope

- Changing parser semantics solely to make a test pass.
- Suppressing genuine fixture failures.

## Inputs

- `build/test scripts`: Makefile, PowerShell runner, and platform selectors.
- `failing command output`: required; must include the observed shell/parser/exit-code error.
- `fixture suite`: required for final verification.

## Outputs

- `<platform-dispatched test target>`: invokes the correct runner.
- `<compatible scripts>`: parse in the supported PowerShell version.
- Success standard: the full suite passes and negative tests preserve their expected nonzero exit codes.
- Failure standard: any remaining fixture failure or ambiguous process status is reported.

## Preconditions

执行前必须确认：

1. The target operating systems and shell versions are known.
2. The failing output distinguishes runner failure from binary failure.
3. The fixture runner can be rerun after each harness change.

前置条件不满足时，停止并报告具体原因。

## Procedure

### Step 1: Classify the failure

- Determine whether the error comes from Make's shell, PowerShell parsing, encoding, stderr redirection, or the native executable.
- Run the native executable directly when the runner's status is suspect.

### Step 2: Dispatch by platform

- Use OS detection in the Makefile.
- On Windows, delegate fixture execution to the PowerShell runner; on Unix-like systems, keep the POSIX loop.
- Replace shell-only directory and cleanup commands with platform branches.

### Step 3: Make PowerShell version-compatible

- Replace unsupported ternary syntax with `if/else`.
- Replace problematic non-ASCII punctuation in strings when the supported shell cannot parse it.

### Step 4: Preserve exit-code evidence

- For negative fixtures, avoid PowerShell 5.1 `2>&1` behavior that turns native stderr into caught error records.
- Suppress or separately capture stderr while reading `$LASTEXITCODE` immediately after the process.

### Step 5: Verify end to end

- Parse both scripts with the PowerShell parser.
- Run the full fixture suite and compare output fixtures.
- Confirm negative fixtures return the expected exit status.

## Decision Rules

### When Make invokes POSIX shell syntax on Windows

执行：

1. Move Windows execution to the PowerShell runner.
2. Keep the Unix path in a separate branch.
3. Verify both build and test targets after the change.

### When a direct binary run returns the expected error but the runner reports `-1`

- Treat it as a runner/stderr handling problem first.
- Capture the native exit code without catching redirected stderr as a PowerShell exception.

### When script parsing fails before the binary starts

- Fix syntax/encoding compatibility first; do not alter the fixture or parser implementation.

## Invariants

- Platform-specific behavior remains in the build/test harness.
- Negative tests still assert real nonzero exit codes.
- Output-comparison tests still compare the complete generated output.
- The final pass count comes from a fresh run after the last harness change.

## Common Failures

### Failure: POSIX loop syntax under Windows `cmd.exe`

症状：

- `make test` reports that `pass` or another shell token is not recognized.

原因：

- The Makefile test recipe used Bash syntax while Windows Make used `cmd.exe`.

恢复：

1. Dispatch Windows tests to the PowerShell runner.
2. Re-run `make test` and inspect the runner output.

### Failure: PowerShell 5.1 parse error

症状：

- Missing string terminator or missing closing brace appears before execution.

原因：

- A PowerShell 7-only ternary or problematic em dash was present in the script.

恢复：

1. Replace the ternary with `if/else` and use parser-compatible text.
2. Parse both scripts before running fixtures.

### Failure: Native error output changes `$LASTEXITCODE` to `-1`

症状：

- A negative fixture returns `-1` in the runner although direct execution returns `1`.

原因：

- PowerShell 5.1 converts redirected native stderr into `NativeCommandError` records caught by the runner.

恢复：

1. Run exit-code fixtures without the problematic `2>&1` redirection.
2. Read `$LASTEXITCODE` immediately and rerun the negative suite.

## Verification

- [x] Both PowerShell scripts parse cleanly.
- [x] Windows Make dispatches to the PowerShell runner.
- [x] Direct and runner exit codes agree for error fixtures.
- [x] The final fixture run reports 32/32 passing.

## Examples

### Example 1: Windows fixture runner

输入：

A Makefile containing a Bash-style test loop and a PowerShell 5.1 environment.

处理：

Add OS-specific Make targets, replace the PowerShell ternary and problematic punctuation, then isolate stderr for exit-code assertions.

预期结果：

The trace first observes `31/32` and a `-1` runner mismatch, then reaches `32/32 passing` after the runner fixes.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6 | segment-02 source_index 379-432 | PowerShell parser error, Windows Make Bash syntax failure, and native fixture parse failure are observed. |
| 关键处理动作 | claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6 | segment-02 source_index 381-427 | Replaced unsupported syntax, adjusted runner, and added OS-specific Makefile dispatch. |
| 对应验证结果 | claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6 | segment-03 source_index 780-791 | Direct exit code was checked, stderr handling was changed, and the final run reported 32/32. |

---

# 为按首参数索引的子句建立两遍构建并验证回溯正确性

```yaml
---
name: build-correct-first-argument-clause-index
description: >
  Use when a rule or clause database needs first-argument indexing to reduce
  candidate scans while preserving clause order and variable catch-all cases.
  Helps build interleaving-safe buckets and integrate candidate lists with
  backtracking. Requires a clause representation with observable first-argument
  tags and solver tests. Do not use when clause order or variable clauses are
  irrelevant to semantics.
---
```

## Goal

Reduce candidate search without changing logical results, including interleaved ground clauses, variable-first clauses, and backtracking to later matching clauses.

## Scope

### In scope

- Classify first arguments by atom, integer, or variable.
- Build buckets and preserve clause positions.
- Feed indexed candidates into solver backtracking.
- Test index hits, variable catch-all behavior, and second-solution recovery.

### Out of scope

- Replacing the unifier or changing logical semantics.
- Claiming performance gains without correctness tests.

## Inputs

- `clause list`: required; includes interleaved ground and variable-first clauses.
- `query term`: required; includes matching, nonmatching, and backtracking cases.
- `solver test harness`: required.

## Outputs

- `<index table>`: bucketed candidate positions plus variable candidates.
- `<solver integration>`: candidate iteration that correctly restores trail and choice-point state.
- Success standard: all indexing and solver regression tests pass with unchanged answers.
- Failure standard: any missing candidate, wrong order, or backtracking regression stops the optimization.

## Preconditions

执行前必须确认：

1. Clause positions are stable and can be stored in candidate lists.
2. First-argument tags distinguish ground values from variables.
3. Existing solver tests cover at least one failed candidate followed by a successful later candidate.

前置条件不满足时，停止并报告具体原因。

## Procedure

### Step 1: Define candidate classes

- Put atom and integer first arguments into keyed buckets.
- Put variable first arguments in a catch-all list.

### Step 2: Build buckets in two passes

- First count/create bucket ranges so each bucket has a stable contiguous range.
- Then append clause positions into the correct ranges in clause order.
- Do not assume clauses for one key are contiguous in the original database.

### Step 3: Integrate with solver backtracking

- Return the keyed candidates plus variable candidates for a ground query.
- Preserve choice-point trail marks and goal-stack positions until a candidate succeeds or is discarded.
- Test a failed first candidate followed by a later successful candidate.

### Step 4: Rebuild and run focused suites

- Recompile all affected objects and fresh test binaries.
- Run indexing, solver, and existing regression suites.

## Decision Rules

### When clauses for the same key are interleaved

执行：

1. Use two-pass range construction.
2. Store absolute clause positions in bucket order.
3. Verify a query that must skip an earlier failed candidate.

### When the first argument is a variable

- Include the clause in the variable catch-all list; never discard it because no ground key matches.

### When an indexed solver test regresses

- Debug candidate ordering and trail/choice-point restoration before changing unification semantics.
- Rebuild fresh binaries to exclude stale test output.

## Invariants

- Every clause remains reachable through exactly the appropriate bucket or catch-all list.
- Candidate order remains deterministic.
- A failed candidate undoes its bindings before the next candidate.
- Indexing changes search selection, not logical answers.

## Common Failures

### Failure: Interleaved clauses produce the wrong bucket range

症状：

- A query skips or selects the wrong clause when clauses for different keys are interleaved.

原因：

- Bucket starts were recorded while appending, so later entries for an existing bucket were not contiguous.

恢复：

1. Rebuild bucket ranges in two passes.
2. Re-run the focused indexing query and full solver suite.

### Failure: Backtracking loses the remaining candidate

症状：

- A query that should find a later solution fails after the first candidate fails.

原因：

- Choice-point pop/backtrack state was updated before the failed candidate's restoration completed.

恢复：

1. Keep the active choice point valid through candidate failure and trail undo.
2. Re-run the backtracking regression test.

## Verification

- [x] Ground buckets and variable catch-all are tested.
- [x] Interleaved clause ordering is covered.
- [x] Backtracking after a failed candidate is covered.
- [x] Fresh binaries are built before the final suite.
- [x] The final trace reports all 13 indexing tests and the 10-suite total passing.

## Examples

### Example 1: Interleaved path clauses

输入：

Clauses whose first arguments are `a`, `b`, and `a` again, plus a variable-first rule.

处理：

Build keyed ranges in two passes, include variable rules in the catch-all list, then query a goal that causes the first `a` clause to fail and the later `a` clause to succeed.

预期结果：

The trace reports all 13 indexing tests and 10/10 suites passing after the bucket and backtracking fixes.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | segment-01 source_index 54-74 | User requested v0.2 indexing and assistant defined ground buckets plus variable catch-all. |
| 关键处理动作 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | segment-02 source_index 207-247 | Diagnosed backtracking state and fixed index construction; final implementation summary records two-pass bucket build. |
| 对应验证结果 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | segment-02 source_index 278-334 | 13 indexing tests and 144/144 tests across 10 suites pass. |

---

# 识别并修复原生测试中的大对象栈溢出

```yaml
---
name: diagnose-large-object-stack-overflow-in-native-tests
description: >
  Use when a native test binary exits with a stack-overflow code or produces no
  output before main, especially after adding large fixed-size tables or index
  arrays. Helps distinguish implementation regressions from test fixture object
  placement and reduce stack usage safely. Requires a reproducible binary exit
  code and access to the test type definitions. Do not use to silence a crash
  without rerunning the affected suite.
---
```

## Goal

Move oversized test data out of automatic storage or avoid copying it by value, then prove the original tests pass with fresh binaries.

## Scope

### In scope

- Measure or estimate large struct sizes.
- Locate local copies and large automatic arrays.
- Use static storage or references only where the test is non-reentrant and isolation is preserved.
- Rebuild and rerun the affected and regression suites.

### Out of scope

- Changing production data structures solely to hide a test fixture allocation.
- Treating stale binaries as evidence about the current source.

## Inputs

- `crashing test binary`: required; include native exit code.
- `test source and type definitions`: required.
- `fresh compile command`: required to separate stale output from current behavior.

## Outputs

- `<test storage fix>`: static storage or reference-based access with preserved test semantics.
- `<fresh suite result>`: affected test and full regression result.
- Success standard: no stack overflow and all relevant tests pass.
- Failure standard: if the crash persists after minimal storage correction, report the remaining location rather than guessing.

## Preconditions

执行前必须确认：

1. The exit code indicates stack overflow or equivalent pre-main failure.
2. The relevant test object sizes can be inspected.
3. Test state can safely use static storage or a reference without introducing cross-test contamination.

前置条件不满足时，停止并报告具体原因。

## Procedure

### Step 1: Reproduce directly

- Run the test binary directly and record its exit code.
- Build a minimal link or fresh binary if stale artifacts are possible.

### Step 2: Find oversized automatic storage

- Inspect local test variables, copied return values, solver stacks, arenas, and fixed arrays.
- Estimate their sizes and identify whether the allocation occurs before `main` or inside a test function.

### Step 3: Apply the smallest storage correction

- For non-reentrant shared test fixtures, move large members to static storage and reset them between tests as needed.
- For a large returned object copied by value, bind a reference instead.
- Avoid changing production semantics to solve a test-only placement issue.

### Step 4: Rebuild fresh and verify

- Compile the affected test with fresh output names or after cleaning stale binaries.
- Run the focused test, then the complete suite.

## Decision Rules

### When a test copies a megabyte-scale table by value

执行：

1. Replace the copy with a reference to the existing object.
2. Rebuild the minimal test and confirm its exit code is zero.

### When a non-reentrant fixture contains very large arrays

- Use static storage only if the test harness resets or reinitializes the state between cases.

### When the old binary shows the same crash

- Classify the issue as pre-existing relative to the feature change, but still fix it only if that fix is in the authorized test scope and verify the final suite.

## Invariants

- Test semantics and assertions remain unchanged.
- Production code is not altered to mask a fixture stack problem.
- Fresh binaries are used for final evidence.
- Static test state does not leak between cases.

## Common Failures

### Failure: Large solver/index structures exhaust the Windows stack

症状：

- Test exits with `0xC00000FD` and emits no test output.

原因：

- Large choice stacks, databases, arenas, or fixture contexts are automatic variables.

恢复：

1. Move non-reentrant large storage to static or heap-backed storage as appropriate.
2. Rebuild and rerun the focused test.

### Failure: A large return value is copied onto the stack

症状：

- A minimal atom test crashes even when linked with only the atom implementation.

原因：

- The test binds a large `AtomTable` return value by value.

恢复：

1. Bind the existing table by reference.
2. Rebuild the minimal test and then the full suite.

## Verification

- [x] Stack-overflow exit code was reproduced directly.
- [x] Object size and storage location were inspected.
- [x] The smallest test-side storage fixes were applied.
- [x] Fresh binaries were built after the fixes.
- [x] The final trace reports 17 atom tests and 144/144 total tests passing.

## Examples

### Example 1: Large atom table copied by value

输入：

A test function that assigns `AtomTable t = make_table()` where `AtomTable` is about 1 MB.

处理：

Inspect the minimal binary, identify the by-value copy, bind a reference, rebuild, and rerun the atom suite.

预期结果：

The trace reports all 17 atom tests passing; the final 10-suite run reports 144/144.

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | segment-02 source_index 181-187, 253-262 | Direct runs show stack overflow; large `ChoicePoint`, `Database`, and fixture structures are sized and located. |
| 关键处理动作 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | segment-02 source_index 263-278, 317-327 | Static fixture members and reference binding are applied after inspecting the test source. |
| 对应验证结果 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | segment-02 source_index 280-334 | Indexing passes, atom tests reach 17 passing, and final total is 144/144. |

---

## 未保留的主要候选及原因

- Yggdrasil Stage 2 feature expansion (namespace tags, comments, spread children, pragma modes, batch mode, and recovery): the provided slices show implementation in progress and only partial fixture evidence in the available segment boundary; the complete Stage 2 completion and all newly added fixture results are not fully visible in the listed collapsed/full slices, so it was not promoted as a separate Skill.
- FrostCore Stage 3's requested physical parser/VM compilation-unit split: the trace explicitly says that split was deferred; only the serialization adapter was verified, so it is represented by the boundary-adapter Skill rather than a physical-split Skill.
- General habits such as reading files, writing code, or running tests: these do not change execution decisions and are too generic to qualify.
- Documentation updates and changelog writing in the Epilog and FrostCore sessions: execution is shown, but the traces do not establish a reusable problem-solving method beyond ordinary project documentation.
- Failed intermediate approaches (wrong directory layout, stale binaries, initial Makefile shell loop, and initial PowerShell exit-code handling): retained only as failure evidence inside the relevant Skills, never as recommended procedures.

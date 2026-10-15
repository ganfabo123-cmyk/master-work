# 本次提取的 Skill 总数：5

- Allocator-injectable multi-runtime boundary isolation — 来源 Session `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833`
- Selective subsystem registration with dependency and idempotency checks — 来源 Session `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833`
- Parse-once-run-many portable bytecode boundary — 来源 Session `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833`
- Prevent stack overflow from large test fixtures copied by value — 来源 Session `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e`
- Verify batch CLI error isolation and distinguish harness failures from product failures — 来源 Session `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6`

# Allocator-injectable multi-runtime boundary isolation

```yaml
---
name: allocator-injectable-multi-runtime-boundary
description: >
  Use when wrapping a C/C++ VM or engine for an embedding layer that needs
  explicit per-runtime allocation and lifecycle control.
  Helps prove multiple runtimes coexist without shared mutable state and that
  allocation failures and JavaScript errors cross a small public C boundary.
  Requires an allocator callback table, opaque runtime handle, and a runnable
  smoke-test harness.
  Do not use when changing the VM's allocator/GC internals or designing a
  scheduler; those were explicitly outside the evidenced stage.
---
```

## Goal

Provide a thin public boundary with injected allocators, explicit create/destroy, minimal evaluation, isolated runtime state, and observable cleanup.

## Scope

### In scope

- Store the allocator table and opaque userdata per runtime.
- Adapt the upstream allocator callback calling convention at the boundary.
- Expose create, destroy, and minimal evaluation/error reporting.
- Exercise three simultaneous runtimes, including one counting allocator.

### Out of scope

- Rewriting the upstream engine, changing its GC, parser, or scheduler.
- Claiming complete leak freedom beyond the allocator accounting exercised by the smoke test.

## Inputs

- `<allocator>`: optional callback table with alloc/free/realloc (and optional calloc/usable-size) plus userdata.
- `<source>`: small valid or invalid JavaScript expressions for the evaluation smoke test.
- `<runtime-count>`: at least three concurrently live runtime handles for isolation testing.

## Outputs

- `<runtime>`: opaque handle with explicit ownership and destroy operation.
- `<error>`: allocated diagnostic string for failed evaluation.
- Success standard: valid evaluations succeed, invalid source returns an error, a sentinel set in one runtime is absent from another, and counting allocator frees equal allocations after destruction.
- Failure standard: report failed creation/evaluation, non-isolated state, missing error text, or mismatched allocator accounting.

## Preconditions

1. The upstream engine exposes a runtime-construction API accepting allocator callbacks.
2. The boundary can retain runtime-specific userdata and owns cleanup of callback-produced resources.
3. A build and smoke-test path can run the wrapper on the target platform.

If any condition is missing, stop and report it rather than silently using global state.

## Procedure

### Step 1: Define the opaque boundary

- Define an opaque runtime handle containing the upstream runtime/context and a copy of the allocator table.
- Keep all allocator userdata associated with that handle.

### Step 2: Adapt callbacks and lifecycle

- Add static adapter thunks that receive the upstream opaque pointer, recover the boundary handle, and forward to the user allocator.
- Provide explicit create/destroy functions; use a system allocator only when the caller passes no table.

### Step 3: Add minimal evaluation and errors

- Evaluate a small expression through the runtime context.
- Convert exceptions to a caller-owned error string and document its release path.

### Step 4: Run isolation and accounting checks

- Create three runtimes with two system configurations and one counting allocator.
- Evaluate independent expressions, set a sentinel in one runtime, and confirm another runtime reports it as undefined.
- Destroy all runtimes and compare counting allocator allocations and frees.

## Decision Rules

### When the embedding API must support independent heaps

Execute:

1. Keep the allocator table and userdata in each runtime object.
2. Pass the runtime object as the upstream allocator opaque value.
3. Test cross-runtime visibility explicitly, rather than inferring isolation from successful creation.

### When the caller supplies no allocator

- Use the documented system allocator fallback and still run the same lifecycle and isolation checks.

### When allocation counts do not balance or a sentinel leaks across runtimes

- Do not report success; inspect callback routing and hidden globals before expanding the API.

## Invariants

- No hidden mutable global owns runtime state.
- Destroy is explicit and safe for the documented null case.
- Error strings have a documented ownership/release path.
- Runtime A's globals and allocator userdata never affect runtime B.

## Common Failures

### Failure: Runtime state or allocator userdata is shared

症状：跨 runtime 可见 sentinel 或 allocator 计数混合。

原因：回调 opaque 没有绑定到单个 runtime，或使用了隐藏全局。

恢复：将 runtime handle 作为 upstream opaque，重跑 sentinel 与分配计数检查。

## Verification

- [ ] Three runtimes are created concurrently.
- [ ] Arithmetic, typeof, array, and boolean evaluations succeed.
- [ ] Syntax, reference, and thrown-error cases return non-null diagnostics.
- [ ] A sentinel in one runtime is undefined in the second.
- [ ] Counting allocator reports `allocs=1246, frees=1246` after destruction in the evidenced run.

## Examples

### Example 1: Valid use case

输入：three runtimes, one counting allocator, and the expressions used by the smoke harness.

处理：route callbacks through per-runtime thunks, evaluate independently, set a sentinel only in the first runtime, then destroy all three.

预期结果：all smoke tests pass; the evidenced run showed zero difference between allocation and free counts.

来源证据：

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 3, 84 | Stage 1 requires injected allocator, explicit lifecycle, three runtimes, and no hidden globals. |
| 关键处理动作 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 100, 109 | Per-runtime callback thunks and three-runtime counting/isolation smoke test were implemented. |
| 对应验证结果 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 149, 151 | All smoke tests passed; `allocs=1246, frees=1246`; sentinel isolation passed. |

# Selective subsystem registration with dependency and idempotency checks

```yaml
---
name: selective-subsystem-registration
description: >
  Use when a bare VM/runtime must expose optional standard-library or runtime
  subsystems through an explicit registration API.
  Helps enforce prerequisites, track what is installed, and make repeated
  registration safe.
  Requires a bare-runtime constructor, subsystem bitmask/state, and focused
  tests for dependency ordering and repeated calls.
  Do not use to redesign unrelated VM internals or to infer behavior for
  subsystems not covered by the registration contract.
---
```

## Goal

Allow an embedding layer to start with a bare runtime and add only selected subsystems while enforcing dependencies and idempotency.

## Scope

### In scope

- Bare runtime creation and explicit registration entry points.
- Bitmask/state tracking for completed registrations.
- Dependency checks and safe repeated registration.
- A dedicated subsystem test suite.

### Out of scope

- Parser/bytecode behavior, scheduler behavior, or performance claims.
- Assuming untested subsystem combinations are valid.

## Inputs

- `<bare-runtime>`: runtime created without the full standard library.
- `<subsystem>`: one registration request from the public subsystem API.
- `<dependency-state>`: current registration bitmask/state.

## Outputs

- Updated registration state and installed subsystem behavior.
- Explicit failure when prerequisites are absent.
- Success standard: registration tests pass for supported orderings, dependency rejection, and repeated calls.
- Failure standard: return/report the unmet dependency or invalid registration without claiming installation.

## Preconditions

1. The runtime exposes a bare constructor and named registration functions.
2. Registration state is stored per runtime, not globally.
3. The test harness can inspect both return status and resulting state/behavior.

## Procedure

### Step 1: Create the bare runtime

- Construct the runtime with only VM bootstrap facilities and initialize its registration bitmask to empty.

### Step 2: Register by named capability

- For each request, check required bits before installing the subsystem.
- Install the subsystem, then set its bit only after successful completion.

### Step 3: Make repeated calls idempotent

- If the bit is already set, return the documented successful/no-op result and do not duplicate registrations.

### Step 4: Verify combinations

- Test valid orderings, missing dependencies, repeated calls, and the resulting behavior in the dedicated suite.

## Decision Rules

### When a required dependency bit is absent

Execute:

1. Reject the registration with an observable failure.
2. Leave the state unchanged and test that the dependent capability is not partially installed.

### When the requested bit is already set

- Treat the call as idempotent and verify no duplicate side effect occurs.

## Invariants

- Registration state belongs to the runtime instance.
- A dependency failure cannot set the dependent bit.
- Repeated successful registration does not duplicate the subsystem.

## Common Failures

### Failure: Dependency ordering is implicit

症状：a bare runtime accepts a dependent subsystem without its prerequisite, or later behavior fails mysteriously.

原因：registration functions do not enforce the state bitmask.

恢复：check dependencies before installation, leave state unchanged on failure, and rerun the subsystem suite.

## Verification

- [ ] Bare creation succeeds.
- [ ] Supported registration paths succeed.
- [ ] Missing prerequisites are rejected explicitly.
- [ ] Repeated registration is idempotent.
- [ ] The full evidenced subsystem suite reports `135/135` passing.

## Examples

### Example 1: Valid use case

输入：a bare FrostCore runtime and the public standard-subsystem registration calls.

处理：track completed registrations with a per-runtime bitmask, enforce dependencies, and make repeated calls no-ops.

预期结果：the Stage 2 suite passed `135/135` assertions.

来源证据：

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 494 | Session continuation summary states bare runtime, selective registration, dependency enforcement, and idempotency as Stage 2 behavior. |
| 关键处理动作 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 515 | Implementation stores `registered_subsystems` as a per-runtime bitmask. |
| 对应验证结果 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 582 | Stage 2 subsystem suite reported `135/135` passed. |

# Parse-once-run-many portable bytecode boundary

```yaml
---
name: parse-once-run-many-portable-bytecode
description: >
  Use when source should be compiled once and executed in multiple independent
  VM runtimes or after the parser runtime has been destroyed.
  Helps produce an owning, runtime-independent bytecode blob and explicit
  load/evaluate lifecycle.
  Requires compile-only evaluation, object serialization/deserialization, and
  runtime-owned loaded-function lifetime.
  Do not use when source execution itself is the only requirement or when the
  engine cannot guarantee serialized objects are self-contained.
---
```

## Goal

Compile source in a short-lived scratch runtime, serialize an owning bytecode blob, and load/evaluate it repeatedly in one or more target runtimes.

## Scope

### In scope

- Compile-only parse operation.
- Serialization into an independently owned blob.
- Load into target runtimes and repeated evaluation.
- Parse-once-run-many and blob independence tests.

### Out of scope

- A new bytecode format or changes to upstream serialization.
- Claims about arbitrary modules or unsupported runtime globals.

## Inputs

- `<source>`: valid or invalid JavaScript source.
- `<target-runtime>`: full or appropriately prepared bare runtime.
- `<bytecode>`: owning serialized blob returned by parse.

## Outputs

- `<bytecode>`: self-contained blob with size query and destroy operation.
- `<error>`: parse/load diagnostic with available line and column.
- Success standard: blob survives scratch-runtime teardown, loads into multiple runtimes, and evaluates repeatedly.
- Failure standard: parse/load/evaluate reports an error and does not leave an invalid loaded handle installed.

## Preconditions

1. The VM supports compile-only evaluation and bytecode serialization/deserialization.
2. Serialized objects can be read by independent runtimes.
3. The API defines ownership for the blob, errors, and loaded function handle.

## Procedure

### Step 1: Compile in a scratch runtime

- Create a minimal scratch runtime/context.
- Call compile-only evaluation so source is parsed without executing it.

### Step 2: Serialize and detach

- Serialize the compiled function with the VM's bytecode writer.
- Copy the bytes into an owning allocation, record its size, free VM values, and destroy the scratch runtime.

### Step 3: Load into a target runtime

- Deserialize the blob in the target context.
- Store the resulting function handle in the target runtime and release/rewrite any previous loaded handle according to the API contract.

### Step 4: Evaluate safely and repeatedly

- Duplicate or otherwise preserve the stored handle before evaluation so execution does not consume the long-lived reference.
- Evaluate once and multiple times, then destroy both blob and runtimes.

## Decision Rules

### When the parser runtime must be torn down before execution

Execute the scratch-runtime serialization path; never retain a raw VM pointer from the parser context.

### When a target runtime is bare

- Register the required core subsystem before loading, then verify that missing prerequisites fail explicitly.

### When parse or load fails

- Return the structured error and stop; do not execute a partially loaded value.

## Invariants

- The bytecode blob contains no dangling pointer into the scratch runtime.
- A target runtime owns its loaded function handle.
- Repeated evaluation preserves the stored handle.
- Blob destruction is independent of runtime destruction.

## Common Failures

### Failure: Loaded function is consumed by the first evaluation

症状：first evaluation succeeds but a second evaluation fails or sees an invalid handle.

原因：the stored VM value was passed directly instead of duplicating/preserving it.

恢复：duplicate the stored handle for each execution and rerun repeated-evaluation tests.

## Verification

- [ ] Valid source parses and reports a nonzero blob size.
- [ ] Invalid source returns a diagnostic.
- [ ] Blob remains usable after scratch runtime teardown.
- [ ] The same blob loads into multiple runtimes.
- [ ] Repeated evaluation and load replacement work.
- [ ] NULL/invalid argument cases fail safely.
- [ ] The evidenced bytecode suite reports `101/101` passing.

## Examples

### Example 1: Valid use case

输入：a valid JavaScript source, five target runtimes, and the FrostCore bytecode API.

处理：`JS_Eval(COMPILE_ONLY)` in a scratch runtime, serialize, destroy scratch runtime, load into targets, and evaluate repeatedly.

预期结果：Stage 3 bytecode tests passed `101/101`, including parse-once-run-many and blob independence.

来源证据：

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 457, 460 | Trace identifies compile-only → serialize → load → evaluate pipeline. |
| 关键处理动作 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 486, 508 | Scratch parser and VM load/eval implementations were written; stored handle is duplicated for evaluation. |
| 对应验证结果 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 564, 582 | Tests cover 13 groups and report `101/101` passed. |

# Prevent stack overflow from large test fixtures copied by value

```yaml
---
name: prevent-large-fixture-value-copy-stack-overflow
description: >
  Use when a C/C++ test crashes before or at startup after introducing a large
  arena, table, database, or registry fixture.
  Helps distinguish a value copy onto the stack from a product regression and
  repair tests without shrinking the production capacity.
  Requires the fixture size, a reproducible test binary, and a focused rebuild.
  Do not use to declare a general memory leak or runtime bug without reproducing
  the crash and checking the test's object declarations.
---
```

## Goal

Eliminate stack overflow caused by copying large test fixtures by value while preserving the test's reset behavior and proving the fix with the full suite.

## Scope

### In scope

- Inspect fixture size and declarations/macros.
- Replace value copies of static/shared fixtures with references.
- Apply the same audit to related arena/registry tests.
- Rebuild focused and complete suites.

### Out of scope

- Redesigning the engine's storage model solely from this symptom.
- Treating a still-locked binary or unrelated compile error as proof of a code defect.

## Inputs

- `<fixture>`: large object such as `AtomTable`, `TermArena`, or `VarRegistry`.
- `<factory>`: helper returning a static/reused initialized fixture.
- `<test-output>`: crash code and focused/full test results.

## Outputs

- Test declarations bind by reference to the existing large fixture.
- Focused test passes and the complete suite result is recorded.
- Failure standard: if the binary still crashes, report the remaining location and do not claim the fixture issue is solved.

## Preconditions

1. The crash is reproducible in the test binary.
2. The fixture is materially larger than the platform's practical test stack.
3. The factory's returned object remains valid for the test duration and can be reset between tests.

## Procedure

### Step 1: Confirm the failure boundary

- Run the focused binary and note whether it crashes before test output.
- Compare with a minimal harness if needed to separate framework startup from the fixture.

### Step 2: Inspect declarations and expansions

- Search for `Type value = factory()` and macro expansions that return a large object or reference.
- Estimate the copied object size; do not assume the factory's return type implies reference binding.

### Step 3: Bind by reference

- Change the test-local binding to `Type& value = factory()` (or `const Type&` when mutation is unnecessary).
- Audit all occurrences in related tests, including arena and registry helpers.

### Step 4: Rebuild and verify

- Rebuild the focused binary, run it, then run the full suite and record counts.

## Decision Rules

### When a factory returns a static reusable large object

Execute:

1. Bind the result by reference.
2. Keep the factory's explicit reset/init call at each test boundary.

### When the crash persists after all value copies are removed

- Stop attributing it to this fix; inspect the next concrete stack/global allocation and report the unresolved evidence.

## Invariants

- Tests do not copy megabyte-scale fixtures onto the stack.
- Each test starts from a reset fixture state.
- Production capacities and semantics remain unchanged.
- Full-suite results distinguish this repair from unrelated locked binaries.

## Common Failures

### Failure: Reference-returning macro is assigned to a value

症状：startup crash/stack overflow despite a static fixture helper.

原因：`Type value = make_fixture()` performs a full object copy; the macro's reference return does not prevent the copy.

恢复：use `Type& value = make_fixture()` for every occurrence, rebuild, and rerun focused/full suites.

## Verification

- [ ] Focused test no longer crashes before `main`/test output.
- [ ] All large-fixture bindings are references.
- [ ] Related arena/registry tests use the same safe binding.
- [ ] Full evidenced run reports `10/10 suites, 144/144 tests pass`.

## Examples

### Example 1: Valid use case

输入：a roughly 1 MB `AtomTable`, a `fresh_table()` static factory, and tests using `AtomTable t = make_table()`.

处理：replace value bindings with `AtomTable&`; apply the same audit to `TermArena` and `VarRegistry` tests.

预期结果：focused atom tests report `17/17`; the later complete run reports `10/10 suites, 144/144 tests pass`.

来源证据：

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e` | 323, 325 | Trace identifies a ~1 MB table and value copy as the stack-overflow cause. |
| 关键处理动作 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e` | 1204, 1208 | All `AtomTable` bindings and related arena/registry bindings were changed to references. |
| 对应验证结果 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e` | 329, 334 | Focused test passed `17/17`; complete run passed `10/10 suites, 144/144 tests`. |

# Verify batch CLI error isolation and distinguish harness failures from product failures

```yaml
---
name: verify-batch-cli-error-isolation
description: >
  Use when a directory or explicit-file CLI processes multiple source files and
  must continue producing valid outputs when one input is invalid.
  Helps build an acceptance matrix for copying, flags, diagnostics, exit codes,
  and per-file output while separating test-harness mistakes from product bugs.
  Requires a runnable CLI, good and bad fixtures, and a script that captures
  stdout, stderr, and exit status.
  Do not use a single happy-path fixture as evidence for error isolation or
  nonexistent-path behavior.
---
```

## Goal

Prove that batch processing preserves good outputs, reports bad inputs, and returns correct exit codes across directory, explicit-file, flag, and invalid-path cases.

## Scope

### In scope

- Directory batch and explicit file-list paths.
- Transpile/copy behavior, pragma/runtime flags, verbose output, and thread-count equivalence.
- Per-file error isolation and nonexistent source-path handling.
- Correcting acceptance checks that misread output or mishandle stderr.

### Out of scope

- General parser correctness beyond the fixture suite.
- Performance claims from one thread-count comparison.

## Inputs

- `<src-dir>`: directory containing valid JSX/JS and at least one invalid fixture set.
- `<flags>`: pragma/runtime/copy/verbose/thread options under test.
- `<out-dir>`: isolated output directory for each test case.
- `<runner>`: script that captures process output and exit code without converting expected stderr into a harness exception.

## Outputs

- Per-file generated/copy outputs and diagnostic output.
- Nonzero exit for invalid input or nonexistent source path.
- Success standard: all acceptance cases pass and a bad file does not prevent a good file from being written.
- Failure standard: report the exact case, process exit, and whether the failure came from the CLI or runner assertion.

## Preconditions

1. The CLI has stable single-file and batch entry points.
2. Fixtures include valid JSX, passthrough JS, an invalid file, and a missing path.
3. The runner can inspect output content without assuming the transformed call starts at byte zero.

## Procedure

### Step 1: Build a behavior matrix

- Check normal directory processing, `--no-copy`, pragma/runtime flags, verbose paths, single-thread mode, explicit file lists, invalid-file isolation, missing paths, and aliases.

### Step 2: Keep assertions semantic

- Search for expected generated calls anywhere in the output when source wrappers legitimately precede them.
- Capture expected nonzero stderr through a mechanism that does not turn it into an unhandled shell exception.

### Step 3: Trace product exit behavior

- For a missing path, verify whether batch mode is selected and whether the file processor increments failure rather than silently classifying it as skipped.
- Fix the product's error accounting when the observed exit code contradicts the contract.

### Step 4: Rerun the complete matrix

- Require both good-output preservation and correct failure status before reporting success.

## Decision Rules

### When a generated call exists but is not at file offset zero

- Fix the assertion to test semantic containment; do not alter valid code generation just to satisfy an anchored regex.

### When expected stderr causes the shell runner to throw

- Capture the command through a shell mode that preserves its exit status and stderr for assertion.

### When a nonexistent source path exits zero

Execute:

1. Trace CLI mode selection and file classification.
2. Treat nonexistent input as a processing error and increment the batch failure count.
3. Rebuild and rerun the missing-path plus full matrix cases.

## Invariants

- A bad file cannot erase or suppress a good file's output.
- Invalid input and nonexistent paths return nonzero status.
- Runner assertions reflect output semantics and expected stderr behavior.
- A passing subset is not reported as a passing full matrix.

## Common Failures

### Failure: Harness false negative from anchored output check

症状：generated `h(...)` exists inside a function, but `^h\(` assertion fails.

原因：the assertion assumes the transformed call is at the beginning of the whole file.

恢复：assert substring/semantic presence and rerun the case.

### Failure: Missing path silently exits zero

症状：a nonexistent source path is skipped and the CLI returns zero.

原因：nonexistent path is routed through explicit-file processing and counted as skipped rather than failed.

恢复：make nonexistent input an error, rebuild, and verify nonzero exit plus the complete suite.

## Verification

- [ ] Valid directory batch and explicit file list produce expected files.
- [ ] `--no-copy`, pragma/runtime, verbose, thread, and alias cases pass.
- [ ] Invalid file returns nonzero while good file is still emitted.
- [ ] Missing source path returns nonzero.
- [ ] Fixture suite reports `48/48`.
- [ ] Stage 3 batch suite reports `17/17`.

## Examples

### Example 1: Valid use case

输入：directory fixtures with JSX files, passthrough JS, a malformed JSX file, and CLI flags for pragma/runtime/copy/thread behavior.

处理：fix semantic output assertions and stderr capture in the PowerShell runner; fix batch failure accounting for nonexistent paths; rerun all fixture and batch cases.

预期结果：the evidenced run reported `48/48` fixture tests and `17/17` batch tests, including error isolation and missing-path checks.

来源证据：

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | 1389, 1413, 1419 | Initial matrix exposed anchored pragma assertion, PowerShell stderr failure, and zero exit for a missing path. |
| 关键处理动作 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | 1392, 1400, 1421 | Assertions/capture were corrected and nonexistent paths were made batch errors. |
| 对应验证结果 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | 1428, 1433, 1450 | Batch reported `17 passed`; fixtures reported `48 passed`; final summary records both suites green. |

## 主要未保留候选

- Odin/Raylib 后台线程修复：轨迹识别出 `thread.destroy` 可能 join 长驻线程，并尝试了 `self_cleanup` 参数，但随后仍有进程锁定/构建失败，没有看到修复后的完整运行验证，因此不提取为成功 Skill。
- FrostCore Stage 3 之外的更广泛架构迁移：轨迹有设计和阶段计划，但没有与本次候选相同粒度的独立证据，避免把阶段计划扩写成 Skill。
- Epilog 中最初的 parser/solver 失败假设：最终有效证据是测试字符串中句点后缺少空格、以及大对象按值复制；其他关于静态存储的推测未单独保留。
- 仅有 README、记忆或变更摘要的候选：这些属于结果陈述，不能替代直接操作和对应验证，因此不单独生成 Skill。

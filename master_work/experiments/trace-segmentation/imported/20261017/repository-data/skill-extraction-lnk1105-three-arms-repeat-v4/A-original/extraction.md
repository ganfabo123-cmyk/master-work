# Skill 提取结果

本次提取的 Skill 总数：5。

| 标题 | 来源 Session ID |
| --- | --- |
| 在 Windows PowerShell 测试原生程序时保留真实退出码 | claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6 |
| 为交错输入构建正确的首参数索引 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e |
| 定位大型 C/C++ 对象引起的栈溢出 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e |
| 为现有 C 引擎增加隔离的嵌入边界 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 |
| 将裸运行时能力与可选标准库注册分层 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 |

---

# 在 Windows PowerShell 测试原生程序时保留真实退出码

```yaml
---
name: preserve-native-exit-codes-in-windows-powershell-tests
description: >
  Use when a Windows PowerShell 5.1 test runner invokes a native executable,
  especially when error fixtures write to stderr and the test must assert a
  non-zero exit code. Helps distinguish the program's exit code from
  PowerShell NativeCommandError handling. Requires a repeatable fixture runner
  and an executable whose stdout/stderr and exit status can be observed. Do not
  use as evidence that the executable's parser or business behavior is correct;
  it only makes the harness observe that behavior reliably.
---
```

## Goal

让 PowerShell 测试脚本准确比较原生程序的输出和退出码，避免 stderr 重定向或异常捕获把真实退出码改写成 `-1`。

## Scope

### In scope

- PowerShell 5.1 调用原生可执行文件。
- 成功用例、预期失败用例和退出码断言。
- 统一处理 stderr 对 `NativeCommandError` 的影响。

### Out of scope

- 修复被测程序本身的解析器或业务逻辑。
- 仅凭测试脚本通过推断所有运行时场景都正确。

## Inputs

- `<binary>`：待测试的原生可执行文件，必需。
- `<fixtures>`：输入 fixture 和期望输出/期望退出码文件，必需。
- `<runner>`：PowerShell 测试脚本，必须能按 fixture 执行程序。

## Outputs

- `<result>`：每个 fixture 的通过/失败结果及真实退出码。
- 成功标准：成功用例输出匹配，错误用例退出码匹配，脚本本身以正确汇总码结束。
- 失败标准：退出码缺失、被脚本改写、或错误输出导致脚本无法完成断言。

## Preconditions

执行前必须确认：

1. 当前环境是 Windows PowerShell，且可以直接运行目标程序。
2. 错误 fixture 明确定义期望退出码；输出比较 fixture 明确定义期望文本。
3. 测试脚本有权限启动程序并读取 fixture。

前置条件不满足时，停止并报告具体原因。

## Procedure

### Step 1: 区分输出比较与退出码比较

- 对正常 fixture 保存 stdout 并与期望文件比较。
- 对错误 fixture 只在需要时断言退出码；不要把 stderr 的 PowerShell 异常对象当成程序输出。

### Step 2: 隔离 PowerShell 的原生错误处理

- 不要在需要读取 `$LASTEXITCODE` 的路径中用 `2>&1` 再包围 `try/catch`。
- 使用 `cmd /c` 启动错误用例并抑制或单独处理 stderr，使 `$LASTEXITCODE` 保持原生进程的退出状态。
- 若必须捕获输出，先取得退出码，再处理捕获对象，并记录两者。

### Step 3: 重新运行完整集合

- 先运行最小错误 fixture 确认退出码没有变成 `-1`。
- 再运行全部成功、失败和阶段性 fixture，汇总通过数和失败数。

## Decision Rules

### When stderr 重定向后错误用例显示 `-1` 而程序应返回 `1`

执行：

1. 将退出码断言路径改为不经过 PowerShell `NativeCommandError` 捕获的调用方式，例如 `cmd /c`。
2. 重新检查原生退出码，再检查错误文本是否符合 fixture。

### When 只有普通输出 fixture 失败

- 保留真实输出并先判断行尾、编码和 runner 的 `Out-String` 处理；不能把格式差异直接归因于程序语义。

### When 没有期望退出码或 stderr 证据

- 不猜测失败原因；报告缺失的 fixture 契约。

## Invariants

执行过程中必须保持：

- 不修改被测程序来迎合测试脚本。
- 不把 PowerShell 的 `-1` 自动解释为程序真实退出码。
- 成功和错误 fixture 使用各自明确的断言。
- 不报告未经完整集合验证的通过。

## Common Failures

### Failure: `NativeCommandError` 将错误用例退出码显示为 `-1`

症状：

- Bash 中程序返回 `1`，但 PowerShell runner 报告 `-1`。
- stderr 经 `2>&1` 合并后进入 `try/catch`。

原因：

- 轨迹确认 PowerShell 5.1 将原生 stderr 转成 `ErrorRecord`，捕获异常会影响 `$LASTEXITCODE`。

恢复：

1. 退出码测试通过 `cmd /c` 运行并抑制 stderr，或在异常处理前保存退出码。
2. 重新运行所有错误 fixture；轨迹最终得到 `32/32` 通过。

## Verification

完成后必须检查：

- [ ] 成功 fixture 的实际输出与期望输出一致。
- [ ] 错误 fixture 获得定义的非零退出码，而非脚本生成的 `-1`。
- [ ] runner 对 stderr 不再异常中断。
- [ ] 全部 fixture 汇总通过；轨迹中阶段 1/2 为 `32/32`，阶段 3 另有 `48/48` 与 `17/17`。
- [ ] 失败原因和修复方式可追溯到 runner 行为，而不是未经验证的推测。

## Examples

### Example 1: JSX 错误 fixture

输入：

一个应报告解析错误并返回 `1` 的 JSX 文件，以及 PowerShell fixture runner。

处理：

发现 `2>&1` 加 `try/catch` 后 `$LASTEXITCODE` 被报告为 `-1`，将退出码测试改为 `cmd /c ... 2>nul`，让错误文本不参与 PowerShell 异常流。

预期结果：

完整 fixture 集合从 `31/32` 变为 `32/32`；这证明 runner 的退出码断言被修复，不额外证明未测试的编译器行为。

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6 | 原始文件第 781、784、787 行 | `31/32 passing`；错误 fixture 得到 `-1`；确认 PowerShell stderr 捕获影响 `$LASTEXITCODE`。 |
| 关键处理动作 | claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6 | 原始文件第 787 行 | 用 `cmd /c ... 2>nul` 避免 `NativeCommandError`。 |
| 对应验证结果 | claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6 | 原始文件第 792 行 | `32/32 passing`。 |

---

# 为交错输入构建正确的首参数索引

```yaml
---
name: build-two-pass-first-argument-index
description: >
  Use when indexing clauses, records, or rules by a first-argument key and
  input records for different keys can be interleaved. Helps construct
  contiguous bucket ranges without overlapping slots. Requires a stable record
  list and a query path that can consume bucket start/count ranges. Do not use
  the one-pass append assumption when records for the same key are separated.
---
```

## Goal

为交错排列的记录构建不重叠的首参数桶，使查询候选集完整且仍可回溯。

## Scope

### In scope

- 按原子、整数或变量首参数分桶。
- 记录顺序与桶顺序不同的情况。
- 索引构建、查询候选和回溯测试。

### Out of scope

- 更换整个求解器或定义未由轨迹支持的索引策略。
- 把索引通过当作所有查询语义都已验证。

## Inputs

- `<clauses>`：按原始插入顺序保存的子句列表，必需。
- `<key-extractor>`：提取首参数标签的逻辑，必需。
- `<query>`：使用桶范围生成候选的查询实现，必需。

## Outputs

- `<index>`：每个键的连续槽范围及变量兜底桶。
- 成功标准：每个桶只引用自己的记录，交错输入不会覆盖别的桶，查询和回溯结果正确。
- 失败标准：桶范围重叠、漏记录、重复记录或查询结果与未索引实现不一致。

## Preconditions

执行前必须确认：

1. 每条记录都有稳定的原始位置和可提取的首参数标签。
2. 查询实现能够消费桶的 `start/count` 或等价范围。
3. 有交错键的回归数据，而非只有按键分组的数据。

## Procedure

### Step 1: 先统计每个桶的数量

- 遍历全部记录，按首参数键计数；变量首参数进入 catch-all 桶。
- 不在第一次遍历时直接把新桶的起点等同于当前全局槽计数。

### Step 2: 分配连续范围并填充

- 根据计数计算每个桶的起点，建立互不重叠的范围。
- 第二次遍历按原记录顺序把记录位置填入对应范围。

### Step 3: 验证查询和回溯

- 检查每个桶的槽内容只属于该键。
- 用键交错的事实和规则运行查询，验证首解失败后仍能尝试后续候选。
- 与完整扫描结果比较。

## Decision Rules

### When 不同键的记录在输入中交错

执行两遍构建：先计数和分配范围，再填槽；禁止复用按键连续排列的单遍起点算法。

### When 首参数是变量

- 放入变量兜底桶，并确保查询始终尝试该桶。

### When 只有按键连续排列的样例

- 不把单遍算法视为已证明正确；补充交错输入后再报告成功。

## Invariants

执行过程中必须保持：

- 每个非变量桶的 `start/count` 对应唯一连续区域。
- 同一槽不能同时属于两个桶。
- 索引失败时可以退回完整扫描以核对结果。
- 不以单个成功查询替代交错数据回归。

## Common Failures

### Failure: 后创建的桶与先创建桶的槽范围重叠

症状：

- `a,b`、`b,c`、`a,c` 这类输入中，第二个 `a` 记录落入 `b` 桶或被覆盖。
- 回溯查询返回 0 个解，尽管完整扫描应有解。

原因：

- 轨迹确认单遍追加在桶创建时固定起点，后续交错记录又追加到其他桶，导致范围不连续并重叠。

恢复：

1. 改为两遍计数、分配、填充。
2. 重新检查桶槽内容，再运行索引和 solver 回归。

## Verification

完成后必须检查：

- [ ] 交错键输入的每个桶范围不重叠。
- [ ] 变量兜底候选仍可用。
- [ ] 回溯查询得到与完整扫描相同的解集。
- [ ] 独立索引测试通过；轨迹中为 `13` 个 indexing 测试通过。
- [ ] 完整测试套件通过；轨迹最终报告 `10/10 suites, 144/144 tests pass`。

## Examples

### Example 1: 交错事实的首参数索引

输入：

按顺序插入 `path(a,b)`、`path(b,c)`、`path(a,c)`，并查询依赖 `path/2` 的规则。

处理：

先按 `a`、`b` 计数和分配连续范围，再把位置 `0`、`1`、`2` 填入对应范围；不要在发现 `b` 时把当前全局槽计数作为其最终起点。

预期结果：

索引内容正确，查询返回预期解；轨迹中索引测试通过，solver 回归最终纳入 `144/144` 总通过数。

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | 原始文件第 230、237 行 | 交错 `path(a,b), path(b,c), path(a,c)` 导致结果为 0；发现桶槽重叠。 |
| 关键处理动作 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | 原始文件第 242 行 | 使用两遍方法：先按桶计数，再连续布局并填充。 |
| 对应验证结果 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | 原始文件第 247、281、335 行 | 索引正确；13 个索引测试通过；最终 `10/10 suites, 144/144 tests pass`。 |

---

# 定位大型 C/C++ 对象引起的栈溢出

```yaml
---
name: diagnose-large-object-stack-overflow
description: >
  Use when a native test or tool exits with a stack-overflow code, silently
  crashes before useful output, or becomes unstable after adding large fixed
  arrays or index tables. Helps distinguish oversized locals, value copies, and
  unrelated linkage issues. Requires a reproducible native binary and access
  to the involved struct definitions and test code. Do not use to claim a
  concurrency or heap-lifetime fix without a corresponding test.
---
```

## Goal

定位栈溢出的实际大对象来源，并以引用、静态存储或堆分配等与可重入性相容的方式消除它，再完成回归验证。

## Scope

### In scope

- 测试上下文、选择栈、数组和大结构体的栈占用。
- 按值返回或复制大结构体。
- 修复后的 native 回归。

### Out of scope

- 把所有崩溃都归因于栈大小。
- 在没有说明非重入约束时盲目改成静态全局。

## Inputs

- `<crash-binary>`：复现栈溢出的程序，必需。
- `<struct-layout>`：相关数组和结构体大小，必需。
- `<test-source>`：创建、复制或传递这些对象的代码，必需。

## Outputs

- `<fix>`：避免大对象落在受限栈上的最小修改。
- 成功标准：原复现程序不再栈溢出，功能测试通过。
- 失败标准：只能改变崩溃位置、引入数据共享副作用，或没有回归证据。

## Preconditions

执行前必须确认：

1. 有可重复的退出码、崩溃或无输出症状。
2. 能读取对象定义和创建点，并估算其大小。
3. 若采用静态存储，已确认调用路径非重入，或改用堆分配。

## Procedure

### Step 1: 先定位栈上的大对象

- 检查求解循环中的局部数组、测试上下文和按值返回的结构体。
- 计算数组容量乘以元素大小，并检查调用者是否再次按值复制。
- 用最小链接或最小测试隔离对象来源，避免把旧二进制或链接依赖误判为新回归。

### Step 2: 选择存储修复

- 只读或需要避免复制的测试对象，改用引用。
- 非重入、生命周期覆盖整个调用的工作数组，可移到静态存储；必须记录这一约束。
- 可重入或并发路径使用堆或调用方提供的工作区。

### Step 3: 验证原复现和完整回归

- 先直接运行原失败二进制，确认不再无输出退出。
- 再运行相关单元测试和完整套件，检查结果没有因共享状态改变。

## Decision Rules

### When 退出码对应 stack overflow 且局部数组占用明显超过线程栈

执行：

1. 将工作数组移出栈，优先选择与线程安全要求匹配的堆或调用方存储。
2. 重新运行原查询/测试，确认不是只绕过了一个路径。

### When 崩溃发生在 `T t = make_table()` 等大对象值复制处

- 改为 `const T&` 或等价避免复制的形式，并验证所有依赖该对象的测试。

### When 静态存储会让并发或递归路径共享状态

- 不采用静态修复；报告不可满足的重入约束并改用堆/显式上下文。

## Invariants

执行过程中必须保持：

- 不以降低数组容量掩盖越界风险。
- 不把旧二进制的失败归因于新改动。
- 静态工作区只在已确认非重入时使用。
- 修复后检查所有相关测试，而非只检查不再崩溃。

## Common Failures

### Failure: 索引表扩大后测试静默退出并返回 Windows stack overflow

症状：

- `test_indexing` 没有输出，退出码为 `0xC00000FD`。
- 求解器局部 `ChoiceStack`、测试上下文和多个大数组叠加。

原因：

- 轨迹通过大小估算确认局部数组和测试上下文落在栈上，超出默认栈限制。

恢复：

1. 将非重入求解器工作栈移到静态存储，并将测试上下文改为静态成员或其他稳定存储。
2. 重新链接并运行全部测试；轨迹最终通过 10 个套件。

### Failure: 单元测试在进入 `main` 前栈溢出

症状：

- `test_atoms` 无输出即崩溃，即使最小链接仍复现。

原因：

- 轨迹定位到 `AtomTable t = make_table()` 按值复制约 1MB 对象到局部栈。

恢复：

1. 改为引用，避免复制。
2. 重新运行 atom 测试和全套件。

## Verification

完成后必须检查：

- [ ] 原 stack overflow 退出码不再出现。
- [ ] 大对象不再被无意按值复制到栈上。
- [ ] 静态修复的调用约束已验证或记录。
- [ ] 相关测试通过；轨迹中 indexing 通过 13 项、atom 通过 17 项。
- [ ] 完整回归没有遗漏；轨迹报告 `144/144 tests pass`。

## Examples

### Example 1: 大型 AtomTable 值复制

输入：

一个返回大型 `AtomTable` 的测试辅助函数，以及 `AtomTable t = make_table()`。

处理：

从无输出栈溢出开始，用最小链接确认问题仍在，再定位到局部按值复制，将其改为引用。

预期结果：

17 个 atom 测试通过，并在后续完整运行中得到 10 个套件、144/144 通过。

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | 原始文件第 185、263、325 行 | 发现 stack overflow；估算大数组；最终定位到 `AtomTable` 按值复制。 |
| 关键处理动作 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | 原始文件第 191、268、325 行 | 工作栈移出栈；测试上下文改用稳定存储；大对象复制改为引用。 |
| 对应验证结果 | claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e | 原始文件第 281、332、335 行 | 13 个索引测试、17 个 atom 测试通过；最终 `144/144`。 |

---

# 为现有 C 引擎增加隔离的嵌入边界

```yaml
---
name: add-isolated-embedding-boundary-to-c-engine
description: >
  Use when exposing a living C runtime to another host while preserving the
  upstream tree and requiring caller-controlled allocation and lifecycle.
  Helps create a thin public C boundary with opaque runtime handles, allocator
  adapters, explicit create/destroy operations, and isolation tests. Requires
  an existing runtime API with a custom allocator hook and a separate overlay
  or wrapper build. Do not use to redesign the upstream engine or claim full
  host-language integration without ABI and lifecycle tests.
---
```

## Goal

在不修改上游引擎源码的前提下，建立可嵌入、可显式销毁、可由调用者控制分配器的 C API 边界。

## Scope

### In scope

- 独立 overlay/wrapper 目录和构建入口。
- 不透明 runtime 句柄、allocator 回调适配、create/destroy/eval API。
- 多 runtime 隔离、错误传播和分配/释放计数测试。

### Out of scope

- 修改上游引擎内部实现以适配 wrapper。
- 未经验证的 C++/Python/Odin 完整绑定。

## Inputs

- `<upstream-runtime>`：现有 C 引擎及其公开 allocator/runtime API，必需。
- `<allocator-vtable>`：调用者提供的 alloc/free/realloc/calloc 和 userdata，必需。
- `<overlay-build>`：独立构建脚本或 Makefile，必需。

## Outputs

- `<public-header>`：只暴露嵌入方需要的不透明 API。
- `<wrapper>`：allocator thunk、生命周期和求值错误提取。
- `<smoke-tests>`：多 runtime、隔离、错误和泄漏验证。
- 成功标准：多个 runtime 可同时工作，状态互不泄漏，分配释放平衡，错误可观察。
- 失败标准：需要修改上游文件、存在隐藏全局状态、或生命周期/泄漏无法验证。

## Preconditions

执行前必须确认：

1. 上游已有可调用的自定义 allocator hook，例如 `JS_NewRuntime2`。
2. 能为 wrapper 提供独立 include、source、tests 和构建入口。
3. 测试环境能运行 clang、归档工具和目标平台脚本。

## Procedure

### Step 1: 建立隔离 overlay

- 在独立目录放置 public header、wrapper source、smoke test 和构建脚本。
- 保持上游构建文件和源文件不变，wrapper 只依赖上游公开 API。

### Step 2: 适配 allocator 和生命周期

- 将调用者 allocator vtable 映射到上游回调签名；若参数顺序不同，使用静态 thunk。
- 提供显式 `runtime_create`、`runtime_destroy` 和求值/错误提取接口。
- 确认不存在隐藏全局 runtime。

### Step 3: 运行隔离与资源测试

- 同时创建至少两个配置不同的 runtime，验证变量、全局和错误状态隔离。
- 使用 counting allocator 记录 alloc/free，并验证生命周期结束后计数平衡。
- 运行正常表达式、语法错误、引用错误和 throw 等错误路径。

## Decision Rules

### When 上游已有 allocator hook

- 复用该 hook，在 wrapper 层做签名适配；不要复制或重写上游分配器。

### When 回调参数顺序不同

- 使用静态 thunk 转换 opaque 和参数顺序，并在 smoke test 中验证 userdata 到达正确分配器。

### When 上游 API 只能通过全局状态工作

- 停止报告“隔离 runtime”已完成；先报告该前置条件不满足。

## Invariants

执行过程中必须保持：

- wrapper API 不暴露上游内部结构。
- 每个 runtime 都绑定自己的 allocator 和状态。
- create/destroy 成对出现，错误路径也释放资源。
- 不修改无关上游文件或构建配置。

## Common Failures

### Failure: 选择错误的构建器或平台头冲突

症状：

- CMake 选择了 MSVC 而不是 clang，或 Windows `winsock.h` 与 `winsock2.h` 冲突。

原因：

- 轨迹显示构建入口没有固定工具链，且上游源在非 MSVC 编译路径中触发头文件冲突。

恢复：

1. 使用直接 clang/llvm-ar 的独立 Makefile，并在 Makefile 中加入 `WIN32_LEAN_AND_MEAN` 与 `_WINSOCKAPI_` 定义。
2. 在目标平台重新构建和运行 smoke/comprehensive tests。

## Verification

完成后必须检查：

- [ ] 上游源文件未被 wrapper 需求修改。
- [ ] 至少两个 runtime 可同时创建并保持状态隔离。
- [ ] 正常求值和至少三类错误可观察且返回约定结果。
- [ ] counting allocator 的 alloc/free 计数平衡。
- [ ] 轨迹中 Stage 1 smoke test 报告 `allocs=1246, frees=1246`，并且 Stage 2 报告 `135 passed, 0 failed`。

## Examples

### Example 1: 为现有 C VM 建立 FrostCore overlay

输入：

一个已有 `JSMallocFunctions` 和 runtime create/destroy 能力的 C VM，以及调用者 allocator vtable。

处理：

在独立 overlay 创建 public C header、wrapper、smoke test 和 clang/llvm-ar 构建入口；通过 thunk 将 userdata 和 calloc 参数映射到上游签名。

预期结果：

3 个 runtime 可同时运行，7 个表达式和 3 个错误案例通过，`allocs=1246, frees=1246`；证据只支持该边界层和测试场景。

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | 原始文件第 77、80、93 行 | 选择独立 overlay；确认上游已有 allocator hook；需要 thunk 处理签名差异。 |
| 关键处理动作 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | 原始文件第 90、99、188、202 行 | 实现 allocator thunk、生命周期 wrapper 和直接 clang/llvm-ar 构建。 |
| 对应验证结果 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | 原始文件第 151、202、212 行 | 多 runtime 隔离、错误路径和 `allocs=1246, frees=1246`；零警告构建通过。 |

---

# 将裸运行时能力与可选标准库注册分层

```yaml
---
name: separate-bare-runtime-capabilities-from-stdlib-registration
description: >
  Use when a C runtime must start with no optional standard-library objects but
  still needs a minimal internal capability for C-level execution. Helps
  separate internal VM enablement from visible subsystem registration and make
  dependency failures explicit. Requires a runtime with distinct intrinsic or
  subsystem registration APIs and tests that can inspect failure reasons. Do not
  use to infer that a bare runtime should expose the full standard library.
---
```

## Goal

让裸 runtime 保持可执行但不自动暴露标准库，并通过有依赖检查的显式注册 API 按子系统启用能力。

## Scope

### In scope

- 裸 context 的最低内部执行能力。
- core、collections、async、time、io 等可选注册及依赖错误。
- 注册状态、错误文本和测试调用顺序。

### Out of scope

- 自动加载全部标准库。
- 把显示出来的全局对象与内部 VM 函数指针混为同一能力。

## Inputs

- `<bare-runtime>`：创建时不含标准库的 runtime，必需。
- `<intrinsic-api>`：内部执行能力启用 API，必需。
- `<subsystem-api>`：带依赖检查和错误输出的注册 API，必需。
- `<tests>`：覆盖成功、缺依赖和注册状态的测试，必需。

## Outputs

- `<runtime>`：可执行的裸 runtime。
- `<registration-result>`：成功的注册位掩码或带具体原因的失败。
- 成功标准：裸 runtime 能完成 C 层求值，未注册子系统不可用，缺依赖时返回可操作错误。
- 失败标准：仅通过增加可见全局对象“修复”执行、错误原因丢失、或测试因未定义参数求值顺序而不可靠。

## Preconditions

执行前必须确认：

1. 上游区分内部 eval/执行入口和 base objects/标准库注册。
2. 每个子系统声明其依赖，注册 API 能返回错误字符串或等价诊断。
3. 测试不依赖 C 语言未指定的函数参数求值顺序。

## Procedure

### Step 1: 只启用内部执行能力

- 在裸 runtime 创建后调用内部 eval enable API，使 C 层求值路径可用。
- 不因此调用会向全局对象注入完整标准库的 API。

### Step 2: 实现显式子系统注册

- 为各子系统提供独立注册函数和依赖检查。
- 成功时更新注册位掩码；失败时返回明确的缺失依赖名称。

### Step 3: 让测试读取稳定的错误结果

- 把会修改错误指针的注册调用单独作为一条语句。
- 再把已写入的错误指针传给断言函数，避免在同一函数调用中同时读取和修改它。

### Step 4: 验证边界

- 在无标准库的 runtime 上执行基础表达式。
- 逐项注册并验证依赖拒绝、状态位和最终成功路径。

## Decision Rules

### When C 层求值报 `eval is not supported`，但需求是裸 runtime

执行内部 eval enable API；不要直接注册全部 base objects 来掩盖问题。

### When 注册子系统缺少依赖

- 拒绝注册并返回具体依赖名；测试应检查该名字存在。

### When 测试写成 `check(register(...), err, ...)`

- 拆成先执行注册、再检查 `err` 的两条语句；不能依赖参数求值顺序。

## Invariants

执行过程中必须保持：

- 裸 runtime 的可执行性与可见标准库对象分离。
- 失败注册不能部分设置成功状态位。
- 错误文本来自正式注册 API，不由测试或调用方旁路拼接。
- 不把 stderr/stdout 输出顺序误判为业务失败。

## Common Failures

### Failure: 裸 runtime 的 C 层求值失败

症状：

- 即使只求值 `1+2` 也得到 `eval is not supported`。

原因：

- 轨迹确认裸 context 的 `eval_internal` 指针仍为 NULL；可见 base objects 尚未注册并不是唯一问题。

恢复：

1. 仅调用内部 eval enable API。
2. 重新运行 VM 基础测试，确认不需要暴露完整 `eval()` 全局函数。

### Failure: 依赖错误断言读到 NULL

症状：

- 注册函数实际设置了错误，但测试显示 `got: (null)`。

原因：

- 同一函数调用的参数同时修改和读取错误指针，C 的参数求值顺序未定义。

恢复：

1. 将注册调用和断言拆开。
2. 重新运行依赖测试并检查错误包含缺失子系统名。

## Verification

完成后必须检查：

- [ ] 裸 runtime 的基础 C 层求值通过。
- [ ] 未注册标准库不会被误报为已可用。
- [ ] 缺依赖注册稳定失败并返回具体原因。
- [ ] 注册位掩码与实际成功子系统一致。
- [ ] 全套 Stage 2 测试通过；轨迹最终报告 `135 passed, 0 failed`。

## Examples

### Example 1: 裸 QuickJS 风格 runtime

输入：

一个通过 raw context 创建的 runtime，以及 `frost_register_std_core`、`frost_register_std_collections` 等注册函数。

处理：

创建裸 runtime 后启用内部 eval；先尝试无依赖的注册，再故意注册缺少 core 的 collections，单独保存返回错误并检查 `requires std_core`；最后按依赖顺序注册。

预期结果：

基础 VM 测试和 13 个测试组共 135 项断言全部通过；错误原因和注册状态可观察。

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | 原始文件第 325、340 行 | 裸 context 的 `eval is not supported`；确认需要内部 `JS_AddIntrinsicEval`，不等于注册可见 eval。 |
| 关键处理动作 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | 原始文件第 359、365 行 | 识别 C 参数求值顺序问题，拆分注册调用和断言。 |
| 对应验证结果 | claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833 | 原始文件第 371、387 行 | `135 passed, 0 failed`；Stage 2 完成。 |

---

## 未保留的主要候选

- JSX 转译器的具体语法修复链：虽然轨迹最终有 `48/48` 与 `17/17`，但候选过多且强依赖该转译器的语法树和 fixture 约定；本次只保留其中可独立迁移的 PowerShell 退出码处理经验。
- “分阶段实现编译器/运行时并更新 README”：属于通用项目流程，不能单独构成改变执行决策的 Skill。
- FFI 的具体 Python/Odin 绑定示例：轨迹只确认了 C ABI wrapper 和使用草图，没有完成这些宿主语言的独立运行验证。
- DMLS 的屏幕/API 启动修复：输入包含问题描述和中途运行输出，但清单证据不足以形成完整、可迁移且验证闭环的 Skill。
- FrostCore 的 Git 分支设置：轨迹明确记录为 deferred，只有计划没有完成与验证证据。


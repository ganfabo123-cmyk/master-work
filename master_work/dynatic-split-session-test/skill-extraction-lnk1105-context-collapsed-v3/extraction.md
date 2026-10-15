# Skill 提取结果

本次提取的 Skill 总数：4

- Windows 大对象测试的栈溢出定位与修复 — 来源 Session：`claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e`、`claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd`
- 用临时运行时生成独立、可重复加载的字节码 — 来源 Session：`claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833`
- 为 C/Python/Odin 提供可审计的 C ABI 封装 — 来源 Session：`claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e`
- Windows/Unix 批处理 CLI 的错误隔离与端到端验收 — 来源 Session：`claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6`

# Windows 大对象测试的栈溢出定位与修复

```yaml
---
name: diagnose-windows-large-object-test-stack-overflow
description: >
  Use when a Windows C or C++ test executable exits before printing test output,
  especially with a stack-overflow-like exit code and test fixtures containing
  large tables, arenas, or registries.
  Helps the agent distinguish a fixture copy onto the stack from a library or
  linker failure and repair the fixture without changing the production API.
  Requires source access and a reproducible test build on Windows.
  Do not use when the failure is a normal assertion failure, a link error, or
  a confirmed heap allocation failure.
---
```

## Goal

定位由大对象按值复制到 Windows 默认线程栈导致的启动崩溃，并让测试在保持每次初始化语义的前提下稳定通过。

## Scope

### In scope

- 检查测试辅助函数和局部变量是否按值复制大对象。
- 将共享测试存储改为静态存储并在每次测试前重新初始化，或绑定为引用。
- 重新编译受影响测试并运行完整测试集。

### Out of scope

- 修改生产对象的容量、布局或 ABI。
- 把所有崩溃都归因于栈溢出。
- 只因某个二进制可链接就报告测试修复完成。

## Inputs

- `<test-source>`：必需，包含失败测试和辅助宏/工厂函数的 C/C++ 源文件。
- `<build-command>`：必需，能够在目标 Windows 工具链下重建测试。
- `<test-output>`：必需，包含进程退出码或无输出现象。

## Outputs

- `<fixture-fix>`：测试中使用静态存储或引用绑定后的源代码。
- 成功标准：失败测试能启动并报告通过，完整相关测试集通过。
- 失败标准：仍无输出、仍有栈溢出迹象，或修复后出现状态跨测试污染。

## Preconditions

执行前必须确认：

1. 崩溃发生在测试主体输出之前，且目标平台是 Windows 或具有同等小线程栈限制的环境。
2. 代码中存在大型聚合对象（例如约 MB 级表）和测试工厂/宏。
3. 能够单独重建并运行该测试；若可执行文件被旧进程锁定，先结束对应进程并记录这一事实。

## Procedure

### Step 1: 先隔离启动崩溃

- 单独编译运行失败测试，保留退出码和“无测试输出”的证据。
- 检查测试文件及其辅助函数中大型对象的声明，特别是 `LargeObject x = make_large_object()` 这类初始化。

### Step 2: 消除隐式按值复制

- 若工厂返回静态对象的引用，将局部声明改为 `LargeObject& x = make_large_object()`。
- 若每个测试都需要干净状态，使用静态存储并在工厂中调用该类型的初始化函数；不要依赖构造新局部对象获得隔离。
- 同步检查同类 `AtomTable`、`TermArena`、`VarRegistry` 等辅助对象，避免只修第一个崩溃点。

### Step 3: 验证生命周期和测试隔离

- 重建单测，确认测试主体开始输出并通过。
- 再运行相关完整测试集，确认静态存储在每次测试前被重新初始化，没有把前一个测试的数据带入下一个测试。

## Decision Rules

### When 失败进程在首条测试输出前退出，且大对象被按值初始化

执行：

1. 优先修正值拷贝或局部大对象，而不是先改链接参数或扩大业务代码。
2. 用引用绑定已有静态测试存储，并显式重新初始化。

### When 只有链接失败、断言失败或运行后才崩溃

- 不套用本 Skill；先按链接、断言或运行时状态问题分别定位。

### When 修复后单测通过但完整套件失败

- 检查静态测试存储是否未重置；没有隔离证据时不得报告成功。

## Invariants

执行过程中必须保持：

- 不修改无关生产接口。
- 不把引用改成悬空引用；静态存储必须在整个测试期间有效。
- 每个测试开始前仍有确定的初始状态。
- 只有实际重跑结果支持时才报告修复成功。

## Common Failures

### Failure: 工厂返回引用，但调用处用 `=` 复制

症状：

- Windows 进程在任何 PASS/FAIL 文本前退出；最小链接仍复现。

原因：

- 约 MB 级对象被复制到默认线程栈。

恢复：

1. 将局部变量改为引用绑定工厂返回值。
2. 重新编译并确认测试从首条用例开始输出。

## Verification

完成后必须检查：

- [ ] 单独测试不再在输出前退出。
- [ ] 大对象声明不再产生按值拷贝。
- [ ] 每次测试前初始化函数确实被调用。
- [ ] 完整相关套件通过，且没有新增跨测试污染。
- [ ] 退出码和通过数量来自实际运行结果。

## Examples

### Example 1: Valid use case

输入：

Windows 上的原子表测试，`make_table()` 返回静态 `AtomTable&`，但某个用例写成 `AtomTable t = make_table()`。

处理：

把声明改为 `AtomTable& t = make_table()`；同样检查 `TermArena` 和 `VarRegistry` 的工厂调用，并在工厂中重新初始化静态对象。

预期结果：

轨迹中原子表测试从无输出崩溃恢复为 17/17 通过；另一条轨迹也记录了同类按值复制导致的栈溢出和后续完整套件验证。

## 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e` | 284–287, 319–324 | 测试无输出并以 `-1073741571` 退出；源码注释指出 `AtomTable` 约 1 MB。 |
| 关键处理动作 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e` | 324–326 | 找到 `AtomTable t = make_table()` 的按值复制并改为引用。 |
| 对应验证结果 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e` | 327–334 | 17/17 原子表测试通过，随后报告 10/10 套件、144/144 通过。 |
| 独立交叉证据 | `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd` | 1200–1218 | 同样识别静态大对象被 `=` 复制，并继续检查测试隔离；该切片末尾仍有未完成失败，不能单独作为成功证据。 |

# 用临时运行时生成独立、可重复加载的字节码

```yaml
---
name: produce-independent-runtime-bytecode
description: >
  Use when a JavaScript engine must compile source once and execute the result
  in one or more later runtimes without retaining a compiler runtime.
  Helps create an owning bytecode blob and preserve loaded function handles
  across repeated evaluation.
  Requires a compile-only API, serialization/deserialization APIs, and explicit
  runtime ownership.
  Do not use when the requirement is only to evaluate source immediately in one
  runtime or when the engine provides no supported bytecode serialization.
---
```

## Goal

把源码编译成与临时编译运行时无关的自有字节码，并支持在多个运行时加载、重复执行和安全释放。

## Scope

### In scope

- 在 scratch runtime 中编译并序列化。
- 将序列化结果复制到独立拥有的内存块。
- 在目标 runtime 中反序列化、保存函数句柄并在执行时复制句柄。
- 覆盖释放编译运行时后的独立性和多 runtime 执行。

### Out of scope

- 改造 VM 的预测、缓存或并发调度。
- 让字节码 blob 依赖 scratch runtime 的内部内存。
- 仅凭构建成功推断执行语义正确。

## Inputs

- `<source>`：必需，待编译的 JavaScript 文本。
- `<compile-options>`：必需，至少包含 compile-only 和去源信息的序列化选项。
- `<target-runtime>`：必需，支持反序列化和函数执行的 runtime。

## Outputs

- `<bytecode>`：拥有独立内存的字节码对象，含长度和释放函数。
- `<loaded-function>`：目标 runtime 中可重复执行的函数句柄。
- 成功标准：scratch runtime 销毁后 blob 仍可加载，并在多个 runtime/多次执行中得到预期结果。
- 失败标准：编译或加载失败有明确错误；blob 释放后仍被使用必须被阻止。

## Preconditions

执行前必须确认：

1. 编译器支持把源码编译为可序列化对象。
2. 序列化 API 的返回缓冲区可被复制，且目标 runtime 有对应反序列化 API。
3. 函数值的引用计数规则已明确，能够在销毁 runtime 时释放。

## Procedure

### Step 1: 在 scratch runtime 中编译

- 创建临时 runtime/context。
- 使用 compile-only 选项编译源码，再以 bytecode/strip-source 选项序列化。
- 将序列化缓冲区复制到由 Skill 管理的系统分配内存中。
- 先销毁 scratch runtime，再把独立 blob 返回给调用者。

### Step 2: 在目标 runtime 中加载

- 使用反序列化 API 读取 blob。
- 将得到的函数值存入 runtime 的 owning 字段，并在替换旧值前按 API 规则释放旧引用。

### Step 3: 重复执行并验证所有权

- 执行前复制或增加函数句柄引用，再调用执行 API，确保保存的 owning 引用仍然存在。
- 用多个目标 runtime 和多次执行测试 blob 独立性、加载替换、未加载执行错误和 NULL 参数行为。

## Decision Rules

### When 编译结果将在 scratch runtime 之外使用

执行：

1. 必须复制序列化 blob，不能返回 scratch runtime 内部指针。
2. 只有在 scratch runtime 销毁后仍能加载，才能报告独立性成立。

### When 需要重复执行同一已加载函数

- 保存 owning 函数引用，并在执行时按 VM 引用规则复制临时句柄；不要把一次执行消费掉保存的引用。

### When 编译、序列化或加载缺少对应 API

- 停止并报告缺失能力，不用源码字符串或未经验证的内部指针替代。

## Invariants

执行过程中必须保持：

- blob 的生命周期独立于 scratch runtime。
- 每个 owning VM 值只释放一次。
- 目标 runtime 不读取已销毁 scratch runtime 的对象。
- 多 runtime 测试之间没有共享可变 VM 状态。

## Common Failures

### Failure: 返回 scratch runtime 的序列化缓冲区

症状：

- scratch runtime 销毁后加载或执行失败，或出现悬空数据。

原因：

- 返回值没有复制到独立拥有的内存。

恢复：

1. 在销毁 scratch runtime 前复制完整 blob 和长度。
2. 销毁后再执行加载测试。

### Failure: 保存的函数句柄被第一次执行消费

症状：

- 首次执行通过，第二次执行失败或引用失效。

原因：

- 执行前未复制保存的函数引用。

恢复：

1. 在执行入口复制 owning 句柄。
2. 重复执行并检查加载值仍然有效。

## Verification

完成后必须检查：

- [ ] 空源码/语法错误能返回失败而不泄漏。
- [ ] blob 长度和释放路径可观察且正确。
- [ ] scratch runtime 销毁后仍可加载。
- [ ] 同一 blob 可在多个 runtime 和多次执行中使用。
- [ ] 未加载执行、NULL 参数和加载替换都有明确结果。

## Examples

### Example 1: Valid use case

输入：

一个带 `frost_bytecode` 所有权的 C API，要求 parse-once-run-many。

处理：

使用 scratch runtime 编译、`COMPILE_ONLY` 序列化并复制 blob；目标 runtime 反序列化后保存 `loaded_fn`，执行前用 `JS_DupValue` 复制句柄。

预期结果：

轨迹报告 Stage 1、Stage 2、Stage 3 分别全部通过，字节码套件为 101/101，并明确验证了 5 个 runtime、blob 独立性、重复执行和未加载错误。

## 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 563–581 | 新增 bytecode 测试，目标是 parse-once-run-many 和跨 runtime 使用。 |
| 关键处理动作 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 581 | 明确记录 scratch runtime、复制 blob、反序列化、保存 `loaded_fn` 和 `JS_DupValue`。 |
| 对应验证结果 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 580–581 | 三套件通过：Stage 1 全部通过、Stage 2 为 135/135、Stage 3 为 101/101。 |

# 为 C/Python/Odin 提供可审计的 C ABI 封装

```yaml
---
name: design-opaque-c-abi-wrapper
description: >
  Use when a C++ engine must be consumed from C or foreign-function interfaces
  such as Python ctypes/cffi or Odin.
  Helps define a stable C-linkage surface with opaque handles, explicit
  lifecycle, callback-based result enumeration, and documented error codes.
  Requires control over the native implementation and a cross-language ABI
  boundary.
  Do not use when callers are all within the same C++ ABI or when no stable
  ownership/lifetime contract can be specified.
---
```

## Goal

将 C++ 内部类型隐藏在 opaque handle 后面，提供可从 C 及其他 FFI 调用的稳定生命周期、查询、回调和错误契约。

## Scope

### In scope

- 纯 C 头文件和 `extern "C"` 实现包装。
- `create/load/query/destroy` 生命周期。
- 回调枚举结果和仅在回调期间有效的 solution handle。
- 明确错误码、NULL 参数行为、线程安全和版本函数。

### Out of scope

- 暴露 C++ STL、模板或内部引擎头文件。
- 承诺多个线程共享同一引擎实例，除非已有独立证据。
- 把 FFI API 当作领域业务协议。

## Inputs

- `<native-engine>`：必需，已有 C++ 生命周期和查询入口。
- `<abi-consumers>`：必需，目标语言及其可用 C ABI 调用能力。
- `<ownership-rules>`：必需，句柄、字符串和回调数据的有效期。

## Outputs

- `<public-header>`：只含 C 可识别类型、枚举、opaque typedef 和函数声明。
- `<wrapper-implementation>`：隐藏 C++ 类型并转译错误和结果。
- 成功标准：目标 ABI 可编译链接，查询结果可通过回调消费，生命周期和 NULL 行为通过测试。
- 失败标准：头文件泄露 C++ 类型、回调越过有效期使用数据，或错误返回无法区分。

## Preconditions

执行前必须确认：

1. C 编译器能独立解析公共头文件。
2. 引擎可由显式 create/destroy 管理，且不依赖隐藏全局状态。
3. 回调中返回的数据有效期、线程限制和错误码可写入契约。

## Procedure

### Step 1: 定义纯 C 表面

- 用不透明 `struct` typedef 隐藏引擎和 solution 类型。
- 用固定宽度整数、枚举、函数指针和 `const char*` 等 ABI 稳定类型表达接口。
- 在头文件中记录生命周期、错误码、回调返回值和指针有效期。

### Step 2: 实现包装层

- `create` 分配并初始化引擎，`destroy` 对 NULL 安全并释放资源。
- `load` 和 `query` 只接收 NUL 结尾字符串，返回成功计数或负错误码。
- 在 native solver 回调中构造短生命周期 solution snapshot，再调用用户回调；不要把内部 C++ 对象直接暴露出去。

### Step 3: 验证 ABI 和生命周期

- 用 C/目标 FFI 方式编译公共头文件和共享库。
- 测试加载、查询、提前停止回调、结果访问、错误码、NULL 参数和多实例隔离。
- 对照完整原生测试，确认包装层没有改变引擎逻辑。

## Decision Rules

### When 调用方跨越 C++ ABI

执行：

1. 只暴露 C linkage 和 opaque handles。
2. 对字符串和回调结果写明有效期，避免调用方保存短生命周期指针。

### When 调用方需要停止结果枚举

- 将回调返回值映射到明确的 `NEXT/STOP` 枚举，并让 query 返回已产生的结果数。

### When 无法确定对象或字符串的所有权

- 停止扩展接口；先补齐所有权和有效期契约，不用隐含约定替代。

## Invariants

执行过程中必须保持：

- 公共头文件不包含 C++ 类型或实现头。
- solution handle 只在回调期间有效。
- 一个引擎实例由一个 create/destroy 对管理。
- 每个错误路径返回可区分的错误码，并保持内部资源可释放。

## Common Failures

### Failure: 把 C++ 类型直接放入公共头

症状：

- C 或 FFI 编译器无法解析头文件，或 ABI 随编译器变化。

原因：

- 公共表面没有保持纯 C。

恢复：

1. 用 opaque typedef 替换实现类型。
2. 将转换和快照逻辑移入 C-linkage 实现文件。

### Failure: 回调返回内部临时数据

症状：

- 回调返回后调用方读取名称/值出现悬空或不一致。

原因：

- 有效期没有限制在回调内，或没有创建 snapshot。

恢复：

1. 在回调前构造 solution snapshot。
2. 在头文件和测试中验证回调外访问被视为无效。

## Verification

完成后必须检查：

- [ ] C 编译器可单独包含公共头文件。
- [ ] create/load/query/destroy 顺序可运行，NULL destroy 安全。
- [ ] 回调可枚举结果并提前停止。
- [ ] 错误码、变量访问器和字符串有效期与文档一致。
- [ ] 原生完整测试仍通过，FFI 新增测试也通过。

## Examples

### Example 1: Valid use case

输入：

一个 C++ 逻辑引擎，需要给 C、Python ctypes/cffi 和 Odin 调用。

处理：

提供纯 C `epilog_ffi.h`，声明 opaque `EpilogEngine`/`EpilogSolution`、错误码和回调；实现文件内部包含 C++ 引擎头，query 回调中生成 solution snapshot。

预期结果：

轨迹报告 v0.2.0 完成，包含 FFI 头和实现、统计/索引/记忆测试，并最终通过 10/10 套件、144/144 测试。

## 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e` | 2, 124–131 | 用户明确要求 extern C translation layer，工具结果展示纯 C 头和 C++ wrapper。 |
| 关键处理动作 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e` | 124–131 | 头文件定义 opaque handles、回调、错误码、生命周期和结果访问器。 |
| 对应验证结果 | `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e` | 328–334, 352 | 原子表修复后完整测试为 10/10 套件、144/144；最终摘要列出 FFI 文件和跨语言示例。 |

# Windows/Unix 批处理 CLI 的错误隔离与端到端验收

```yaml
---
name: validate-cross-platform-batch-cli-error-isolation
description: >
  Use when a source-processing CLI must handle a directory or explicit file
  list, continue processing independent files, and return a nonzero status for
  invalid input or per-file errors on both Windows and Unix-like systems.
  Helps define platform-specific build/test dispatch and observable batch
  acceptance checks.
  Requires a CLI with single-file and batch entry points and a fixture runner.
  Do not use for a single-file-only tool or when the requirement is merely a
  unit test of one parser function.
---
```

## Goal

验证批处理 CLI 在不同 shell/平台下能正确构建、处理有效文件、隔离坏文件、复制允许的旁路文件，并对错误输入返回非零状态。

## Scope

### In scope

- Windows PowerShell 与 Unix shell 的构建/运行分派。
- 目录批处理、显式文件列表、线程数和 passthrough 选项。
- 单个坏文件不阻塞其他好文件，错误仍影响最终退出码。
- 端到端 fixture、输出文件和退出码检查。

### Out of scope

- 未被轨迹验证的性能、增量 watch 语义或部署系统。
- 只检查日志而不检查文件内容和退出码。
- 把一个平台的 shell 语法直接当作另一平台语法。

## Inputs

- `<source-tree>`：必需，含有效、无效和旁路文件的 fixture 目录。
- `<cli-options>`：必需，包含 batch、no-copy、pragma/runtime 和线程选项。
- `<platform-build>`：必需，Windows 和 Unix 对应的构建入口。

## Outputs

- `<output-tree>`：按输入相对路径生成的转换或复制结果。
- `<test-report>`：每项 fixture 的内容、退出码和通过/失败计数。
- 成功标准：完整 fixture 与批处理套件通过，坏输入返回非零且好文件仍产出。
- 失败标准：平台语法不兼容、错误文件中断全批次，或退出码与错误状态不一致。

## Preconditions

执行前必须确认：

1. CLI 支持单文件和目录/显式文件列表路径。
2. runner 能独立比较输出内容，并能捕获原生程序的 stderr 和退出码。
3. Windows runner 不依赖 PowerShell 7 专有语法，Unix 路径使用对应 shell 语法。

## Procedure

### Step 1: 建立平台分派

- 在 Makefile 中根据平台把 `test` 委托给 PowerShell runner 或 Unix shell loop。
- 使用平台对应的目录创建、清理、空设备和退出码语法。
- 在 Windows 上对原生程序 stderr 使用 try/catch 或等效捕获，避免 runner 自身吞掉目标退出码。

### Step 2: 构造覆盖 fixture

- 放入多个 JSX/源文件、旁路 `.js` 文件、坏文件和不存在路径。
- 分别检查默认批处理、`--no-copy`、pragma/runtime、verbose、线程数和显式文件列表。
- 对坏文件验证同批次好文件仍被处理。

### Step 3: 检查内容和最终状态

- 比较每个预期输出文件的内容，不只检查文件存在。
- 检查旁路复制是否按选项启用/禁用。
- 检查坏文件、不存在目录或文件的最终进程退出码为非零。
- 汇总 fixture 和 batch 两套结果后再报告完成。

## Decision Rules

### When 批次内一个输入失败但其他输入独立

执行：

1. 记录该文件错误并继续处理其他文件。
2. 最终 `failed > 0` 时返回非零，即使好文件已生成。

### When 运行在 Windows PowerShell 5.1

- 避免 `? :` 等 PowerShell 7 语法，并对 native stderr 做显式异常处理。

### When 输入路径不存在

- 将其视为错误并返回非零，不要静默当作“没有待处理文件”而返回成功。

## Invariants

执行过程中必须保持：

- 错误文件不能阻止独立好文件输出。
- 输出路径和输入相对层级可追踪。
- runner 的平台适配不能改变 CLI 的业务退出码。
- 结果比较必须基于实际文件内容。

## Common Failures

### Failure: Windows runner 把 native stderr 当作自身异常

症状：

- 预期错误测试被标记为 runner 失败，无法读取真实退出码。

原因：

- PowerShell 的 `2>&1` 将 native 错误包装成 `NativeCommandError`。

恢复：

1. 对该调用使用 try/catch 或等效隔离。
2. 单独保存 stderr 和 `$LASTEXITCODE`，再比较预期退出码。

### Failure: Makefile 混用 shell 语法

症状：

- Windows `cmd.exe` 无法执行 `mkdir -p`、bash 变量或子 shell。

原因：

- Makefile 默认 shell 与脚本语法不一致。

恢复：

1. 做显式 OS 分派。
2. Windows 直接调用 PowerShell runner，Unix 使用 bash 逻辑。

## Verification

完成后必须检查：

- [ ] 单文件和目录批处理都能构建运行。
- [ ] 有效文件内容与预期一致。
- [ ] `.js` 旁路复制和 `--no-copy` 行为分别通过。
- [ ] pragma/runtime、verbose、线程数和显式文件列表通过。
- [ ] 坏文件和不存在路径返回非零，同时独立好文件仍成功。
- [ ] Windows 与 Unix 分派入口都能被实际调用。

## Examples

### Example 1: Valid use case

输入：

一个 JSX 转换 CLI，fixture 含 3 个 JSX 文件、1 个旁路 JS 文件、坏文件和不存在目录。

处理：

使用平台分派的 Makefile/PowerShell runner，分别验证默认批处理、`--no-copy`、pragma、runtime、verbose、单线程和显式文件列表；坏文件测试检查好文件仍输出且批次退出非零。

预期结果：

轨迹中的 Stage 3 runner 报告批处理测试 17/17，随后完整 fixture 与 batch 合计 48/48 + 17/17。

## 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | 409–429, 760–769 | 发现 Makefile shell 不兼容、PowerShell stderr 异常和错误路径退出码问题。 |
| 关键处理动作 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | 422–429, 760–769, 1422 | 按 OS 分派 Makefile，修正 runner 错误捕获，并将不存在路径视为错误。 |
| 对应验证结果 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | 1427–1433 | Stage 3 报告 17 项通过；随后报告 48/48 fixture + 17/17 batch。 |

## 未保留的主要候选

- Odin 长驻 HTTP 线程的 `thread.destroy`/`self_cleanup` 修复：轨迹末尾仍被旧进程锁定，未出现修复后的最终构建或运行验证，因此不满足“关键验证已完成”。
- FrostCore bare runtime 的中途诊断：切片包含 126 passed/9 failed 等中间状态，虽然之后有完整通过摘要，但具体失败修复链的部分证据被切片压缩，未把它扩展成独立 Skill，避免把局部 QuickJS 细节泛化。
- JSX lexer/parser 的大量单点修复：轨迹确实最终通过，但每个语法特例的触发条件和可迁移边界不同；合并成一个通用“实现 JSX” Skill 会超出宁缺毋滥原则。
- 仅更新 README、PLAN 或 CHANGELOG 的操作：属于文档维护流程，没有形成改变执行决策的独立可复用经验。

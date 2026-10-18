# Skill 提取结果

本次提取的 Skill 总数：3

| 标题 | 来源 Session ID |
| --- | --- |
| 在跨平台构建与测试链路中定位环境、脚本和进程状态问题 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6`; `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa` |
| 用最小 Token 证据和增量 fixture 调试词法/语法边界 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` |
| 为编译结果建立可独立加载的序列化边界并验证 parse-once-run-many | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` |

# 在跨平台构建与测试链路中定位环境、脚本和进程状态问题

```yaml
---
name: cross-platform-build-test-triage
description: >
  Use when a project builds or tests through different shells or operating systems and
  the failure may come from IDE diagnostics, shell syntax, PowerShell version behavior,
  missing runtime DLLs, or locked binaries.
  Helps the agent separate source defects from execution-environment defects and reach
  a reproducible build/test result.
  Requires the real target build command, its shell/runtime, and an observable exit code.
  Do not use when the task only asks for a design review without running the build/test path.
---
```

## Goal

定位跨平台构建或测试失败的实际原因，修复与目标平台相关的脚本/环境问题，并用同一入口重新得到可观察的构建与测试结果。

## Scope

### In scope

- 区分 IDE include/path 诊断与真实编译错误。
- 检查目标 shell 的语法、重定向和退出码语义。
- 检查运行时依赖 DLL、文件锁和已运行进程。
- 在脚本修复后重新构建并运行完整测试入口。

### Out of scope

- 没有执行结果支持的部署或发布结论。
- 将未验证的环境猜测写成根因。
- 与当前失败无关的构建系统重构。

## Inputs

- `<build-command>`：项目实际构建命令，必需。
- `<test-command>`：项目实际测试命令，必需。
- `<target-shell-and-platform>`：目标 shell、PowerShell 版本或操作系统，必需。
- `<artifacts-and-processes>`：失败时涉及的二进制、DLL 和运行中进程，按需提供。

## Outputs

- `<fixed-build-or-test-path>`：兼容目标平台的构建/测试脚本或必要环境修复。
- 成功标准：构建完成，测试入口返回成功，并输出与目标对应的通过计数。
- 失败标准：仍有编译错误、运行时依赖缺失、文件锁未解除，或测试退出码与预期不符。

## Preconditions

执行前必须确认：

1. 已有可复现的构建和测试入口。
2. 能在目标 shell 中观察 stdout、stderr 和进程退出码。
3. 有权检查并结束阻塞目标二进制的本地进程；没有该权限时停止并报告。

## Procedure

### Step 1: 在目标入口复现并分类

- 直接运行目标构建/测试命令，记录完整错误、退出码和执行 shell。
- 若只出现 IDE include 错误，使用实际编译器重新构建确认；轨迹中缺少 `-Iinclude` 的 IDE 诊断被实际构建结果证明为 false positive（39082932，事件 85、96）。

### Step 2: 检查脚本与 shell 语义

- 对 PowerShell 脚本先用 PowerShell 解析器检查语法；轨迹中用 `Parser.ParseFile` 验证两个脚本均为 `OK`（39082932，事件 401–404）。
- 检查目标版本不支持的语法、Unicode 字符和重定向行为。轨迹实际修复了 Windows PowerShell 5.1 不支持的 `? :`，以及导致字符串解析问题的 em dash（39082932，事件 381、386）。
- 检查 Makefile 使用的 shell；Windows `cmd.exe` 不执行 bash 的 `$$`、`$()` 和 `mkdir -p`，应改为目标 shell 可执行的分派方式（39082932，事件 409–429）。

### Step 3: 排除锁和运行时依赖

- 若链接器报告无法覆盖 exe，先确认目标进程是否仍在运行并解除文件锁，再重建。DMLS 轨迹在 `dmls.exe` 被锁时失败，结束进程并删除锁定产物后构建成功（a20a4070，事件 454–465）。
- 若程序以 DLL 缺失退出，检查二进制依赖和构建输出目录；不要把静默失败的复制命令当作成功。DMLS 轨迹定位到 `raylib.dll` 未被复制，并改为从已定位的 `odin.exe` 路径派生依赖路径（a20a4070，事件 405–434）。

### Step 4: 重跑同一验证入口

- 修复后先重新编译，再运行完整 fixture/test runner，不只运行触发失败的单个案例。
- 记录通过/失败计数和退出码；Yggdrasil 最终得到 32/32，Stage 3 得到 48/48 fixture + 17/17 batch（39082932，事件 789–791；39082932 segment-04，事件 1426–1449）。

## Decision Rules

### When IDE diagnostics fail but the compiler succeeds

执行：

1. 保留真实编译器输出作为依据。
2. 将 IDE include 配置作为开发体验问题单独处理，不把它当作源码根因。

### When a script parses on one shell but not the target shell

执行：

1. 以目标 shell 的解析器和版本为准修复语法。
2. 重跑脚本解析检查，再进入构建和测试。

### When a linker reports a locked output or runtime reports a missing DLL

- 先检查运行中进程、文件是否存在和依赖搜索路径；修复后重新执行完整入口。
- 不以“脚本命令已执行”代替依赖复制或链接成功的证据。

### When the target shell or exit-code behavior is unknown

- 不猜测；报告 shell、版本或退出码证据缺口并停止跨平台结论。

## Invariants

执行过程中必须保持：

- 不把 IDE 假阳性当成源码错误。
- 不把脚本解析通过当成构建或运行通过。
- 不把单个 fixture 通过当成完整测试通过。
- 记录实际 shell、退出码和通过计数。

## Common Failures

### Failure: Windows PowerShell 5.1 rejects a script

症状：

- `ParserError` 指向 ternary `? :` 或包含 em dash 的字符串。

原因：

- 轨迹明确显示这些语法/字符在目标 PowerShell 版本下不可用。

恢复：

1. 用兼容的 `if/else` 替换 ternary，并改写有问题的字符串。
2. 用 PowerShell parser 检查脚本，再运行测试（39082932，事件 381–404）。

### Failure: linker cannot close executable

症状：

- `LNK1105` 或等价的文件锁错误。

原因：

- 轨迹证明目标 exe 仍在运行。

恢复：

1. 结束占用进程并重新构建。
2. 观察链接成功和后续运行结果（a20a4070，事件 454–466）。

### Failure: runtime DLL is missing

症状：

- 程序以 `0xC0000135` 退出。

原因：

- 轨迹中 `raylib.dll` 不在输出目录，复制命令因环境变量未设置而静默失败。

恢复：

1. 从实际工具路径定位 DLL，并让构建脚本显式派生和复制该路径。
2. 重新构建并运行，确认依赖初始化成功（a20a4070，事件 405–466）。

## Verification

完成后必须检查：

- [ ] 目标 shell 能解析构建和测试脚本。
- [ ] 编译器返回成功且没有目标相关的未解决错误。
- [ ] 链接输出不再被进程锁定。
- [ ] 运行时依赖位于实际搜索路径，程序能启动。
- [ ] 完整测试入口报告通过计数和成功退出码；轨迹支持 32/32、48/48 + 17/17 和 135/135 的对应结果。
- [ ] 结果可追溯到目标 shell、命令和事件证据。

## Examples

### Example 1: Valid use case

输入：

Windows 项目通过 Makefile 和 PowerShell runner 构建，runner 报 PowerShell 解析错误，随后 `make test` 在 Windows shell 中行为异常。

处理：

用目标 PowerShell parser 定位 5.1 不支持的语法，修复脚本；把 Makefile 的 bash 语法改为 Windows 可执行的分派，同时保留 Unix 分支。

预期结果：

轨迹实际得到脚本 `OK`、clean build，并由 `make test` 报告 32/32 passing（39082932，事件 381–429、401–404、789–791）。

# 用最小 Token 证据和增量 fixture 调试词法/语法边界

```yaml
---
name: token-trace-incremental-parser-debugging
description: >
  Use when a lexer/parser or source-to-source compiler fails on a syntax boundary and
  the visible parse error may be downstream of an incorrect token stream.
  Helps isolate mode, delimiter, precedence, whitespace, or expression-context bugs.
  Requires a small reproducible fixture, a token dump or equivalent intermediate view,
  and a runnable regression suite.
  Do not use when the failure is solely a runtime or linker failure.
---
```

## Goal

通过最小输入、Token 流和增量回归 fixture 找到词法/语法边界的真实错误，并使完整回归套件恢复通过。

## Scope

### In scope

- JSX/类似嵌套语法的 mode、delimiter、expression-context 和 whitespace 边界。
- 用 token dump 区分 lexer 错误与 parser 错误。
- 每次只处理当前失败类别并重跑累计 fixture。

### Out of scope

- 没有中间表示证据时臆测 parser 根因。
- 只更新 expected 输出来掩盖无效语义。
- 未经验证的完整语言规范支持声明。

## Inputs

- `<minimal-fixture>`：触发失败的最小源文件，必需。
- `<token-dump-or-intermediate-output>`：包含 token kind、顺序或上下文的诊断输出，必需。
- `<regression-runner>`：已有正向和错误案例的 runner，必需。

## Outputs

- `<lexer-parser-fix>`：针对已证实边界的最小实现修复。
- `<regression-result>`：累计 fixture 的通过结果。
- 成功标准：Token 流符合预期，目标 fixture 通过，完整 suite 通过。
- 失败标准：Token 仍错误、输入语义未验证，或完整 suite 有残留失败。

## Preconditions

执行前必须确认：

1. 失败可以由单个或少量 fixture 重现。
2. 能输出 lexer 的实际 token 流。
3. 有完整回归入口和错误 fixture 的退出码期望。

## Procedure

### Step 1: 先跑最小 fixture 并保存失败形态

- 记录失败输入、报错 token、目标输出和当前通过数。
- 不直接修改 expected 文件；先判断实际输出是否语义正确。

### Step 2: 打印并核对 Token 流

- 对复合 delimiter、嵌套表达式和 mode 切换输出 token kind 与顺序。
- 轨迹发现 `/>` 被拆成 `Slash` + `Greater`，并通过 token dump 证明 `JSXTag` mode 没被压入（39082932，事件 436–482）。
- 发现 `}` 后没有回到 `JSXTag`，用 brace-depth 记录和 token dump 修复为 `}` → `JSXGreater` → 文本/closing token（39082932，事件 600–615）。

### Step 3: 修复最小状态边界

- 让 lexer 在自身 tokenization 过程中管理 mode stack；对 opening/closing tag 使用明确状态，不用含义歧义的 `lastKind_` 推断（39082932，事件 444–458）。
- 若 Token 流正确而 parser 仍失败，只修改对应 parse branch；例如在 expression context 中接受 `JSXLess`，在 ternary 后把 `QuestionMark` 纳入 JSX 允许集合（39082932，事件 639–662）。

### Step 4: 逐类增加 fixture 并回归

- 先运行当前最小 fixture，再运行累计 suite；每次记录通过数和剩余失败。
- 对 whitespace、表达式容器、destructuring、export、async、错误退出码分别增加或修正 fixture；轨迹从 8、13、20、25、29、31/32 逐步到 32/32（39082932，事件 620–791）。
- PowerShell 错误退出测试要单独验证真实进程退出码，避免 stderr 重定向产生 `NativeCommandError` 并污染 `$LASTEXITCODE`（39082932，事件 757–786）。

## Decision Rules

### When the token kind or order is wrong

执行：

1. 修复 lexer mode、delimiter 或 brace-depth 状态。
2. 用同一 fixture 重打印 token 流后再触碰 parser。

### When the token stream is correct but parsing fails

执行：

1. 检查对应 parse branch 是否在当前 expression/context 接受该 token。
2. 只修改该 branch，并运行累计回归。

### When output differs only in line endings or formatting

- 先确认语义输出正确；修复 runner 的换行归一化，或让 expected 明确反映已确认的格式。
- 不把格式差异直接当成 lexer/parser 语义错误（39082932，事件 579、721–731）。

### When no token dump or reproducible fixture exists

- 不猜测；报告证据缺口并停止该 Skill。

## Invariants

执行过程中必须保持：

- token 诊断先于 parser 结论。
- 每次修复只针对已证实的状态边界。
- expected 更新必须基于已确认的合法输出。
- 完整回归和错误退出码都必须验证。

## Common Failures

### Failure: compound JSX delimiter is split

症状：

- self-closing input receives separate `/` and `>` tokens and parser asks for another attribute.

原因：

- 轨迹证明 lexer mode stack 没在 tokenization 阶段压入 `JSXTag`。

恢复：

1. 让 lexer 自己在发出 JSX opening token 后切换 mode，并用 closing-tag flag 区分 `>`。
2. 重新 dump tokens，确认产生单一 `JSXSlashGreater`（39082932，事件 439–495）。

### Failure: expression container does not return to tag mode

症状：

- `}` 后的 tag `>` 被错误处理，或 JSX expression 后续 token 错位。

原因：

- brace-depth 返回条件不正确。

恢复：

1. 记录进入 JSX expression 时的 brace depth，在回到该 depth 时弹出状态。
2. 用 token 序列验证闭合顺序，再跑 suite（39082932，事件 600–615）。

### Failure: expected error test reports `-1`

症状：

- 程序实际返回 1，但 PowerShell runner 报 `-1`。

原因：

- PowerShell 5.1 将 native stderr 重定向包装为 `ErrorRecord`，catch 改写了 `$LASTEXITCODE`。

恢复：

1. 对 error-exit 测试避免该重定向路径，直接保留真实进程退出码。
2. 重新运行错误 fixture 和完整 suite（39082932，事件 780–791）。

## Verification

完成后必须检查：

- [ ] 最小 fixture 的 token kind 和顺序符合预期。
- [ ] 目标 parser 失败消失，且没有新增 token 错位。
- [ ] 语义相关的正向 fixture 通过。
- [ ] 错误 fixture 返回预期退出码。
- [ ] 完整 suite 通过；轨迹最终报告 32/32。
- [ ] 每个修复可追溯到 token dump、fixture 和回归结果。

## Examples

### Example 1: Valid use case

输入：

`<input disabled />`、属性表达式、`&&`/ternary 中嵌套 JSX，以及未闭合 tag 的错误 fixture。

处理：

先打印 token 流，修复 lexer mode stack 和 brace-depth，再补 parser expression branch；修复 runner 的换行和 native error-exit 处理。

预期结果：

token 流正确，逐步通过 fixture，最终 `make test` 报 32/32 passing（39082932，事件 468–495、600–615、639–662、780–791）。

# 为编译结果建立可独立加载的序列化边界并验证 parse-once-run-many

```yaml
---
name: serialized-compile-runtime-boundary
description: >
  Use when a C or C++ runtime needs a compile-only API whose result can be loaded and
  executed by later independent runtime instances.
  Helps define ownership, serialization, loading, destruction, and repeated execution
  boundaries around an existing compiler/runtime.
  Requires an existing compile-only API, serialization/deserialization primitives, and
  tests that can create multiple runtime instances.
  Do not use when the task requires rewriting the underlying engine's parser or atom
  table and the wrapper boundary cannot provide the requested semantics.
---
```

## Goal

把编译结果封装为独立、可销毁、可跨 runtime 加载的字节码对象，并验证一次解析、多次加载执行的生命周期行为。

## Scope

### In scope

- compile-only parse、序列化 blob、独立 runtime load、执行和销毁。
- scratch runtime 与执行 runtime 的职责分离。
- 多 runtime、替换 load、空参数和执行前 load 错误测试。

### Out of scope

- 轨迹明确未支持的底层 quickjs-ng 编译单元拆分或全局 atom table 重写。
- 没有测试证据的性能或线程安全承诺。

## Inputs

- `<source>`：可由现有编译器 compile-only 处理的源文本，必需。
- `<serialize-and-load-primitives>`：已有的序列化/反序列化 API，必需。
- `<runtime-factory>`：可创建多个独立 runtime 的 API，必需。

## Outputs

- `<bytecode-api>`：parse、data/size、runtime_load、destroy 等边界 API。
- `<validation-suite>`：生命周期、错误和多 runtime 测试。
- 成功标准：blob 在 scratch runtime 销毁后仍可加载，多个 runtime 可执行且无泄漏报告。
- 失败标准：序列化对象依赖已销毁 runtime、load/execute 生命周期错误或关键测试失败。

## Preconditions

执行前必须确认：

1. 底层运行时支持 compile-only 评估和对象序列化。
2. compile-only 阶段可以创建 scratch runtime 并注册编译所需的基础 intrinsic。
3. 可以观察构建、测试、分配/释放或等价资源结果。

## Procedure

### Step 1: 先确认底层边界

- 检查 `JS_EVAL_FLAG_COMPILE_ONLY`、`JS_WriteObject`、`JS_ReadObject` 和 `JS_EvalFunction` 的实际可用 flags/API。
- 轨迹把 `JS_Eval → compile → JS_WriteObject → JS_ReadObject → JS_EvalFunction` 确定为现有可行管线，并明确“编译单元拆分”需要改写底层引擎，暂不伪装成 wrapper 能力（6a7964ed，事件 444–459）。

### Step 2: 分离 parse 与 execute 生命周期

- parse API 创建内部 scratch runtime，启用 compile-only 所需的 `std_core`/基础对象，但不执行用户代码（6a7964ed，事件 478–484）。
- 将序列化 blob 的所有权从 scratch runtime 中分离；runtime load 只消费 blob 并生成可执行对象。
- 为 bytecode 对象提供 size/data 访问和显式 destroy，避免调用方依赖内部 runtime 指针。

### Step 3: 接入构建并逐层测试

- 将 parse/vm 源文件加入 Makefile，先做 clean build。
- 先保留既有 smoke/subsystem 测试作为回归，再加入 bytecode boundary suite。
- 若链接被正在运行的旧测试二进制锁定，结束进程后重建再判断源码结果；该环境问题在轨迹中被单独识别（6a7964ed，事件 568–580）。

### Step 4: 验证独立性和重复执行

- 测试 parse success/failure、size、NULL destroy、load/eval、eval-before-load 错误、load replacement。
- 创建 5 个 runtime 验证同一 blob 的 parse-once-run-many，并在 scratch runtime 销毁后继续加载执行。
- 记录所有 suite 的实际通过数和资源结果；轨迹最终报告 smoke 全通过、subsystem 135/135、bytecode 101/101（6a7964ed，事件 580–581）。

## Decision Rules

### When compile-only plus serialization already exists

执行：

1. 以序列化格式作为 portable IR，建立 wrapper API。
2. 测试 scratch runtime 销毁后的 blob 独立性。

### When the requested boundary requires changing global engine internals

- 明确记录为 out of scope；轨迹判断 atom table 解耦需要改写 quickjs-ng，不能由简单 wrapper 证明（6a7964ed，事件 444）。

### When a test binary is locked

- 先解除运行进程造成的锁，再重新构建；不能把链接锁错误归因于新 API。

### When ownership or load lifetime is unclear

- 不报告 parse-once-run-many 成功；补充 blob data/size/destroy 和 scratch/runtime 生命周期证据后再继续。

## Invariants

执行过程中必须保持：

- compile-only 不执行用户代码。
- serialized blob 不依赖已销毁的 scratch runtime。
- load、execute、destroy 的所有权边界显式可测试。
- 既有 smoke/subsystem 回归不能被新 API 替代。
- 不把 wrapper 证据扩大为底层引擎已完成重构。

## Common Failures

### Failure: linking new test binary fails with file lock

症状：

- linker 报不能关闭已有测试 exe。

原因：

- 轨迹确认旧测试进程仍在运行。

恢复：

1. 结束旧进程并重新构建。
2. 重新执行全部三组测试（6a7964ed，事件 575–580）。

### Failure: proposed API assumes full compilation-unit split

症状：

- 需求声称要 parser/runtime atom table 完全解耦，但底层只提供对象序列化。

原因：

- 轨迹审计明确指出该能力需要重写 quickjs-ng，wrapper 不能单独提供。

恢复：

1. 将当前阶段收敛到 parse/serialize/load/execute 边界。
2. 将底层重写列为未来扩展，不把它写入当前成功标准。

## Verification

完成后必须检查：

- [ ] compile-only 返回有效 bytecode，且没有执行用户代码。
- [ ] blob 有可观察 data/size 和显式 destroy 行为。
- [ ] scratch runtime 销毁后，多个独立 runtime 仍可 load/eval。
- [ ] eval-before-load、NULL 参数和 load replacement 的错误/边界结果符合 API 契约。
- [ ] 既有回归与新 bytecode suite 都通过；轨迹实际为 smoke 全通过、135/135、101/101。
- [ ] 分配/释放结果没有轨迹已观察到的泄漏。

## Examples

### Example 1: Valid use case

输入：

一段需要先编译、之后在多个 runtime 中执行的 JavaScript 源文本，底层提供 compile-only、`JS_WriteObject` 和 `JS_ReadObject`。

处理：

在 scratch runtime 中 compile-only，序列化为 blob；销毁 scratch runtime；在 5 个独立 runtime 中 load/eval；最后 destroy bytecode，并保留 smoke/subsystem 回归。

预期结果：

轨迹实际得到三组全绿结果：smoke 全通过、subsystem 135/135、bytecode 101/101（6a7964ed，事件 459、478–484、575–581）。

## 未保留的主要候选

- `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd` 中“用 static/thread-local 规避大型 C++ 测试 fixture 栈溢出并修复 solver/unifier 测试”的候选：轨迹在清单范围内仍显示 `test_solver`、`test_unifier` 等失败，未形成完整成功验证，不能提取为已证实 Skill。
- `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa` 中 Material 3/Alpine.js dashboard 接入候选：清单内证据停在 Odin 编译错误修复过程中，没有最终构建或运行通过结果。
- 仅有“写 README、创建 fixture、阅读代码”的普通流程：缺少独立的决策机制或问题解决证据，按宁缺毋滥原则舍弃。


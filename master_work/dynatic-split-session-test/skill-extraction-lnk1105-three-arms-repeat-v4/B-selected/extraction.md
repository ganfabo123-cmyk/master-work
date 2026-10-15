# Skill 提取结果

本次提取的 Skill 总数：2

| Skill 标题 | 来源 Session ID |
| --- | --- |
| 让 Windows PowerShell 5.1 与 Makefile 测试入口保持可执行，并用跨平台回归闭环验证 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` |
| 处理测试二进制被运行进程锁定导致的链接失败 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` |

# 让 Windows PowerShell 5.1 与 Makefile 测试入口保持可执行，并用跨平台回归闭环验证

```yaml
---
name: windows-shell-compatible-build-and-test-entrypoints
description: >
  Use when a C/C++ project supplies PowerShell build or test scripts and a Makefile
  that must run on Windows, especially when the repository targets Windows PowerShell
  5.1 as well as Unix-like shells. Helps make the scripts parse and dispatch tests
  correctly, then verifies the actual build and fixture/batch suites. Requires the
  project compiler, its test fixtures, and a way to invoke PowerShell and make.
  Do not use this as evidence that product runtime behavior is correct when only
  script parsing or compilation has been checked.
---
```

## Goal

使 Windows PowerShell 5.1 能解析并运行构建/测试脚本，使 Makefile 的测试入口按操作系统选择正确命令，并以实际构建、fixture 和 batch 测试结果证明入口可用。

## Scope

### In scope

- 检查 PowerShell 脚本是否使用了 PowerShell 7 才支持的语法或会破坏解析的字符。
- 修复 Windows `cmd.exe` 下 Makefile 测试目标使用 bash 语法的问题，并按平台分派命令。
- 构建项目并运行已有 fixture、批处理和错误用例。

### Out of scope

- 仅凭脚本解析通过推断编译器、运行时或部署正确。
- 为未出现的 shell、编译器或 CI 平台增加支持。
- 改变产品语义或扩展测试用例覆盖范围之外的功能。

## Inputs

- `<build.ps1>`：项目现有 PowerShell 构建脚本，必需；应包含实际项目的编译入口。
- `<run_tests.ps1>`：项目现有测试 runner，必需；应能返回非零失败码。
- `<Makefile>`：项目 Make 入口，必需；需要识别目标 shell 或操作系统。
- `<fixtures>`：已有正常和错误 fixture，必需；格式由项目测试 runner 定义。
- `<compiler>`：项目要求的编译器及其 include/config 参数，必需。

## Outputs

- `<build.ps1>`、`<run_tests.ps1>` 和 `<Makefile>`：只包含使既有入口在目标平台可执行所需的修正。
- 成功标准：两个 PowerShell 脚本可被 PowerShell 5.1 解析；项目成功构建；fixture 与 batch 测试达到 runner 报告的通过数；错误 fixture 保持预期非零行为。
- 失败标准：脚本仍无法解析、Makefile 测试目标无法启动 runner、构建失败，或任一回归测试失败。

## Preconditions

执行前必须确认：

1. Windows 上实际使用的 PowerShell 版本；本 Skill 的证据针对 Windows PowerShell 5.1。
2. `clang++`/项目编译器、Make 和测试 fixture 可访问。
3. runner 的退出码和输出格式可观察。

前置条件不满足时，停止并报告具体原因，不把其他 shell 的结果冒充 PowerShell 5.1 结果。

## Procedure

### Step 1: 先验证脚本语法

- 对 `build.ps1` 和 `run_tests.ps1` 做 PowerShell 解析检查。
- 若解析失败，优先检查目标版本不支持的语法（轨迹中为 PowerShell 7 的三元表达式）和脚本字符串中的异常字符（轨迹中为导致解析失败的 em dash）。
- 用 Windows PowerShell 5.1 兼容的 `if/else` 和普通 ASCII 字符替换后，重新进行解析检查。

### Step 2: 让 Makefile 的测试目标调用正确的 shell

- 检查 `test`、目录创建和清理目标是否包含 bash 专用的 `$$`、`$()`、`mkdir -p` 或 `rm -rf`。
- 在 Windows 分支中改为 `cmd.exe` 可执行的目录/清理命令，并直接委托给 PowerShell runner；保留 Unix/macOS 分支的 shell 命令。
- 用目标平台的 Make 实际执行一次构建和测试入口，确认生成的二进制路径与 runner 参数一致。

### Step 3: 运行构建与完整已有回归

- 先进行干净构建，确认编译器输出无未解决错误；若有已知警告修复，必须再次构建。
- 运行 fixture suite，逐项确认正常输入的输出比较和错误输入的预期退出码。
- 运行 batch suite，确认目录批处理、复制/跳过选项、pragma/runtime 选项、线程选项、显式文件列表以及错误隔离等已有断言。
- 只在 runner 报告完整通过时报告成功。

## Decision Rules

### When PowerShell 5.1 解析失败且错误指向三元表达式或异常字符串字符

执行：

1. 将三元表达式改写为等价 `if/else`，将导致解析失败的非必要特殊字符改成兼容字符。
2. 重新做脚本解析检查，再进入构建；不要仅凭文本替换宣称 runner 可用。

### When Makefile 在 Windows 使用 bash 专用命令

执行：

1. 按操作系统分支选择 `cmd.exe` 或 Unix shell 语法。
2. 在 Windows 测试目标中调用已通过解析检查的 PowerShell runner，并验证 Make 的真实退出码。

### When 只通过了脚本解析或编译

- 不报告测试入口或产品功能已完成；继续执行对应的 fixture/batch 验证，或明确说明验证范围。

### When 解析、构建或回归失败且轨迹没有支持的恢复动作

- 停止并报告具体失败输出，不猜测根因。

## Invariants

执行过程中必须保持：

- 不修改无关源代码或测试语义。
- 不把 PowerShell 7 语法重新引入 PowerShell 5.1 入口。
- 不把 Windows `cmd.exe` 命令放入 Unix 分支，或把 bash 专用语法放入 Windows 测试目标。
- 正常 fixture 的输出比较和错误 fixture 的退出码都必须保留。
- 不以构建通过替代运行时或批处理回归验证。

## Common Failures

### Failure: Windows PowerShell 5.1 解析失败

症状：

- 解析检查在含三元表达式或特殊字符串字符的脚本处失败。

原因：

- 轨迹确认三元表达式只适用于 PowerShell 7+；另一个解析错误由双引号字符串中的 em dash 触发。

恢复：

1. 改成 `if/else`，并替换导致解析失败的字符。
2. 重新解析两个脚本；轨迹中结果为 `build.ps1: OK` 和 `run_tests.ps1: OK`。

### Failure: Windows `make test` 使用了 bash 语法

症状：

- Makefile 的测试目标包含 `mkdir -p`、`rm -rf` 或 bash 循环，Windows Make 调用 `cmd.exe` 时不能正确执行。

原因：

- Make 在 Windows 上使用的 shell 与 Unix 假设不同。

恢复：

1. 增加 Windows/Unix 分支；Windows 测试目标委托给 PowerShell runner。
2. 重新构建并执行 Make 测试入口，确认二进制可生成且 runner 被调用。

## Verification

完成后必须检查：

- [ ] `build.ps1` 和 `run_tests.ps1` 在目标 PowerShell 版本下解析成功。
- [ ] Makefile 的 Windows 测试目标不再依赖 bash 专用命令，并能实际构建。
- [ ] fixture suite 的每项输出或预期错误退出码通过；轨迹中最终报告为 `48/48`。
- [ ] batch suite 的每项断言通过；轨迹中最终报告为 `17/17`。
- [ ] 构建与测试输出没有残留的目标失败；不能只引用“文件已修改”作为验证。
- [ ] 结果可追溯到脚本解析输出、构建输出和两个 runner 的通过计数。

## Examples

### Example 1: Valid use case

输入：

一个 C++ JSX 转译器项目，在 Windows 上提供 `build.ps1`、`tests/runner/run_tests.ps1` 和 Makefile；PowerShell 5.1 解析脚本失败，Makefile 测试目标含 bash 语法。

处理：

将 PowerShell 三元表达式改为 `if/else`，移除触发解析失败的 em dash；把 Makefile 的 Windows 分支改为 `cmd.exe` 兼容命令，并让 `test` 目标调用 PowerShell runner。随后执行构建、fixture suite 和 batch suite。

预期结果：

轨迹实际支持的结果是两个脚本解析为 `OK`，构建成功且无警告，fixture suite 报告 `48/48`，batch suite 报告 `17/17`。这证明该组脚本与测试入口及这些回归用例可用，不扩大为所有运行时场景已验证。

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | `segment-02.json`, source events 381–404 | 解析失败归因于 PowerShell 5.1 不支持三元表达式及字符串中的 em dash；修复后报告 `build.ps1: OK`、`run_tests.ps1: OK`。 |
| 关键处理动作 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | `segment-02.json`, source events 409–429 | 识别 Windows Make 使用 `cmd.exe`，修复 `mkdir -p` 等 bash 命令并加入 OS 分支；随后构建成功。 |
| 对应验证结果 | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6` | `segment-04.json`, source events 1427–1432 | Stage 3 batch suite 报告 `17 passed`；fixture suite 最终由 assistant 报告 `48/48 + 17/17`。 |

# 处理测试二进制被运行进程锁定导致的链接失败

```yaml
---
name: recover-from-locked-test-binary-link-failure
description: >
  Use when a rebuild fails at the linker because a test or application binary
  cannot be closed or replaced, with an OS-level file-lock error such as Windows
  LNK1105. Helps distinguish a process lock from a source or link-symbol error,
  terminate the identified stale test process, rebuild, and rerun the affected
  regression suites. Requires permission to inspect and stop the known project
  process. Do not use when the linker reports missing symbols, compiler errors,
  or an unknown process owns the file.
---
```

## Goal

解除已知测试进程对目标二进制的占用，成功重新链接，并用完整回归套件确认锁定恢复没有掩盖真实失败。

## Scope

### In scope

- 识别明确的 Windows 链接锁定错误。
- 查找并停止占用目标测试二进制的已知项目进程。
- 重新构建并运行项目已有的全部相关测试套件。

### Out of scope

- 处理缺少符号、语法错误或 ABI 不匹配等非锁定链接错误。
- 终止不相关或无法确认归属的进程。
- 以一次成功链接替代测试结果或内存/泄漏检查。

## Inputs

- `<linker-output>`：链接器错误文本，必需；应能确认是文件无法关闭/被占用。
- `<target-binary>`：无法替换的测试或应用二进制，必需。
- `<known-process>`：由项目启动、可确认对应目标二进制的进程，必需。
- `<build-command>`：项目标准构建命令，必需。
- `<test-suites>`：项目已有的回归套件及其通过计数，必需。

## Outputs

- 重新生成的 `<target-binary>`。
- 各测试套件的可观察通过结果和退出码。
- 成功标准：链接完成，所有相关套件通过，且任何资源计数/泄漏指标达到 runner 报告的预期。
- 失败标准：无法确认占用进程、终止后仍锁定、构建失败或任一套件失败。

## Preconditions

执行前必须确认：

1. 链接器错误明确属于目标文件被占用（轨迹中的 `LNK1105` 和 error code 1224）。
2. 可以把进程列表中的实例与该项目的目标二进制对应起来。
3. 项目已有可重复的构建和测试命令。

前置条件不满足时，停止并报告，不对未知进程执行终止操作。

## Procedure

### Step 1: 区分文件锁定与源代码错误

- 读取完整 linker 输出，确认错误是“cannot close file”/文件被占用，而不是编译错误或 unresolved symbol。
- 确认目标文件路径与正在运行的项目测试二进制一致。

### Step 2: 定位并停止占用进程

- 查询进程列表，按项目目标名称定位仍在运行的测试实例。
- 只终止已确认对应目标文件的实例；记录终止动作及结果。
- 等待文件句柄释放后，再次发起标准构建。

### Step 3: 重建并运行全部回归

- 使用原构建命令重新链接目标和测试二进制。
- 依次运行 smoke、subsystem、bytecode 等已有套件，保留每个套件的退出码、通过数和资源计数。
- 仅在链接成功且全部相关套件通过时报告恢复完成。

## Decision Rules

### When linker 明确报告目标文件无法关闭且 error code 表示文件被占用

执行：

1. 查找仍运行的对应项目进程。
2. 终止该已确认进程，重新构建，再运行全套回归。

### When linker 报告缺少符号、编译错误或其他非锁定错误

- 不套用本 Skill；按错误输出诊断源代码或链接配置。

### When 找不到或无法确认占用目标的进程

- 不猜测、不终止无关进程；报告目标路径、错误文本和缺失的进程归属证据。

## Invariants

执行过程中必须保持：

- 只处理已确认属于目标项目的进程。
- 不修改源代码来掩盖文件锁定。
- 重新构建后必须重新运行测试，不能沿用锁定前的结果。
- 不能把链接成功误报为功能验证成功。

## Common Failures

### Failure: 旧测试进程持有目标文件句柄

症状：

- Windows linker 报告 `LNK1105: cannot close file`，并带有文件占用错误码；重复构建仍失败。

原因：

- 轨迹中确认旧的测试二进制仍在运行并锁定输出文件。

恢复：

1. 查找并终止对应的运行实例。
2. 重新链接，然后执行全部套件；轨迹中恢复后 Stage 1、Stage 2 和 Stage 3 均通过。

## Verification

完成后必须检查：

- [ ] 原锁定错误不再出现，目标二进制成功链接。
- [ ] Stage 1 smoke suite 通过，并保留 `allocs=1246 / frees=1246` 的资源计数证据。
- [ ] Stage 2 subsystem suite 报告 `135/135 passed`。
- [ ] Stage 3 bytecode suite 报告 `101/101 passed`。
- [ ] 构建和新测试输出退出码为成功；不能只看到“kill succeeded”。
- [ ] 结果可追溯到锁定错误、进程处理和重建后的每个 suite 输出。

## Examples

### Example 1: Valid use case

输入：

Windows C 项目重新链接 `build/frost_smoke.exe` 时报告目标文件无法关闭，进程列表显示对应的旧测试实例仍在运行。

处理：

确认错误是文件锁定后终止该项目实例，重新执行原始构建命令，并运行 smoke、subsystem 和 bytecode 三个已有套件。

预期结果：

轨迹实际支持的结果是库重新构建成功，Stage 1 全部通过且 `allocs=1246 / frees=1246`，Stage 2 为 `135/135`，Stage 3 为 `101/101`。这证明锁定恢复后的这些回归套件通过，不扩大为所有平台部署都已验证。

### 来源证据

| 支持内容 | Session ID | 事件 ID 或原始文件行号 | 关键证据 |
| --- | --- | --- | --- |
| 问题及适用条件 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | `segment-03.json`, source events 572–576 | 构建首次失败；assistant 明确判断 link error 来自仍运行的测试二进制锁定，并决定终止实例后重建。 |
| 关键处理动作 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | `segment-03.json`, source events 576–580 | 终止运行实例后重新执行链接命令，三个测试二进制成功生成。 |
| 对应验证结果 | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833` | `segment-03.json`, source event 581 | assistant 报告 Stage 1 smoke、Stage 2 `135/135`、Stage 3 `101/101` 全部通过，且 smoke 资源计数无泄漏。 |

## 未保留的主要候选

- DMLS HTTP 路由修复：轨迹显示从 `404` 到多轮代码修正和编译错误，但清单中的末尾仍停在文件锁定/工具权限问题，没有完整的最终构建与路由验证，因此不足以提取“修复路由”的 Skill。
- DMLS 大型 `World`/`SimSnapshot` 堆分配修复：轨迹有针对栈溢出的合理修改，但在清单范围内没有对应的最终成功构建和运行证据，不能把方案当成已验证 Skill。
- Epilog 求解器/变量绑定调试：包含失败尝试、临时日志和未收口的测试失败（如 `5/6 suites PASSED, 2 FAILED`），缺少可归因的完整成功闭环。
- 单纯的文件创建、代码阅读、README 更新和通用“编写后测试”流程：没有独立改变执行决策的可迁移经验，按提取原则不单独包装。

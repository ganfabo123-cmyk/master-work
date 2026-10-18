---
name: handle-locked-or-stale-test-binaries
description: Use when the linker reports LNK1105 "cannot close file" or when test results contradict the latest code changes. Helps the agent detect running processes that hold the output exe, identify stale binaries by comparing LastWriteTime with source edits, and relink under a fresh name or after killing the holder so results are可信. Requires file timestamps, process control (Stop-Process/taskkill), and the ability to relink. Do not use when a freshly built binary reproduces the same failure — that is a real product bug.
---
# Get trustworthy test results when binaries are locked or stale

## Goal
在链接报 LNK1105（输出 exe 被占用）或测试结果与最新代码矛盾时，产出一组由新鲜二进制产生、可作为裁决依据的测试运行结果。

## Scope
### In scope
- 链接错误 `LINK : fatal error LNK1105: cannot close file ...`（上一次运行的进程仍持有 exe）。
- 结果可疑：源码已修改，但同名 exe 的 `LastWriteTime` 未更新，或目录里混有改动前生成的旧二进制（如带 `_dbg`、旧日期后缀的副本）。
- 处置：结束占用进程（Stop-Process/taskkill）、或改用新文件名重新链接，只用新鲜二进制的结果做判断。
- 结果解读：只有新鲜二进制的 PASS/FAIL 才计入结论。

### Out of scope
- 新鲜二进制同样复现的失败（真实产品缺陷）。
- 编译阶段错误。
- 断言语义、测试框架问题。

## Inputs
1. **链接/运行输出**：字符串，来源：编译与测试命令的工具结果，必需。约束：含 `LNK1105` / `error code 1224`，或结果与源码改动矛盾。默认值：无。
2. **二进制时间戳清单**：表格/字符串，来源：`Get-ChildItem ... | Select Name, LastWriteTime`，必需。约束：用于与最近一次源码修改比较。默认值：无。
3. **进程清单与终止能力**：PowerShell 命令结果，来源：Get-Process/Stop-Process/taskkill，必需（占用场景）。约束：只能结束本项目相关进程。默认值：无。
4. **重链接命令**：字符串，来源：既有编译行，必需。约束：支持指定新的 `-o` 输出路径。默认值：无。
5. **源码最近修改时间**：时间戳，来源：文件属性，可选。约束：与二进制时间同精度比较。默认值：无。

## Outputs
### Artifacts
- 新文件名（或重建后原名）的测试二进制及其运行输出。
- 时间戳/进程处置记录（用于解释旧结果为何无效）。

### Success criteria
- 链接不再报 LNK1105，二进制成功生成。
- 测试结果来自时间戳晚于最新源码修改的二进制，并含明确的 `N/N tests passed` 与 exit code。

### Failure criteria
- 仍以旧二进制的结果下结论。
- 结束了无关进程，或在未重链的情况下直接沿用旧输出。

## Preconditions
- 能列出文件时间戳、能终止本项目的测试进程、能以新的输出路径重新链接。
- 拥有重编译/重链接所需源文件与对象文件。
- 若新鲜二进制复现同一失败，立即退出本流程并按真实缺陷处理。
- 无法判断二进制新旧（既无时间戳也无重建能力）时，停止并报告，不得引用其结果。

## Procedure
### Step 1: 识别文件锁
- actions: 读取链接错误，确认 `LNK1105 ... cannot close file`（error code 1224）。
- inputs: 链接输出。
- outputs: 结论：目标 exe 被某进程占用。
- cautions: 不要把它当成编译错误继续改源码。
- preserve: 不删除已有二进制。
- next: 确认为锁 → Step 2。

### Step 2: 结束占用进程或改用新输出名
- actions: 优先 `Stop-Process`/`taskkill /F /IM <name>.exe` 结束残留测试进程并短暂等待；若不便杀进程，则改用新文件名（如 `test_x2025.exe`、`test_x_final.exe`）重链。
- inputs: 进程名、重链接命令。
- outputs: 可写入的输出路径。
- cautions: 只结束本项目测试进程；杀进程后留出等待时间再链接。
- preserve: 保留旧二进制作对照，不覆盖其结果记录。
- next: 链接成功 → Step 3。

### Step 3: 核对二进制新旧
- actions: `Get-ChildItem build/tests -Filter *.exe | Select Name, LastWriteTime`，与最近源码修改时间比较；识别改动前遗留的 `_dbg`、旧日期副本。
- inputs: 时间戳清单。
- outputs: "可信/不可信"二进制列表。
- cautions: 目录里同名或近名文件可能来自改动之前；仅凭文件名判断不可靠。
- preserve: 不删除旧文件（留作对照）。
- next: 存在新鲜二进制 → Step 4；否则回到 Step 2 重建。

### Step 4: 只用新鲜二进制裁决
- actions: 运行新鲜二进制，记录输出与 exit code；把旧二进制的结果标记为无效。
- inputs: 新鲜二进制路径。
- outputs: `N/N tests passed` + exit 0/非 0。
- cautions: 运行中的旧进程会持续锁文件，影响后续重建。
- preserve: 保留双方输出以便说明差异。
- next: 新鲜结果通过 → 完成；失败 → 转入真实缺陷流程。

## Decision Rules
### When 链接报 `LNK1105: cannot close file` / error code 1224
判定为输出 exe 被占用：结束持有进程，或改用新的输出文件名重链。

### When 同名 exe 的 LastWriteTime 早于最近一次源码修改
该结果不可信：重建后再运行。

### When 目录中存在改动前生成的同类二进制（如 `_dbg`、旧副本）
其 FAIL 结果一律作废；只采信按当前源码新链的二进制。

### When 新鲜二进制复现同一失败
停止本流程，视为真实缺陷进入对应修复流程。

### When 同一套件在"直接运行"与"汇总脚本"中结果不一致
先排查汇总脚本用的是哪个路径/哪个文件，确认是同一二进制后再比较。

## Invariants
- 只以时间戳晚于最新源码修改的二进制结果作为结论依据。
- 不覆盖、不删除旧二进制（保留对照），不伪造运行记录。
- 只终止本项目相关测试进程，不碰无关进程。
- 不在文件锁未解除时反复重链并把失败归因于代码。
- 不因结果"不好看"而改用旧的通过记录。
- 不报告未验证的成功。

## Common Failures
### Failure: 把 LNK1105 当编译错误排查
- symptoms: `LINK : fatal error LNK1105: cannot close file ...`，反复改源码仍无法链接。
- causes: 上一次运行的测试进程未退出。
- recovery: 结束进程（Stop-Process/taskkill）或换输出文件名后重链。

### Failure: 用旧二进制的失败结果误判修复无效
- symptoms: 源码已修复，但运行旧 exe 仍显示 FAIL（轨迹中 `test_solver2.exe` 为改动前生成，18/22；同名新鲜 `test_solver.exe` 22/22）。
- causes: 目录混有改动前的遗留二进制。
- recovery: 列 LastWriteTime 比对，重建后再运行，仅采信新鲜结果。

### Failure: 汇总脚本引用了错误路径
- symptoms: 汇总显示失败，但直接运行同一名称的二进制通过。
- causes: 脚本用相对/绝对路径不一致，或命中了另一份文件。
- recovery: 统一二进制路径并确认时间戳一致后重跑汇总。

## Verification
- 链接命令 exit 0，不再出现 `LNK1105`。
- `Get-ChildItem` 显示用于裁决的 exe 时间戳晚于最近一次源码修改。
- 运行该 exe 得到明确计数（如 `22/22 tests passed`）与 exit code 0。
- 同目录中改动前遗留的旧二进制被标记为无效，未计入结论。
- 汇总脚本与手动运行指向同一路径且结果一致。

## Examples
### Example 1: 链接时输出 exe 被占用
- input: 重链 `test_indexing.exe` 报 `LINK : fatal error LNK1105: cannot close file`（error code 1224），前一步该 exe 刚被运行且可能卡死。
- procedure: Step 1 确认 LNK1105 → Step 2 结束残留测试进程并等待，或改输出为 `test_indexing2025.exe` → Step 4 运行新二进制。
- expected result: 链接 exit 0；新二进制运行给出明确结果。
- parameterized values: 进程名、输出后缀按项目替换。

### Example 2: 旧二进制导致"修复无效"的假象
- input: 修改后运行 `test_solver2.exe` 仍 `18/22 tests passed`（该文件时间戳早于改动），而同批新链的 `test_solver.exe` 为 `22/22 tests passed`。
- procedure: Step 3 列出 LastWriteTime 识别旧副本 → Step 4 仅用新鲜二进制裁决，作废旧结果。
- expected result: 结论基于新鲜二进制（22/22），旧结果标记无效。
- parameterized values: 文件名与时间戳按实际环境替换。

## Evidence
- problem: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=223, source_part_index=0, quote="LINK : fatal error LNK1105: cannot close file", supports=输出 exe 被占用导致无法链接的症状。
- problem: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=167, source_part_index=0, quote="are **old pre-existing binaries**", supports=目录中混有改动前遗留二进制、会污染结果判断。
- problem: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=169, source_part_index=0, quote="test_solver2.exe   06-06-2026 12:26:06 PM", supports=用 LastWriteTime 甄别旧二进制的具体证据。
- action: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1190, source_part_index=0, quote="Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue", supports=结束占用进程以解除文件锁的关键动作。
- action: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=258, source_part_index=0, quote="test_solver2025.exe", supports=改用新文件名重新链接以绕开占用的关键动作。
- verification: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=259, source_part_index=0, quote="test_solver: 0", supports=新文件名链接成功（exit 0）。
- verification: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=261, source_part_index=0, quote="22/22 tests passed", supports=新鲜二进制给出与旧二进制（18/22）不同的可信结果，据此裁决。

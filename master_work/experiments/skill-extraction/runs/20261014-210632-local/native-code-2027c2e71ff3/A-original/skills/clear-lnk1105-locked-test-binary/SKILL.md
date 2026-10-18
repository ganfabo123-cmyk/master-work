---
name: clear-lnk1105-locked-test-binary
description: Use when a link fails with `LNK1105: cannot close file '<path>.exe'; error code 1224` on targets that compiled and linked fine earlier in the session. Helps the agent recognize the output exe is held by a still-running (often crashed or hung) test process, end those processes by name, and rerun the build so previously locked targets relink and run. Requires the ability to enumerate/end processes and rerun the build command. Do not use when the same output error is a genuine missing-symbol LNK2019, when no such process can exist (first build of a fresh path), or when the exe path differs from any running process.
---
# Clear LNK1105 File-Locked Test Binaries by Killing Lingering Test Processes Before Relink

## Goal
解决测试批量构建中 `LNK1105: cannot close file ... error code 1224` 的输出 exe 被占用问题：结束残留的测试进程后重跑构建，使原被锁目标重新链接并运行。

## Scope
### In scope
- 链接期错误 `LINK : fatal error LNK1105: cannot close file '<path>\<name>.exe'; error code 1224`，而同一目标此前已成功链接过（或同批其他目标正常）。
- 成因：上一轮运行/崩溃的同名测试进程仍持有该 exe（Windows 文件锁）。
- 处置：按进程名/模式结束残留进程，等待后重跑原构建命令。

### Out of scope
- `LNK2019`/`LNK1120` 等 unresolved external 符号错误（另见对应 Skill）。
- 首次构建全新路径就报 LNK1105 的情形（轨迹未提供证据）。
- 编译期错误（与文件锁无关）。

## Inputs
- **LNK1105 错误输出**：字符串；来源：构建脚本结果；必需；须含 `LNK1105: cannot close file '<路径>'; error code 1224` 与目标名；默认值：无。
- **被锁 exe 的目标名**：字符串；来源：从 LNK1105 路径解析（如 `test_parser.exe` → 进程名 `test_parser`）；必需；用于按名结束进程；默认值：无。
- **进程枚举/结束能力**：工具（PowerShell `Get-Process`/`Stop-Process` 或 `taskkill`）；来源：运行环境；必需；默认值：无。
- **原构建命令**：shell 命令；来源：轨迹中的测试构建脚本；必需；用于释放锁后原样重跑；默认值：无。
- **等待时间**：整数毫秒；来源：经验参数；可选；结束进程后给系统释放句柄的时间；默认值：轨迹使用 500–800 毫秒。

## Outputs
### Artifacts
- 结束残留测试进程的命令记录。
- 重跑后的构建输出（原被锁目标不再出现 LNK1105）。

### Success criteria
- 原报 LNK1105 的目标在重跑中完成链接并生成 exe，输出转为该目标的测试结果行（如 `--- test_parser ---` + `12/12 tests passed`）。
- 构建输出中 LNK1105 出现 0 次（或仅剩已明确说明的个别目标，见 Failure criteria）。

### Failure criteria
- 释放锁并重跑后同一目标仍报 LNK1105。
- 目标链接成功但运行崩溃（属独立运行时问题，不算本 Skill 成功也不算失败，需转交）。

## Preconditions
- 错误文本确为 `LNK1105 ... error code 1224`（文件锁），而不是 unresolved external 等其他链接错误。
- 该 exe 在本会话此前成功链接/运行过，或存在其进程仍在运行的可能。
- 拥有枚举与结束进程的权限，且只会结束与被锁目标同名/同模式的测试进程，不碰无关进程。
- 可原样重跑构建命令。
- 以上任一不满足时停止并报告。

## Procedure
### Step 1: 从 LNK1105 提取被锁目标并核对性质
- actions：读取构建输出，列出所有 LNK1105 行及其 exe 路径/基名；确认这些目标在本轮之前可链接（同一脚本中其他目标正常、或此前轮次成功）。
- inputs：构建输出。
- outputs：被锁目标清单（轨迹中为 test_parser/test_terms/test_unifier/test_variables，随后还有 test_atoms）。
- cautions：同一批输出里若混有 LNK2019，分开处理，不要一起当作文件锁问题。
- preserve：不改任何源码或构建脚本。
- next：清单非空后进入 Step 2。

### Step 2: 结束持有这些 exe 的残留进程
- actions：按基名结束进程，如 `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue`；等待 500ms 左右；若仍锁，扩大匹配范围（如 `Get-Process | Where-Object { $_.Name -like "*test*" -or $_.Name -like "*epilog*" } | Stop-Process -Force -ErrorAction SilentlyContinue` 或 `taskkill /F /IM "<name>.exe"`）。
- inputs：被锁目标清单。
- outputs：进程结束结果。
- cautions：只匹配测试/被锁目标相关进程；结束后必须等待句柄释放。
- preserve：不结束开发工具或其他项目进程。
- next：进入 Step 3。

### Step 3: 原样重跑构建
- actions：重跑同一构建脚本，观察原 LNK1105 目标。
- inputs：原构建命令。
- outputs：新的链接与运行结果。
- cautions：个别目标可能仍报 LNK1105（进程名与 exe 基名不一致等），对剩余项重复 Step 2 的扩大匹配。
- preserve：不因文件锁问题改动测试代码。
- next：全部目标完成链接为止。

## Decision Rules
### When 错误是 `LNK1105 ... error code 1224` 且目标此前成功链接过
→ 判定为残留进程持有 exe；按名结束进程 + 等待 + 重跑（Step 2–3）。

### When 按精确进程名结束后该目标仍报 LNK1105
→ 扩大进程匹配（`*test*` / `*epilog*` 模式或 `taskkill /F /IM`）后再次重跑（轨迹中 test_atoms 需要这一步）。

### When 同批输出同时出现 LNK2019 与 LNK1105
→ 两类分开处理：LNK2019 走符号解析流程，LNK1105 走进程清理流程；不要用其中之一的结论覆盖另一个。

### When 释放锁后目标链接成功但运行 exit `-1073741571`
→ 属启动崩溃（栈上大对象问题），转交对应 Skill；文件锁本身已解除。

## Invariants
- 只结束与被锁测试目标相关的进程，不结束无关进程。
- 不为绕过文件锁改写输出路径、跳过目标或修改构建脚本逻辑。
- 结束进程后给予句柄释放等待时间，再重跑链接。
- 不把“文件锁解除后仍存在的运行时崩溃/断言失败”报告为本 Skill 的成功。
- 不在未重跑构建的情况下报告已解除。

## Common Failures
### Failure: 按精确名结束进程后仍 LNK1105
- symptoms：`Stop-Process -Name <name>` 执行后重跑，同一目标仍 `LNK1105 ... error code 1224`。
- causes：实际进程名与 exe 基名不一致，或仍有其他同族进程持有句柄。
- recovery：改用模式匹配（`*test*`、`*epilog*`）或 `taskkill /F /IM "<name>.exe"`，再等待并重跑（轨迹中 test_atoms 走到这一步后链接恢复）。

### Failure: 只看到了 LNK1105 而忽略了同批的运行时崩溃
- symptoms：锁解除后目标运行仍无输出、exit `-1073741571`。
- causes：独立的启动崩溃问题（大对象占栈）。
- recovery：转交启动崩溃 Skill；不要把它计为文件锁修复失败。

### Failure: 误把 unresolved external 当作文件锁
- symptoms：清理进程后错误原样为 `LNK2019`。
- causes：根本不是文件占用，而是符号缺失。
- recovery：回退到 LNK2019 流程；本 Skill 不适用。

## Verification
重跑构建并检查以下可观察项（应观察的检查，不声称已执行）：
- 输出中 `LNK1105` 出现 0 次（或逐轮减少直至 0）。
- 原被锁目标出现运行结果行而非 `COMPILE ERROR`（如 `--- test_parser ---` 后 `12/12 tests passed`、`--- test_unifier ---` 后 `18/18 tests passed`、`--- test_terms ---` 后 `15/15 tests passed`、`--- test_variables ---` 后 `17/17 tests passed`）。
- 构建脚本的通过统计上升（轨迹中从 `=== 2 suite(s) PASSED, 5 FAILED ===` 提升到 `=== 6 PASSED, 1 FAILED ===`，仅剩仍被锁的 test_atoms）。
- `Get-Process` 中不再存在与被锁目标同名的进程。

## Examples
### Example 1: 四个测试 exe 同时被锁（轨迹原例）
- input：构建输出中 `COMPILE ERROR: test_parser.cpp` + `LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224`（test_terms/test_unifier/test_variables 同样），同批 test_lexer 正常 `22/22 tests passed`。
- procedure：Step 1 列出四个被锁目标；Step 2 `Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue` + `Start-Sleep -Milliseconds 500`；Step 3 原样重跑构建。
- expected result：四个目标完成链接并输出各自测试结果（12/12、15/15、18/18、17/17），统计升至 `=== 6 PASSED, 1 FAILED ===`（仅 test_atoms 仍锁）。
- parameterized values：`<locked targets>=test_parser,test_terms,test_unifier,test_variables`、`<wait>=500ms`。

### Example 2: 单个目标按名未解锁后扩大匹配
- input：重跑后仅 `test_atoms` 仍 `LNK1105 ... error code 1224`。
- procedure：`Get-Process | Where-Object { $_.Name -like "*test*" -or $_.Name -like "*epilog*" } | Stop-Process -Force ...`，`Start-Sleep -Milliseconds 800`，重跑该目标链接。
- expected result：该目标进入链接流程（输出出现 `performing full link` 而非 LNK1105）；后续运行结果另行判定。
- parameterized values：`<pattern>=*test*`、`<wait>=800ms`。

## Evidence
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1187；source_part_index：0；quote：`LINK : fatal error LNK1105: cannot close file 'build\tests\test_parser.exe'; error code 1224`；supports：problem（同批输出还有 test_terms/test_unifier/test_variables 的同类 LNK1105，而 test_lexer/test_solver 已正常运行出结果）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1189；source_part_index：0；quote：`The "compile errors" are just file-locked binaries from the previous run still in memory.`；supports：problem 成因判定（Assistant 判断）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1190；source_part_index：0；quote：`Stop-Process -Name test_atoms,test_terms,test_unifier,test_variables,test_parser -ErrorAction SilentlyContinue`；supports：action（按被锁目标名结束残留进程，随后等待 500ms 并原样重跑构建）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1191；source_part_index：0；quote：`--- test_parser ---`；supports：verification（原 LNK1105 的 test_parser 恢复链接并 `12/12 tests passed`；同批 `15/15 tests passed`、`18/18 tests passed`、`17/17 tests passed`，统计 `=== 6 PASSED, 1 FAILED ===`，仅 test_atoms 仍 `LNK1105`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1193；source_part_index：0；quote：`Get-Process | Where-Object { $_.Name -like "*test*" -or $_.Name -like "*epilog*" } | Stop-Process -Force -ErrorAction SilentlyContinue`；supports：action（精确名无效时的扩大匹配处置，等待 800ms 后重跑）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1194；source_part_index：0；quote：`LINK : build\tests\test_atoms.exe not found or not built by the last incremental link; performing full link`；supports：verification（释放锁后该目标进入完整链接流程，LNK1105 消失；其后 `exit: -1073741571` 属独立运行时崩溃）。

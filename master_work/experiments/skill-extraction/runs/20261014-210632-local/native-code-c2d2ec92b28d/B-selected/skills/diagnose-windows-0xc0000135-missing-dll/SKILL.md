---
name: diagnose-windows-0xc0000135-missing-dll
description: Use when a Windows exe exits immediately with -1073741515 / 0xC0000135 or shows no window after a successful build. Helps the agent identify the exact missing imported DLL and fix the build script copy step that failed silently. Requires PowerShell access to the build output directory and the build script. Do not use when the build itself fails, or when the exe exits with a different NTSTATUS.
---
# Diagnose Windows exe Exit 0xC0000135 (Missing DLL)

## Goal
把“构建成功但 exe 立即退出、无窗口/无输出、退出码 0xC0000135（-1073741515）”定位到具体缺失的导入 DLL，修复构建脚本中静默失败的 DLL 复制步骤，并以 exe 实际启动运行（框架初始化日志、进程存活）作为最终产物。

## Scope
### In scope
- 复现并解码 exe 的十进制退出码（-1073741515 → 0xC0000135）。
- 在没有 dumpbin 的情况下用字节串 + 正则提取 exe 的 DLL 导入列表。
- 对比导入列表与 exe 同目录已有 DLL，定位缺失项。
- 在磁盘（工具链目录）中搜索缺失 DLL 并手动复制到 exe 目录先行验证。
- 修复构建脚本中因重定向输出（`>nul 2>&1`）和未设置环境变量而静默失败的复制步骤。
- 重建并实际启动 exe 做端到端验证（含 LNK1105 文件占用导致重建失败的处理）。

### Out of scope
- 构建本身失败（编译/链接错误）的修复。
- 其他 NTSTATUS 退出码（如访问冲突 0xC0000005）的诊断。
- 依赖 PATH 而非 exe 同目录的 DLL 解析方案、DLL 架构不匹配（x86/x64）问题（轨迹未提供此类证据）。
- 非 Windows 平台的共享库加载问题。

## Inputs
1. **症状描述**（string，来源：用户报告，必需，约束：典型为“no screen/output on running”或进程启动即退出；默认值：无）。
2. **exe 路径**（string，来源：构建输出目录（如 `<project>\build\<name>.exe`），必需，约束：必须是最近一次构建产出的二进制；默认值：无）。
3. **退出码**（int/NTSTATUS，来源：运行 exe 后的 `$LASTEXITCODE` 或 `Start-Process -PassThru -Wait` 的 `$proc.ExitCode`，必需，约束：以十进制原值为准；默认值：无）。
4. **exe 同目录 DLL 列表**（list，来源：`ls <exedir>\*.dll`，必需，约束：用于与导入表求差；默认值：无）。
5. **构建脚本**（file，来源：仓库根目录（如 `build.bat`），修复根因时必需，约束：需能读写；默认值：无）。
6. **工具链根目录**（string，来源：`where <tool>` 推导（案例中 odin 位于 `D:\Odin\dist`），可选，约束：仅用于定位待复制的 DLL；默认值：无）。
7. **PowerShell 执行权限**（环境，来源：执行环境，必需，约束：可运行 exe、读文件、复制文件；默认值：无）。

## Outputs
### Artifacts
- **缺失 DLL 已就位**：缺失 DLL 出现在 exe 同目录（文件系统，格式：`.dll` 文件）。
- **修复后的构建脚本**：复制步骤由工具链位置推导源路径、失败时打印可见警告（仓库内脚本文件）。
- **启动证据**：一次完整运行的输出日志或存活的进程记录（工具结果）。

### Success criteria
- 再次运行 exe 不再返回 -1073741515，出现运行时初始化输出（如 `INFO: Initializing raylib 5.5` 至 `INFO: Window closed successfully`），或分离启动后 `Get-Process` 仍能查到该进程。
- 导入列表中的非系统 DLL 全部存在于 exe 同目录。
- 构建脚本在 DLL 源文件缺失时打印警告，而非静默跳过。

### Failure criteria
- 复制 DLL 后重跑仍返回 0xC0000135。
- 导入的 DLL 在整机上找不到可复制来源。
- 只完成构建、未观察到任何运行时证据。

## Preconditions
- 构建本身已成功，exe 文件存在且可读（构建失败则先解决构建错误，本流程不适用）。
- 执行环境为 Windows，可在 PowerShell 中运行 exe、列目录、读取文件字节、复制文件。
- 能拿到构建输出目录和构建脚本（如 `build.bat`）的读写权限。
- 若有残留进程占用 exe（重建报 LNK1105），需先按 Decision Rules 处理后再进入本流程。
- 上述任一条件不满足：停止并向用户报告缺少的条件。

## Procedure
### Step 1: 复现退出并解码状态码
- actions: 在 exe 目录直接运行 `& ".\<exe>"` 读取 `$LASTEXITCODE`；再用 `Start-Process -FilePath ".\<exe>" -PassThru -Wait` 读 `$proc.ExitCode` 交叉确认；同时 `Get-Process <name>` 看进程是否存在。
- inputs: exe 路径。
- outputs: 十进制退出码（案例为 `-1073741515`）。
- cautions: PowerShell 可能只显示 `Exit code 53` 这类包装值，以十进制 `ExitCode` 为准；`Get-Process` 查不到进程说明进程启动即退出，未进入业务逻辑。
- preserve: 不修改任何源码。
- next: 退出码为 -1073741515（即 0xC0000135）→ Step 2；否则停止本流程。

### Step 2: 提取 exe 的 DLL 导入列表
- actions: 若 `dumpbin` 不可用，用 `[System.IO.File]::ReadAllBytes("<exe>")` → `[System.Text.Encoding]::ASCII.GetString` → `[regex]::Matches($text, '[A-Za-z0-9_\\-]+\\.dll')` → `Sort-Object -Unique`。
- inputs: exe 文件。
- outputs: 导入 DLL 列表（案例：`ADVAPI32.dll / bcrypt.dll / epilog.dll / KERNEL32.dll / raylib.dll`）。
- cautions: 这是启发式扫描，可能混入字符串表误报；只关心非系统 DLL（`KERNEL32.dll`、`ADVAPI32.dll` 等由 System32 提供）。
- next: Step 3。

### Step 3: 对比导入列表与 exe 旁已有 DLL
- actions: `ls <exedir>\*.dll`，与 Step 2 结果求差集。
- inputs: exe 目录 DLL 列表。
- outputs: 缺失 DLL 清单（案例：`epilog.dll` 已在位，`raylib.dll` 缺失）。
- cautions: 项目自己的 DLL 在位不代表所有导入都满足；任何一个缺失都会让加载器在 `main` 之前终止进程。
- next: 差集为空 → 停止并按其他原因排查；非空 → Step 4。

### Step 4: 定位缺失 DLL 并先手动补齐
- actions: 在工具链目录搜索该文件（案例：`Get-ChildItem <odin> -Recurse -Filter raylib.dll` 找到 `<odin>\vendor\raylib\windows\raylib.dll`）；`Copy-Item <src> <exedir>` 复制过去。
- inputs: 缺失 DLL 名、工具链根目录。
- outputs: exe 目录中出现该 DLL。
- cautions: 构建脚本引用的环境变量可能根本未设置（案例中 `%ODIN_ROOT%` 为空），不能据脚本推断文件位置。
- next: Step 5（必须修根因，否则 clean/换机后复发）。

### Step 5: 修复构建脚本的静默失败
- actions: 读构建脚本复制 DLL 的行；把依赖未设置环境变量的源路径改为由 `where <tool>` 推导工具目录（`for /f ... in ('where odin 2^>nul') do set ODIN_BIN=...` → `%%~dpi` → `vendor\raylib\windows\raylib.dll`）；`if exist` 才复制，否则 `echo [warn] ...` 显式警告，去掉 `>nul 2>&1` 式吞错。
- inputs: 构建脚本。
- outputs: 更新后的复制逻辑。
- preserve: 保留对其它 DLL（如 `epilog.dll`）的复制与其余构建步骤不动。
- next: Step 6。

### Step 6: 重建并验证启动
- actions: 运行构建脚本；若出现 `LINK : fatal error LNK1105 ... error code 1224`（exe 被占用），先 `Remove-Item -Force <exe>`（或结束占用进程）再重建；构建成功后运行 exe，观察框架初始化日志，或 `Start-Process` 后 `Start-Sleep` + `Get-Process` 确认进程存活。
- inputs: 构建脚本、exe。
- outputs: 运行日志（案例：`INFO: Initializing raylib 5.5` 起始至 `INFO: Window closed successfully`）与存活进程记录。
- cautions: 构建成功不等于运行成功；必须拿到运行时证据才算完成。
- next: 所有验证项可观察到即结束。

## Decision Rules
### When 退出码为 -1073741515（0xC0000135）
按“缺失依赖 DLL”处理：直接进入导入表提取与比对，不要去排查应用逻辑或屏幕绘制代码。

### When 项目自有 DLL 已在 exe 旁
仍要枚举完整导入列表——一个缺失的第三方 DLL（如 `raylib.dll`）足以让加载失败，不能因“自己的 DLL 在”就排除缺 DLL。

### When 构建脚本的复制步骤带 `>nul 2>&1`（或 `||` 兜底也静默）
认定该步骤可能已多次失败：直接检查目标 DLL 是否存在，而不是相信构建日志；修复时改为源缺失打印 `[warn]`。

### When 引用的环境变量（如 `%ODIN_ROOT%`）可能未设置
用 `where <tool>` 现场推导工具目录，不再依赖环境变量。

### When 重建报 `LINK : fatal error LNK1105 ... error code 1224`
说明 exe 被某进程占用：删除/结束占用者后重建。轨迹中具体是哪个进程占用未确认，但 `Remove-Item -Force <exe>` 成功后重建即通过。

### When 缺失 DLL 在项目与工具链中都搜不到
停止并报告：无法定位来源时不要伪造或改链接参数。

## Invariants
- 不在重新运行 exe 之前声称问题已修复；构建通过不算修复证据。
- 问题在 DLL 布局时，不改链接参数、不改源码 import、不改链接目标类型。
- 新增/修改的复制步骤必须在源缺失时给出可见警告，不允许再用 `>nul 2>&1` 吞掉错误。
- 保持“DLL 与 exe 同目录”的布局，不改为依赖 PATH 或系统目录。
- 不把 PowerShell 打包的 `Exit code 53` 之类包装值当作最终状态码，必须记录十进制 `ExitCode`。
- 不在找不到 DLL 来源时伪造文件或虚报成功。

## Common Failures
### Failure: 构建成功但 exe 秒退、无窗口无输出
- symptoms: 用户报 “no screen/output on running”；`Get-Process` 查不到进程；直接运行返回 `Exit: -1073741515`。
- causes: 加载器在进入 `main` 前找不到某个导入 DLL（0xC0000135），进程被 OS 终止。
- recovery: 执行 Step 2–Step 4：提取导入表 → 求差 → 找到并复制缺失 DLL。

### Failure: 因“自己的 DLL 在旁边”而误判不缺 DLL
- symptoms: 检查了项目 DLL（如 `epilog.dll`）存在就转去排查其他方向，绕圈。
- causes: 只核对了已知 DLL，没有枚举完整导入列表。
- recovery: 用字节串正则列出全部 `.dll` 导入，与目录内容求差（案例差集为 `raylib.dll`）。

### Failure: DLL 复制步骤跨多次构建静默失败
- symptoms: 构建日志看不出任何复制错误，但目标 DLL 始终不在输出目录。
- causes: `copy ... >nul 2>&1` 吞掉错误，且源路径依赖未设置的环境变量（`%ODIN_ROOT%` 为空），`||` 兜底同样静默。
- recovery: 先手动 `Copy-Item` 补齐，再把脚本改为 `where <tool>` 推导源路径 + 源缺失打印 `[warn]`。

### Failure: 重建报 LNK1105（error code 1224）
- symptoms: `[odin] ERROR: Odin build failed`，`LINK : fatal error LNK1105: cannot close file '<exe>'`。
- causes: 上一次运行残留的进程占用 exe。轨迹未确认具体是哪个进程（`Get-Process` 按路径过滤无输出）。
- recovery: `Remove-Item -Force <exe>`（或结束进程）后重建；删除成功后重建即通过。

### Failure: 只看 PowerShell 包装的退出码
- symptoms: 只记录到 `Exit code 53`，与 0xC0000135 对不上。
- causes: 管道/包装层改写了显示值。
- recovery: 用 `$LASTEXITCODE` 或 `Start-Process -PassThru` 的 `ExitCode` 取十进制原值（-1073741515）。

## Verification
可观察检查项（不使用 [x]，逐项对照工具输出）：
- 再次运行 exe：`$LASTEXITCODE` / `ExitCode` 不是 -1073741515。
- 运行日志出现框架初始化行，例如 `INFO: Initializing raylib 5.5`、`INFO: DISPLAY: Device initialized successfully`，并以正常关闭行（如 `INFO: Window closed successfully`）结束。
- `ls <exedir>\*.dll` 的结果包含导入表中全部非系统 DLL（案例中 `raylib.dll` 出现在列表中）。
- 分离启动（`Start-Process`）+ 等待数秒后 `Get-Process <name>` 返回进程行。
- 重建日志显示复制步骤正常，或在源缺失时明确打印 `[warn] ...`，且没有任何被 `>nul` 吞掉的复制。
- 若曾遇 LNK1105：删除/结束占用后重建输出 `[odin] Built <exe>`。

## Examples
### Example 1: GUI 程序构建后无窗口（缺失 raylib.dll）
- input: 用户报告 “no screen/output on running”；`& ".\build\dmls.exe"` 得到 `Exit: -1073741515`；`Start-Process -PassThru -Wait` 得到相同值。
- procedure: Step 1 解码为 0xC0000135 → Step 2 正则提取导入表得到 `ADVAPI32.dll / bcrypt.dll / epilog.dll / KERNEL32.dll / raylib.dll` → Step 3 发现 `build\` 只有 `epilog.dll` → Step 4 在 `<odin>\vendor\raylib\windows\` 找到并 `Copy-Item` → Step 5 把 `build.bat` 的复制改为 `where odin` 推导 + `[warn]` → Step 6 重建并运行。
- expected result: 构建后运行输出 `INFO: Initializing raylib 5.5` 至 `INFO: Window closed successfully`；`ls build\*.dll` 含 `raylib.dll`。
- parameterized values: exe 路径、缺失 DLL 名（`raylib.dll`）、工具链根（`D:\Odin\dist`）、构建脚本名（`build.bat`）、日志前缀（raylib 5.5）。

### Example 2: 重建被运行中的 exe 阻塞
- input: 复制完 DLL 后重建，输出 `LINK : fatal error LNK1105: cannot close file 'D:\DMLS\build\dmls.exe'; error code 1224`。
- procedure: `Stop-Process -Name dmls` 后仍失败（未确认是否生效）→ `Get-Process` 按路径过滤无输出 → `Remove-Item -Force <exe>` 返回 `True` → 重新运行构建。
- expected result: 构建输出 `[odin] Built build\dmls.exe` 并进入运行阶段。
- parameterized values: exe 路径、进程名、错误码 1224。

## Evidence
file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02

- source_index: 391, source_part_index: 0, quote: "no screen/output on running", supports: problem——用户报告的症状（进程无窗口/无输出）。
- source_index: 404, source_part_index: 0, quote: "Exit code 53\nExit: -1073741515", supports: problem——直接运行 exe 的实际退出码（工具结果，is_error=true）。
- source_index: 413, source_part_index: 0, quote: "Exit: -1073741515", supports: problem——Start-Process -PassThru -Wait 交叉确认的退出码（工具结果）。
- source_index: 405, source_part_index: 0, quote: "Exit code `-1073741515` is `0xC0000135` — **DLL not found**. The `epilog.dll` isn't next to the executable. Let me check:", supports: problem——退出码到 0xC0000135（STATUS_DLL_NOT_FOUND）的解码判断（assistant 判断，需与工具结果共同使用）。
- source_index: 416, source_part_index: 0, quote: "[regex]::Matches($text, '[A-Za-z0-9_\\-]+\\.dll')", supports: action——无 dumpbin 时用字节串正则提取 DLL 导入表的命令。
- source_index: 417, source_part_index: 0, quote: "ADVAPI32.dll\r\nbcrypt.dll\r\nepilog.dll\r\nKERNEL32.dll\r\nraylib.dll", supports: verification——提取出的导入列表，显示 exe 依赖 epilog.dll 与 raylib.dll（工具结果）。
- source_index: 420, source_part_index: 0, quote: "epilog.dll", supports: problem——exe 同目录 DLL 清单中只有 epilog.dll，raylib.dll 不在其中（工具结果目录列表）。
- source_index: 426, source_part_index: 0, quote: "Line 90 tries to copy `raylib.dll` from `%ODIN_ROOT%\\vendor\\raylib\\windows\\` — but the `copy` output was suppressed with `>nul 2>&1`. The copy silently failed.", supports: action——构建脚本复制步骤静默失败的根因定位（assistant 判断，基于 build.bat 正文）。
- source_index: 431, source_part_index: 0, quote: "Copy-Item \"D:\\Odin\\dist\\vendor\\raylib\\windows\\raylib.dll\" \"D:\\DMLS\\build\\raylib.dll\" -Force", supports: action——手动把缺失 DLL 复制到 exe 目录。
- source_index: 435, source_part_index: 0, quote: "for /f \"tokens=*\" %%i in ('where odin 2^>nul') do set ODIN_BIN=%%i", supports: action——修复构建脚本：由 `where odin` 推导工具目录而非依赖未设置的环境变量。
- source_index: 453, source_part_index: 0, quote: "LINK : fatal error LNK1105: cannot close file 'D:\\DMLS\\build\\dmls.exe'; error code 1224", supports: problem——exe 被占用导致重建失败（工具结果）。
- source_index: 461, source_part_index: 0, quote: "Remove-Item -Force D:\\DMLS\\build\\dmls.exe -ErrorAction SilentlyContinue; $? ", supports: action——删除被占用的 exe 以便重建。
- source_index: 462, source_part_index: 0, quote: "True", supports: verification——删除成功（工具结果）。
- source_index: 465, source_part_index: 0, quote: "[odin] Built build\\dmls.exe\r\n[run] Starting DMLS...\r\nINFO: Initializing raylib 5.5", supports: verification——复制 DLL 并修复脚本后，构建成功且程序进入运行时初始化（工具结果）。
- source_index: 781, source_part_index: 0, quote: "dmls 43232 0.05", supports: verification——分离启动后进程持续存活（Get-Process 工具结果）。

---
name: capture-powershell-dev-server-startup-output
description: Use when 需要在非交互 PowerShell 会话里启动长驻的 `npm run dev` 类进程并在有限时间内拿到其启动或崩溃输出。Helps the agent 用 Start-Job + 有限 sleep 的方式获取完整输出、并从 PowerShell 的 NativeCommandError 包裹噪声中提取真正的错误正文。Requires PowerShell 工具权限、可前台阻塞的启动命令、已知的工作目录。Do not use when shell 是 Bash、或目标是长期常驻监控/保活进程，或输出已可直接从前台命令获得。
---
# 在非交互 PowerShell 中有界捕获 dev server 启动/崩溃输出

## Goal
目标：在非交互 PowerShell 会话中启动长驻 dev server（如 `npm run dev`）并在有限等待窗口内取得其启动或崩溃的完整输出，最终产物是一段可直接用于判定"启动成功"或"已复现某错误"的原始输出文本。

## Scope
### In scope
- 非交互 PowerShell 中以作业（`Start-Job`）方式运行长驻 Node/npm dev 命令，配合有限 `Start-Sleep` 取回输出，再 `Stop-Job`/`Remove-Job` 收尾。
- 启动命令带 `2>&1`，使 native 进程 stderr 与 stdout 一并进入作业输出。
- 从 PowerShell `NativeCommandError` 包裹（`+ CategoryInfo`、`+ FullyQualifiedErrorId`）中提取 `[Error: ...]` 等真正错误正文。
- 对"输出为空/输出被包裹"的分支处理与判定。

### Out of scope
- 非 PowerShell shell（Bash/`timeout` 等等价做法）。
- 长期常驻监控、日志落盘、进程守护与自动重启。
- 停止作业后子进程是否被完全回收的确认（轨迹未提供该验证）——若后续出现目录删除失败，进程占用只是一条未验证的怀疑，需另行验证。
- dev server 输出之外的应用层错误诊断。

## Inputs
- **启动命令**，类型：字符串，来源：项目 `package.json` scripts 或用户指定，必需：是，约束：前台长驻命令（轨迹中为 `npm run dev`），末尾需 ` 2>&1` 合并 stderr，无默认值。
- **工作目录**，类型：路径，来源：用户上下文，必需：是，约束：作业块内部要单独 `cd`/`Set-Location` 到该目录（作业不继承调用处当前位置——轨迹两种写法都在作业内重设了目录），无默认值。
- **等待秒数**，类型：整数，来源：调用方设定，必需：否，约束：覆盖启动到报错/就绪的时间窗；轨迹中取 8、10、12 三种值，均取到了输出，无默认值（建议从 8 起步）。
- **判定锚点**，类型：字符串数组，来源：调用方预期，必需：否，约束：用于在输出中定位关键内容（如 `[Error:`、脚本头 `> dev`），默认值：`[Error:` 与 `> `。
- **是否收尾停止作业**，类型：布尔，来源：调用方策略，必需：否，约束：轨迹中每次都在取回输出后 `Stop-Job` + `Remove-Job`，默认值：true。

## Outputs
### Artifacts
- **启动/崩溃输出文本**：位置——`Receive-Job` 的工具结果，格式——原始文本，可能混有 PowerShell 的 `NativeCommandError` 包裹头与 ANSI 转义序列（脚手架进度条场景常见）。
- **提取后的错误正文**：位置——会话内诊断记录，格式——以 `[Error:` 起始的块，含 `errno`、`code`、`syscall`、`path` 与 Node 版本行。

### Success criteria
- 在等待窗口内 `Receive-Job` 返回了非空输出，且输出中能定位到判定锚点（预期错误码或 dev server 启动日志）。
- 作业已按策略 `Stop-Job` + `Remove-Job` 收尾，无残留作业对象。

### Failure criteria
- 等待窗口内输出为空或不含任何锚点——需增加等待或改用其他采集方式，不得凭空推断启动结果。
- 只看到 PowerShell 包裹头就下结论（未读包裹内正文）。
- 把"取到输出"等同于"服务已健康"——输出本身可能就是崩溃栈。

## Preconditions
- 执行通道是 PowerShell 工具且会话非交互（无 TTY 可供交互式脚手架提示输入；轨迹中 `create-react-router` 因此走 `--yes` 默认项）。
- 目标命令可在前台长驻运行（dev server 类），并允许在其运行有限时间后被停止。
- 工作目录存在且可写（dev server 通常要写缓存/生成文件）。
- `Start-Job`、`Receive-Job`、`Stop-Job`、`Remove-Job` 在该会话可用；不可用则本 Skill 不适用，停止并报告。
- 用户已知该操作会启动并随后终止一次 dev server 进程；如需保留服务常驻，改用其他方案（超出本 Skill 范围）。

## Procedure
### Step 1: 以作业方式启动并限时等待
- actions：执行形如 `cd <项目根>; $job = Start-Job { Set-Location <项目根>; npm run dev 2>&1 }; Start-Sleep -Seconds <N>; Receive-Job $job; Stop-Job $job; Remove-Job $job` 的单条命令（轨迹中 N 取 8、10、12，作业块内用 `cd` 或 `Set-Location` 重设目录）。
- inputs：启动命令、工作目录、等待秒数（默认从 8 开始）。
- outputs：`Receive-Job` 返回的原始输出文本。
- cautions：作业块内必须自行切到工作目录；`2>&1` 必须写在被包裹的命令上，否则错误流不进作业输出。
- preserve：除 dev server 自身产生的缓存/生成文件外，不改动任何文件。
- 下一步条件：输出非空 → Step 2；输出为空 → 按 Decision Rules 增加等待重试。

### Step 2: 从包裹噪声中提取错误正文
- actions：在输出中定位 `[Error:` 锚点，提取其后的 `errno`、`code`、`syscall`、`path` 字段与 Node 版本行；同时保留脚本头（如 `> dev`、`> react-router dev`）以确认命令确实被触发。
- inputs：Step 1 的输出文本。
- outputs：提取后的错误正文（或"无错误锚点"的结论）。
- cautions：PowerShell 会输出 `+ CategoryInfo : NotSpecified:`、`+ FullyQualifiedErrorId : NativeCommandError` 等包裹行，它们只说明"native 进程写了 stderr"，不指示错误类型；脚手架场景的输出还可能夹带 ANSI 进度条转义序列，判读时按文本锚点匹配而非按行首格式。
- preserve：保留原始输出，不改写、不截断后覆盖。
- 下一步条件：含预期错误码 → 交付"错误已复现"；含启动日志 → 交付"已启动"；两者皆无 → 按 Decision Rules 处理。

### Step 3: 收尾与交接
- actions：确认 `Stop-Job`、`Remove-Job` 已执行；把提取结果交给后续诊断（若错误落在 `.react-router/types` 类缓存清理，转入对应诊断 Skill）。
- inputs：提取后的错误正文。
- outputs：交接记录（原始输出 + 提取正文 + 判定）。
- cautions：作业已停止不等于子进程已全部回收——该点轨迹未验证，若随后删除文件遇阻，只把"进程残留"列为待验证怀疑，不作结论。
- preserve：不删除、不覆盖既有日志或工件。
- 下一步条件：交接完成即结束；不得在未复跑验证的情况下对外声称服务可用。

## Decision Rules
### When 目标命令是长驻 dev server 且 shell 非交互
用 `Start-Job` + 有限 `Start-Sleep` + `Receive-Job` + `Stop-Job` + `Remove-Job` 的组合一次性取回输出；轨迹中该组合连续三次（等待 8/10/12 秒）都取到了完整输出。

### When 输出中出现 `+ FullyQualifiedErrorId : NativeCommandError`
按包裹内正文判读：`NativeCommandError` 只是 PowerShell 对 native stderr 的记录化包装，错误类型以 `[Error: ...]` 中的 `code` 字段为准（轨迹中分别为 `ENOTEMPTY` 与 `EPERM`）。

### When 等待窗口内 `Receive-Job` 输出为空
增大 `Start-Sleep` 秒数后重跑（轨迹中 8 秒已能捕获崩溃，10、12 秒变体同样成功）；不得在无输出时推断启动结果。

### When 需要交互确认的脚手架命令
非交互 shell 下应显式传入等价于确认的参数（轨迹中 `create-react-router ... --yes` 走了默认项并继续执行）；无法以参数绕过交互的命令（轨迹中 `create-solid` 需交互选择）则停止该路径、改为手工构建，不要在本 Skill 内做交互式抓取。

### When 输出已含预期错误码
判定为"错误已复现"，停止重复启动，转入针对该错误的诊断流程；重复运行同一命令不产生新的证据增量。

## Invariants
- 不改写、不截断后覆盖 `Receive-Job` 返回的原始输出；提取正文是额外产物，不替代原文。
- 不在未取得输出时报告启动结果，也不在只看到包裹头时报告错误类型。
- 不把"取到输出"或"作业已停止"当作服务健康或子进程已全部退出的证明。
- 不在前台直接执行长驻命令导致会话挂起（本 Skill 的既定做法就是作业 + 有限等待）。
- 不跳过收尾：`Stop-Job`、`Remove-Job` 必须执行，避免作业对象残留影响后续命令。
- 不借本 Skill 执行任何文件删除或配置修改；诊断与处置由后续流程负责。

## Common Failures
### Failure: 输出为空或不含任何锚点
- symptoms：`Receive-Job` 无内容，或只有作业元信息。
- causes：等待窗口短于启动/报错耗时，或 `2>&1` 未写在被包裹命令上导致错误流丢失（后者为推断，需以命令原文核对）。
- recovery：增加 `Start-Sleep` 秒数重跑；核对作业块内是否有 `2>&1` 与目录切换。

### Failure: 输出被 NativeCommandError 包裹，错误正文被噪声包围
- symptoms：结果以 `npm : node:internal/process/promises:394`、`At line:1 char:...`、`+ CategoryInfo ... NativeCommandError` 开头，真正的 `[Error: ...]` 夹在中间。
- causes：PowerShell 对 native 进程 stderr 的记录化包装（工具输出原文即如此呈现）。
- recovery：以 `[Error:` 为锚提取正文，读取 `errno`/`code`/`syscall`/`path` 字段后再判定错误类型。

### Failure: 输出取到的是崩溃栈而非启动日志
- symptoms：输出含 `triggerUncaughtException`、`[Error: ...]`、`Node.js vX` 等行。
- causes：dev 进程在启动阶段即异常退出——取到输出本身不代表服务可用。
- recovery：按"错误已复现"判定并转诊断流程；需要"启动成功"结论时必须另行取得启动日志。

### Failure: 作业停止后目录操作仍受阻
- symptoms：随后删除某目录报 `Directory not empty` 或 `Access is denied`。
- causes：轨迹未确认（`Stop-Job` 是否回收 node 子进程未被验证，文件系统/权限因素亦未排除）。
- recovery：不在此 Skill 内下结论；转入相应诊断流程，并把进程残留列为待验证怀疑。

## Verification
可观察检查项（不使用已完成标记）：

1. `Receive-Job` 的工具结果为非空文本，且以脚本头行开头（轨迹中为 `> dev` 与 `> react-router dev`，证明命令确实被作业触发）。
2. 输出中存在判定锚点之一：`[Error:` + 指定错误码字段（`code: 'ENOTEMPTY',` 或 `code: 'EPERM',`）用于"错误已复现"；或 dev server 启动日志（轨迹未提供成功样例，需实际取得）用于"已启动"。
3. 输出中可同时读到 `errno`、`syscall`、`path` 与 Node 版本行，说明拿到了完整错误块而非被截断的片段。
4. 同一条命令链末尾的 `Stop-Job`、`Remove-Job` 已执行（命令原文中存在这两步），会话中无遗留作业。
5. 提取的错误正文与原始输出逐字一致（引用时给出 source_index 对应的原文），未以转述替代。

## Examples
### Example 1: 8 秒窗口捕获 dev 启动期 ENOTEMPTY 崩溃（本轨迹已验证）
- input：启动命令 `npm run dev`，工作目录 `<PROJECT_ROOT>`，等待 8 秒，`2>&1` 合并错误流。
- procedure：Step 1 作业启动 → Step 2 以 `[Error:` 提取 → Step 3 收尾并交接。
- expected result：`Receive-Job` 返回以 `> dev`、`> react-router dev` 开头的文本，随后是被 `NativeCommandError` 包裹的 `[Error: ENOTEMPTY: directory not empty, rmdir '...']`、`errno: -4051,`、`code: 'ENOTEMPTY',`、`syscall: 'rmdir',` 与 `Node.js v22.20.0`；作业被 Stop/Remove。
- parameterized values：等待秒数 8；脚本头 `> dev`；错误码 `ENOTEMPTY`；项目根 `<PROJECT_ROOT>`。

### Example 2: 10/12 秒窗口的变体与错误演变
- input：同 Example 1，但等待改为 10 秒与 12 秒（作业块内用 `Set-Location`）。
- procedure：重复 Step 1–3。
- expected result：两种等待都取到输出；在缓存目录已被部分删除后，捕获到的错误由 `ENOTEMPTY`（`rmdir`）变为 `EPERM`（`scandir`、`errno: -4048`），说明同一采集方式可稳定复现并跟踪错误状态演变。
- parameterized values：等待秒数 10、12；错误码 `EPERM`；`syscall: 'scandir'`。

### Example 3: 交互式脚手架命令的处理（本轨迹已验证的分支）
- input：非交互 shell 中运行 `npx create-react-router@latest . --yes`。
- procedure：Step 1 作业/命令方式启动并取回输出；Step 2 判读。
- expected result：输出含 `Shell is not interactive.` 并标注 `Using default options. This is equivalent to running with the --yes flag.`，命令继续执行到模板复制与依赖安装阶段；对比之下 `create-solid` 无等价参数、需交互选择，应停止该路径（轨迹中该任务被停止后转为手工搭建）。
- parameterized values：脚手架命令、`--yes` 参数。

## Evidence
来源：file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`（同一切片，source_part_index 均为 0）。

**problem**
1. source_index 45，quote：`Shell is not interactive.`，supports：会话为非交互 shell，交互式提示不可用，必须用非交互方式启动命令并取回输出（同事件标注等价参数为 `--yes`）。
2. source_index 83，quote：`+ FullyQualifiedErrorId : NativeCommandError`，supports：native 进程 stderr 被 PowerShell 包裹成记录，错误类型需从包裹正文判定。

**action**
3. source_index 81，quote：`npm run dev 2>&1`，supports：在作业块内以 `2>&1` 启动 dev server，使 stderr 进入作业输出（该命令为 `Start-Job { ... }` 的被包裹命令）。
4. source_index 81，quote：`Start-Sleep -Seconds 8; Receive-Job $job; Stop-Job $job; Remove-Job $job`，supports：有限等待 8 秒后取回输出并收尾的完整动作序列。
5. source_index 96，quote：`Start-Sleep -Seconds 10; Receive-Job $job; Stop-Job $job; Remove-Job $job`，supports：等待 10 秒的同型变体。
6. source_index 121，quote：`Start-Sleep -Seconds 12; Receive-Job $job -ErrorAction SilentlyContinue; Stop-Job $job; Remove-Job $job`，supports：等待 12 秒并容忍接收错误的变体。
7. source_index 45，quote：`npx create-react-router@latest . --yes 2>&1`，supports：非交互场景下为脚手架命令显式传入确认参数的做法。
8. source_index 205，quote：`Successfully stopped task:`，supports：无法以参数绕过交互的脚手架命令被终止并改道（对应 Decision Rules 的交互分支）。

**verification**
9. source_index 83，quote：`> react-router dev`，supports：作业输出中出现 npm 脚本头，证明命令在等待窗口内确实被触发并取回了输出。
10. source_index 83，quote：`code: 'ENOTEMPTY',`，supports：8 秒窗口捕获到完整错误块（同事件含 `errno: -4051,`、`syscall: 'rmdir',`、`Node.js v22.20.0`），"错误已复现"判定成立。
11. source_index 97，quote：`code: 'EPERM',`，supports：同一采集方式在后续运行中再次捕获到错误正文（同事件含 `syscall: 'scandir',`），可跟踪错误状态从 ENOTEMPTY 演变为 EPERM。
12. source_index 45，quote：`Template copied`，supports：`--yes` 分支下脚手架流程确实推进（同事件其后为 `Dependencies installing with npm...`），证明该非交互启动方式能取得阶段性真实输出。

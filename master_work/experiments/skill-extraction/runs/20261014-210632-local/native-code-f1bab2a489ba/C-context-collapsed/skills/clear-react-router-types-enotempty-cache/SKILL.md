---
name: clear-react-router-types-enotempty-cache
description: Use when Windows 上 `npm run dev` 因 `.react-router/types` 目录 ENOTEMPTY/EPERM 崩溃、且常规删除工具全部失败时。Helps the agent 定位真正执行 rmdir 的 typegen 清理代码、判断哪些修复路径在该环境下不可用、并在获授权时用已验证的整树删除完成重置。Requires 项目根目录、PowerShell/Git Bash 命令权限、删除或修改 node_modules 的用户授权。Do not use when 错误路径不在 `.react-router/types`、或问题只是应用代码的类型错误。
---
# React Router typegen 缓存 ENOTEMPTY/EPERM 诊断与清理

## Goal
目标：解决 Windows 环境下 `npm run dev` 启动 React Router 项目时在清理 `.react-router/types` typegen 缓存目录触发的 `ENOTEMPTY`/`EPERM` 崩溃；最终产物是一份已定位的调用点清单、一条经验证可行（或明确标注未验证）的处理路径，以及与该路径匹配的可观察验证结果。

## Scope
### In scope
- `npm run dev`（`react-router dev`）或 `react-router typegen` 运行时对 `<项目根>/.react-router/types` 执行删除失败而崩溃的诊断。
- 在 `node_modules/@react-router/dev/dist` 中定位执行 `fs.promises.rm(typesDirectory(ctx), { recursive: true, force: true })` 的具体调用点。
- 该环境下已证实不可用的修复路线（ACL/ownership 类）的识别与止损。
- 用户授权的整体重置路径：先列出并排除需保留文件、再对整项目树执行删除、最后用目录列表验证。
- 与之配套的验证方式：区分"typegen/tsc 局部通过"与"dev server 真正可启动"。

### Out of scope
- 通用的 Windows 文件锁排查（杀进程、句柄工具），轨迹未提供此类已验证操作。
- React Router 应用代码、路由配置或类型错误的修复。
- 未获授权时修改 `node_modules`、删除项目文件或改动任何配置。
- Linux/macOS 上的同类错误处理（轨迹仅覆盖 Windows + PowerShell/Git Bash）。

## Inputs
- **崩溃输出文本**，类型：字符串，来源：`npm run dev` 的工具结果（stderr/stdout 合并），必需：是，约束：必须包含错误码（`ENOTEMPTY` 或 `EPERM`）且 `path`/`syscall` 指向 `.react-router\types` 目录，否则不适用本 Skill，无默认值。
- **项目根目录**，类型：路径，来源：用户上下文或当前工作目录，必需：是，约束：含 `package.json` 与 `node_modules/@react-router/dev`，无默认值。
- **Shell 环境**，类型：枚举（PowerShell / Git Bash），来源：执行环境实测，必需：是，约束：轨迹中两条路径均在 Windows 上分别使用 PowerShell 与 Bash 工具，无默认值。
- **需保留的文件清单**，类型：字符串数组，来源：用户指示，必需：否，约束：仅在走"整体重置"分支时需要；轨迹中的取值为 `DESIGN.MD`、`CLAUDE.MD`，默认值：无（即无文件需保留）。
- **授权级别**，类型：枚举（只读诊断 / 允许改 node_modules / 允许删除项目文件），来源：用户批准，必需：是，约束：未明确授权时只允许只读诊断步骤，无默认值。
- **Node.js 版本**，类型：字符串，来源：崩溃输出末行，必需：否，约束：仅作环境记录（轨迹中为 `Node.js v22.20.0`），无默认值。

## Outputs
### Artifacts
- **崩溃日志文本**：位置——会话内工具结果，格式——原始 PowerShell/npm 输出（含被 `NativeCommandError` 包裹的 `[Error: ...]` 正文）。
- **清理调用点清单**：位置——会话内诊断记录，格式——`文件路径:行号: 调用语句`（轨迹中为 `vite.js:1344` 与 `cli/index.js:1339`、`cli/index.js:1348`）。
- **处理路径记录**：位置——会话内，格式——所选分支（整树删除 / node_modules 补丁 / 放弃并报告）+ 每步命令的工具结果原文。
- **（整树删除分支）清理后的目录列表**：位置——删除后的 `ls` 工具结果，格式——纯文件名行（轨迹中为 `CLAUDE.MD`、`DESIGN.MD`）。

### Success criteria
- `npm run dev` 的输出中不再出现 `ENOTEMPTY` 或 `EPERM` 且路径指向 `.react-router/types`，并出现 dev server 启动日志（轨迹未提供该成功样例，需自行取得）。
- 或（整体重置分支）删除命令返回成功标记，且随后 `ls` 只列出需保留的文件。
- 所引用的每一步都有对应工具结果原文支撑，未验证的补丁不被报告为"已修复"。

### Failure criteria
- 目标目录在无授权情况下仍不可删除，且无可继续的授权动作——停止并报告已观测到的错误原文。
- 局部命令（如 `typecheck`）通过就宣称 dev server 可启动。
- 把未完成验证的 node_modules 补丁当作成功结果汇报。

## Preconditions
- 执行环境为 Windows，可同时使用 PowerShell 工具与 Git Bash 工具（轨迹中两条命令通道的失败/成功表现不同，需两条通道都可用）。
- 项目根目录可访问，`node_modules/@react-router/dev/dist` 存在且可读——否则 Step 3 无法定位调用点；不满足则停止并报告。
- 崩溃输出可获得：至少一次 `npm run dev` 的完整输出（含 `[Error: ...]` 正文），否则无法确认适用本 Skill；不满足则停止并报告。
- 删除类操作（Step 4 的整树删除）与 `node_modules` 修改（Step 4 的补丁候选）必须先获得用户明确授权；未授权时只执行 Step 1–3 只读诊断。
- 需保留文件清单（如 `DESIGN.MD`、`CLAUDE.MD`）在走整树删除前必须已确认；无法确认则不得执行删除。
- `npm`/`node` 命令可运行；轨迹中观测到的版本为 Node.js v22.20.0、npm 11.8.0（仅作环境对照，不是硬性门槛）。

## Procedure
### Step 1: 有界复现崩溃并拿到错误正文
- actions：在项目根用 PowerShell 作业方式运行 dev 命令：`Start-Job { ... npm run dev 2>&1 }; Start-Sleep -Seconds 8; Receive-Job $job; Stop-Job $job; Remove-Job $job`（轨迹中等待 8、10、12 秒三种取值均取到了输出）。
- inputs：项目根目录、启动命令（默认 `npm run dev`）。
- outputs：崩溃输出文本（工件：崩溃日志）。
- cautions：PowerShell 会把 native 进程的 stderr 包成 `NativeCommandError` 记录，`+ CategoryInfo`/`+ FullyQualifiedErrorId` 是包裹噪声，真正的错误正文在 `[Error: ...]` 段；必须读包裹内部，不要只看 PowerShell 的错误头。
- preserve：本步不修改任何文件。
- 下一步条件：若错误码为 `ENOTEMPTY`/`EPERM` 且路径落在 `.react-router\types` 下 → Step 2；否则本 Skill 不适用，停止。

### Step 2: 用可用的观察命令确认故障范围
- actions：对错误中的目录做列举。轨迹中 `ls` 对 `+types` 子目录返回 `Permission denied`，而 `cmd /c "dir /a <目录>"` 能列出内容（观察到 `routes` 下只有一个 `+types` 目录、`0 File(s)`）——两种列举结果都要记录。
- inputs：错误文本中的 `path`。
- outputs：目录结构观察记录（哪些条目存在、是否为空、哪个工具被拒）。
- cautions："`0 File(s)` 却无法列举/删除"是本轨迹的实际观察，其成因轨迹未确认；不要据此断言文件被锁或被占用。
- preserve：只读操作。
- 下一步条件：确认故障条目就是 typegen 缓存目录（`<项目根>/.react-router/types`）→ Step 3。

### Step 3: 定位执行删除的调用方
- actions：(a) 在 `node_modules/@react-router/dev/dist` 内检索 `typesDirectory`，确认 `typesDirectory(ctx)` 即 `<项目根>/.react-router/types`；(b) 读取 `vite.js` 中 `watch()` 内的清理语句与 `cli/index.js` 中 `run()`、`watch()` 内的清理语句，形如 `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`。
- inputs：项目根目录、包名（轨迹中为 `@react-router/dev`，版本随 scaffold 而异）。
- outputs：调用点清单（文件:行号:语句）。
- cautions：行号随包版本变化（轨迹中为 `vite.js:1344`、`cli/index.js:1339` 与 `1348`），必须以实测检索为准；崩溃发生在 dev 运行期，并不代表应用路由代码有问题——错误路径始终指向缓存目录。
- preserve：只读检索与读取。
- 下一步条件：拿到调用点清单 → Step 4 做分支决策。

### Step 4: 按授权选择处理分支
- actions（分支 A：只读诊断到此为止）：报告调用点清单与不可用路线（见 Decision Rules），等待用户授权。
- actions（分支 B：整树重置，需删除授权）：(1) 先列出项目文件并排除需保留的文档；(2) 对整项目树执行 Git Bash `rm -rf <除保留文件外的全部条目> && echo done`——轨迹中该方式在 `+types` 目录此前无法删除的情况下仍成功；(3) 立即 `ls` 验证。
- actions（分支 C：保留项目、抑制清理错误，需改 node_modules 授权）：在 Step 3 找到的每个调用点为 `rm(...)` 追加 `.catch(() => {})`（轨迹中 3 处编辑均返回 `has been updated successfully.`）。
- inputs：授权级别、需保留文件清单（分支 B）、调用点清单（分支 C）。
- outputs：分支记录 + 每步工具结果原文。
- cautions：分支 C 在本轨迹中**未完成验证**——随后那次用于验证的 `npm run dev` 被用户拒绝执行；不得把分支 C 当作已生效。分支 B 与更早一次针对子目录的 `rm -rf` 失败之间的差异（时间、进程状态）轨迹未确认，不要归因。
- preserve：只删除授权范围内的路径；保留文件清单中的文件不得触碰。
- 下一步条件：执行 Step 5 与所选分支匹配的验证。

### Step 5: 与分支匹配的验证
- actions：分支 B：检查删除命令输出（轨迹中为 `done`）并 `ls` 确认只剩保留文件（轨迹中为 `CLAUDE.MD`、`DESIGN.MD`）；分支 C：重新运行 `npm run dev`，确认输出不再含 `ENOTEMPTY`/`EPERM` 且出现启动日志。
- inputs：分支记录。
- outputs：验证证据（工具结果原文）。
- cautions：`npm run typecheck`（`react-router typegen && tsc`）通过只证明 typegen+tsc 这一步，不能替代 dev 启动验证——本轨迹中 typecheck 通过后 dev 依旧崩溃。
- preserve：不改写任何已有日志或结果。
- 下一步条件：匹配验证通过 → 报告成功；未通过 → 按 Failure criteria 报告失败原文。

## Decision Rules
### When 崩溃输出的 `path` 指向 `<项目根>/.react-router/types`
优先定位 typegen 的清理逻辑（Step 3），不要先去改应用路由或组件代码——崩溃发生在缓存目录删除阶段。

### When `takeown` 返回 `ERROR: File ownership cannot be applied on insecure file systems;` / `there is no support for ACLs.`
立即放弃 ownership/ACL 修复路线：该卷不支持 ACL，`icacls`/`takeown` 类方案在本环境不可用，继续尝试只会重复失败。

### When `rm -rf`、`Remove-Item -Recurse -Force`、`cmd rd /s /q`、`node fs.rmSync`、`robocopy /MIR` 对同一 `+types` 目录全部报 `Directory not empty` 或 `Access is denied`
停止继续枚举删除工具，转为定位触发删除的调用方（Step 3），并把分支决策交给用户授权；轨迹中这五种方式对 `+types` 均失败。

### When 用户已授权重建/换栈且确认了需保留的文件清单
走分支 B：先列出（排除保留文件）→ 整项目树 `rm -rf` → `ls` 验证。轨迹中这是唯一取得成功工具结果的删除路径（`done`，随后 `ls` 仅剩 `CLAUDE.MD`、`DESIGN.MD`）。

### When 项目必须保留且缓存目录确认不可删
可考虑分支 C（在 `@react-router/dev` 的各清理调用点追加 `.catch(() => {})`），但必须随后重新运行 `npm run dev` 并拿到无 `ENOTEMPTY`/`EPERM` 的启动输出才算完成；本轨迹该验证被用户拒绝，效果未知。

### When `npm run typecheck` 或 `npm run build` 通过
仍需单独运行 `npm run dev` 验证启动：本轨迹中 typecheck（`react-router typegen && tsc`）通过后，紧接着的 dev 运行仍以 `ENOTEMPTY` 崩溃。

### When 输出只看到 PowerShell 的 `NativeCommandError` 包裹头
按包裹正文中的 `[Error: ...]` 判断错误码与路径，不要以 PowerShell 错误头作为错误类型依据。

## Invariants
- 不修改与本问题无关的文件：应用源码、设计文档、未授权的配置一律不动。
- 未获授权前不删除任何文件、不改写 `node_modules`；走整树删除时，需保留文件清单中的文件必须先被排除并事后核对。
- 不跳过与所选分支匹配的验证：分支 B 必须有 `ls` 结果，分支 C 必须有重新运行 `npm run dev` 的输出。
- 不把推测当作事实：`+types` 不可删的确切成因、`Stop-Job` 是否回收了 node 子进程、整树删除为何在此前子目录删除失败后成功——轨迹均未给出确认，不得写成结论。
- 不把局部成功当作整体成功：typecheck/build 通过不等于 dev server 可启动。
- 不报告未经验证的成功：分支 C 的补丁在本轨迹中没有完成验证，任何引用本 Skill 的执行者必须自行验证后才能声称修复。
- 失败时保留并引用原始错误文本（错误码、syscall、path），不以改写或省略后的描述替代。

## Common Failures
### Failure: `rm -rf` 对缓存子目录报 `Directory not empty`
- symptoms：`rm: cannot remove '/d/IceBerg/.react-router/types/app/routes': Directory not empty`，退出码非 0。
- causes：轨迹未确认（未做进程/句柄排查，不能断言是占用还是文件系统状态）。
- recovery：不要在同一子目录上反复换删除工具；转 Step 3 定位调用方，或在获得授权且确认保留清单后走整树删除分支（该分支在本轨迹中成功）。

### Failure: `+types` 目录列出为 0 文件却无法列举/删除
- symptoms：`ls: cannot open directory '.../+types/': Permission denied`；`dir /a` 显示 `0 File(s)`；`rmdir` 返回 `Access is denied.`（退出码 5）；`robocopy /MIR` 报 `ERROR 5 (0x00000005) Deleting Extra Directory`。
- causes：轨迹未确认。
- recovery：停止枚举删除工具；按 Decision Rules 转入调用方定位或授权后的整树删除。

### Failure: `takeown`/`icacls` 修复权限失败
- symptoms：`takeown : ERROR: File ownership cannot be applied on insecure file systems;`、`there is no support for ACLs.`、`icacls : Invalid parameter "(OI)(CI)F"`，后续 `rd` 仍 `Access is denied.`。
- causes：工具输出已给出——该文件系统不支持 ACL（另注：icacls 参数在该调用方式下也未被正确解析）。
- recovery：放弃 ACL/ownership 路线，改走 Decision Rules 中的其余分支。

### Failure: 局部验证通过但 dev 启动仍崩溃
- symptoms：`npm run typecheck` 输出 `> typecheck` / `> react-router typegen && tsc` 无错误，随后 `npm run dev` 仍抛 `ENOTEMPTY`。
- causes：typecheck 只覆盖 typegen+tsc，不覆盖 dev 运行期的类型生成 watcher 清理流程。
- recovery：以 `npm run dev` 的实际输出作为最终验证，不以 typecheck/build 结论替代。

### Failure: PowerShell 包裹噪声掩盖错误正文
- symptoms：工具结果以 `npm : node:internal/process/promises:394`、`+ FullyQualifiedErrorId : NativeCommandError` 开头，真正的 `[Error: ...]` 被埋在中间。
- causes：PowerShell 对 native 进程 stderr 的记录化输出。
- recovery：读取包裹内部正文，按 `[Error:` 锚点提取错误码、syscall 与 path。

## Verification
可观察检查项（逐项对应所选分支，不使用已完成标记）：

1. 崩溃复现输出中存在 `[Error: ENOTEMPTY` 或 `[Error: EPERM`，且其 path 位于 `.react-router\types` 下，并含 `errno`、`code`、`syscall` 字段与 Node 版本行。
2. 调用点清单至少包含一处 `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`，且检索结果给出 `typesDirectory` 的定义为 `Path3.join(ctx.rootDirectory, ".react-router/types")`。
3. （分支 B）删除命令的工具结果为成功标记（轨迹中为 `done`）；紧随其后的 `ls` 输出只包含需保留的文件名（轨迹中两行：`CLAUDE.MD`、`DESIGN.MD`），不含 `node_modules`、`.react-router` 等被删条目。
4. （分支 C）重新运行 `npm run dev` 的工具结果中：不再出现 `ENOTEMPTY`/`EPERM`，并出现 dev server 启动日志；这是判定修复生效的唯一充分检查——typecheck/build 输出不能替代。
5. （只读诊断分支）交付物包含原始错误文本、目录列举观察（`dir /a` 结果）、调用点清单三类工具结果原文，且明确标注哪些路线在本环境已证实不可用（ACL 类）、哪些结论未验证。
6. 报告内容与证据一致性抽查：任何"已修复"表述都能对应到第 3 或第 4 项的工具结果；否则改为"未验证"。

## Examples
### Example 1: 定位崩溃来源到 typegen 清理调用点（本轨迹已验证的诊断）
- input：`npm run dev` 输出 `[Error: ENOTEMPTY: directory not empty, rmdir '...react-router\types\app\routes']`，项目根 `<PROJECT_ROOT>`，包 `@react-router/dev`。
- procedure：Step 1 有界复现 → Step 2 `dir /a` 观察 → Step 3 在 `node_modules/@react-router/dev/dist` 检索 `typesDirectory` 并读取 `vite.js` 的 `watch()`。
- expected result：得到 `typesDirectory(ctx)` = `<PROJECT_ROOT>/.react-router/types`，以及 `vite.js` 与 `cli/index.js` 中共 3 处 `await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`（分别位于 `watch()`、`run()`、`watch()`）。
- parameterized values：包名 `@react-router/dev`（轨迹中为 create-react-router@7.15.1 带入）、行号 `1344`/`1339`/`1348`（随版本变化）、缓存目录 `.react-router/types`、错误码 `ENOTEMPTY`（errno -4051）或 `EPERM`（errno -4048）。

### Example 2: 用户授权换栈后的整树重置（本轨迹已验证的删除路径）
- input：用户明确要求整体重建并保留设计文档（轨迹中保留 `DESIGN.MD`、`CLAUDE.MD`）；此前 5 种删除方式均对 `+types` 失败。
- procedure：Step 4 分支 B——先列出项目文件并排除保留文档 → 在项目根执行 `rm -rf <其余全部条目> && echo "done"` → Step 5 `ls` 核对。
- expected result：删除命令输出 `done`；`ls` 输出只有 `CLAUDE.MD` 与 `DESIGN.MD` 两行，`.react-router`、`node_modules` 等均已移除。
- parameterized values：保留清单（2 个 Markdown 文档）、删除工具（Git Bash `rm -rf`）、验证命令 `ls /d/IceBerg/`。

### Example 3: 抑制清理错误的补丁（已应用、**未验证**）
- input：项目必须保留、缓存不可删，且已获修改 `node_modules` 授权。
- procedure：Step 4 分支 C——在 Step 3 得到的 3 个调用点把 `rm(typesDirectory(ctx), { recursive: true, force: true });` 改为追加 `.catch(() => {})`；随后必须重新运行 `npm run dev`。
- expected result：编辑工具返回 `has been updated successfully.`（本轨迹 3 处均如此）；**关键**：修复生效必须由下一次 `npm run dev` 的无错误启动输出证明——本轨迹中该次运行被用户拒绝，故本例只证明"编辑写入"，不证明"问题解决"。
- parameterized values：文件 `vite.js`、`cli/index.js`；验证命令 `npm run dev`。

## Evidence
来源：file_id `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`（同一切片，source_part_index 均为 0）。

**problem**
1. source_index 83，quote：`[Error: ENOTEMPTY: directory not empty, rmdir '`，supports：`npm run dev` 在删除 typegen 缓存目录时崩溃（错误正文同事件还含 `errno: -4051,`、`code: 'ENOTEMPTY',`、`syscall: 'rmdir',` 与 `Node.js v22.20.0`）。
2. source_index 89，quote：`rm: cannot remove '/d/IceBerg/.react-router/types/app/routes': Directory not empty`，supports：对出错子目录直接 `rm -rf` 失败，说明换更暴力的单目录删除不能解决。
3. source_index 93，quote：`ls: cannot open directory '/d/IceBerg/.react-router/types/app/routes/+types/': Permission denied`，supports：`+types` 子目录连列举都被拒，故障条目定位到该子树。
4. source_index 125，quote：`ERROR 5 (0x00000005) Deleting Extra Directory`，supports：`robocopy /MIR` 镜像空目录的方式同样无法删除 `+types`（同事件含 `Access is denied.`）。
5. source_index 105，quote：`ERROR: File ownership cannot be applied on insecure file systems;`，supports：`takeown` 路线在该卷不可用（同事件含 `there is no support for ACLs.`）。
6. source_index 79，quote：`> react-router typegen && tsc`，supports：typecheck 局部步骤当时无错误输出，而随后 source_index 83 的 dev 运行仍崩溃——局部验证不覆盖运行期。

**action**
7. source_index 148，quote：`981:  return Path3.join(ctx.rootDirectory, ".react-router/types");`，supports：确认 `typesDirectory` 就是 `<项目根>/.react-router/types`，即错误路径所属目录。
8. source_index 155，quote：`1344:  await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`，supports：`vite.js` 中 dev/typegen watcher 每次启动执行的清理语句，是 ENOTEMPTY 的直接来源（同事件给出 `typesDirectory(ctx)` 的全部引用行）。
9. source_index 167，quote：`1339:  await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true });`，supports：`cli/index.js` 的 `run()` 内同类调用点（同事件另有 `1348:` 的 `watch()` 调用点）。
10. source_index 160，quote：`await import_promises.default.rm(typesDirectory(ctx), { recursive: true, force: true }).catch(() => {});`，supports：分支 C 的补丁动作内容（抑制清理失败）。
11. source_index 164，quote：`has been updated successfully.`，supports：`vite.js` 编辑已写入（同源还有 172、174 两处 `cli/index.js` 编辑成功结果）——只证明写入，不证明生效。
12. source_index 189（命令）与 source_index 190，quote：`done`，supports：分支 B 的关键动作——对整项目树（排除保留文档）执行 `rm -rf ... && echo "done"` 返回成功标记。

**verification**
13. source_index 194，quote：`CLAUDE.MD
DESIGN.MD`，supports：删除后的 `ls` 只列出两个保留文档，证明含此前不可删的 `.react-router` 在内的整树已按授权清理完成（分支 B 验证通过）。
14. source_index 177，quote：`The user doesn't want to proceed with this tool use.`，supports：补丁之后那次用于验证的 `npm run dev` 被拒绝执行——分支 C 在本轨迹中没有完成验证，不得当作已修复。
15. source_index 97，quote：`code: 'EPERM',`，supports：清理失败在后续运行中演变为 `EPERM scandir`（同事件含 `syscall: 'scandir',`），说明故障在该子树持续存在。

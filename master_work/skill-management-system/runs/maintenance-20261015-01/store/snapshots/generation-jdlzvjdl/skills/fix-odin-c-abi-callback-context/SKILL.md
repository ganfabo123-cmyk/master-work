---
name: fix-odin-c-abi-callback-context
description: Use when an Odin build fails with "'context' has not been defined within this scope" inside a proc "c" callback. Helps the agent restore calls that depend on implicit context by initializing context at callback entry and switching to the non-deprecated runtime import. Requires the failing build log and the ability to edit and rebuild the Odin project. Do not use when the same error occurs in normal Odin procs, or for unrelated undeclared-name errors.
triggers:
  - "'context' has not been defined within this scope"
  - "runtime.default_context()"
---
# Fix Odin 'context' Undefined Errors in proc "c" Callbacks

## Goal
修复 Odin 构建错误 “'context' has not been defined within this scope, but is required for this procedure call”——该错误出现在 `proc "c"` ABI 回调内部——最终产物是一次不含该错误的完整成功构建。

## Scope
### In scope
- 判定 “'context' has not been defined within this scope” 报错位于 `proc "c"` ABI 回调内。
- 在回调函数体首行显式赋值 `context = runtime.default_context()`。
- 处理随之而来的 import 问题：`"core:runtime"` 已被标记 deprecated、应改用 `"base:runtime"`。
- 重新构建，确认该错误消失且整体构建成功。

### Out of scope
- 普通 Odin proc 中的未定义名/拼写错误（机制不同）。
- c ABI 回调的签名、Epilog FFI 接口本身的改动。
- 构建中出现的其他类别错误（缺 import、字符串拼接限制、栈帧警告等）。

## Inputs
1. **构建错误输出**（string，来源：构建脚本的 stderr/exit 1 输出，必需，约束：需包含 `Error: 'context' has not been defined within this scope` 及文件行号；默认值：无）。
2. **回调源文件**（file，来源：报错行号指向的 `.odin` 文件，必需，约束：该 proc 声明为 `proc "c"`；默认值：无）。
3. **Odin 工具链目录**（string，来源：编译器安装位置（如 `D:\Odin\dist`），用于确认可用 import 路径，可选；默认值：无）。
4. **构建命令**（string，来源：项目构建脚本（如 `build.bat`），必需，约束：改完必须重跑；默认值：无）。

## Outputs
### Artifacts
- **修改后的回调源文件**：`proc "c"` 回调首行包含 `context = runtime.default_context()`；对应文件 import 使用 `base:runtime`（若原为 `core:runtime` 则已替换）。
- **成功构建日志**：构建脚本退出码 0 并输出二进制产物行（如 `[odin] Built build\dmls.exe`）。

### Success criteria
- 构建输出中不再出现 `Error: 'context' has not been defined within this scope`。
- 整体构建成功并产出可执行文件。

### Failure criteria
- 该错误在其他 c ABI 回调中重复出现（改漏了调用点）。
- 只修了 import 未在回调体内赋值 context，错误依旧。
- 构建仍因其他错误失败（本 skill 不覆盖）。

## Preconditions
- 拥有完整构建输出，且其中确有 `Error: 'context' has not been defined within this scope, but is required for this procedure call`。
- 报错所在 proc 的声明确认为 `proc "c"`（c ABI 回调无隐式 context）——不满足则说明机制不同，停止并按其他错误处理。
- 具备编辑该 `.odin` 文件并重新运行构建的权限。
- Odin 工具链目录可枚举（用于确认 `base:runtime` 路径存在），轨迹中以 `D:\Odin\dist\core` 目录列表方式验证。

## Procedure
### Step 1: 定位报错回调并确认机制
- actions: 读取构建输出，记录 `Error: 'context' has not been defined within this scope, but is required for this procedure call` 的文件与行号；打开该行所在 proc，确认声明形如 `proc "c" (soln: ^..., ud: rawptr) -> ...`。
- inputs: 构建错误输出。
- outputs: 回调名、文件、行号、机制判定（c ABI 回调）。
- cautions: 同样的文案若出现在普通 proc 中属于未定义名问题，机制不同，不走本流程。
- next: 确认是 c ABI 回调 → Step 2；否则停止并另案处理。

### Step 2: 在回调入口显式初始化 context
- actions: 在该 proc 体的第一行加入 `context = runtime.default_context()`；import 列表加入 `runtime`（`import "base:runtime"` 或先 `import "core:runtime"`）。
- inputs: 回调源文件。
- outputs: 回调内可解析 `context`。
- cautions: 仅添加 import 不够——必须在 proc 体内赋值；一个构建里可能有多个同类回调，逐个检查（案例中同一文件的同一回调一处，其它回调原本已有该赋值）。
- preserve: 不改回调签名、FFI 结构与业务逻辑。
- next: Step 3。

### Step 3: 处理 runtime import 的弃用提示
- actions: 若构建输出 `import "core:runtime" has been deprecated in favour of "base:runtime"`，将该 import 改为 `import "base:runtime"`。
- inputs: 新一轮构建输出。
- outputs: 不再出现该 deprecated 警告。
- cautions: 这是警告而非错误，但它指示了推荐路径，顺手改掉避免后续清理。
- next: Step 4。

### Step 4: 重建验证
- actions: 重新运行构建脚本，通读全部输出。
- inputs: 构建脚本。
- outputs: 构建结果（成功行或残余错误清单）。
- cautions: 构建成功只证明编译期问题解决；运行时行为需另行验证（不在本 skill 范围）。
- next: 输出中无该 context 错误且构建成功 → 结束；仍有同文案错误 → 回到 Step 1 检查是否漏改回调。

## Decision Rules
### When 报错位于 `proc "c"` 回调内
在该 proc 体首行写 `context = runtime.default_context()`；这是 c ABI 无隐式 context 的直接对策。

### When 构建提示 `import "core:runtime" has been deprecated in favour of "base:runtime"`
改用 `import "base:runtime"`，不要保留弃用路径。

### When 同一文案出现在普通 Odin proc 中
不适用本流程：那是普通的未定义名问题，需要按拼写/作用域另行定位。

### When 修完仍有同文案错误
说明还有其他 c ABI 回调未加赋值：用构建输出逐个行号处理，不要只修第一个。

### When 仅添加 runtime import 而错误依旧
import 只提供名字，必须在 proc 体内赋值；回到 Step 2 补上。

## Invariants
- 不用 import 替代 proc 体内赋值；两者缺一不可。
- 不修改 c ABI 回调的签名、FFI 结构体或跨语言接口约定。
- 不在普通 proc 里添加 `runtime.default_context()` 来掩盖真正的未定义名错误。
- 不跳过重建验证，不把“改完了”当“修好了”。
- 除 context 相关改动外不动无关代码。

## Common Failures
### Failure: 添加了 runtime import 但错误依旧
- symptoms: 构建仍报 `Error: 'context' has not been defined within this scope`。
- causes: import 只引入名字，c ABI proc 内不会隐式存在 `context` 变量。
- recovery: 在 proc 体首行加 `context = runtime.default_context()`。

### Failure: 保留 `"core:runtime"` 触发弃用警告
- symptoms: 构建输出 `Syntax Warning: import "core:runtime" has been deprecated in favour of "base:runtime"`。
- causes: 该包路径已被官方迁移到 `base:` collection。
- recovery: 改 import 为 `base:runtime`。

### Failure: 只修了第一个回调，构建仍报同文案
- symptoms: 同文件/同包另一个 c ABI 回调在下一次构建报同样错误。
- causes: 每个 c ABI proc 都需要独立赋值 context。
- recovery: 按构建输出的行号逐个补齐。

### Failure: 该错误其实来自普通 proc 的拼写/作用域问题
- symptoms: 报错行所在 proc 并非 `proc "c"`。
- causes: 机制不同（普通未定义名）。
- recovery: 停止本流程，按未定义名错误另行定位（轨迹未覆盖此分支）。

## Verification
可观察检查项（不使用 [x]）：
- 新一轮构建输出中检索不到 `Error: 'context' has not been defined within this scope`。
- 构建输出中检索不到 `import "core:runtime" has been deprecated`（若已切换 import）。
- 构建脚本以成功结束并打印产物行（案例中为 `[odin] Built build\dmls.exe`），退出码为 0。
- 每个 `proc "c"` 回调的函数体首行均可见 `context = runtime.default_context()`（源码检查）。
- 说明：以上只覆盖编译期；该回调的运行时行为（Epilog 查询回调）不在本 skill 的验证范围。

## Examples
### Example 1: Epilog 关系查询回调缺 context
- input: 构建输出 `D:/DMLS/src/api_snapshot.odin(225:17) Error: 'context' has not been defined within this scope, but is required for this procedure call`，并给出 `Suggestion: 'context = runtime.default_context()'`；报错行位于 `_rel_snap_cb :: proc "c" (...)`。
- procedure: Step 1 确认是 c ABI 回调 → Step 2 在函数体首行加 `context = runtime.default_context()` 并 `import "core:runtime"` → Step 3 构建提示 `core:runtime` 弃用，改 `import "base:runtime"` → Step 4 重建。
- expected result: 该错误消失，构建成功（`[odin] Built build\dmls.exe`）。
- parameterized values: 文件名（`api_snapshot.odin`）、回调名（`_rel_snap_cb`）、行号（225）、import 路径（`base:runtime`）。

### Example 2: 一轮构建里同类错误只改了一处
- input: 第一次构建仍列出其他 `Error: 'context' has not been defined ...` 行号。
- procedure: 按行号逐个打开对应 `proc "c"`，补赋值，再构建。
- expected result: 全部同类错误清零，构建成功。
- parameterized values: 报错行号集合。

## Evidence
file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02

- source_index: 676, source_part_index: 0, quote: "Error: 'context' has not been defined within this scope, but is required for this procedure call", supports: problem——构建失败的具体错误（工具结果，报错位置 api_snapshot.odin:225，位于 `_rel_snap_cb`）。
- source_index: 676, source_part_index: 0, quote: "Suggestion: 'context = runtime.default_context()'", supports: problem——编译器给出的修复建议（工具结果）。
- source_index: 681, source_part_index: 0, quote: "_rel_snap_cb :: proc \"c\" (soln: ^EpilogSolution, ud: rawptr) -> EpilogSignal {", supports: problem——报错回调确为 `proc "c"` c ABI（Edit 的 old_string，源码正文）。
- source_index: 681, source_part_index: 0, quote: "    context = runtime.default_context()", supports: action——在 c ABI 回调首行显式初始化 context。
- source_index: 685, source_part_index: 0, quote: "import \"core:runtime\"", supports: action——为该文件添加 runtime import。
- source_index: 746, source_part_index: 0, quote: "import \"core:runtime\" has been deprecated in favour of \"base:runtime\"", supports: problem——随后构建提示该 import 路径弃用（工具结果）。
- source_index: 749, source_part_index: 0, quote: "import \"base:runtime\"", supports: action——切换到非弃用的 runtime import 路径。
- source_index: 778, source_part_index: 0, quote: "[odin] Building DMLS...\r\n[odin] Built build\\dmls.exe", supports: verification——修复后完整构建成功，输出中不再含 context 错误（工具结果，is_error=false）。

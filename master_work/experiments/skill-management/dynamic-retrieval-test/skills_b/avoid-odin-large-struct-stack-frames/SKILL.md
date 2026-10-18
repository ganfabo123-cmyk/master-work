---
name: avoid-odin-large-struct-stack-frames
description: Use when the Odin compiler warns that a declaration of a large struct (hundreds of KB) may cause a stack overflow. Helps the agent restructure pass-by-value snapshots into pointer + context.temp_allocator passing and fill-style construction, then verify a clean build and a runnable exe. Requires build warnings, grep over call sites, and the ability to rebuild and launch the program. Do not use for small structs or for crashes with an unrelated root cause.
triggers:
  - "may cause a stack overflow due to its type"
---
# Avoid Odin Large-Struct Stack Frames via Pointer + Temp Allocator

## Goal
消除 Odin 对数百 KB 级结构体局部变量的 “may cause a stack overflow” 警告，通过指针 + `context.temp_allocator` 传递与 caller 分配的 fill 式构造重构相关代码，最终产物是一次无该警告的成功构建，且程序仍可启动运行。

## Scope
### In scope
- 识别构建输出中 “Declaration of '<name>' may cause a stack overflow due to its type '<Type>' having a size of N bytes” 警告（轨迹中出现 425760 字节与 786976 字节两级）。
- 将按值返回/按值接收的大结构体改为 `^T` 指针传递，分配使用 `new(T, context.temp_allocator)` 并在循环处 `free_all(context.temp_allocator)`。
- 将返回大结构体的构造函数改为 caller 分配 + `fill(dst: ^T, ...)` 形式，避免构造函数内部再次产生同尺寸栈帧。
- 处理改指针后连锁出现的 `^^T` 类型错误（调用点 `&ptr` 需去掉 `&`）。
- 重建并启动程序做验证。

### Out of scope
- 小结构体、普通局部变量。
- 运行时崩溃/栈溢出事故的取证（轨迹未提供运行时崩溃证据，只有编译期警告）。
- 数据结构本身的裁剪或序列化设计变更。

## Inputs
1. **构建警告文本**（string，来源：构建输出，必需，约束：形如 `Declaration of '<name>' may cause a stack overflow due to its type '<Type>' having a size of N bytes`；默认值：无）。
2. **大结构体类型与其尺寸**（string + int，来源：警告正文（案例：SimSnapshot 425760 字节、World 786976 字节），必需；默认值：无）。
3. **产生/传递该结构体的函数与调用点**（list，来源：grep（如 `shared_read_snapshot()`、`snapshot_build(`），必需，约束：包含按值返回、按值传参、按值接收三类；默认值：无）。
4. **`context.temp_allocator` 可用性**（bool，来源：Odin 运行时 context，必需，约束：调用路径（请求线程/主循环）已 `free_all` 或可安全分配；默认值：无）。
5. **构建命令**（string，来源：项目构建脚本，必需；默认值：无）。

## Outputs
### Artifacts
- **重构后的源文件**：大结构体改为指针传递（`^T`，`new(T, context.temp_allocator)` 分配、按周期 `free_all`），构造改为 `fill(dst: ^T, ...)` caller 分配形式。
- **调用点修正**：`^^T` 报错的调用点已去掉多余 `&`。
- **构建与启动证据**：无该警告的构建日志 + 程序可启动的运行证据。

### Success criteria
- 构建输出中不再包含 `may cause a stack overflow` 警告（本次构建全部输出中均无该行）。
- 构建成功（如 `[odin] Built build\dmls.exe`）。
- 启动后进程存活（`Get-Process` 返回该进程行）。

### Failure criteria
- 同一警告仍出现在新构建输出中。
- 构建因 `^^T`、`Cannot slice array ... value is not addressable` 等指针化连锁错误失败而未修复。
- 仅构建成功但从未启动程序（无法排除运行时问题）。

## Preconditions
- 构建输出中确有 `may cause a stack overflow ... size of N bytes` 警告，且 N 为数百 KB 级。
- 能通过 grep 找到该类型的全部按值产生点（返回值、参数、局部变量）。
- 调用路径运行在可用 `context.temp_allocator` 的线程上下文中，并且该路径上有 `free_all(context.temp_allocator)`（或可以安全加）。
- 能重新构建并启动程序用于验证。
- 任一条件不满足：停止并报告。

## Procedure
### Step 1: 收集警告与按值产生点
- actions: 从构建输出提取全部 `Declaration of '<name>' may cause a stack overflow due to its type '<Type>' having a size of N bytes`；grep 出该类型的所有按值来源：构造返回（如 `snapshot_build(...) -> SimSnapshot`）、按值读取（如 `shared_read_snapshot() -> SimSnapshot`）、按值参数（如 `api_push_tick(snap: SimSnapshot)`）、大局部变量（如 `world := World{}`）。
- inputs: 构建警告、类型名。
- outputs: 警告清单 + 调用点清单。
- cautions: 警告只是编译期提示，轨迹未提供运行时崩溃证据；但它出现在请求/每 tick 热路径上，仍应消除。
- next: Step 2。

### Step 2: 读取器改为指针 + temp_allocator 分配
- actions: 把按值返回大结构体的读取函数改为返回 `^T`，内部 `s := new(T, context.temp_allocator)`（调用方无需逐处 `defer free`，靠已有的 `free_all(context.temp_allocator)` 回收）；调用点字段访问无需改动（Odin 自动解引用）。
- inputs: 读取函数与全部调用点。
- outputs: 返回 `^T` 的读取函数。
- cautions: 若调用点随后报 `Cannot assign value '&world' of type '^^World'`，说明调用点多写了 `&`（见 Common Failures）。
- preserve: 不改数据布局与业务字段。
- next: Step 3。

### Step 3: 构造函数改为 caller 分配的 fill 形式
- actions: 把 `build(...) -> T` 改为 `fill(dst: ^T, ...)`：调用方 `p := new(T, context.temp_allocator)` 后 `snapshot_fill(p, ...)`；删除原构造内的 `return snap`。
- cautions: 曾尝试在构造内 `snap := new(...)` 再按值返回（同样会产生指针/类型混乱），该路径被回退——保持“调用方分配、构造方填充”的单向数据流。
- next: Step 4。

### Step 4: 修正指针化连锁错误
- actions: 对报 `^^T` 的调用点去掉多余 `&`（整文件 `&world` → `world` 时注意保留 `&world.grid` 这类取子字段地址的写法）；对 `Cannot slice array ... value is not addressable`，把按值接收改为指针接收（`proc(e: ^EventSnap)`）再传 `&arr[i]`。
- cautions: `replace_all` 级别的替换会误伤 `&world.grid` → `world.grid`（案例中确实发生并被单独修回），替换后必须重新构建检查。
- next: Step 5。

### Step 5: 重建并启动验证
- actions: 运行构建，通读全部输出确认无 stack overflow 警告且成功；随后启动 exe 并确认进程存活。
- outputs: 干净构建日志 + 运行证据。
- next: 两项证据齐备即结束。

## Decision Rules
### When 警告尺寸达数百 KB 且该值位于请求线程/每 tick 热路径
改为指针 + `context.temp_allocator` 分配，并保证调用路径上有 `free_all(context.temp_allocator)`。

### When 构造函数按值返回大结构体导致栈帧警告
改为 caller 分配 + `fill(dst: ^T, ...)` 形式，不要在构造内部再 `new` 后按值返回（该尝试在轨迹中被回退）。

### When 把变量改成指针后出现 `^^T` 类型错误
调用点去掉 `&`（`&world` → `world`）；字段访问（`world.tick`、`world.grid`）依赖自动解引用，一般无需改动。

### When 使用 `replace_all` 做 `&world` → `world` 替换
替换后必须重新构建：`&world.grid` 这类对子字段取地址的写法会被误伤，需要单独修回 `&world.grid`。

### When 同时存在 `Cannot slice array ... value is not addressable`
按值接收的结构体改为指针参数（`^EventSnap`），调用点传 `&arr[i]`。

## Invariants
- 重构只改传递方式与分配位置，不改结构体字段布局和业务逻辑。
- temp_allocator 分配必须配套 `free_all`（或位于已有 free_all 的循环/请求作用域内），不在热路径上泄漏到 default allocator。
- 不以“警告可以忽略”替代修复，也不以“警告消失”替代运行验证。
- 全局替换（`replace_all`）后必须重新构建，确认没有误伤 `&field` 类取址写法。
- 不报告未经构建输出与启动证据支持的成功。

## Common Failures
### Failure: 改指针后构建报 `^^T` 类型错误
- symptoms: `Cannot assign value '&world' of type '^^World' to '^World' in a procedure argument`，一次性在多个调用点出现。
- causes: 变量本身已是 `^T`，调用点还写 `&world`。
- recovery: 调用点去掉 `&`（`&world` → `world`）。

### Failure: `replace_all` 误伤子字段取址
- symptoms: `Cannot assign value 'world.grid' of type 'Grid' to '^Grid' in a procedure argument`。
- causes: `&world` → `world` 的全局替换把 `&world.grid` 一起改坏了。
- recovery: 单独把该处改回 `&world.grid`；以后替换后立即重建检查。

### Failure: 在构造函数内部 `new` 后仍按值返回
- symptoms: 改到一半出现指针与值混用（`snap := snap_ptr` 后 `snap.field = ...` 的赋值语义混乱），被迫回退。
- causes: 构造返回类型仍是值，内部指针化破坏赋值语句。
- recovery: 彻底改为 caller 分配 + `fill(dst: ^T, ...)`，构造函数不再返回该结构体。

### Failure: 忽略“stack overflow”警告只做其他错误修复
- symptoms: 每次构建都重复输出同一警告（轨迹中 425760/786976 字节警告连续多轮出现）。
- causes: 警告不阻塞构建，容易被后续错误淹没。
- recovery: 把警告项与错误一起纳入修复清单，按 Step 2–3 重构。

### Failure: 按值传结构体引发 `value is not addressable`
- symptoms: `Cannot slice array 'e.kind[:]', value is not addressable`。
- causes: 结构体按值接收，固定数组字段不可取址。
- recovery: 该过程改为接收 `^T`，调用点传 `&arr[i]`。

## Verification
可观察检查项（不使用 [x]）：
- 完整构建输出中不再出现 `may cause a stack overflow`（本次构建输出全部行均无该文案）。
- 构建成功并打印产物行（如 `[odin] Built build\dmls.exe`），无 `^^T`、`value is not addressable` 等指针化连锁错误。
- 启动 exe 后 `Get-Process <name>` 返回存活进程行（案例中进程持续存在、CPU 非零）。
- 源码检查：读取函数返回 `^T` 且用 `new(T, context.temp_allocator)` 分配；构造为 `fill(dst: ^T, ...)`；调用路径存在 `free_all(context.temp_allocator)`。
- 说明：轨迹未提供“修复前运行时栈溢出崩溃”的证据，验证目标是警告消失 + 构建成功 + 程序可运行，不声称修复了某个观察到的运行时崩溃。

## Examples
### Example 1: 425KB 快照结构体在请求路径上按值复制
- input: 构建警告 `Declaration of 'snap' may cause a stack overflow due to its type 'SimSnapshot' having a size of 425760 bytes`，出现在 13 个 `snap := shared_read_snapshot()` 调用点。
- procedure: Step 1 grep 调用点 → Step 2 把 `shared_read_snapshot` 改为返回 `^SimSnapshot`（`new(SimSnapshot, context.temp_allocator)` 分配），13 个调用点字段访问不改 → Step 3 把 `snapshot_build(...) -> SimSnapshot` 改为 `snapshot_fill(snap: ^SimSnapshot, ...)`，调用方 `p := new(SimSnapshot, context.temp_allocator)` → Step 5 重建。
- expected result: 构建输出无 stack overflow 警告，构建成功，exe 可启动并保持存活。
- parameterized values: 类型名（`SimSnapshot`）、尺寸（425760 字节）、调用点数（13）、读取函数名（`shared_read_snapshot`）、构造函数名（`snapshot_build` → `snapshot_fill`）。

### Example 2: 769KB 世界结构体局部变量 + 指针化连锁错误
- input: 警告 `Declaration of 'world' may cause a stack overflow due to its type 'World' having a size of 786976 bytes`（`world := World{}`）。
- procedure: 改 `world := new(World)` + `defer free(world)` → 构建出现多处 `Cannot assign value '&world' of type '^^World'` → `replace_all` 把 `&world` 换成 `world` → 构建又报 `Cannot assign value 'world.grid' of type 'Grid' to '^Grid'` → 单独改回 `&world.grid` → 重建。
- expected result: 两类错误与警告全部消失，构建成功。
- parameterized values: 类型名（`World`）、尺寸（786976 字节）、被误伤的写法（`&world.grid`）。

## Evidence
file_id: claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02

- source_index: 608, source_part_index: 0, quote: "Warning: Declaration of 'snap' may cause a stack overflow due to its type 'SimSnapshot' having a size of 425760 bytes", supports: problem——425KB 结构体按值声明的栈溢出警告（工具结果，api_routes.odin:399）。
- source_index: 676, source_part_index: 0, quote: "Warning: Declaration of 'world' may cause a stack overflow due to its type 'World' having a size of 786976 bytes", supports: problem——769KB 结构体局部变量的同类警告（工具结果，headless.odin:143）。
- source_index: 635, source_part_index: 0, quote: "s := new(SimSnapshot, context.temp_allocator)", supports: action——读取函数改为返回指针并在 temp_allocator 上分配副本。
- source_index: 640, source_part_index: 0, quote: "// Push snapshot to API thread (heap-alloc to avoid 425KB stack frame)", supports: action——调用点改为先分配指针再填充，避免按值大拷贝。
- source_index: 698, source_part_index: 0, quote: "world     := new(World)", supports: action——大结构体局部变量改为堆分配（World 786976 字节）。
- source_index: 712, source_part_index: 0, quote: "Cannot assign value '&world' of type '^^World' to '^World' in a procedure argument", supports: problem——指针化后的连锁错误：调用点多写了 `&`（工具结果）。
- source_index: 719, source_part_index: 0, quote: "&world", supports: action——replace_all 将 `&world` 替换为 `world` 的操作对象（Edit 参数）。
- source_index: 722, source_part_index: 0, quote: "Cannot assign value 'world.grid' of type 'Grid' to '^Grid' in a procedure argument", supports: problem——全局替换误伤 `&world.grid` 子字段取址（工具结果）。
- source_index: 743, source_part_index: 0, quote: "grid_remove_character(&world.grid, c.position[0], c.position[1])", supports: action——把误伤处改回 `&world.grid`。
- source_index: 756, source_part_index: 0, quote: "// snapshot_build fills a caller-provided struct to avoid a 425KB stack frame.", supports: action——构造函数改为 caller 分配 + fill 形式。
- source_index: 778, source_part_index: 0, quote: "[odin] Building DMLS...\r\n[odin] Built build\\dmls.exe", supports: verification——最终构建成功，且该次输出全部行中不再出现 stack overflow 警告（工具结果，is_error=false）。
- source_index: 781, source_part_index: 0, quote: "dmls 43232 0.05", supports: verification——重构后 exe 可启动且进程存活（Get-Process 工具结果）。

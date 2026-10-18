---
name: fix-windows-0xc00000fd-stack-overflow
description: Use when a compiled test executable on Windows exits with -1073741571 / 0xC00000FD and prints no output. Helps the agent locate oversized fixed-size structs placed on the call stack (function locals, fixture members, by-value helper copies) and move them to static storage or bind them by reference. Requires PowerShell to run the exe and read $LASTEXITCODE, plus source access to the struct definitions. Do not use when the exit code is -1073741515 (missing DLL), when compilation or linking fails, or when tests run and report ordinary assertion failures.
triggers:
  - "-1073741571"
  - "0xC00000FD"
---
# Fix Windows 0xC00000FD (stack overflow) crashes in C++ test binaries

## Goal
让因 0xC00000FD（栈溢出）在 Windows 上静默崩溃的 C++ 测试二进制恢复正常运行：定位占满 1 MB 默认线程栈的固定大小大结构体，将其移出调用栈，最终产物是修复后的源码与 exit code 0、输出 "N/N tests passed" 的测试运行结果。

## Scope
### In scope
- 退出码 -1073741571 / 0xC00000FD 且启动后无任何输出的测试 exe。
- 三类栈占用来源：函数内的大型局部栈结构（如 ChoiceStack/GoalStack）、测试 fixture 按值持有大成员、helper 按值返回大结构体后被 `T t = ...` 复制到栈上。
- 修复手段：改为函数内 `static`（函数非可重入时）、fixture 改 static 成员 + 引用绑定、helper 返回引用并用 `T &t = ...` 接收。
- 修复后重新编译并运行验证（单套件与全套）。

### Out of scope
- 退出码 -1073741515（缺失 DLL，如 ASAN 运行库不在 PATH）。
- 编译错误、链接错误（LNK2019/LNK1105 等）。
- 测试正常运行但断言失败的逻辑缺陷。
- 通过增大系统栈（linker /STACK）或放宽断言来绕过崩溃。

## Inputs
1. **崩溃退出码与输出**：字符串，来源：运行测试 exe 的工具结果（PowerShell `$LASTEXITCODE`），必需。约束：形如 `Exit: -1073741571` 或 `(exit -1073741571)`，且 exe 未打印任何测试行。默认值：无。
2. **结构体定义源码**：文件内容，来源：Read/Grep 引擎与测试头文件，必需。约束：关注含固定容量数组成员（数千到数万元素）的 struct（AtomTable、TermArena、Database、ChoiceStack 等），估算 sizeof 达数百 KB 以上。默认值：无。
3. **结构体使用点**：文件内容，来源：Read 测试与引擎实现，必需。约束：定位局部声明、fixture 成员、`T t = make_x()` 形式的复制。默认值：无。
4. **编译命令**：字符串，来源：既有 build.bat/Makefile 或既有 PowerShell 编译行，必需。约束：clang++ -std=c++23 + 项目 include 路径。默认值：无。
5. **可接受的重入前提**：布尔条件，来源：项目设计（如 JPL "non-reentrant" 规则），可选。约束：仅当目标函数非可重入时才能用函数内 static。默认值：无。

## Outputs
### Artifacts
- 修复后的源文件（在原文件就位修改）：引擎实现与/或 `tests/*.cpp`。
- 验证记录：受影响测试 exe 的运行输出与 exit code（工具结果）。

### Success criteria
- 目标 exe 运行 exit code = 0，且打印 `N/N tests passed`。
- 全套测试汇总不再出现 -1073741571，全部套件通过。

### Failure criteria
- 修复后仍以 -1073741571 退出。
- 修复引入新的编译错误。
- 只确认构建成功但未运行 exe（不能证明崩溃已解决）。

## Preconditions
- 运行环境为 Windows，默认线程栈约 1 MB（这是崩溃的环境前提）。
- 能通过 PowerShell 执行 `.exe` 并读取 `$LASTEXITCODE`；bash 无法运行这些 exe（轨迹中 bash 运行返回 exit 127，不能作为结果）。
- 已确认退出码是 -1073741571（0xC00000FD）；若为 -1073741515 则停止本流程并按缺 DLL 处理。
- 拥有目标源文件的编辑权限与重编译能力。
- 若无法重编译或无法运行 exe，停止并报告，不得仅凭静态分析声称已修复。

## Procedure
### Step 1: 确认崩溃码与"零输出"症状
- actions: 在 PowerShell 中运行崩溃的测试 exe 并打印 `$LASTEXITCODE`；确认没有任何 PASS/FAIL 输出。
- inputs: 测试 exe 路径。
- outputs: `-1073741571`。
- cautions: 无输出不等于无失败，必须看退出码；不要把 PowerShell 的 `Exit code 253` 外壳码当作程序码，读取程序自身的值。
- preserve: 不改动任何测试断言或产品代码。
- next: 退出码为 -1073741571 → Step 2；否则停止本流程。

### Step 2: 估算并定位栈上的大对象
- actions: 读取可疑 struct 定义并估算 sizeof（容量常量 × 元素大小）；按三类搜索使用点：(a) 函数内局部大 struct；(b) fixture 按值持有的大成员；(c) helper 返回大结构体且调用方写 `T t = ...`。
- inputs: 结构体定义与使用点源码。
- outputs: 一份"占栈对象 + 估算字节数 + 位置"清单。
- cautions: 单个 330 KB 的局部栈数组在多次调用/嵌套下即可溢出；`T t = fresh_x()` 是隐式全量复制，最容易漏掉。
- preserve: 只标记，不在本步修改。
- next: 找到 >100 KB 的栈上对象 → Step 3；全部在静态/堆上 → 停止并重新审视（可能不是栈溢出）。

### Step 3: 把大对象移出调用栈
- actions: 按场景选择修法——(a) 非可重入函数内的局部栈数组改为 `static` 并在入口 `memset` 清零；(b) fixture 大成员改为 `static` 成员 + 引用成员，构造函数通过引用初始化并在构造时 `*_init()`；(c) helper 改为返回引用（内部 `static T t;`），调用方改为 `T &t = make_x();`。
- inputs: Step 2 清单、重入前提。
- outputs: 修改后的源文件。
- cautions: static 成员需要在 struct 之外补定义（`T Ctx::s_x = {};`）；改为 static 后每次构造仍须调用初始化函数，否则测试间状态残留。
- preserve: 不改测试断言、不改无关文件、不改容量常量。
- next: 每处修改后进入 Step 4。

### Step 4: 重新编译并运行受影响的测试
- actions: 用既有编译命令重编译受影响 .cpp 及依赖它的测试二进制；运行该 exe 并打印 exit code 与输出。
- inputs: 编译命令、测试 exe。
- outputs: exit 0 且 `N/N tests passed`。
- cautions: 若链接报 LNK1105（文件被占用），先按 handle-locked-or-stale-test-binaries 处理，不要误判为修复无效。
- preserve: 保留修复前的失败输出作为对照。
- next: 单套件通过 → Step 5；仍崩溃 → 回到 Step 2 继续找遗漏的复制点。

### Step 5: 全套回归
- actions: 重新构建并运行全部测试套件，汇总 pass/fail。
- outputs: 汇总行显示 0 failed，且无任何 -1073741571。
- cautions: 全套运行中若个别旧二进制未重建，结果不可信（见 handle-locked-or-stale-test-binaries）。
- preserve: 不删除失败套件。
- next: 全部通过 → 完成；否则定位失败套件回到 Step 1。

## Decision Rules
### When exe 在任何输出前静默退出且 exit = -1073741571
判定为 0xC00000FD 栈溢出，按 Step 2 找占栈大对象，不要先去改测试逻辑。

### When helper 返回大结构体且调用方写作 `T t = make_x()`
这是隐式按值复制（把 ~1 MB 复制到栈上），必须改为 `T &t = make_x()` 并让 helper 返回引用。

### When 大结构体是非可重入函数内的局部变量
改为函数内 `static`，并在函数入口 memset/初始化；若函数可重入则不得用 static，改用其他存储。

### When 测试 fixture 持有多个大成员
改为 static 成员 + 引用成员（构造时逐一 `*_init()`），并在 struct 外补静态定义。

### When 退出码为 -1073741515
不是栈溢出，是缺失 DLL（例如 ASAN 运行库），停止本流程按环境问题处理。

### When 只有部分测试二进制崩溃
逐个二进制用最小链接集（只链真正需要的 .o）复现，以缩小到具体源文件。

## Invariants
- 不通过修改/放宽测试断言来"消除"崩溃。
- 不通过增大线程栈（/STACK、setrlimit）掩盖结构体尺寸问题。
- 不改动与该崩溃无关的文件或未授权的构建配置。
- 不跳过运行验证：只有重编译后真实运行 exe 才能声称修复。
- 不把 clangd/IDE 诊断当作编译结论，也不把"构建成功"当作"运行成功"。
- 改为 static 后必须保留每次使用前的初始化调用，避免测试间状态污染。
- 不报告未验证的成功；未运行就说"应该好了"是禁止的。

## Common Failures
### Failure: 只修了 fixture，仍崩溃
- symptoms: static 成员改完后重编译运行仍是 -1073741571。
- causes: 仍有按值复制点，典型为 `AtomTable t = make_table()`（helper 已返回静态引用，但调用方用 `=` 复制了 ~1 MB 到栈上）。此原因在轨迹中经全局 Grep `AtomTable t` 后确认。
- recovery: 搜索所有 `= make_`/`= fresh_` 形式的接收点，改为引用绑定后重编译验证。

### Failure: 把缺 DLL 当栈溢出
- symptoms: `-1073741515`，或 ASAN 版本二进制启动即失败。
- causes: 运行库（如 ASAN runtime）不在 PATH。
- recovery: 按环境/PATH 处理，不要动数据结构。

### Failure: 无输出被误读为"测试通过/没跑"
- symptoms: 汇总脚本只看 stdout，崩溃的套件显示为空行。
- causes: 崩溃发生在 main 输出之前，stdout 为空。
- recovery: 每个套件都检查 `$LASTEXITCODE`，把 exit ≠ 0 计为失败。

### Failure: 链接新二进制时报 LNK1105 导致误判修复无效
- symptoms: `LINK : fatal error LNK1105: cannot close file ...`。
- causes: 上一次运行的 exe 仍被占用。
- recovery: 结束进程或改用新文件名输出后重链（见 handle-locked-or-stale-test-binaries）。

## Verification
- 对修复后的目标 exe 运行并读取 exit code：应为 0，而不是 -1073741571。
- 目标套件输出包含 `N/N tests passed`（例如 `13/13 tests passed`、`17/17 tests passed`）。
- 全套汇总行显示 0 failed（例如 `=== FINAL RESULT: 10/10 suites passed, 0 failed ===`）。
- 源码中不再存在把大结构体按值放到栈上的写法：Grep `AtomTable t = `、`TermArena a = `、函数内无 `ChoiceStack cs;` 一类声明。
- 编译输出无与本次修改相关的新错误/警告。

## Examples
### Example 1: 求解器局部 ChoiceStack 溢出
- input: `build/tests/test_indexing.exe` 运行输出 `Exit: -1073741571`，无任何测试行。
- procedure: Step 1 确认 0xC00000FD → Step 2 估算 ChoicePoint×256 ≈ 330 KB 且 GoalStack/ChoiceStack/RenameMap 是 `solve()` 的局部变量 → Step 3 将三者改为 `static` 并在入口 memset → Step 4 重编译 solver.o 与测试并运行。
- expected result: `test_indexing` 输出 `13/13 tests passed`，exit 0。
- parameterized values: 结构体名与容量常量（CHOICE_STACK_CAPACITY 等）按项目替换；重入前提为 solve() 非可重入。

### Example 2: 测试 fixture 按值持有六大成员
- input: 多个套件运行即 `-1073741571`（如 `(exit -1073741571)`），单套件最小复现仍崩溃。
- procedure: Step 2 发现 `SolverCtx`/`ParseCtx`/`UnifyCtx` 按值持有 AtomTable/Database/合计数 MB 成员 → Step 3 改 static 成员 + 引用成员并在 struct 外补 `Ctx::s_x = {};` 定义 → Step 4 重编译运行。
- expected result: `test_solver` 等恢复输出并 `22/22 tests passed`；汇总恢复多套件通过。
- parameterized values: fixture 名与成员清单按测试文件替换。

### Example 3: helper 返回值被按值复制
- input: `test_atoms` 在所有修复后仍静默崩溃。
- procedure: Grep `AtomTable t` 定位到 `AtomTable t = make_table();` → 改为 `AtomTable &t = make_table();` → 重编译运行。
- expected result: `17/17 tests passed`，exit 0。
- parameterized values: 类型名（AtomTable/TermArena）与 helper 名按项目替换。

## Evidence
- problem: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=183, source_part_index=0, quote="Exit: -1073741571", supports=崩溃码输入（test_indexing 无输出、退出码 -1073741571）。
- problem: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=987, source_part_index=0, quote="(exit -1073741571)", supports=另一 session 中五个测试套件同样静默以该码崩溃。
- problem: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=184, source_part_index=0, quote="`0xC00000FD` = stack overflow", supports=退出码到栈溢出的判定。
- action: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=190, source_part_index=0, quote="we can make `GoalStack`, `ChoiceStack`, and `RenameMap` `static` in `solve()` since the solver is non-reentrant", supports=局部大栈结构改 static 的关键动作与前提。
- action: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1203, source_part_index=0, quote="So `AtomTable t = make_table()` **copies** the ~1MB AtomTable onto the local stack. That's the crash.", supports=按值复制 helper 返回值这一原因（经后续 Grep 与修复验证确认）。
- action: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1036, source_part_index=0, quote="    static AtomTable   s_atoms;", supports=fixture 大成员改 static 成员 + 引用成员的关键动作。
- verification: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=279, source_part_index=0, quote="13/13 tests passed", supports=局部栈结构 static 化后 test_indexing 恢复并通过。
- verification: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=328, source_part_index=0, quote="17/17 tests passed", supports=按值复制改引用后 test_atoms 恢复并通过。
- verification: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=333, source_part_index=0, quote="=== FINAL RESULT: 10/10 suites passed, 0 failed ===", supports=全套 10 套件通过、无 0xC00000FD。
- verification: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1191, source_part_index=0, quote="=== 6 PASSED, 1 FAILED ===", supports=fixture static 化后 6 个套件恢复运行并全部通过（仅剩被文件锁占用的 test_atoms）。

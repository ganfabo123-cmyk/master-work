---
name: fix-windows-test-startup-stack-overflow
description: Use when test executables compile and link but exit immediately with code -1073741571 (0xC00000FD, Windows stack overflow) and print no test output. Helps the agent move multi-megabyte test fixtures off the stack into static storage (function-local statics returned by reference, static class members) so every suite actually runs. Requires the harness output with per-binary exit codes and edit access to the test sources. Do not use when the failure is a link error (LNK2019/LNK1105) or when binaries print test results and only assertions fail.
---
# Fix Windows Test Binaries That Crash at Startup With Exit -1073741571

## Goal
消除测试二进制在 Windows 上启动即以退出码 -1073741571（0xC00000FD，栈溢出）崩溃、不产生任何测试输出的问题，使全部测试套件正常执行并输出 PASS/FAIL 明细与通过计数。

## Scope
### In scope
- 区分“链接失败”与“链接成功但启动即崩溃”（无输出 + 退出码 -1073741571）。
- 定位测试代码中按值占用栈的多 MB fixture（返回大结构体的 helper、测试函数内局部大对象、类内联持有大成员）。
- 将这些 fixture 改为静态存储：函数局部静态 + 引用返回（配合 `#define` 保持调用点不变）、replace_all 替换残余按值局部变量、类静态数据成员并给出定义。
- 用同一 harness 重跑，确认原先无输出的套件恢复输出。

### Out of scope
- 已有正常输出后的断言失败与引擎逻辑 bug（轨迹中 `test_solver`/`test_unifier` 的断言失败需另查）。
- 链接阶段错误（LNK2019、LNK1105 文件锁）。
- 非 Windows 平台的栈大小问题与产品运行时代码的栈优化：轨迹未提供。
- 共享静态 fixture 跨用例状态残留的彻底治理：轨迹仍在调试中，未完成验证。

## Inputs
1. **测试 harness 运行输出** — 类型：工具结果（PowerShell 测试循环 stdout/stderr）；来源：原样重跑的构建脚本；必需：是；约束：需包含每个套件是 `--- <name> ---` 还是 `FAIL: <name>` 以及汇总行；默认值：无。
2. **失败二进制的单独运行退出码** — 类型：工具结果（直接执行 exe 并读取 `$LASTEXITCODE`）；来源：单独运行命令；必需：是；约束：需确认是否为 -1073741571；默认值：无。
3. **测试源文件中的 fixture helper 与局部大对象** — 类型：源文件（如 `tests/test_atoms.cpp` 的 `make_table()`、`tests/test_solver.cpp` 的 `SolverCtx`）；来源：仓库 tests 目录；必需：是；默认值：无。
4. **大结构体规模信息** — 类型：源码字段与轨迹中的估算（`AtomTable` ~1MB、`TermArena` ~4MB）；来源：include 下头文件；必需：是；默认值：无。
5. **编译命令** — 类型：构建脚本参数（`clang++ -std=c++23 -Iinclude -Itests -g -O0 ...`）；来源：harness 脚本；必需：是；默认值：无。

## Outputs
### Artifacts
- 修改后的测试源文件：静态 fixture helper（如 `static AtomTable &fresh_table()` + `#define make_table() fresh_table()`）、`#define` 兼容层、类静态数据成员定义（均位于 `tests/*.cpp`）。
- 新的 harness 运行输出：各套件用例级 PASS/FAIL 明细、`N/N tests passed` 行与汇总行（工具结果文本）。

### Success criteria
- 此前“`FAIL: <name>` 后无任何用例输出”的二进制开始打印用例明细与 `N/N tests passed`。
- harness 汇总行显示每个套件都有结果计数，而不是静默失败。
- 已通过的套件仍通过（`test_lexer` 保持 22/22、`test_variables` 保持 17/17）。

### Failure criteria
- 仍有二进制无输出且退出码 -1073741571。
- 修改引发编译错误（类型不匹配、重定义、漏掉类静态成员定义）。
- 因共享静态 fixture 污染导致此前通过的用例转为失败。

## Preconditions
执行前必须确认：
- 环境为 Windows，且失败二进制能被单独执行以读取退出码（本轨迹退出码为 -1073741571 = 0xC00000FD 栈溢出）。
- 该二进制已通过编译与链接（输出中无 `COMPILE ERROR`/LNK 错误），否则属于链接问题，停止并转用链接流程。
- 能访问并编辑 `tests/` 下的测试源文件；若只允许改产品运行时代码则停止并报告。
- 测试 fixture 中确有多 MB 级结构体按值出现在栈帧（helper 按值返回或测试函数内局部变量）。
- 能用同一 harness 脚本做修改前后对照重跑。

任一条件不满足时停止执行并报告缺失项。

## Procedure
### Step 1: 确认是启动崩溃而非断言失败
- actions: 重跑同一 harness；对输出中 `FAIL: <name>` 后没有任何用例行的二进制，逐个直接执行并打印退出码。
- inputs: harness 输出、单独运行命令。
- outputs: 退出码清单（本轨迹 `test_atoms`、`test_terms`、`test_parser`、`test_unifier`、`test_solver` 全为 `(exit -1073741571)`，而 `test_lexer`/`test_variables` 正常通过）。
- cautions: “FAIL + 无输出”与“FAIL + 断言行”是两种不同故障，不要混为一谈；此时链接阶段已无 LNK2019。
- preserve: 不修改产品代码与 harness 脚本。
- next: 退出码为 -1073741571 → Step 2。

### Step 2: 找出按值占用栈的大 fixture
- actions: 读取失败测试的 helper 与测试体，估算结构体大小；识别三类模式：helper 按值返回大对象（`static AtomTable make_table(){ AtomTable t; ... return t; }`）、测试体内多 MB 局部对象、上下文类内联持有多个 arena（`SolverCtx` 含两个 `TermArena` 级别的大成员）。
- inputs: `tests/*.cpp`、include 下结构体定义。
- outputs: 待改 helper 与待改结构体清单。
- cautions: 轨迹中对该退出码的首次解读（`0xC000000D`）不正确，应以“栈溢出、需把大对象移出栈”的后续定位为准；`AtomTable` ~1MB、`TermArena` ~4MB 为轨迹中的估算值，需按实际类型复核。
- preserve: 不删改任何测试用例。
- next: 存在多 MB 按值栈分配 → Step 3。

### Step 3: helper 改为函数局部静态 + 引用返回
- actions: 将 `static AtomTable make_table()` 改为 `static AtomTable &fresh_table(){ static AtomTable t; atom_table_init(&t); return t; }`，并加 `#define make_table() fresh_table()` 保持原调用点不变；对 `TermArena`/`VarRegistry` 同样处理（`fresh_arena()`/`fresh_reg()`/`fresh_atoms()`）。
- inputs: 测试 helper 定义。
- outputs: 修改后的 helper 与兼容宏。
- cautions: 每次获取时必须重新初始化（init 调用留在 helper 内），否则跨用例残留状态；这些静态实例在同一二进制内被所有用例共享。
- preserve: 保留原 helper 名称，调用点无需逐一改动。
- next: Step 4。

### Step 4: 清理残余的按值局部大对象
- actions: 用 `replace_all` 把测试体内的 `AtomTable t; atom_table_init(&t);` 替换为 `AtomTable &t = fresh_atoms();`。
- inputs: 测试源文件。
- outputs: 已无按值大对象的测试体。
- cautions: 替换后引用必须指向 Step 3 中会重新初始化的静态实例。
- preserve: 不改断言表达式本身。
- next: Step 5。

### Step 5: 类内联持有的大成员改为静态数据成员
- actions: 为上下文类声明的大成员给出文件作用域定义（本轨迹为 `AtomTable SolverCtx::s_atoms = {};` 等六个成员：`s_atoms`、`s_db`、`s_clause_arena`、`s_clause_vars`、`s_query_arena`、`s_query_vars`）。
- inputs: `tests/test_solver.cpp` 中的上下文类。
- outputs: 静态成员定义。
- cautions: 六处修改与 Step 3/4 同批发生，最终验证只支持整批修改的效果，不能归因于单一编辑。
- preserve: 类的构造/初始化流程（`db_init`、`term_arena_init` 等）保持不变。
- next: Step 6。

### Step 6: 重新编译并用同一 harness 重跑
- actions: 原样执行同一 PowerShell 测试循环，观察每个套件是否输出用例明细。
- inputs: 修改后的测试源、原 harness。
- outputs: 新的 harness 输出（用例 PASS/FAIL 行、`N/N tests passed`、汇总行）。
- cautions: 恢复输出不等于全部通过；断言失败仍需另查。
- preserve: 不修改 harness，以便与 Step 1 输出对照。
- next: 原先无输出的套件均产生用例输出 → 完成。

## Decision Rules
### When 二进制能链接但无输出且退出码 -1073741571
按 Windows 栈溢出处理：检查测试栈帧中的 fixture 大小并移入静态存储，而不是回滚此前的链接修复或怀疑测试逻辑。

### When fixture helper 按值返回 ~1MB 级结构体（或多 MB arena）
改用函数局部静态 + 引用返回，并在 helper 内重新初始化，配合 `#define` 保持调用点不变（本轨迹 `make_table()` → `fresh_table()`）。

### When 上下文类内联持有多个大成员
把这些成员改为静态数据成员并提供文件作用域定义（本轨迹 `SolverCtx::s_atoms` 等六个成员），避免对象在栈上携带全部大缓冲。

### When 二进制有正常用例输出、仅断言失败
不属于本技能范围：保持 fixture 修改，转为引擎/用例逻辑排查（轨迹中 `test_solver` 18/22、`test_unifier` 16/18 的失败走的是该流程）。

### When 输出中出现 LNK2019/LNK1105 等链接错误
先按链接问题处理，本技能不适用；轨迹未提供 LNK1105（文件被占用，error code 1224）的已验证恢复步骤。

## Invariants
- 不删除或弱化任何测试用例与断言来让套件“通过”。
- 不修改产品运行时代码来规避测试栈问题（已核对的修改均位于 `tests/` 下：`test_atoms.cpp`、`test_terms.cpp`、`test_solver.cpp`）。
- 不回滚已生效的链接修复（头文件中的 `inline` 全局定义保持不动）。
- 每个静态 fixture 在每次被 helper 获取时重新初始化，不得依赖上次调用的残留数据。
- 保持原 harness 脚本不变以进行前后对照。
- 不把“恢复输出”报告为“测试全部通过”。
- 不在未重跑 harness 前声称崩溃已修复。

## Common Failures
### Failure: “FAIL + 无输出”被当成断言失败
- symptoms: harness 中 `FAIL: test_atoms` 之后直到下一个套件头之间没有任何用例行；单独运行显示 `(exit -1073741571)`。
- causes: 二进制在测试框架执行任何用例前就因栈溢出崩溃，与断言无关。
- recovery: 先单独运行取退出码确认崩溃，再按 Step 2–6 把 fixture 移出栈；不要去改用例。

### Failure: 只修复了一个测试文件
- symptoms: 修改某个测试后，其余套件仍无输出即退出。
- causes: 多个 `tests/test_*.cpp` 都含有按值的大 fixture；本轨迹在 source_index 1002–1043 之间对多个测试文件同批修改（已核对 `test_atoms.cpp`、`test_terms.cpp`、`test_solver.cpp` 的编辑）。
- recovery: 对所有无输出的套件应用同一静态 fixture 模式后整体重跑。

### Failure: 静态 fixture 在套件内跨用例残留状态
- symptoms: 崩溃修复后出现用例间相互影响的诊断，例如 `loaded=-1 db.clause_count=1` 被判断为上一个用例（single-body rule）留下的数据。
- causes: 静态存储在同一二进制内被所有用例共享（轨迹未提供该问题的最终修复验证）。
- recovery: 保证每个 helper 获取时重新初始化（`fresh_*` 内调用 `atom_table_init`/`term_arena_init` 等）；更彻底的用例隔离轨迹仍在调试，未形成已验证步骤。

### Failure: 对退出码的首次解读错误
- symptoms: 把 -1073741571 说成 `0xC000000D`/`STATUS_INVALID_PARAMETER`，并据此怀疑 `inline` 变量的静态初始化顺序。
- causes: 手工换算错误（-1073741571 实为 0xC00000FD 栈溢出）。
- recovery: 以实际退出码与“无输出”现象重新定位；后续分析自行更正为栈溢出并由修复验证支持。

## Verification
用同一 harness 前后对照，逐项检查：
- 修改前：`FAIL: test_atoms`、`FAIL: test_parser`、`FAIL: test_terms`、`FAIL: test_unifier`、`FAIL: test_solver` 均无用例输出；单独运行为 `(exit -1073741571)`。
- 修改后：上述套件均输出用例明细，例如 `PASS  parse simple fact: foo.`（`test_parser` 12/12）、`PASS  term_arena_init zeroes count`（`test_terms` 15/15）、`PASS  atom unifies with itself`（`test_unifier` 16/18）。
- 修改后汇总行由 `=== 2 suite(s) PASSED, 5 FAILED ===`（5 个失败无输出）变为 `=== 4 suite(s) PASSED, 3 FAILED ===`，且 3 个失败都附带具体断言行（如 `FAIL  D:\Epilog\tests\test_solver.cpp:196`），不再有静默失败。
- 回归检查：原本正常的 `test_lexer` 仍为 `22/22 tests passed`，`test_variables` 仍为 `17/17 tests passed`。
- 逐个二进制复核退出码是否已不再是 -1073741571：轨迹未提供修改后的逐个退出码记录，不作结论。
- 仍未通过的断言失败属于另一问题，不由本技能的完成条件覆盖。

## Examples
### Example 1: 五个测试套件启动即栈溢出崩溃
- input: harness 输出中 `FAIL: test_atoms`、`FAIL: test_parser`、`FAIL: test_terms`、`FAIL: test_unifier`、`FAIL: test_solver` 之后没有任何用例行，汇总 `=== 2 suite(s) PASSED, 5 FAILED ===`；单独运行这五个二进制均为 `(exit -1073741571)`；链接阶段已无 LNK2019。
- procedure: Step 1 用退出码确认为启动期栈溢出；Step 2 发现 `make_table()` 按值返回 ~1MB 的 `AtomTable`、`make_arena()` 按值返回 `TermArena`，且 `SolverCtx` 内联持有多个大成员；Step 3 把 helper 改为 `static AtomTable &fresh_table(){ static AtomTable t; atom_table_init(&t); return t; }` 并加 `#define make_table() fresh_table()`，对 arena/var registry 同样处理；Step 4 用 replace_all 把 `AtomTable t; atom_table_init(&t);` 换成 `AtomTable &t = fresh_atoms();`；Step 5 为 `SolverCtx` 的六个大成员补充静态定义；Step 6 原样重跑 harness。
- expected result: 五个套件恢复用例级输出（`test_parser` 12/12、`test_terms` 15/15、`test_unifier` 16/18、`test_solver` 18/22），汇总变为 `=== 4 suite(s) PASSED, 3 FAILED ===`，3 个失败均带具体断言行——崩溃消失，剩余为断言层面问题。
- parameterized values: 退出码 -1073741571、结构体 `AtomTable`（~1MB）与 `TermArena`（~4MB）、helper 名 `make_table`/`make_arena`/`make_reg`、静态名 `fresh_table`/`fresh_arena`/`fresh_reg`/`fresh_atoms`、类 `SolverCtx` 及其六个静态成员；替换到其他工程时按实际类型与文件代入。

## Evidence
- **problem** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 987, source_part_index: 0, quote: `(exit -1073741571)`, supports: 链接已成功的 `test_atoms`、`test_terms`、`test_parser`、`test_unifier`、`test_solver` 五个二进制在启动后立即以该退出码结束，崩溃发生在任何测试输出之前。
- **problem** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 984, source_part_index: 0, quote: `FAIL: test_parser`, supports: 同一可见结果中该 FAIL 行之后直到下一个套件头之间没有任何用例行，说明失败不是断言失败而是无输出即退出。
- **action** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1002, source_part_index: 0, quote: `AtomTable is ~1 MB — too large for the default Windows stack.`, supports: 编辑 `tests/test_atoms.cpp` 时对问题的定位：按值构造/返回的 `AtomTable` 超出 Windows 默认栈容量，据此把 `make_table()` 改为静态存储方案。
- **action** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1002, source_part_index: 0, quote: `static AtomTable &fresh_table()`, supports: helper 从按值返回改为返回函数局部静态对象的引用（同事件中还有 `#define make_table() fresh_table()`，保持原调用点不变）。
- **action** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1005, source_part_index: 0, quote: `static TermArena &fresh_arena()`, supports: 同一静态化模式扩展到 `tests/test_terms.cpp` 的 `TermArena`/`VarRegistry`/`AtomTable` 三个大结构体 helper（同事件含注释 `Large structs live in static storage — too big for Windows default stack.` 与对应 `#define` 兼容宏）。
- **action** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1009, source_part_index: 0, quote: `AtomTable &t = fresh_atoms();`, supports: 用 replace_all 清理测试体内残余的按值 `AtomTable t; atom_table_init(&t);` 局部对象。
- **action** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1043, source_part_index: 0, quote: `SolverCtx::s_atoms`, supports: 为 `test_solver.cpp` 中内联持有多个大成员的 `SolverCtx` 补充六个静态数据成员定义（`s_atoms`、`s_db`、`s_clause_arena`、`s_clause_vars`、`s_query_arena`、`s_query_vars`），使大缓冲不随对象落在栈上。
- **verification** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1048, source_part_index: 0, quote: `PASS  parse simple fact: foo.`, supports: 此前无输出即退出的 `test_parser` 在整批修改后输出了用例明细（12/12），同样恢复输出的还有 `test_terms` 15/15、`test_unifier` 16/18、`test_solver` 18/22，证明启动崩溃已消除。
- **verification** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 1048, source_part_index: 0, quote: `=== 4 suite(s) PASSED, 3 FAILED ===`, supports: 同一 harness 的汇总由修改前的 2 通过/5 无输出失败变为 4 通过/3 失败，且 3 个失败均带具体断言行；回归项 `test_lexer` 仍为 `22/22 tests passed`。多处修改同批发生（source_index 1002–1043），该验证只支持整批修改的效果。

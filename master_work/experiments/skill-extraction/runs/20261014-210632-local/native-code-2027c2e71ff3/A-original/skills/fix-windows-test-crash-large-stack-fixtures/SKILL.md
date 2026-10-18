---
name: fix-windows-test-crash-large-stack-fixtures
description: Use when C++ test binaries exit with code -1073741571 and print no test output at all on Windows, while other tests compile and link fine. Helps the agent find multi-MB fixture structs (arenas, databases, tables) declared as locals or by-value members in test bodies and move them to static storage, then re-run the suite to confirm previously-crashing tests produce results. Requires the ability to run each test binary and read its exit code. Do not use when the binary prints test results, when the crash occurs mid-run rather than before any output, or when the failure is a link error.
---
# Fix Windows Test Binaries That Crash at Startup Due to Multi-MB Stack Fixtures

## Goal
解决 Windows 上测试二进制启动即以 exit `-1073741571` 崩溃、完全无测试输出的问题：把测试夹具中按值持有的数 MB 大结构移入静态存储，并重跑测试套件确认原本崩溃的测试开始产生结果。

## Scope
### In scope
- 测试二进制**在任何测试输出之前**崩溃：exit code `-1073741571`、输出为空。
- 崩溃测试的夹具结构（如 `SolverCtx`/`ParseCtx`/`UnifyCtx`）按值内嵌多个数 MB 级结构（`TermArena` ~4MB、`AtomTable` ~1MB、`Database` ~4MB），在测试函数体内构造时全部落在栈上。
- 修复方式：把大成员改为 `static` 存储（类内 `static` 成员 + 文件作用域定义，或返回 `static` 局部引用的工厂），构造函数以引用绑定并在构造时重新初始化。
- 同类的局部 `AtomTable t;` 声明逐一替换为静态实例。

### Out of scope
- 已能输出测试结果、仅断言失败的测试（属逻辑问题）。
- 链接错误（LNK2019/LNK1105）与编译错误。
- 崩溃发生在部分测试输出之后的情形（本轨迹未提供证据）。
- 提高进程/线程栈大小（如 `/STACK`）的做法：轨迹未验证，不作为推荐。

## Inputs
- **测试运行输出与 exit code**：字符串+整数；来源：运行 `build\tests\<test>.exe` 的工具结果；必需；需见 `(exit -1073741571)` 且无任何测试行；默认值：无。
- **崩溃测试源文件**：文件（如 `tests/test_solver.cpp`、`tests/test_atoms.cpp`）；来源：按崩溃的测试名定位；必需；需包含夹具结构定义；默认值：无。
- **各结构体字节数线索**：字符串（注释/代码中的容量常量）；来源：源码阅读（如 `TERM_ARENA_CAPACITY`、`AtomTable`）；可选；用于估算按值成员的总大小；默认值：无。
- **测试构建脚本**：shell 命令；来源：轨迹中的测试构建脚本；必需；用于重编译并整套重跑；默认值：无。
- **Windows 默认栈大小前提**：环境约束；来源：平台常识+轨迹 Assistant 判断（“Windows has a 4MB default stack”）；必需；默认值：无。

## Outputs
### Artifacts
- 修改后的测试源文件：夹具大成员改为 `static` 类成员 + 文件作用域静态定义 + 引用绑定的构造函数；测试体内局部大对象替换为静态实例。
- 重编译并重跑的测试套件输出。

### Success criteria
- 原先 exit `-1073741571` 且无输出的测试开始打印测试结果（如 `12/12 tests passed`、`18/22 tests passed`），整套结果从 `0 输出的崩溃 suite` 变为可统计的通过/失败。

### Failure criteria
- 目标测试仍以 exit `-1073741571` 结束且无任何输出。
- 修改后其他原本通过的测试出现新的失败（说明静态存储引入了跨测试状态污染，需另行处理并报告）。

## Preconditions
- 能逐个运行测试二进制并读取 exit code（已确认崩溃值为 `-1073741571`）。
- 已排除链接/编译错误：这些测试文件在崩溃前成功编译链接并生成了 .exe。
- 崩溃发生在启动阶段：运行无任何测试输出（`--- <test> ---` 下为空或直接打印 `(exit -1073741571)`）。
- 已能在测试源码中找到按值持有大结构的夹具类型与局部大对象声明。
- 具备修改测试源文件并重跑构建的权限；不满足则停止并报告。

## Procedure
### Step 1: 确认崩溃形态（启动即崩、无输出）
- actions：单独运行每个失败的测试 exe，记录 exit code 与输出；筛选出“无任何测试输出 + exit -1073741571”的目标。
- inputs：构建产物。
- outputs：崩溃清单（轨迹首诊为 test_atoms、test_terms、test_parser、test_unifier、test_solver 五个全部 `(exit -1073741571)`）。
- cautions：exit `-1073741571` 仅说明启动崩溃，不要把它与断言失败混淆。
- preserve：不动已正常输出结果的测试。
- next：全部命中形态后进入 Step 2。

### Step 2: 找出夹具中按值持有的大结构
- actions：阅读崩溃测试的夹具结构，列出按值成员及其容量（如 `SolverCtx` 内两个 `TermArena` + `Database` + `AtomTable`）；估算总字节（轨迹估算：`AtomTable` ~1MB、`TermArena` ~4MB，两个 TermArena 即 ~8MB 在测试函数栈上）。
- inputs：崩溃测试源文件。
- outputs：需要移入静态存储的成员清单 + 测试体内的局部大对象清单（如 `AtomTable t;`）。
- cautions：只统计测试文件中的对象；引擎内部的静态数据不在本次范围。
- preserve：不改引擎源码。
- next：产出清单后进入 Step 3。

### Step 3: 把大成员移到静态存储
- actions：夹具结构改为 `static AtomTable s_atoms;` 等静态数据成员 + 引用成员绑定（`AtomTable &atoms;`），构造函数初始化列表绑定并在体内调用 `atom_table_init(&atoms)` 等重新初始化；在文件作用域补 `AtomTable SolverCtx::s_atoms = {};` 等定义；测试体内的局部大对象改为返回静态实例的工厂（如 `static AtomTable &fresh_table()` + `#define make_table() fresh_table()`），并逐一替换残留的局部声明。
- inputs：崩溃测试源文件。
- outputs：更新后的测试源文件。
- cautions：静态存储会跨测试共享，构造函数必须在每次构造时完整重新初始化（init 调用保留）；`static` 局部 `TokenList` 等既有静态保持 memset 初始化不变。
- preserve：测试断言、测试顺序、`TEST` 宏调用全部不动。
- next：重编译并整套重跑。

### Step 4: 重编译并整套重跑，区分残余问题
- actions：重跑构建脚本（编译+运行全部测试）；记录每个 suite 的输出与统计；对仍崩溃的目标重复 Step 2–3 检查是否还有遗漏的局部大对象。
- inputs：构建脚本。
- outputs：修复后结果（轨迹中 test_parser `12/12 tests passed`、test_terms `15/15 tests passed`、test_unifier `16/18 tests passed`、test_solver `18/22 tests passed`，仅 test_atoms 仍无输出）。
- cautions：断言失败（如 `18/22` 中的 4 个 FAIL）不是本 Skill 的目标，单独跟踪；test_atoms 崩溃需继续排查遗漏的局部声明。
- preserve：不通过放宽断言来“通过”测试。
- next：原崩溃目标均能输出结果为止；仍崩溃者按 Common Failures 继续。

## Decision Rules
### When 测试 exe exit `-1073741571` 且零输出
→ 判定为启动期崩溃（轨迹 Assistant 判断为栈溢出）；执行 Step 2–3 把大对象移入静态存储。

### When 夹具按值内嵌多个数 MB 结构且在测试函数体内构造
→ 必然超默认栈（轨迹估算 `SolverCtx` 两个 `TermArena` ~8MB）；改为静态成员 + 引用绑定（Step 3）。

### When 静态化后其他测试出现新失败
→ 静态存储跨测试共享导致状态污染；检查构造函数是否每次完整重新初始化（init 调用缺失即为原因候选，轨迹未提供该分支的完整验证，出现时停止并报告）。

### When 某测试静态化后仍崩溃
→ 继续在该测试文件中搜索残留的局部大对象声明（轨迹中 `test_atoms` 首轮静态化后仍崩，后续逐个替换局部 `AtomTable t;`）。

## Invariants
- 只改测试文件中的对象存储方式，不改引擎源码、不改测试断言与测试顺序。
- 静态化后的每个夹具在每次构造时都执行完整初始化（保持原有的 init 调用序列）。
- 不用放宽断言、跳过测试或提高栈大小等未验证手段换取“通过”。
- 不因某个 suite 仍崩溃而回滚其他已生效的静态化修改。
- 不把断言失败计为本修复的失败，也不把链接成功计为本修复成功；成功标准是“产生测试输出”。
- 不声称测试全部通过（轨迹最终仍有 suite 未恢复）。

## Common Failures
### Failure: 静态化后测试仍以 exit -1073741571 崩溃
- symptoms：重跑后该测试仍无输出、exit code 不变（轨迹中 `test_atoms` 在首轮静态化后仍 `exit: -1073741571`）。
- causes：该测试体内仍残留局部大对象声明（轨迹在 `test_atoms.cpp` 发现第一个测试仍有 `AtomTable t;` 局部声明，约 1MB）。
- recovery：逐个搜索并替换残留局部声明为静态实例后重编译重跑。

### Failure: 某个目标 exe 无法重新链接（LNK1105 文件被占用）
- symptoms：`LINK : fatal error LNK1105: cannot close file 'build\tests\<test>.exe'; error code 1224`。
- causes：上一轮运行/崩溃残留的测试进程仍持有该 exe。
- recovery：先结束同名测试进程再重跑链接（见 LNK1105 Skill）；不要误判为静态化修改导致的编译问题。

### Failure: 静态化引入跨测试状态污染
- symptoms：原本通过的测试在静态化后开始失败。
- causes：静态成员跨测试共享而构造时未完整重新初始化。
- recovery：确认每个构造函数重新执行全部 init；若仍失败，停止并报告（该分支轨迹未提供验证结论）。

## Verification
重编译并重跑整套测试，检查以下可观察项（应观察的检查，不声称已执行）：
- 原崩溃测试的运行输出不再出现 `(exit -1073741571)`，且出现 `--- <test> ---` 下的具体测试行。
- 整套统计从修复前形态（多个 `FAIL: <test>` 且其下为空 / `0 suite 输出`）变为可统计结果（轨迹中修复后为 `=== 4 suite(s) PASSED, 3 FAILED ===`，其中崩溃类为空输出仅剩 1 个）。
- 抽查恢复的 suite 有真实计数：`12/12 tests passed`、`15/15 tests passed`、`16/18 tests passed`、`18/22 tests passed`。
- 对仍无输出的目标单独运行，exit code 仍为 `-1073741571` 时按 Common Failures 继续排查，不计入成功。

## Examples
### Example 1: SolverCtx 两个 TermArena 按值内嵌导致启动崩溃（轨迹原例）
- input：运行 `build\tests\test_solver.exe` 等 5 个二进制全部 `(exit -1073741571)`、零输出；`SolverCtx` 按值含 `AtomTable atoms; Database db; TermArena clause_arena; … TermArena query_arena;`。
- procedure：Step 2 估算（两个 TermArena ~8MB 落在测试函数栈）；Step 3 改为 `static AtomTable s_atoms; …` + 引用成员 + 构造函数初始化列表绑定并调用各 init；补文件作用域 `AtomTable SolverCtx::s_atoms = {};` 等定义；Step 4 整套重跑。
- expected result：该 suite 从“无输出崩溃”变为打印 `18/22 tests passed  (4 FAILED)`（4 个断言失败属独立逻辑问题）。
- parameterized values：`<fixture>=SolverCtx`、`<big members>=TermArena×2 / Database / AtomTable`、`<exit code>=-1073741571`。

### Example 2: 测试体内的局部大对象
- input：`test_atoms.cpp` 第一个测试 `AtomTable t; atom_table_init(&t);`，整文件多处相同模式，静态化后仍崩溃。
- procedure：Step 3 引入 `static AtomTable &fresh_table() { static AtomTable t; atom_table_init(&t); return t; }` 与 `#define make_table() fresh_table()`，并逐个替换残留的局部 `AtomTable t;`。
- expected result：该测试停止在启动期崩溃并输出测试结果（轨迹未给出最终运行输出，最终状态以实测为准）。
- parameterized values：`<type>=AtomTable`、`<size>=~1MB`。

## Evidence
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：987；source_part_index：0；quote：`(exit -1073741571)`；supports：problem（test_atoms/test_terms/test_parser/test_unifier/test_solver 五个二进制全部该 exit code，且 `=== test_atoms ===` 之后无任何测试输出）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：989；source_part_index：0；quote：`These test binaries crash on startup — before any test runs.`；supports：problem 判定（Assistant 判断，含栈溢出解释）；同事件 quote：`in `test_solver.cpp` the `SolverCtx` struct has two `TermArena`s inline. That's ~8MB on the stack inside a test function. Need to make those `static`:`；supports：action 依据。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1057；source_part_index：0；quote：`AtomTable is ~1 MB — too large for the default Windows stack.`；supports：problem（`test_atoms.cpp` 中的源码注释，解释为何局部 `AtomTable t;` 不可用）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1036；source_part_index：0；quote：`static AtomTable   s_atoms;`；supports：action（`SolverCtx` 的按值成员改为静态成员，同 Edit 的 new_string 还包含 `AtomTable   &atoms;` 引用绑定与构造函数初始化列表 `: atoms(s_atoms), db(s_db), …`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1043；source_part_index：0；quote：`AtomTable   SolverCtx::s_atoms        = {};`；supports：action（文件作用域静态定义，同 Edit 还定义 `s_db`、`s_clause_arena`、`s_clause_vars`、`s_query_arena`、`s_query_vars`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1048；source_part_index：0；quote：`12/12 tests passed`；supports：verification（原崩溃的 test_parser 恢复输出；同一结果中还有 `15/15 tests passed`（test_terms）、`18/22 tests passed`（test_solver）、`16/18 tests passed`（test_unifier），整套 `=== 4 suite(s) PASSED, 3 FAILED ===`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1053；source_part_index：0；quote：`exit: -1073741571`；supports：scope 限制（test_atoms 首轮静态化后仍崩溃，说明修复需覆盖该文件所有局部大对象；最终结果轨迹未给出）。

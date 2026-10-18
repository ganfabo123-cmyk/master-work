---
name: fix-lnk2019-header-extern-inline-global
description: Use when MSVC/clang-cl links fail with LNK2019/LNK1120 for a symbol declared `extern` in a shared header whose single definition lives in a translation unit (e.g. main.cpp) that is not part of the failing link. Helps the agent relocate the definition into the header as a C++17 inline variable, drop the duplicate definition, and re-link the whole test set. Requires the LNK2019 output, the link command's source list, and edit access to the header and definition file. Do not use when the failure is a runtime crash or assertion failure after linking succeeds, or when the project cannot compile as C++17 or newer.
---
# Fix LNK2019 for a Header-Declared Global Defined Only Outside the Test Link

## Goal
消除因共享头文件中的 `extern` 全局变量其唯一定义位于测试链接集合之外的翻译单元而导致的 LNK2019 未解析外部符号错误，使所有测试二进制成功链接并进入运行阶段。

## Scope
### In scope
- 从 LNK2019/LNK1120 输出中识别未解析符号、引用函数与受影响的目标二进制。
- 核对失败链接命令中的翻译单元集合，确认定义所在文件是否被排除。
- 将共享头文件中的 `extern` 声明改为 C++17 `inline` 变量定义，并删除原源文件中的重复定义。
- 用同一链接脚本重跑，确认 LNK2019 消失且二进制可启动执行。

### Out of scope
- 链接成功之后的运行期失败（如启动即退出码 -1073741571 的栈溢出）与断言失败，这些另行处理。
- 非 C++17 环境（C、C++14）下该问题的替代方案：轨迹未提供。
- 构建系统重构、库拆分、预编译头等结构调整。
- MSVC 之外链接器的专有诊断行为。

## Inputs
1. **LNK2019/LNK1120 链接错误输出** — 类型：工具结果（构建脚本 stdout/stderr）；来源：测试构建脚本运行结果；必需：是；约束：需含未解析符号的可读名与 mangled 名、引用函数、目标 exe 路径；默认值：无。
2. **失败链接命令的翻译单元列表** — 类型：构建配置（PowerShell 测试循环与 Makefile 测试规则）；来源：仓库内构建脚本；必需：是；约束：需能确认定义所在源文件（如 `main.cpp`）是否在测试链接集合内；默认值：无。
3. **声明该符号的共享头文件路径** — 类型：源文件；来源：由错误中的符号与引用函数定位（本轨迹为 `d:\Epilog\include\log.hpp`）；必需：是；默认值：无。
4. **符号唯一定义所在源文件** — 类型：源文件；来源：全局搜索符号定义（本轨迹为 `d:\Epilog\main.cpp`）；必需：是；默认值：无。
5. **C++ 编译标准选项** — 类型：编译参数（本轨迹为 `-std=c++23`）；来源：构建脚本；必需：是（inline 变量要求 C++17 及以上）；默认值：无。

## Outputs
### Artifacts
- 修改后的共享头文件：`include/log.hpp` 中 `extern int g_verbose;` 替换为 `inline int g_verbose = 0;`（C++ 头文件，格式为源码文本）。
- 修改后的定义源文件：`main.cpp` 中原 `int g_verbose = 0;` 定义被移除（源码文本）。
- 新的测试构建运行输出：同一 harness 脚本产生的链接/运行结果（工具结果文本）。

### Success criteria
- 同一链接命令下所有 `tests/test_*.cpp` 目标不再出现 `error LNK2019` 与 `LNK1120`。
- 每个测试二进制被生成并进入运行阶段（出现 `--- test_xxx ---` 或运行期 PASS/FAIL 输出、退出码）。
- 原有日志宏 `LOG_INIT`/`VLOG` 的调用方式保持不变（仅符号定义位置改变）。

### Failure criteria
- 输出中仍存在 LNK2019/LNK1120。
- 出现新的重复定义或 ODR 类编译/链接错误。
- 部分或全部测试二进制仍无法生成。

## Preconditions
执行前必须确认：
- 能拿到完整的 LNK2019/LNK1120 链接输出，且失败发生在链接阶段（编译阶段无错误）。
- 能读到测试链接命令的源文件/目标文件清单，足以判断定义所在翻译单元是否在集合内（本轨迹 Makefile 明确注释测试只链接除 `main.o` 外的对象）。
- 编译标准为 C++17 或更高（本轨迹为 `-std=c++23`），否则 inline 变量方案不可用，需停止并报告。
- 允许编辑共享头文件与定义该符号的源文件；若只允许改测试代码则停止并报告。
- 能原样重跑同一测试构建脚本以做前后对照。

任一条件不满足时停止执行并报告缺失项，不做部分修改。

## Procedure
### Step 1: 从链接输出定位未解析符号
- actions: 读取 LNK2019 输出，提取可读符号名（`int g_verbose`）、mangled 名、引用函数（`vlog`）与目标 exe；统计有多少个测试二进制报告同一符号。
- inputs: LNK2019/LNK1120 工具结果。
- outputs: 未解析符号清单及其在各目标中的分布。
- cautions: 同一符号在全部 7 个测试二进制中失败，指向“单一定义缺失”，不要逐个测试文件加桩。
- preserve: 不改测试用例与断言。
- next: 若所有失败目标报同一符号 → Step 2。

### Step 2: 核对测试链接集合是否包含定义所在翻译单元
- actions: 阅读测试链接脚本与 Makefile 测试规则，列出参与链接的源/对象；全局搜索该符号的定义位置。
- inputs: 构建脚本、Makefile、符号搜索结果。
- outputs: 结论：定义只存在于被排除的 `main.cpp`（Makefile 注释 `# Shared object files (everything except main.o) linked into each test binary`）。
- cautions: 结论必须来自实际的链接清单，而不是推测。
- preserve: 不改链接集合本身（不把 main.cpp 加进测试链接，因其含 `main()` 会与测试的 `main` 冲突——本轨迹未做该尝试，仅记录为不采用的方向）。
- next: 确认定义被排除 → Step 3。

### Step 3: 在共享头文件中改为 inline 定义
- actions: 编辑 `include/log.hpp`，将 `extern int g_verbose;` 替换为 `inline int g_verbose = 0;`；确认头文件中 `log_init`/`vlog` 等内联函数仍能引用该变量。
- inputs: 头文件路径、C++ 标准版本。
- outputs: 已更新的头文件。
- cautions: 仅在标准 ≥ C++17 时执行；本项目其余内联函数已是 `inline`，符号定义方式与之保持一致。
- preserve: 保留日志宏与函数签名不变。
- next: 编辑成功 → Step 4。

### Step 4: 移除原定义源文件中的重复定义
- actions: 编辑 `main.cpp`，删除 `int g_verbose = 0;`（保留 `int main` 及其后的代码）。
- inputs: `main.cpp`。
- outputs: 已更新的 `main.cpp`。
- cautions: 头文件已给出定义后，原处的非 inline 定义必须删除；轨迹中该动作由“Remove the now-redundant definition from `main.cpp`”引出并执行成功。
- preserve: 不改动 `main()` 的其余逻辑（`LOG_INIT`、`repl_*` 调用）。
- next: 两处编辑均成功 → Step 5。

### Step 5: 重跑同一测试构建脚本验证链接
- actions: 原样执行 Step 1 使用的 PowerShell/构建脚本，逐个编译并运行 `tests/test_*.cpp`。
- inputs: 修改后的源码、原构建脚本。
- outputs: 新的 harness 输出（编译错误列表、各套件运行结果与汇总行）。
- cautions: 此步只证明链接问题已解决；输出中出现的运行期 FAIL 属于其他问题，不要据此回滚本修改。
- preserve: 不修改 harness 脚本以便前后对照。
- next: 输出不再含 LNK2019 且各二进制进入运行阶段 → 完成。

## Decision Rules
### When 同一未解析符号出现在所有测试二进制
说明定义所在翻译单元不在测试链接集合中：把定义移入共享头文件作为 `inline` 变量（本轨迹 `inline int g_verbose = 0;`），并删除原源文件中的定义，而不是修改链接集合或给每个测试加桩。

### When 编译标准低于 C++17
轨迹未提供该情形下已验证的替代方案（本轨迹在 `-std=c++23` 下验证）；停止并报告环境不满足。

### When 链接错误消失但部分测试仍失败
停止按链接问题处理：本轨迹修复后出现 5 个套件运行失败（其中 5 个二进制无输出、退出码 -1073741571），应转入运行期问题诊断流程，保留本修改。

### When 只有个别测试二进制报 LNK2019
与本技能已验证的模式不同（轨迹中 7/7 目标同报一符号），此时应先核对该目标独有的链接输入，轨迹未提供该分支的处理经验。

## Invariants
- 不修改测试用例、断言与 harness 脚本逻辑来绕过链接错误（验证要求脚本原样重跑）。
- 不向每个测试源文件添加该符号的重复定义。
- 不把 `main.cpp` 加入测试链接集合来掩盖定义缺失（避免 `main` 冲突）。
- 符号定义在头文件与原源文件之间只能存在一处（头文件 inline 定义 + 删除原定义）。
- 不改动与该符号无关的文件、宏和构建配置。
- 不把“链接成功”报告为“测试通过”；两者在输出中是不同阶段。
- 不在未重跑链接脚本前声称 LNK2019 已修复。

## Common Failures
### Failure: 只改头文件而保留原定义
- symptoms: 轨迹未提供该情形的工具输出；表现为预期会出现重复定义/ODR 类编译或链接错误（按 C++ 规则推断，非轨迹观察结果）。
- causes: 头文件已给出 `inline` 定义后，`main.cpp` 中残留的非 inline 定义与之并存。
- recovery: 按轨迹做法同步删除 `main.cpp` 中的 `int g_verbose = 0;`（Step 4），再重跑链接。

### Failure: 链接修复后测试仍失败被误当作链接未修好
- symptoms: harness 输出中已无 LNK2019，但汇总为 `=== 2 suite(s) PASSED, 5 FAILED ===`，且部分 `FAIL: <name>` 后无任何用例输出。
- causes: 与链接无关的运行期问题（本轨迹中后续定位为测试 fixture 占用栈过大导致启动即崩溃）。
- recovery: 保留本修改，按运行期问题流程单独处理；不要回滚 `inline` 定义。

### Failure: 未删除原定义或未重跑脚本即宣称修复
- symptoms: 只有编辑成功的提示（“The file ... has been updated successfully”），没有新的链接输出。
- causes: 把文件编辑成功当作链接成功。
- recovery: 必须用原 harness 重跑并检查输出中无 `error LNK2019` 后再下结论。

## Verification
对照修改前后的同一构建脚本输出，逐项检查：
- 修改前输出包含 7 条 `COMPILE ERROR`，每条都含 `error LNK2019: unresolved external symbol "int g_verbose"` 与 `fatal error LNK1120: 1 unresolved externals`；修改后输出中不再出现 `LNK2019` 与 `LNK1120` 字样。
- 每个 `tests/test_*.cpp` 都生成了对应 exe 并进入运行阶段：出现 `--- test_lexer ---`、`PASS  lex empty string produces only EOF` 之类的运行期输出，而不是编译错误块。
- 汇总行从 `=== 0 suite(s) PASSED, 7 FAILED ===`（全部因链接失败）变为 `=== 2 suite(s) PASSED, 5 FAILED ===`（失败已转为运行期性质）。
- `include/log.hpp` 中可见 `inline int g_verbose = 0;`，且不再有 `extern int g_verbose;`。
- `main.cpp` 中不再含 `int g_verbose = 0;`。
- 主程序 `epilog` 目标在删除定义后是否重新构建通过：轨迹未提供，未验证项不作结论。

注意：以上检查只证明 LNK2019 已解决；套件通过数与断言失败属于另一阶段的验证。

## Examples
### Example 1: 测试全数因 `g_verbose` 报 LNK2019
- input: 测试 harness 输出，7 个 `tests/test_*.cpp` 全部 `COMPILE ERROR`，错误为 `error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)" (?vlog@@YAXPEBD0ZZ)`，汇总 `=== 0 suite(s) PASSED, 7 FAILED ===`。
- procedure: Step 1 识别符号 `g_verbose` 与引用函数 `vlog`；Step 2 确认 Makefile 注释 `# Shared object files (everything except main.o) linked into each test binary` 且 `main.cpp` 是唯一定义处；Step 3 将 `d:\Epilog\include\log.hpp` 中 `extern int g_verbose;` 改为 `inline int g_verbose = 0;`；Step 4 从 `d:\Epilog\main.cpp` 删除 `int g_verbose = 0;`；Step 5 原样重跑 harness。
- expected result: 链接阶段不再报 LNK2019/LNK1120，全部 7 个二进制生成并运行；实测输出为 `=== 2 suite(s) PASSED, 5 FAILED ===`，其中 `test_lexer` 输出 `22/22 tests passed`、`test_variables` 输出 `17/17 tests passed`，其余 5 个为运行期失败（无用例输出），需另行处理。
- parameterized values: 符号名 `g_verbose`、引用函数 `vlog`、头文件 `include/log.hpp`、定义文件 `main.cpp`、编译标准 `-std=c++23`、测试目标数 7；替换到其他工程时按实际符号与文件路径代入。

## Evidence
- **problem** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 975, source_part_index: 0, quote: `error LNK2019: unresolved external symbol "int g_verbose" (?g_verbose@@3HA) referenced in function "void __cdecl vlog(char const *,char const *,...)" (?vlog@@YAXPEBD0ZZ)`, supports: 7 个测试目标在链接阶段报同一未解析符号 `g_verbose`，引用点为 `vlog`，属单一定义缺失而非单个测试的问题。
- **problem（条件）** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 940, source_part_index: 0, quote: `# Shared object files (everything except main.o) linked into each test binary`, supports: Makefile 中测试链接集合明确排除 `main.o`，即符号唯一定义所在翻译单元不在测试链接内。
- **action** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 977, source_part_index: 0, quote: `inline int g_verbose = 0;`, supports: 在 `d:\Epilog\include\log.hpp` 中把 `extern int g_verbose;`（同事件 old_string）替换为 C++17 inline 变量定义，工具结果为文件更新成功。
- **action** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 981, source_part_index: 0, quote: `int g_verbose = 0;`, supports: 从 `d:\Epilog\main.cpp` 删除原定义（old_string `int g_verbose = 0;` 被替换为 `int main`），配套动作由 source_index 980 的文本 `Remove the now-redundant definition from `main.cpp`:` 引出，工具结果为更新成功。
- **verification** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 984, source_part_index: 0, quote: `=== 2 suite(s) PASSED, 5 FAILED ===`, supports: 用同一 harness 重跑后输出中不再出现 `COMPILE ERROR`/`LNK2019`/`LNK1120`，全部 7 个测试二进制完成链接并进入运行阶段（对照 source_index 975 的 `=== 0 suite(s) PASSED, 7 FAILED ===` 与 7 条 COMPILE ERROR）。
- **verification** — file_id: `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`, source_index: 984, source_part_index: 0, quote: `PASS  lex empty string produces only EOF`, supports: 链接后的二进制真实执行并输出用例结果（`test_lexer` 22/22、`test_variables` 17/17），证明链接修复使程序可启动；其余 5 个套件的失败为运行期问题，不在本技能结论内。

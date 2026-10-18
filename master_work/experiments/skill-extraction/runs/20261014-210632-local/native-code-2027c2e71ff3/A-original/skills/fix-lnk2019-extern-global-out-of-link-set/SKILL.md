---
name: fix-lnk2019-extern-global-out-of-link-set
description: Use when LNK2019/LNK1120 reports an unresolved global variable that is declared extern in a shared header but defined only in a translation unit (e.g. main.cpp) that is not part of the failing link (e.g. per-test binaries). Helps the agent convert the header declaration into a single inline definition, remove the now-duplicate definition, and re-verify the exact link. Requires a C++ project compiled with a standard >= C++17 and the original build command. Do not use when the missing symbol is a function or class member with no definition anywhere, when the project is C (no inline variables), or when the link succeeds but tests fail at runtime.
---
# Fix LNK2019 for an Extern Global Defined Only in a TU Outside the Failing Link

## Goal
把 LNK2019（unresolved external symbol）指向的、仅定义在未参与链接的翻译单元中的 header 级 extern 全局变量，改为 header 内唯一 `inline` 定义并删除重复定义，使原先失败的每个目标都链接成功，且不改动任何引擎/业务逻辑。

## Scope
### In scope
- LNK2019 + LNK1120 报告的**全局变量**符号，该符号在共享头文件中以 `extern` 声明，定义只存在于一个不参与失败链接的 TU（如 `main.cpp` 不在测试链接的源列表中）。
- C++ 项目，编译标准 >= C++17（轨迹中为 `clang++ -std=c++23`，Windows/MSVC 风格 mangled name，如 `(?g_verbose@@3HA)`）。
- 用原构建命令重跑受影响目标的链接作为验证。

### Out of scope
- 缺失的函数或类成员实现（本轨迹未提供此类证据）。
- C 语言项目（`inline` 变量不可用，轨迹未提供方案）。
- 链接已成功后的运行时测试失败/崩溃（另行诊断，见该 Skill）。
- 通过把 `main.cpp` 加进每个测试目标或为每个目标单独补定义的替代做法：轨迹未验证，不作为推荐。

## Inputs
- **LNK2019/LNK1120 错误文本**：字符串；来源：链接命令输出（工具结果）；必需；须包含 `unresolved external symbol` 的符号名、mangled 名和引用它的函数；默认值：无。
- **声明所在头文件路径**：文件（如 `include/log.hpp`）；来源：由符号引用函数所属模块定位；必需；须能在其中找到 `extern int <symbol>;`；默认值：无。
- **符号定义所在 TU**：文件（如 `main.cpp`）；来源：全仓搜索符号定义；必需；用于确认其是否缺席于失败链接的源列表；默认值：无。
- **原始构建/链接命令**：shell 命令（可原样重跑的脚本）；来源：轨迹中的测试构建脚本；必需；需能观察每个目标的编译/链接退出码与输出；默认值：无。
- **C++ 标准版本参数**：编译参数；来源：构建命令；可选；`inline` 变量需要 >= C++17；轨迹中为 `-std=c++23`；默认值：轨迹未提供时按 >= C++17 检查。
- **链接源列表（$SOURCES）**：字符串数组；来源：构建脚本；必需；用于确认定义 TU 是否被排除（轨迹中该列表为 internals/parser/engine/repl 文件，不含 `main.cpp`）；默认值：无。

## Outputs
### Artifacts
- 修改后的共享头文件：`extern <type> <symbol>;` 替换为 `inline <type> <symbol> = <初始值>;`。
- 修改后的原定义 TU：删除其中对该符号的独立定义。
- 重跑的构建/链接输出（每个目标的编译与链接结果）。

### Success criteria
- 原先失败的目标链接输出中 `LNK2019` 与 `LNK1120` 出现 0 次，且生成了可执行文件。
- 全仓该符号只剩一个定义（header 中的 inline 定义），无 `Redefinition` 诊断。

### Failure criteria
- 任一目标仍出现 `LNK2019`/`LNK1120`。
- 编辑后出现 `Redefinition of '<symbol>'` 错误。
- 出现 “Inline variables are a C++17 extension” 且实际编译标准低于 C++17。

## Preconditions
- 已拿到完整 LNK2019 文本，能读出缺失符号名与 mangled 名（轨迹中为 `error LNK2019: unresolved external symbol` + `LNK1120: 1 unresolved externals`）。
- 能够原样重跑失败的构建/链接命令（同一源列表、同一编译参数）。
- 项目语言为 C++ 且编译标准 >= C++17；否则停止并报告（`inline` 变量方案不适用，轨迹未提供替代方案）。
- 已确认：符号在头文件中是 `extern` 声明，定义只存在于一个不参与该链接的 TU（如测试源列表不含 `main.cpp`）。
- 对头文件与原定义 TU 有编辑权限，且不会同时改动无关逻辑。
- 以上任一不满足时停止并报告，不做部分修改。

## Procedure
### Step 1: 从 LNK2019 定位符号、声明与定义
- actions：读链接输出，取 `unresolved external symbol` 的符号名（如 `int g_verbose`）与 mangled 名（如 `(?g_verbose@@3HA)`）；在头文件中找到 `extern` 声明；搜索该符号的定义所在 TU；对照链接命令的源列表确认该 TU 是否缺席。
- inputs：LNK2019 文本、头文件、构建脚本。
- outputs：符号名、声明文件、定义文件、定义 TU 是否在链接集合中的结论。
- cautions：mangled 名只说明符号类型（变量/函数）与语言，不要据此推断更多。
- preserve：不做任何修改。
- next：确认“声明在共享头 + 定义 TU 不在链接集合中”后进入 Step 2；否则停止并报告不适用。

### Step 2: 把头文件声明改为 inline 定义
- actions：将 `extern int <symbol>;` 替换为 `inline int <symbol> = 0;`（初始值沿用原定义）。
- inputs：头文件。
- outputs：更新后的头文件。
- cautions：编辑后编辑器诊断可能出现 “Inline variables are a C++17 extension” 警告——确认编译参数 >= C++17 即可忽略。
- preserve：不改动头文件中的其他声明、宏与函数。
- next：立即进入 Step 3（否则原定义会与 inline 定义冲突）。

### Step 3: 删除原定义 TU 中的重复定义
- actions：在原定义 TU（如 `main.cpp`）中删除 `int <symbol> = 0;` 及其注释行，保留 `main` 等其余代码。
- inputs：原定义 TU。
- outputs：更新后的 TU。
- cautions：若跳过本步，编辑器会报 `Redefinition of '<symbol>'`（轨迹中该错误确实在 Step 2 后立即出现）。
- preserve：只删除该符号定义行，不删除相邻函数。
- next：重跑构建。

### Step 4: 用原命令重跑受影响目标的链接
- actions：原样重跑构建脚本（对每个失败目标编译+链接），收集全部输出。
- inputs：原始构建命令。
- outputs：每个目标的链接结果。
- cautions：把“编译失败/链接失败/运行时失败”区分开；本步只对链接成功负责。
- next：链接无 LNK2019 后进入 Step 5。

### Step 5: 区分残余的运行时失败
- actions：若输出中出现 `FAIL:` 或空输出的测试，单独记录为运行时问题（轨迹中随后定位为测试栈溢出等问题），不回滚本修复。
- inputs：Step 4 输出。
- outputs：链接修复结论 + 独立的运行时问题清单。
- cautions：不得因运行时失败而宣称链接修复无效，也不得因链接成功宣称测试全部通过。
- preserve：不改测试代码来“配合”链接错误。

## Decision Rules
### When LNK2019 的符号是共享头文件中 `extern` 声明的全局变量，且其定义 TU 不在失败链接的源列表中
→ 采用“头文件 `inline` 定义 + 删除原 TU 定义”的两步修改（Step 2 + Step 3 必须成对执行）。

### When 编辑后出现 `Redefinition of '<symbol>'`
→ 说明原定义 TU 仍保留独立定义；立即按 Step 3 删除它，不要回退 header 的 inline 定义。

### When 编译诊断出现 `Inline variables are a C++17 extension`
→ 确认编译标准 >= C++17（轨迹使用 `-std=c++23`）；标准不足时停止并报告，不强行继续。

### When 链接已无 LNK2019 但测试运行失败或崩溃
→ 判定为独立的运行时问题（轨迹中为测试进程启动即崩溃，exit `-1073741571`），转交运行时诊断流程；本修复保持不变。

## Invariants
- 只修改共享头文件与该符号的原定义 TU，不改引擎/业务逻辑、不改测试断言。
- 每个全局符号最终只保留一处定义（header 中的 inline 定义），不留下第二处独立定义。
- 不为“绕过链接错误”向测试目标或构建脚本里塞入未验证的源文件/链接选项。
- 不跳过 Step 4 的原样重跑链接验证，不以编辑成功代替链接成功。
- 不把推测（如“可能是运行时初始化顺序问题”）当作结论写入报告。
- 不报告未经链接输出验证的“已修复”；链接成功也不等于测试全部通过。

## Common Failures
### Failure: 转换后原定义 TU 报 `Redefinition of '<symbol>'`
- symptoms：编辑器诊断 `Redefinition of 'g_verbose'`，指向 `main.cpp` 中残留的 `int g_verbose = 0;`。
- causes：header 已改为 inline 定义，但原 TU 的独立定义未删除（两步修改只做了第一步）。
- recovery：删除原 TU 中的该定义行后重新编译；轨迹中该错误在删除后消失。

### Failure: 链接通过后测试仍失败/空输出
- symptoms：构建输出不再有 LNK2019，但出现 `FAIL: <test>` 或测试二进制 exit `-1073741571` 且无任何测试输出。
- causes：与链接修复无关的独立运行时问题（轨迹后续定位为测试夹具把数 MB 结构放在栈上导致启动崩溃）。
- recovery：单独诊断运行时问题；不要回滚 header 的 inline 定义，也不要宣称链接修复失败。

### Failure: `Inline variables are a C++17 extension` 警告伴随较低标准
- symptoms：诊断消息 `Inline variables are a C++17 extension`。
- causes：编译标准低于 C++17。
- recovery：以 >= C++17 编译（轨迹为 `-std=c++23`）；无法升级标准时停止并报告（轨迹未提供替代方案）。

## Verification
对每个原失败目标，用**同一条构建命令**重跑并检查以下可观察项（描述为应观察的检查，不声称已执行）：
- 链接输出中 `LNK2019` 出现次数为 0。
- 链接输出中 `LNK1120` 出现次数为 0，且没有 `clang++: error: linker command failed`。
- 每个目标生成了可执行文件：构建脚本对其输出 `--- <test> ---`（或运行时 `FAIL:`）而不是 `COMPILE ERROR: <test>`。
- 汇总行不再是 0 通过（轨迹中修复前为 `=== 0 suite(s) PASSED, 7 FAILED ===`，修复后为 `=== 2 suite(s) PASSED, 5 FAILED ===`，其余 5 个为独立运行时失败）。
- 全仓搜索该符号：`extern int <symbol>;` 不再出现在头文件中，且 `int <symbol> = 0;` 定义仅剩 0 处（原 TU 已删）。
- 编辑器诊断中不存在 `Redefinition of '<symbol>'`。

## Examples
### Example 1: 测试二进制链接时缺少 `g_verbose`（轨迹原例）
- input：7 个测试目标的构建输出全部为 `error LNK2019: unresolved external symbol`（符号 `int g_verbose`，mangled `(?g_verbose@@3HA)`，引用者 `vlog`），`LNK1120: 1 unresolved externals`，`=== 0 suite(s) PASSED, 7 FAILED ===`；测试链接源列表包含 `internals/*、parser/*、engine/*、repl.cpp` 但不含 `main.cpp`。
- procedure：Step 1 定位 `include/log.hpp` 的 `extern int g_verbose;` 与 `main.cpp` 的 `int g_verbose = 0;`；Step 2 将声明改为 `inline int g_verbose = 0;`；Step 3 删除 `main.cpp` 中的 `int g_verbose = 0;`；Step 4 原样重跑测试构建脚本。
- expected result：所有测试目标完成链接（无 LNK2019/LNK1120）；随后运行结果为 2 个 suite 通过、5 个 suite 运行时失败（属独立问题）。
- parameterized values：`<symbol>=g_verbose`、`<header>=include/log.hpp`、`<defining TU>=main.cpp`、`<std flag>=-std=c++23`、`<type>=int`、`<初始值>=0`。

### Example 2: 判定不适用的情形
- input：LNK2019 指向一个函数符号，全仓搜索不到任何定义。
- procedure：执行 Step 1 的定位动作后即停止。
- expected result：报告“缺失实现/定义不存在，不属于本 Skill”，不执行 Step 2（本轨迹未提供此类证据与方案）。
- parameterized values：`<symbol>=<任意函数名>`。

## Evidence
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：975；source_part_index：0；quote：`solver-c181c1.o : error LNK2019: unresolved external symbol`；supports：problem（7 个测试目标均报告同一符号 `int g_verbose` 未解析，且 `build\tests\test_atoms.exe : fatal error LNK1120: 1 unresolved externals`，`=== 0 suite(s) PASSED, 7 FAILED ===`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：976；source_part_index：0；quote：`The only issue is `g_verbose` is `extern int` in `log.hpp` but defined in `main.cpp` which isn't linked into tests.`；supports：problem 定位（声明/定义/链接集合三者关系）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：974；source_part_index：0；quote：`clang++ -std=c++23 -Iinclude -Itests -g -O0 @SOURCES "$($test.FullName)" -o $bin 2>&1`；supports：problem 上下文（测试链接的编译命令；其 `$SOURCES` 列出 `internals/…、parser/…、engine/…、"repl.cpp"`，不含 `main.cpp`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：977；source_part_index：0；quote：`inline int g_verbose = 0;`；supports：action（将 `include/log.hpp` 中 `extern int g_verbose;` 替换为该 inline 定义）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：979；source_part_index：0；quote：`Redefinition of 'g_verbose'`；supports：action 的必要后续（`main.cpp` 残留独立定义触发错误，须删除；同一诊断还给出 `Inline variables are a C++17 extension` 警告）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：981；source_part_index：0；quote：`int g_verbose = 0;`；supports：action（从 `main.cpp` 删除该定义，old_string 为 `int g_verbose = 0;` 紧接空行与 `int main`，new_string 为 `int main`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：984；source_part_index：0；quote：`=== 2 suite(s) PASSED, 5 FAILED ===`；supports：verification（同一条构建脚本重跑后输出中不再出现任何 `COMPILE ERROR:`/`LNK2019` 行，7 个测试二进制全部链接并执行；其余 5 个为运行时失败，见 `FAIL: test_atoms`）。

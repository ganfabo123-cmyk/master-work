---
name: unique-test-ids-with-counter-macro
description: Use when a TEST-style registration macro fails to compile with repeated `redefinition of '_reg_...'` or `use of undeclared identifier '_test_body_N'` errors because a counter/paste id is expanded multiple times or pasted literally. Helps the agent capture __COUNTER__ exactly once by passing it as an argument to an implementation macro, so forward declaration, registrar, and body share one id. Requires a C/C++ preprocessor with __COUNTER__ support and a build command to recompile the test files. Do not use when identifiers are already unique, when the macro pastes a counter only once, or when the compile error is unrelated to token pasting (e.g. linker errors).
---
# Generate Unique Per-Test Identifiers in a Registration Macro with __COUNTER__

## Goal
让 TEST 风格的测试注册宏为每个测试生成唯一且一致的标识符，消除 `redefinition of '_reg_...'` 与 `use of undeclared identifier '_test_body_N'` 编译错误，使全部测试文件通过编译并正常注册运行。

## Scope
### In scope
- 一个宏内同时生成前向声明、静态 Registrar 注册对象和测试函数体，需要每次展开产生唯一标识符的场景。
- 两类已证实的失败：`##` 直接粘贴 `__LINE__`/`__COUNTER__` 得到字面量 `_reg___COUNTER__`（粘贴先于展开）；改用两级 `EPILOG_CONCAT` 间接展开后，同一宏体内 `__COUNTER__` 被引用三次导致三个不同数字、声明与定义不匹配。
- 使用 `__COUNTER__` 并通过“实现宏按参数接收一次”的修复方式。

### Out of scope
- 不涉及 `##` 粘贴、仅普通编译错误的宏问题。
- 测试注册机制的运行时问题（注册顺序、测试执行逻辑）。
- 链接或运行期失败（如 LNK2019、测试二进制崩溃），这些与标识符唯一性无关。

## Inputs
- **编译错误文本**：字符串；来源：测试构建命令输出；必需；需含 `redefinition of '<标识符>'` 或 `use of undeclared identifier '<标识符>'` 及宏展开 note（含宏定义行号）；默认值：无。
- **测试框架头文件**：文件（如 `tests/test_framework.hpp`）；来源：编译错误中的宏展开 note 定位；必需；包含 `TEST`、（可能已有）`EPILOG_CONCAT`/`EPILOG_CONCAT2` 宏定义；默认值：无。
- **预处理器计数宏支持**：编译器能力；来源：编译器（轨迹为 clang++/clangd on Windows）；必需；`__COUNTER__` 需可用；默认值：无。
- **重跑的编译命令**：shell 命令；来源：轨迹中的测试构建脚本；必需；用于验证修复后全部测试文件编译通过；默认值：无。
- **失败样例测试文件**：文件（如 `tests/test_atoms.cpp`）；来源：编译错误指向的文件；可选；用于最小化复现；默认值：无。

## Outputs
### Artifacts
- 修改后的测试框架头文件：`TEST_IMPL(name, uid)` 实现宏 + `#define TEST(name) TEST_IMPL(name, __COUNTER__)` 入口宏；保留 `EPILOG_CONCAT2(a, b) a##b` / `EPILOG_CONCAT(a, b) EPILOG_CONCAT2(a, b)` 两级粘贴。
- 重跑的测试编译输出。

### Success criteria
- 全部测试文件编译完成，不再出现 `redefinition of '_reg_...'` 或 `use of undeclared identifier '_test_body_...'`；错误进入链接阶段（或完全通过）。
- 测试二进制能运行并按声明顺序输出各测试结果（如 `22/22 tests passed`）。

### Failure criteria
- 同类 `redefinition` / `undeclared identifier` 错误再次出现。
- 编译虽通过但测试注册数与源文件中 `TEST(...)` 数量不一致（轨迹未提供该失败形态的验证，出现即停止报告）。

## Preconditions
- 编译器支持 `__COUNTER__`（轨迹中 clang 在 Windows 上可用；`__LINE__` 方案在该场景已证实失败，不作为替代）。
- 编译错误能定位到测试框架头文件中的宏定义行（错误 note 中含 `expanded from macro 'TEST'` 与头文件路径）。
- 能原样重跑测试编译命令以验证。
- 宏的使用者是“同一宏体内引用计数宏多次”的结构（前向声明 + 注册 + 定义）；否则本 Skill 不适用。
- 以上任一不满足时停止并报告。

## Procedure
### Step 1: 判定失败形态
- actions：读编译错误：若标识符是 `_reg___LINE__`/`_reg___COUNTER__` 这类“未展开字面量”，属于粘贴先于展开；若标识符是 `_test_body_2`、`_test_body_6` 等“数字存在但声明与定义不一致”，属于同一宏体内计数宏被多次展开。
- inputs：编译错误文本。
- outputs：失败形态结论。
- cautions：错误 note 中 `_test_body_0 declared here` 与 `expanded from here <scratch space>` 的数字差异是关键证据。
- preserve：不修改测试用例文件。
- next：两种形态都进入 Step 2；已具备计数宏间接层但仍不一致时直接进入 Step 3。

### Step 2: 建立两级 token 粘贴间接层
- actions：确保头文件中有 `#define EPILOG_CONCAT2(a, b) a##b` 与 `#define EPILOG_CONCAT(a, b)  EPILOG_CONCAT2(a, b)`；所有 `_reg_##X` / `_test_body_##X` 形式的粘贴改走 `EPILOG_CONCAT(prefix, X)`。
- inputs：测试框架头文件。
- outputs：更新后的宏定义。
- cautions：两级间接只解决“粘贴先于展开”，不解决“计数宏被多次展开”；完成后必须编译确认。
- preserve：不改 `Registrar` 类与测试执行逻辑。
- next：重跑编译；若出现“数字不一致”的 undeclared identifier，进入 Step 3。

### Step 3: 用实现宏把 __COUNTER__ 捕获一次
- actions：新增 `#define TEST_IMPL(name, uid)`，其体内三处（前向声明、Registrar 注册、函数定义）全部使用参数 `uid` 经 `EPILOG_CONCAT` 拼接；入口宏改为 `#define TEST(name) TEST_IMPL(name, __COUNTER__)`，使 `__COUNTER__` 仅在入口展开一次。
- inputs：测试框架头文件。
- outputs：更新后的 `TEST`/`TEST_IMPL` 宏。
- cautions：`TEST_IMPL` 体内不得再出现 `__COUNTER__`；否则回到多数字不一致。
- preserve：`TEST(name)` 的对外调用方式不变，测试文件零改动。
- next：重跑全部测试编译。

### Step 4: 用原构建命令重跑测试编译与运行
- actions：重跑测试构建脚本；确认不再有宏相关编译错误；运行生成的测试二进制观察通过数。
- inputs：原编译/运行命令。
- outputs：编译与运行结果。
- cautions：链接阶段的 LNK2019 等错误属于其它问题（另行处理），但“编译+注册+运行”链路须验证到测试能输出 `N/N tests passed`。
- preserve：不为消除链接错误改动宏。
- next：全部测试文件编译并可运行为止。

## Decision Rules
### When 错误是 `redefinition of '_reg___LINE__'` 或 `redefinition of '_reg___COUNTER__'`
→ `##` 在宏展开前粘贴，得到字面量标识符；先建立 `EPILOG_CONCAT2`/`EPILOG_CONCAT` 两级间接层（Step 2）。注意 `__LINE__` 在该结构下同样失败，改用 `__COUNTER__`。

### When 错误是 `use of undeclared identifier '_test_body_<N>'` 且 N 每次展开递增不同
→ 计数宏在同一宏体内被展开多次（每次递增）；将实现体抽成 `TEST_IMPL(name, uid)` 参数化，让 `__COUNTER__` 只在入口宏展开一次（Step 3）。

### When 编译错误已变为链接错误（如 LNK2019）
→ 标识符问题已解决，转入链接错误处理流程；不要继续修改测试宏。

## Invariants
- `TEST(name)` 的对外调用形式不变：不改任何测试用例文件即可修复。
- 一个宏体内对 `__COUNTER__` 的展开次数恰好为 1（只存在于入口宏）。
- token 粘贴一律经两级间接（`EPILOG_CONCAT` → `EPILOG_CONCAT2`），不直接 `prefix ## 计数宏`。
- 不改 `Registrar` 的注册/执行语义、不改测试执行顺序（按声明顺序）。
- 不把链接期或运行期错误当作本宏问题处理；不报告未经重跑编译验证的“已修复”。

## Common Failures
### Failure: `_reg___COUNTER__` 字面量重定义
- symptoms：`error: redefinition of '_reg___COUNTER__'`，note 显示 `expanded from here _reg___COUNTER__`（无数字）。
- causes：`prefix ## __COUNTER__` 中 `##` 先于参数展开执行，粘贴结果是字面量，所有测试得到同一标识符。
- recovery：改为 `EPILOG_CONCAT(prefix, __COUNTER__)` 两级间接展开（Step 2）；轨迹中 `__LINE__` 版本出现同样错误，不能靠换行号宏解决。

### Failure: `_test_body_<N>` 声明与定义数字不一致
- symptoms：`error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`，同一 `TEST` 展开中出现 0、2、6 等不同数字。
- causes：`TEST` 宏体三处引用 `__COUNTER__`，每次展开各自递增；两级间接层只解决粘贴、不解决多次展开。
- recovery：抽 `TEST_IMPL(name, uid)`，入口 `TEST(name) TEST_IMPL(name, __COUNTER__)`（Step 3）。

### Failure: 编译通过后出现 LNK2019 等链接错误
- symptoms：宏相关错误消失，输出转为 `error LNK2019: unresolved external symbol ...`。
- causes：与标识符无关的独立链接问题（轨迹中为 header extern 全局变量未参与测试链接）。
- recovery：按链接错误流程处理，不再改动测试宏。

## Verification
用同一条测试构建命令重跑，检查以下可观察项（应观察的检查，不声称已执行）：
- 输出中 `redefinition of '_reg_` 出现 0 次、`redefinition of '_test_body_` 出现 0 次。
- 输出中 `use of undeclared identifier '_test_body_` 出现 0 次。
- 每个 `tests/test_*.cpp` 都走到编译之后阶段：不再出现 `COMPILE ERROR: <file>`（宏错误形态下该行会带展开 note）。
- 运行生成的测试二进制输出形如 `22/22 tests passed`、`17/17 tests passed`，且测试名与源文件声明一致。
- 宏定义处 `__COUNTER__` 只出现一次（入口宏），`TEST_IMPL` 体内 0 次。

## Examples
### Example 1: 两级间接修复字面量粘贴（轨迹第 1 次尝试后的形态）
- input：`TEST("atom_table_init zeroes count")` 等多处 `error: redefinition of '_reg___COUNTER__'`；宏体为 `static ::epilog_test::Registrar _reg_##__COUNTER__(...)`。
- procedure：Step 2 加入 `#define EPILOG_CONCAT2(a, b) a##b` / `#define EPILOG_CONCAT(a, b)  EPILOG_CONCAT2(a, b)`，宏体改用 `EPILOG_CONCAT(_reg_, __COUNTER__)`。
- expected result：字面量重定义错误消失；若仍报数字不一致（`_test_body_2`），进入 Example 2。
- parameterized values：`<prefix>=_reg_` / `_test_body_`、`<counter>=__COUNTER__`。

### Example 2: TEST_IMPL 捕获计数一次（轨迹最终形态）
- input：`error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`，宏体三处引用 `__COUNTER__`。
- procedure：Step 3 将宏体重写为 `#define TEST_IMPL(name, uid)`，内部三处使用 `EPILOG_CONCAT(_test_body_, uid)`；入口 `#define TEST(name) TEST_IMPL(name, __COUNTER__)`。
- expected result：全部测试文件编译通过（错误降级为链接期 LNK2019），测试二进制输出 `22/22 tests passed` 等结果。
- parameterized values：`<name>=测试名字符串`、`<uid>=入口展开的唯一数字>`。

## Evidence
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：946；source_part_index：0；quote：`error: redefinition of '_reg___LINE__'`；supports：problem（`__LINE__` 直接 `##` 粘贴同样得到字面量标识符，note 显示 `static ::epilog_test::Registrar _reg_##__LINE__(name, _test_body_##__LINE__);`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：955；source_part_index：0；quote：`error: redefinition of '_reg___COUNTER__'`；supports：problem（换成 `__COUNTER__` 后仍因直接粘贴而全部重定义）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：964；source_part_index：0；quote：`error: use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`；supports：problem 的第二种形态（两级 `EPILOG_CONCAT` 后，`TEST` 宏体内三处 `__COUNTER__` 各自递增，声明 0、引用 2/6/10…）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：956；source_part_index：0；quote：`This happens because the `##` paste happens before macro expansion in this compiler invocation mode. The standard fix is an extra indirection level:`；supports：problem 机理与 Step 2 依据（来自 Assistant 判断）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：967；source_part_index：0；quote：`The root cause is clear: `__COUNTER__` is invoked **three times** inside the `TEST` macro — each invocation increments it, so the forward declaration, registration, and body get three different numbers.`；supports：problem 定位（Step 3 的依据，来自 Assistant 判断）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：968；source_part_index：0；quote：`#define TEST(name) TEST_IMPL(name, __COUNTER__)`；supports：action（同一 Edit 的 new_string 还包含 `#define TEST_IMPL(name, uid)` 与 `/* TEST — capture __COUNTER__ once via an intermediate macro so the * forward-declaration, registrar, and body definition all share one id. */` 的实现体）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：976；source_part_index：0；quote：`Good — `__COUNTER__` now works, all compile.`；supports：verification（重跑构建后宏错误消失，仅剩 LNK2019 链接错误，见 source_index 975 的输出中所有 `COMPILE ERROR` 行均为 `error LNK2019`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：984；source_part_index：0；quote：`--- test_lexer ---`；supports：verification（修复后测试二进制注册并运行，`22/22 tests passed`；`--- test_variables ---` 行下 `17/17 tests passed`）。

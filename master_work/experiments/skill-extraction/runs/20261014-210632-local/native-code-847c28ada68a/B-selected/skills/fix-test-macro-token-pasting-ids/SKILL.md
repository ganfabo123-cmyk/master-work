---
name: fix-test-macro-token-pasting-ids
description: Use when a single-header C++ test framework fails to compile with "redefinition of '_reg___LINE__'" or "use of undeclared identifier '_test_body_2'". Helps the agent fix token-pasting of __LINE__/__COUNTER__ in registration macros using a two-level concat helper and a single-capture TEST_IMPL macro. Requires the macro definition source and a real clang++/g++ compile to verify. Do not use for unrelated compile errors, link errors (e.g. unresolved externals), or test assertion failures.
---
# Generate unique TEST macro identifiers with __COUNTER__ captured once

## Goal
修复单头文件 C++ 测试框架中 TEST 注册宏因 `##__LINE__`/`##__COUNTER__` 未展开而生成重复标识符的编译错误，产出一个能被多个测试 .cpp 正常编译的宏定义。

## Scope
### In scope
- `#define TEST(name) static void _test_body_##__LINE__(); ...` 这类直接 `##` 粘贴 `__LINE__`/`__COUNTER__` 的写法，编译报 `redefinition of '_reg___LINE__'`。
- 两级 concat 宏（`CAT2(a,b) a##b` / `CAT(a,b) CAT2(a,b)`）使 `__LINE__`/`__COUNTER__` 先展开再粘贴。
- 同一宏体内多处引用 `__COUNTER__` 导致各处取到不同计数，需用 `TEST_IMPL(name, uid)` 一次性捕获。
- 用真实 clang++ 编译验证（不以 IDE/clangd 诊断为准）。

### Out of scope
- 链接错误（如 `unresolved external symbol "int g_verbose"`，属链接配置问题）。
- 测试逻辑断言失败。
- 测试框架的断言语义、注册容器设计。
- 其他与 token paste 无关的预处理错误。

## Inputs
1. **编译错误输出**：字符串，来源：真实 clang++/g++ 编译的工具结果，必需。约束：含 `redefinition of '_reg___LINE__'`、`redefinition of '_reg___COUNTER__'` 或 `use of undeclared identifier '_test_body_2'`。默认值：无。
2. **测试框架宏定义源码**：文件内容，来源：Read 测试头文件，必需。约束：需包含 TEST 宏及其辅助宏全文。默认值：无。
3. **真实编译命令**：字符串，来源：项目构建脚本或既有 PowerShell 编译行，必需。约束：必须逐编译单元执行；clangd/IDE 诊断不可作为验证。默认值：无。
4. **受影响测试文件列表**：字符串列表，来源：`tests/test_*.cpp` 通配，必需。约束：每个 .cpp 独立编译。默认值：无。

## Outputs
### Artifacts
- 修复后的测试框架头文件（原位修改），含 CAT/CAT2 与 TEST_IMPL 宏。
- 真实编译输出（证明 redefinition / undeclared identifier 消失）。

### Success criteria
- 所有 `tests/test_*.cpp` 真实编译不再出现 `_reg___LINE__`/`_reg___COUNTER__` redefinition 或 `_test_body_N` undeclared identifier。
- 测试二进制成功生成并可运行。

### Failure criteria
- 仅 IDE/clangd 显示正常但真实编译仍报错。
- 编译通过但因其他错误（链接、语法）无法生成二进制且未区分原因。

## Preconditions
- 已能运行真实编译器（clang++）并对每个测试 .cpp 单独编译；轨迹证明 IDE/clangd 的"误报"判断可能错误，未做真实编译不得下结论。
- 拥有测试框架头文件的编辑权限。
- 确认错误确实来自 token paste（错误信息中出现字面 `_reg___LINE__` / `_reg___COUNTER__`），否则停止并按其他编译错误处理。
- 每个测试 .cpp 作为独立翻译单元编译（同名 `__LINE__` 在不同 TU 本不冲突，冲突说明粘贴失败）。

## Procedure
### Step 1: 读取编译错误并确认粘贴失败
- actions: 运行真实编译，记录首个错误全文。
- inputs: 编译命令、任一测试 .cpp。
- outputs: 错误含 `redefinition of '_reg___LINE__'`（标识符是字面 `__LINE__` 而非数字）。
- cautions: 不要先假定"clangd 误报"——轨迹中该假定随后被真实编译失败推翻。
- preserve: 不改测试文件本身。
- next: 确认为粘贴问题 → Step 2；错误为其他类型 → 停止。

### Step 2: 引入两级 concat 宏
- actions: 在框架头中新增 `#define EPILOG_CONCAT2(a, b) a##b` 与 `#define EPILOG_CONCAT(a, b) EPILOG_CONCAT2(a, b)`，把 `_reg_##__LINE__` 改为 `EPILOG_CONCAT(_reg_, __LINE__)`（`__COUNTER__` 同理）。
- inputs: 宏定义源码。
- outputs: 更新后的 TEST 宏。
- cautions: 两级展开顺序不可颠倒（先 `##` 的那级必须是被调用方）。
- preserve: 寄存器/断言逻辑不变。
- next: Step 3。

### Step 3: 捕获单次 __COUNTER__
- actions: 若编译报 `use of undeclared identifier '_test_body_2'`（同一宏内 3 处 `__COUNTER__` 取到不同值），新增 `TEST_IMPL(name, uid)`，在其中用 `uid` 展开前向声明、注册与函数体；TEST 仅写 `#define TEST(name) TEST_IMPL(name, __COUNTER__)`。
- inputs: Step 2 后的宏与新错误输出。
- outputs: `#define TEST(name) TEST_IMPL(name, __COUNTER__)`。
- cautions: uid 只在 TEST 中求值一次；`__LINE__` 场景同理可捕获。
- preserve: 不改变测试的注册顺序语义。
- next: Step 4。

### Step 4: 真实编译验证
- actions: 对全部 `tests/test_*.cpp` 逐一执行真实编译，检查是否还有 redefinition/undeclared identifier。
- inputs: 编译命令。
- outputs: 编译阶段无该类错误（若出现 LNK2019 等链接错误，记录为链接问题，另行处理）。
- cautions: 不要在此步顺手把链接问题当作宏问题继续改宏。
- preserve: 保留原失败输出作对照。
- next: 编译干净 → Step 5；仍有宏错误 → 回到 Step 2/3。

### Step 5: 生成并运行测试
- actions: 完成链接后运行各测试二进制，确认输出测试计数。
- outputs: `N/N tests passed` 且 exit 0。
- cautions: 若运行崩溃（如 -1073741571），转 fix-windows-0xc00000fd-stack-overflow，不属于本流程。
- preserve: 不改断言。
- next: 全部套件可运行并通过 → 完成。

## Decision Rules
### When 错误信息中的标识符是字面 `_reg___LINE__` / `_test_body___LINE__`
`##` 未先展开参数：使用两级 concat 宏（CAT2/CAT）。

### When 改用直接 `##__COUNTER__` 后仍报 `_reg___COUNTER__` redefinition
直接粘贴同样不展开：改用两级 concat。

### When 两级 concat 后报 `use of undeclared identifier '_test_body_2'`（前向声明是 `_test_body_0`）
同一宏体内 `__COUNTER__` 被求值多次、每次递增：用 `TEST_IMPL(name, uid)` 一次性捕获。

### When IDE/clangd 报 redefinition 但不确定真假
一律以真实编译器输出为准；轨迹中"clangd 误报"的判断被真实编译失败否定。

### When 真实编译已无宏错误但链接报 unresolved external
属于链接配置问题（不在本 skill 范围），不要继续修改宏。

## Invariants
- 只改测试框架头中的宏定义，不改各测试 .cpp 的用法。
- 不用删除测试、合并测试的方式绕过重定义错误。
- 不改断言语义、不改注册容器实现。
- 每次修改后必须真实编译验证，不以 IDE 诊断替代。
- 不把链接阶段错误归因于宏，也不把宏问题归因于链接。
- 不报告未验证的成功。

## Common Failures
### Failure: 先判定为"clangd 误报"而未验证
- symptoms: 助手声称 redefinition 是 IDE 跨文件分析的假象，随后真实编译同样报 `redefinition of '_reg___LINE__'`。
- causes: 直接 `##__LINE__` 确实不会先展开，编译器层面就是错误。
- recovery: 立即用真实编译复核，再决定修法。

### Failure: 只把 `__LINE__` 换成 `__COUNTER__` 仍重定义
- symptoms: 错误变为 `redefinition of '_reg___COUNTER__'`。
- causes: `##` 粘贴前参数不展开，`__COUNTER__` 保持字面量。
- recovery: 使用两级 concat 宏。

### Failure: 两级 concat 后出现 undeclared identifier 序号错位
- symptoms: `use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`
- causes: 一个宏体内 3 次 `__COUNTER__` 分别递增，声明/注册/定义拿到不同 id。
- recovery: 引入 `TEST_IMPL(name, uid)` 让 uid 只求值一次。

## Verification
- 对每个 `tests/test_*.cpp` 运行真实 clang++ 编译：输出中不再出现 `redefinition of '_reg_` 或 `use of undeclared identifier '_test_body_`。
- 编译错误清单中该类错误归零；若仅剩 `unresolved external symbol` 等链接错误，说明宏问题已解决（链接另行处理）。
- 链接完成后运行测试二进制，出现 `22/22 tests passed` 一类计数且 exit 0。
- 宏展开抽查：编译器诊断（-E 或错误行号）显示注册名与函数体名一致（同为 `_reg_<N>`/`_test_body_<N>`）。

## Examples
### Example 1: __LINE__ 字面粘贴导致全部 TEST 重定义
- input: 编译 `tests/test_atoms.cpp` 报 `redefinition of '_reg___LINE__'`，同一文件内多个 TEST 全部冲突。
- procedure: Step 1 确认字面 `__LINE__` → Step 2 引入 `EPILOG_CONCAT2/EPILOG_CONCAT` 并替换 `##__LINE__` → Step 4 真实编译。
- expected result: 该文件编译不再出现 redefinition。
- parameterized values: 宏前缀（EPILOG_/项目名）与标识符前缀 `_reg_`/`_test_body_` 按框架替换。

### Example 2: __COUNTER__ 多次求值导致序号错位
- input: 两级 concat 生效后编译报 `use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?`。
- procedure: Step 3 新增 `TEST_IMPL(name, uid)` 承载前向声明/注册/函数体，TEST 改为 `TEST_IMPL(name, __COUNTER__)` → Step 4 全量真实编译 → Step 5 运行。
- expected result: 编译阶段无宏类错误；随后各套件可运行（如 lexer `22/22 tests passed`）。
- parameterized values: uid 变量名、`__LINE__`/`__COUNTER__` 选择按框架需求替换。

## Evidence
- problem: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=946, source_part_index=0, quote="redefinition of '_reg___LINE__'", supports=直接 `##__LINE__` 未展开导致的真实编译错误。
- problem: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=955, source_part_index=0, quote="redefinition of '_reg___COUNTER__'", supports=仅替换为 `##__COUNTER__` 后错误依旧（粘贴仍不展开）。
- problem: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=964, source_part_index=0, quote="use of undeclared identifier '_test_body_2'; did you mean '_test_body_0'?", supports=两级 concat 后暴露的多点 `__COUNTER__` 求值错位。
- action: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=967, source_part_index=0, quote="`__COUNTER__` is invoked **three times** inside the `TEST` macro", supports=根因判断（一次捕获的依据）。
- action: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=968, source_part_index=0, quote="#define TEST(name) TEST_IMPL(name, __COUNTER__)", supports=一次性捕获 uid 的关键修复。
- action: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=937, source_part_index=0, quote="The redefinition errors are a clangd false positive", supports=失败教训：先误判为 IDE 误报，随后被真实编译否定。
- verification: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=975, source_part_index=0, quote="unresolved external symbol", supports=宏修复后编译阶段不再报宏类错误、仅剩链接问题（边界确认）。
- verification: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=984, source_part_index=0, quote="22/22 tests passed", supports=随后测试二进制生成并运行通过（该步之前另有链接修复，见 Out of scope）。

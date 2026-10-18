---
name: fix-lexer-dot-after-concatenated-literals
description: Use when a Prolog-style parser reports "expected '.', got operator '.'" only for test programs built from adjacent string literals. Helps the agent find lexer rules that accept '.' as a terminator only at EOF or before whitespace, locate concatenated literals that dropped the separating space, and fix the literals rather than the lexer. Requires the parse error message, the lexer's dot-handling source, and the ability to rebuild and run the test suite. Do not use when the failure reproduces with a single non-concatenated string, or when lexing/parsing fails for other tokens.
---
# Restore separator whitespace lost when concatenating clause string literals

## Goal
修复因相邻字符串字面量拼接丢失分隔空白、导致 `.` 被词法器当作 operator 而出现 "expected '.', got operator '.'" 的解析失败，产出可在多子句程序上正确解析并通过相关测试的结果。

## Scope
### In scope
- Prolog 风格词法器把 `.` 识别为 TOK_DOT 的条件是"到达字符串结尾或下一个字符是空白"。
- 由 `".... clause." "next clause..."` 这类相邻字面量拼接造成的 `.` 后紧跟字母/括号。
- 修复动作：在前一字符串字面量末尾补一个空格，并 grep 全部同类拼接点。
- 重编译并运行相关测试套件验证。

### Out of scope
- 修改词法器规则来接受无空白的 `.`（除非产品需求明确变更）。
- 单个非拼接字符串也复现的解析错误。
- 词法器其他 token 规则、求解器行为、断言失败。

## Inputs
1. **解析错误消息**：字符串，来源：测试/调试程序的工具结果，必需。约束：形如 `[load] parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'`。默认值：无。
2. **词法器 dot 规则源码**：文件内容，来源：Read 词法器实现，必需。约束：需看到判定 `i+1U >= len || is_space(src[i+1U])` 一类条件。默认值：无。
3. **含子句程序的字符串字面量**：文件内容，来源：Read/Grep 测试文件，必需。约束：定位以 `."` 结尾并紧邻下一段字面量的位置。默认值：无。
4. **编译与运行命令**：字符串，来源：项目既有构建方式，必需。约束：能重编译受影响套件并运行。默认值：无。

## Outputs
### Artifacts
- 修改后的测试/示例字符串字面量（原位修改，每处末尾补分隔空格）。
- 重编译后的测试二进制与运行输出。

### Success criteria
- `load()` 不再返回 -1，`loaded` 子句数与预期一致。
- 相关测试套件输出 `N/N tests passed`（如 22/22），exit 0。

### Failure criteria
- 仍有 `expected '.', got operator '.'`。
- 为绕过错误改写了词法器规则或删除了测试。

## Preconditions
- 已读取词法器 `.` 处理代码，确认"仅在结尾或后随空白时才是 TOK_DOT"这一规则存在。
- 已能重编译并运行受影响测试套件。
- 拥有测试/示例源文件编辑权限；修改词法器需另行授权。
- 若错误消息不是关于 `.` 的，停止本流程。

## Procedure
### Step 1: 从错误消息确认 dot 被当成 operator
- actions: 运行失败用例，记录解析错误全文；确认 `expected '.', got operator '.'` 且 `load()` 返回 -1（可临时加诊断打印子句计数）。
- inputs: 失败测试或最小复现。
- outputs: 错误消息与"第几条子句后失败"。
- cautions: `loaded=-1` 且已入库子句数小于预期，说明失败发生在中途而非第一条。
- preserve: 不改断言。
- next: 错误是 dot 相关 → Step 2。

### Step 2: 读取词法器确认规则
- actions: Read 词法器源码中生成 TOK_DOT/TOK_OP 的分支。
- inputs: 词法器源文件。
- outputs: 确认 `.` 只有在结尾或后随空白时才产出 TOK_DOT。
- cautions: 规则确认前不要动测试字符串。
- preserve: 不改词法器。
- next: 规则符合 → Step 3。

### Step 3: 找出所有会丢分隔符的字面量拼接
- actions: Read 出错的测试字符串；再用 Grep（如 `\.\" *$`）列出所有"以 `.` 结尾且与下一段拼接"的字面量。
- inputs: 测试文件。
- outputs: 需修改的字面量清单（行号）。
- cautions: 只有当后一段以非空白字符（字母、`(`、`?` 等）开头时才必须补空格；补在前一段末尾。
- preserve: 只改字符串内容，不改测试结构。
- next: 清单非空 → Step 4。

### Step 4: 在前一段末尾补一个空格
- actions: 逐处 Edit，如 `"parent(alice, bob). parent(bob, carol). "` 与下一段拼接；确保拼接后 `.` 后恰有一个空白。
- inputs: 字面量清单。
- outputs: 修改后的测试源文件。
- cautions: 漏改一处仍会在该用例失败；不要给已有空格的字面量重复加空格。
- preserve: 不改词法器、不删测试。
- next: Step 5。

### Step 5: 重编译并运行验证
- actions: 重编译受影响套件并运行，检查解析错误消失与测试计数。
- inputs: 编译/运行命令。
- outputs: `N/N tests passed`、exit 0。
- cautions: 若链接报文件被占用，先处理占用（handle-locked-or-stale-test-binaries）。
- preserve: 保留修复前的失败输出。
- next: 全部通过 → 完成；仍有同类错误 → 回 Step 3 补漏。

## Decision Rules
### When 解析错误为 `expected '.', got operator '.'` 且 `load()` 中途返回 -1
优先检查子句源字符串的拼接处是否丢失了 `.` 后的空白。

### When 单条子句的用例通过、多子句拼接的用例失败
确认是拼接分隔问题，按 Step 3/4 补空格。

### When 词法器规则为"结尾或后随空白才算 TOK_DOT"
不要改词法器迁就测试；改测试字符串。

### When 某些拼接处 `.` 后已经是空格
无需修改；只处理 `.` 直接紧邻字母/括号的位置。

## Invariants
- 不修改词法器规则来掩盖字符串拼接缺陷（除非另有明确需求变更授权）。
- 不删除或放宽相关测试。
- 每处字面量修改后必须重新编译并运行该套件验证。
- 不只修报错的那一处而留下其他同类拼接隐患。
- 不把解析失败归因于求解器或测试框架。
- 不报告未验证的成功。

## Common Failures
### Failure: 只修了首个报错的字符串
- symptoms: 第一个失败用例通过，后续用例（ancestor、reachable 等）仍报同样的 dot 错误或 load 失败。
- causes: 同一文件有多处 `."` + 字母开头的拼接。
- recovery: Grep 全文件列出所有 `."` 结尾的字面量并逐处补空格。

### Failure: 把解析错误当成求解器问题
- symptoms: 反复查回溯/索引但 `load()` 返回 -1、子句根本没入库。
- causes: 失败发生在 parse 阶段，数据库里只有部分子句。
- recovery: 先打印 load 的子句计数与 `p.error_msg`，确认错误类别后再定位。

### Failure: 诊断打印残留
- symptoms: 测试输出混入 `[DEBUG ...]`/`[load] ...` 行。
- causes: 临时诊断未移除。
- recovery: 验证完成后删除诊断打印再做最终运行。

## Verification
- 重编译后运行目标套件：不再出现 `expected '.', got operator '.'`。
- `load()` 返回的子句数与字符串中的子句数一致（如 3 条子句返回 3）。
- 原先失败的用例转为 PASS（例如 `PASS  two-body rule resolves via conjunction`、`PASS  recursive rule — ancestor`）。
- 套件计数为满值（如 `22/22 tests passed`）且 exit 0。
- Grep `\.\" *$` 复查：不存在 `.` 后紧跟非空白的拼接点。

## Examples
### Example 1: two-body 规则字符串拼接丢空格
- input: `ctx.load("parent(alice, bob). parent(bob, carol)." "gp(X,Y) :- parent(X,Z), parent(Z,Y).")` 报 `[load] parse error after 1 clauses: code=2 msg=line 1: expected '.', got operator '.'`，`loaded=-1`。
- procedure: Step 1 确认 dot 错误与子句计数 → Step 2 读词法器确认"后随空白才 TOK_DOT" → Step 4 在前一段末尾补空格 → Step 5 重编译运行。
- expected result: `PASS  two-body rule resolves via conjunction`，套件 `22/22 tests passed`。
- parameterized values: 谓词名与子句内容按项目替换；错误消息文本保持一致。

### Example 2: 多处同类拼接的批量清理
- input: 首处修复后 `ancestor`、`reachable` 用例仍失败。
- procedure: Step 3 Grep 列出所有以 `."` 结尾的字面量 → Step 4 逐处补空格（含 `"path(a, b). path(b, c). path(a, c)."` 与下一段的拼接、规则行之间的拼接）→ Step 5 全量重跑。
- expected result: 全部相关用例 PASS，套件满值通过。
- parameterized values: Grep 模式 `\.\" *$` 按实际引号风格调整。

## Evidence
- problem: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1127, source_part_index=0, quote="expected '.', got operator '.'", supports=解析错误症状（load 中途失败，仅 1 条子句入库）。
- problem: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1113, source_part_index=0, quote="[DEBUG two-body] loaded=-1 db.clause_count=1 db.pred_count=1 arena.count=6", supports=load 返回 -1、子句计数与 arena 计数不匹配的可观测症状。
- action: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1128, source_part_index=0, quote="the lexer is tokenizing `.` as `TOK_OP` instead of `TOK_DOT`. This happens when the character after `.` is NOT whitespace.", supports=根因（依据词法器规则）。
- action: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1136, source_part_index=0, quote="parent(alice, bob). parent(bob, carol). ", supports=在前一字符串字面量末尾补分隔空格的关键动作。
- action: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1141, source_part_index=0, quote="ancestor(X,Y) :- parent(X,Z), ancestor(Z,Y).", supports=用 Grep 列出同类 `."` 结尾字面量、系统定位全部拼接点。
- verification: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1191, source_part_index=0, quote="PASS  two-body rule resolves via conjunction", supports=修复后原失败用例通过。
- verification: file_id=claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06, source_index=1191, source_part_index=0, quote="22/22 tests passed", supports=修复后 test_solver 整套满值通过。

---
name: fix-prolog-literals-clause-separator-space
description: Use when multi-clause Prolog/Epilog source passed to a loader fails to load (load returns -1, partial clause count) and the source is written as adjacent C++ string literals whose split point removes the space after a `.` clause terminator. Helps the agent locate the concatenation seams, add a trailing space at the end of each literal before the join, and re-run the affected tests until all clauses load. Requires a C/C++ compiler, the test build command, and a loader that reports the clause/parse failure. Do not use when the source is a single literal, when load succeeds and only query results differ, or when the failure is a link error.
---
# Keep Whitespace After the Clause Terminator When Splitting Prolog Source Across Adjacent String Literals

## Goal
修复“相邻 C++ 字符串字面量拼接处缺失空白导致多子句 Prolog 源加载失败”的问题，使 `load()` 成功加载全部子句、相关测试由 FAIL 转为 PASS。

## Scope
### In scope
- 测试中以相邻字符串字面量书写的 Prolog/Epilog 源，拼接缝正好落在 `.` 子句终止符之后（如 `"...carol)."` 紧接 `"gp(X,Y) :- ..."`，合成后成为 `carol).gp`）。
- 症状：`load()` 返回 -1，调试输出显示已加载子句数少于源中的子句数（如 `loaded=-1 db.clause_count=1 arena.count=6`），随后 `query()` 断言失败。
- 修复：在每个拼接缝的前一个字面量末尾补一个空格，使子句终止符后保留分隔空白。
- 验证：重编译并重跑测试，原失败用例转为 PASS。

### Out of scope
- 单一字面量书写、内部子句之间本就有空格的源。
- `load()` 成功但查询语义错误的用例（引擎逻辑问题）。
- 链接错误（LNK2019/LNK1105）与启动崩溃。
- `assert` 经 query 写入会被重置的 arena 所导致的失败（已知机制限制，属另一问题）。

## Inputs
- **失败测试输出**：字符串；来源：测试构建脚本运行结果；必需；含具体 FAIL 用例名与断言行；默认值：无。
- **测试源文件**：文件（如 `tests/test_solver.cpp`）；来源：FAIL 行指向的文件与行号；必需；含 `ctx.load("..." "..." )` 形式的相邻字面量；默认值：无。
- **加载器返回值/调试输出**：字符串；来源：临时在 `load()` 中加入的 fprintf 或测试内调试打印；可选；用于确认 `loaded=-1` 与部分子句已入库；默认值：无。
- **测试构建命令**：shell 命令；来源：轨迹中的测试构建脚本；必需；用于重编译重跑；默认值：无。
- **子句加载辅助函数签名**：代码；来源：测试夹具（如 `int load(const char *src)`，内部依次 `lex` → `parser_init` → 循环 `parser_next_clause` → `db_assert_last`）；必需；用于判断失败发生在哪一段；默认值：无。

## Outputs
### Artifacts
- 修改后的测试源文件：每个拼接缝的前一字面量末尾多一个空格（如 `"parent(alice, bob). parent(bob, carol). "`）。
- （可选）临时加入的加载调试打印，修复确认后移除。
- 重编译重跑的测试输出。

### Success criteria
- `load()` 不再返回 -1，断言该返回值的用例通过。
- 原失败用例在重跑输出中显示 PASS，所在 suite 达到全通过（轨迹中 test_solver 达到 `22/22 tests passed`）。

### Failure criteria
- 加空格后 `load()` 仍返回 -1，或失败用例仍为 FAIL。
- 为“通过”而修改断言或放宽期望值。

## Preconditions
- 失败用例的源字符串是**多个相邻字面量拼接**而成，且至少有一个拼接缝紧跟在 `.` 之后。
- 能拿到 `load()` 的实际返回值（直接返回值或临时调试输出），确认加载失败而非查询逻辑失败。
- 能用原构建命令重编译并重跑相关测试。
- 加载器在遇到非法/歧义 token 时会使 `parser_next_clause` 返回非 `PARSE_OK`、`load()` 返回 -1（本项目行为）。
- 以上任一不满足（如源为单一字面量、load 成功）则停止并报告不适用。

## Procedure
### Step 1: 用调试输出确认是“加载失败”而非“查询失败”
- actions：在测试夹具的 `load()` 各失败分支加 `fprintf(stderr, ...)`（`lex failed` / `parser_init failed` / `parse error after %d clauses` / `db_assert_last failed after %d clauses`），或在失败用例中打印 `load()` 返回值与 `db.clause_count`/`arena.count`；重跑该测试。
- inputs：测试源文件、构建命令。
- outputs：失败分支与已加载子句数（轨迹观察到 `[DEBUG two-body] loaded=-1 db.clause_count=1 db.pred_count=1 arena.count=6`，即第 3 个子句处失败）。
- cautions：调试打印只加在失败用例与 `load()` 内部，确认后移除。
- preserve：不改断言、不改引擎。
- next：确认 `load()` 返回 -1 且失败点位于多子句子句串后，进入 Step 2。

### Step 2: 检查源字符串的字面量拼接缝
- actions：打开失败用例的 `ctx.load(...)` 实参，列出相邻字面量的每个拼接位置；找出“前一字面量以 `.` 结尾、后一字面量以标识符开头”的缝。
- inputs：测试源文件。
- outputs：需要补空格的拼接缝清单（轨迹中为两处：`"...parent(bob, carol)."` + `"gp(X,Y) :- ..."` 与 `"...parent(carol, dave)."` + `"ancestor(X,Y) :- ..."` 等）。
- cautions：`load()` 的返回值能精确指出第几个子句失败，优先核对该子句对应的缝。
- preserve：不重排子句、不改子句内容。
- next：进入 Step 3。

### Step 3: 在每个问题拼接缝补一个尾随空格
- actions：把 `"…carol)."` 改为 `"…carol). "`（在闭合引号前加空格），使拼接结果为 `…carol). gp(X,Y)…`；对清单中每个缝逐一处理。
- inputs：测试源文件。
- outputs：更新后的测试源文件。
- cautions：只加空白，不改任何 token；注意字符串里其他位置已有空格的不要动。
- preserve：同一用例中的断言、查询字符串不变。
- next：移除 Step 1 的临时调试打印（若有），进入 Step 4。

### Step 4: 重编译并重跑相关测试
- actions：重跑构建脚本，观察原失败用例与整个 suite 的结果。
- inputs：构建命令。
- outputs：PASS/FAIL 与 `N/N tests passed` 统计。
- cautions：同 suite 中因其他机制失败的用例（如 assert-via-query）单独跟踪，不要混入本修复的结论。
- preserve：不改断言。
- next：原失败用例全部 PASS 为止。

## Decision Rules
### When `load()` 返回 -1 且失败子句号正好对应一个字面量拼接缝
→ 在该缝的前一字面量末尾补一个空格（Step 3），不做其他改动。

### When 调试显示 `db.clause_count`/`arena.count` 显示前几个子句已入库、最后一个未入库
→ 失败发生在拼接后的子句串上；检查该子句与前一子句之间的缝是否缺少分隔空白。

### When `load()` 成功（返回子句数正确）但断言仍失败
→ 不是本问题；转向查询/引擎逻辑排查，不改字符串。

### When 用例失败源于 `assert` 经 query 写入被重置的 arena
→ 属已知机制限制（轨迹以改写测试为“load 后查询”处理），不属于拼接空白问题；不要给字符串加空格了事。

## Invariants
- 只允许在字面量拼接缝处增删空白，不改任何子句、token、查询或断言。
- 调试打印是临时手段，验证后必须移除，不留生产/测试噪音。
- 不为消除失败而放宽断言或删除测试。
- 不把 `assert-via-query` 的机制限制、链接错误、启动崩溃混入本修复的结论。
- 不在未确认 `load()` 返回值的情况下改动字符串。

## Common Failures
### Failure: 加了空格后 `load()` 仍返回 -1
- symptoms：重跑仍 `loaded=-1`，失败子句号不变。
- causes：该缝并非唯一问题，或失败发生在 `lex`/`parser_init` 阶段（见 Step 1 分支打印）；也可能存在其他拼接缝。
- recovery：按调试打印的失败分支继续定位；确认所有缝都已处理；仍失败则停止并报告（轨迹未提供此分支结论）。

### Failure: 拼接缝数量被遗漏
- symptoms：修完一处后另一用例仍以相同方式失败。
- causes：源文件中存在多处 `"...terminator."` + `"identifier..."` 形式的缝。
- recovery：用 Step 2 的清单法遍历全部 `ctx.load(...)` 实参逐一核对。

### Failure: 断言失败与字符串无关却改了字符串
- symptoms：字符串改动后 FAIL 不变（如 assert-via-query 用例）。
- causes：失败机制不同（query arena 在查询间被重置）。
- recovery：回滚无谓的字符串改动，按对应机制处理（轨迹中改写该测试为 load-then-query 并注明原因）。

## Verification
重编译并重跑相关测试，检查以下可观察项（应观察的检查，不声称已执行）：
- 原失败用例的输出从 `FAIL  <用例名>` 变为 `PASS  <用例名>`（如 `two-body rule resolves via conjunction`、`recursive rule — ancestor`、`backtracking finds second solution after first fails`）。
- 失败用例所在 suite 统计达到 `22/22 tests passed`。
- `load()` 调试值恢复为非 -1、`db.clause_count` 等于源中子句数（若保留了调试输出）。
- 测试源中不再存在“字面量以 `.` 结尾直接拼接标识符开头字面量”的缝（逐个 `ctx.load(...)` 实参核对）。
- 临时 `fprintf` 调试语句在最终源中出现 0 次。

## Examples
### Example 1: two-body 规则用例（轨迹原例）
- input：`TEST("two-body rule resolves via conjunction")` 中 `ctx.load("parent(alice, bob). parent(bob, carol)." "gp(X,Y) :- parent(X,Z), parent(Z,Y).");`，运行显示 `FAIL  two-body rule resolves via conjunction`，调试打印 `[DEBUG two-body] loaded=-1 db.clause_count=1 db.pred_count=1 arena.count=6`。
- procedure：Step 1 打印确认 `loaded=-1` 且失败在第 3 个子句；Step 2 定位缝 `"…carol)."` + `"gp(X,Y)…"`；Step 3 改为 `"parent(alice, bob). parent(bob, carol). "`；Step 4 移除调试并重跑。
- expected result：该用例 PASS；整个 suite `22/22 tests passed`。
- parameterized values：`<前缀子句>=parent(alice, bob). parent(bob, carol). `、`<规则子句>=gp(X,Y) :- parent(X,Z), parent(Z,Y).`、`<断言期望>=1U`。

### Example 2: 同文件其余同类缝
- input：`"…path(a, c)."` + `"reachable(X, Y) :- path(X, Y)."`（backtracking 用例）与 `"…ancestor(X,Y) :- parent(X,Y)."` + `"ancestor(X,Y) :- parent(X,Z), ancestor(Z,Y)."`（recursive 用例）。
-procedure：按 Step 2 清单法逐缝补尾随空格后重跑。
- expected result：`recursive rule — ancestor`、`backtracking finds second solution after first fails` 由 FAIL 转 PASS。
- parameterized values：`<缝>=前一字面量末尾`、`<修复>=闭合引号前加一个空格`。

## Evidence
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1113；source_part_index：0；quote：`[DEBUG two-body] loaded=-1 db.clause_count=1 db.pred_count=1 arena.count=6`；supports：problem（同一输出中 `FAIL  two-body rule resolves via conjunction`、`FAIL  recursive rule — ancestor`、`FAIL  backtracking finds second solution after first fails`、`FAIL  assert adds fact queryable immediately`，统计 `18/22 tests passed  (4 FAILED)`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1129；source_part_index：0；quote：`"parent(alice, bob). parent(bob, carol)."`；supports：action（Edit 的 old_string，拼接缝缺空白；同一 Edit 的 new_string 为 `"parent(alice, bob). parent(bob, carol). "`，仅在闭合引号前多一个空格）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1152；source_part_index：0；quote：`"path(a, b). path(b, c). path(a, c)."`；supports：action（backtracking 用例同类缝，new_string 为 `"path(a, b). path(b, c). path(a, c). "`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1147；source_part_index：0；quote：`"ancestor(X,Y) :- parent(X,Y)."`；supports：action（recursive 用例，new_string 中每行字面量末尾补空格：`"parent(alice, bob). parent(bob, carol). parent(carol, dave). "` 等）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1187；source_part_index：0；quote：`PASS  two-body rule resolves via conjunction`；supports：verification（同一输出含 `PASS  recursive rule — ancestor`、`PASS  backtracking finds second solution after first fails`，suite 统计 `22/22 tests passed`）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1171；source_part_index：0；quote：`the stable path is loading clauses directly`；supports：scope（assert 用例是另一机制：`assert/1 via query writes to query_arena which is reset between queries;`，改写为 load-then-query，不靠字符串空格修复）。
- file_id：claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__original；source_index：1177；source_part_index：0；quote：`if (lex(src, &toks) < 0) { return -1; }`；supports：action（验证后移除 Step 1 临时调试打印，恢复原始 `load()` 形态）。

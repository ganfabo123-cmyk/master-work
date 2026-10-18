---
name: fix-interleaved-key-index-two-pass-build
description: Use when a predicate index returns wrong candidate clauses and queries that should succeed report 0 solutions after indexing was added. Helps the agent prove corruption by dumping per-bucket slots with a minimal repro, identify single-pass bucket layouts that break when equal keys interleave, and convert the build to a classify-then-layout two-pass algorithm. Requires the index build source, a reproducible failing query, and a way to compile a small debug harness against the engine objects. Do not use for solver backtracking bugs with a correct index, or for performance tuning.
---
# Rebuild first-argument indexes in two passes when equal keys interleave

## Goal
修复"同一 first-arg 键的子句在插入顺序上交错"时索引返回错误候选、应成功的查询返回 0 解的问题，把单趟建索引改为两趟（分类 + 连续布局），并用可观察的桶内容与测试套件证明修复。

## Scope
### In scope
- 按 first-arg 值分桶、桶用 `idx_start/idx_count` 指向平铺 `idx_clause_slots[]` 的索引结构。
- 单趟构建在建桶时固定 `idx_start`、随后追加 slot，遇到 `f(a). f(b). f(a).` 这类交错插入即错位。
- 修复：pass 1 把每个子句分类到临时桶累加器，pass 2 按桶连续布局并回填 `idx_start/idx_count`。
- 用最小复现程序打印桶内容验证，再跑回归测试。

### Out of scope
- 求解器回溯/choice point 逻辑（索引正确后仍失败才是求解器问题）。
- 索引性能优化、容量参数调优。
- 与 first-arg 无关的查询错误、解析错误。

## Inputs
1. **失败查询与期望值**：字符串 + 整数，来源：测试输出，必需。约束：如 `ctx.query(\"?- reachable(a, c).\") == 1U` 实得 0。默认值：无。
2. **索引构建函数源码**：文件内容，来源：Read 数据库实现，必需。约束：含建桶与 slot 追加逻辑（`idx_start[bucket] = idx->idx_slot_count`、`idx_clause_slots[idx_slot_count++]`）。默认值：无。
3. **调试打印能力**：编译运行小 harness 的命令与工程对象文件列表，来源：既有编译行，必需。约束：能链接引擎对象并打印桶/子句头。默认值：无。
4. **测试套件运行方式**：字符串，来源：既有测试命令，必需。约束：能重编译并运行索引与求解器测试。默认值：无。

## Outputs
### Artifacts
- 修改后的索引构建函数（两趟算法，原位修改）。
- 桶内容调试输出（修复前后对照）。
- 重编译后的测试结果。

### Success criteria
- 调试输出显示每个桶的 slot 序列与该键的真实子句一致，桶区间互不重叠。
- 最小复现查询返回 1 解；回归套件满值通过（如 `22/22 tests passed`）。

### Failure criteria
- 桶内容仍错位或查询仍返回 0 解。
- 仅改了求解器回溯而未修复索引却声称索引问题已解决。

## Preconditions
- 已有一个可稳定复现的"应成功却 0 解"查询，且该谓词的子句 first-arg 值存在交错插入（如 a, b, a）。
- 能编译并运行一个打印索引内部状态的小程序（或在测试中加临时诊断）。
- 拥有索引构建源码的编辑权限与重编译能力。
- 求解器相关测试在改动前的状态已记录（用于区分索引问题与回溯问题）。

## Procedure
### Step 1: 最小复现并确认 0 解
- actions: 写一个小 harness：加载 `path(a, b). path(b, c). path(a, c). reachable(X, Y) :- path(X, Y).`，查询 `reachable(a, c)`，打印解数与谓词/索引计数。
- inputs: 引擎对象文件、编译命令。
- outputs: `Solutions: 0 (expected 1)`，索引计数本身看似正常（buckets=2, var_clauses=0/1）。
- cautions: 索引"计数正常"不等于"内容正确"，必须继续打印 slot。
- preserve: 不改产品代码。
- next: 稳定复现 0 解 → Step 2。

### Step 2: 打印每个桶的 slot 与子句头
- actions: 遍历桶，输出 `bucket[i]: start/count` 与每个 slot 对应的子句头。
- inputs: harness。
- outputs: 例如 bucket0 的 `slot[1]=pos1 head=path(b,c)`（应为 pos2 的 path(a,c)），bucket1 的 start 与实际槽位重叠。
- cautions: 重点看"同一桶的 slot 是否连续且属于该键"。
- preserve: 保留输出作为修复前证据。
- next: 发现错位 → Step 3。

### Step 3: 定位单趟构建的结构性缺陷
- actions: Read 索引构建函数，确认在"创建桶"时就把 `idx_start` 固定为当前 `idx_slot_count`，之后靠追加维持连续性。
- inputs: 索引构建源码。
- outputs: 结论：交错插入会破坏 `idx_start..idx_start+idx_count` 的连续性假设。
- cautions: 不要先去改求解器回溯（轨迹中回溯重写后测试仍失败）。
- preserve: 不改容量常量。
- next: 确认假设被破坏 → Step 4。

### Step 4: 改为两趟构建
- actions: pass 1 分类：遍历子句，ground 键查/建桶并把 abs_pos 追加进临时 `BucketTemp` 数组（变量首参进 var catch-all）；pass 2 布局：按桶顺序写入 `idx_clause_slots[]`，回填 `idx_start/idx_count`；临时数组用 static 并在入口清零 count。
- inputs: 索引构建函数。
- outputs: 两趟实现的 `db_build_index`。
- cautions: 桶上限溢出时仍要按原策略退回 var catch-all；不要改变 ground/var 的分类标准。
- preserve: 索引结构体布局与对外函数签名不变。
- next: Step 5。

### Step 5: 用调试输出与测试双重验证
- actions: 重编译 harness，确认桶内容正确且查询返回 1 解；再重编译并运行索引/求解器全套测试。
- inputs: 编译与运行命令。
- outputs: `Total solutions: 1`、`22/22 tests passed`。
- cautions: 若索引正确后仍有查询失败，才是求解器问题，另行处理。
- preserve: 删除临时诊断后再做最终运行。
- next: 全部通过 → 完成。

## Decision Rules
### When 同一键的子句插入顺序与其他键交错
单趟"创建桶时记录 start + 追加"必然破坏连续性，必须两趟（分类后布局）。

### When 索引计数正常（bucket/var 数量对）但查询返回 0 解
计数不证明内容，先打印桶内 slot 与子句头再下结论。

### When 改写求解器回溯逻辑后同一查询仍失败
停止在求解器方向继续试错，回到索引内容检查（轨迹中回溯重写后仍 `FAIL ... reachable(a, c)`，索引修复后才通过）。

### When 最小复现的索引内容正确而查询仍错
此时才转向求解器/回溯路径排查，并保留索引修复。

## Invariants
- 不以修改测试期望或删除测试来"修复" 0 解。
- 不在未打印/未核对桶内容前断言索引正确。
- 不改动与该缺陷无关的文件或未授权配置。
- 修复必须同时通过最小复现与既有回归套件，缺一不得声称完成。
- 不把"回溯逻辑被重写"与"索引修复"混为同一因果；只有使复现通过的操作才算验证。
- 不报告未验证的成功。

## Common Failures
### Failure: 先怀疑求解器、反复重写回溯
- symptoms: 重写 backtrack 循环后 `FAIL ... reachable(a, c)` 依然存在（轨迹中确有此阶段）。
- causes: 真正缺陷在索引桶布局，回溯逻辑无从补救错误候选集。
- recovery: 写最小 harness 打印桶 slot，确认错位后改两趟构建。

### Failure: 只看索引元数据就宣布正常
- symptoms: `count=3 buckets=2 var_clauses=0/1` 看似正确，但查询 0 解。
- causes: 元数据不反映 slot 归属；start/count 重叠错位元数据仍可能"合理"。
- recovery: 必须打印每个 slot 对应的子句头逐一核对。

### Failure: 两趟布局后临时桶数组越界/残留
- symptoms: 桶数变化后个别桶内容串桶。
- causes: 临时累加器未按桶数清零或容量截断策略丢失。
- recovery: 入口清零全部 `tmp[i].count`，并保留原有的桶上限回退策略。

## Verification
- 修复前调试输出（对照）：bucket0 `slot[1]=pos1 head=path(b,c)`，查询 `Total solutions: 0 (expected 1)`。
- 修复后调试输出：bucket0 `slot[1]=pos2 head=path(a,c)`、bucket1 `start=2 count=1`，且查询 `Total solutions: 1`。
- 最小复现中 `path/2` 桶区间互不重叠：bucket0 start=0 count=2、bucket1 start=2 count=1。
- 索引与求解器回归套件满值通过：`22/22 tests passed`；全套测试无新增失败。

## Examples
### Example 1: 交错 first-arg 导致桶错位
- input: `path(a, b). path(b, c). path(a, c).` + `reachable(X, Y) :- path(X, Y).`，查询 `reachable(a, c)` 返回 0。
- procedure: Step 1 最小复现 → Step 2 打印桶 slot（发现 bucket0 的第二个 slot 是 `path(b,c)`）→ Step 3 确认单趟构建假设被交错破坏 → Step 4 两趟重建 → Step 5 验证。
- expected result: 桶内容正确且 `Total solutions: 1`，`test_solver` 22/22。
- parameterized values: 谓词名（path/reachable）、键值（a/b/c）、容量常量按项目替换。

### Example 2: 修复后回归确认
- input: 索引两趟构建已合入，需全套回归。
- procedure: Step 5 重编译索引/求解器测试并运行，再跑全套汇总。
- expected result: `22/22 tests passed`（索引与求解器），全套 0 failed。
- parameterized values: 套件数量与文件名按项目替换。

## Evidence
- problem: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=231, source_part_index=0, quote="Solutions: 0 (expected 1)", supports=可复现的 0 解症状（索引元数据却正常）。
- problem: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=234, source_part_index=0, quote="slot[1]=pos1 head=path(b,c)", supports=桶内容错位的直接证据（bucket0 第二个 slot 应为 path(a,c)）。
- action: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=236, source_part_index=0, quote="**buckets don't stay contiguous** when multiple buckets interleave", supports=根因判断：单趟追加无法维持桶区间连续。
- action: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=242, source_part_index=0, quote="Pass 1: classify each clause into a bucket or the var catch-all", supports=两趟修复的第一趟（分类到临时桶累加器）。
- action: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=242, source_part_index=0, quote="Pass 2: lay out buckets contiguously in idx_clause_slots[]", supports=两趟修复的第二趟（连续布局回填 start/count）。
- problem: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=226, source_part_index=0, quote="FAIL  tests/test_solver.cpp:226", supports=在索引修复之前、回溯逻辑重写之后测试仍失败（排除"回溯重写即修复"的误归因）。
- verification: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=245, source_part_index=0, quote="slot[1]=pos2 head=path(a,c)", supports=修复后桶内容正确。
- verification: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=245, source_part_index=0, quote="Total solutions: 1", supports=修复后最小复现返回 1 解。
- verification: file_id=claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03, source_index=261, source_part_index=0, quote="22/22 tests passed", supports=修复后 test_solver 回归满值通过。

# Luna 全量错误聚类审查（修订版）

按最新范围只审查 native-code 14 组与 exception-type 28 组，共 42 组；`expected_group_count=42`、`reviewed_group_count=42`。message-template 已停止，不计入比例。逐组回读每个 reviewed_member_id 的原始 JSONL；usable 仅保留同一切片内针对该错误的具体动作及随后对应的实际验证。

## 总体判断

本次采用保守口径：链接/编译修复只有在动作明确作用于该链接/编译根因且后续有对应构建或运行结果时才判 usable；重写其他代码、Read/README/Todo 回显、移除探针或无关测试通过均降级。

## 策略统计

- native-code: 14 组；usable 4/14 (28.6%)；candidate 7/14 (50.0%)；状态 `{'mixed/usable': 2, 'consistent/unsupported': 3, 'insufficient/usable': 1, 'insufficient/candidate': 1, 'consistent/usable': 1, 'consistent/candidate': 6}`
- exception-type: 28 组；usable 4/28 (14.3%)；candidate 15/28 (53.6%)；状态 `{'consistent/unsupported': 6, 'consistent/candidate': 13, 'consistent/usable': 2, 'insufficient/candidate': 1, 'mixed/candidate': 1, 'mixed/unsupported': 3, 'insufficient/usable': 1, 'mixed/usable': 1}`

## 重点复核

- `native-code-f9479c34ae84`：LNK1120/LNK2019 的 g_verbose 未定义被错误配到 AtomTable 栈修复，降为 unsupported。
- `exception-type-e34a737b03fe`：UnicodeEncodeError 被错误配到 pygame 重写及源码 Read，降为 unsupported。
- `exception-type-554ec18aefd8`：删除失败探针后的 BUILD SUCCESSFUL 不证明 IllegalArgumentException 已修复，降为 unsupported。
- `native-code-c6460e120c75`：保留 usable；动作明确生成 Windows import library/调整 DLL 链接，随后有 Bridge smoke test PASS。

## 语义重复与局限

本次只统计 native-code 与 exception-type；message-template 已停止。所有引用限于成员切片 start_event..end_event，source_index 为零基、jsonl_line 为一基；切片外修复/验证不计入。单成员 usable 只证明局部轨迹经验。

## 完成核对

两策略 14 + 28 = 42 组；group_id 集合已逐一核对无遗漏、无重复。

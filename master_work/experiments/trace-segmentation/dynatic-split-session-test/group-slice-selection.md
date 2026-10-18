# 通用分组切片选择入口

脚本：[select_group_slices.py](D:/PycharmProjects/CodeHarness/master_work/experiments/trace-segmentation/dynatic-split-session-test/select_group_slices.py)。

## 输入与输出

输入：已有原始轨迹分组的 `groups.json`、一个 `group_id`、该组中的原始轨迹 ID 集合 `session_ids`、对应的切片根目录，以及选择策略。

每次批量处理同一个组中的原始轨迹 t1…tn：对每条轨迹分别按当前策略选择切片，再汇总输出切片集合 s1…sm。不会重新分组，不需要重新读取原始轨迹全文；选择依据来自已有分组的原始事件引用。输入 ID 自动去重并排序；每个 ID 必须属于所选组。

输出到一个新的目录：

```text
selection.json
slices/
  <session_id>/
    segment-xx.json
    ...
  <another_session_id>/
    segment-xx.json
    ...
```

`selection.json` 保存输入 ID 集合、组标识、策略、总候选/选中/排除数量，以及汇总切片 ID 集合 `selected_slice_ids`、完整清单 `selected_slices` 和每条轨迹的结果 `sessions`。切片和未映射事件均标注对应 `session_id`，每个切片保存原始位置与输出位置、选择证据。选中文件始终按字节原样复制并记录 SHA256；非选中切片如何输出由下面的内容策略决定，不改变选择依据。

先完成整批输入的校验和选择，再创建输出目录。如果某条轨迹不属于所选组、缺少切片目录或输入格式错误，则整次调用报错，不先导出其他轨迹的部分结果。

## 当前策略

- `group-evidence`：选择核心区包含该组命中事件的切片。
- `group-context`（默认）：选择核心区包含命中事件，或已有分组产物中附近上下文事件的切片。上下文是既有分组保存的窗口，不新加距离参数。

匹配使用原始 `source_index` 和 `source_part_index`，不能使用切片的 `start_event` 或投影 `event_index` 代替原始坐标。上下文缺少显式原始索引时，从原始 JSONL 行指针或 OpenCode message 指针解码；无法解码则报错。

只用核心区决定归属，避免相邻切片的重叠区造成额外选择；复制文件时完整保留重叠区。缺失 part 信息时保守地按同一个原始记录匹配，避免漏掉信息。切片中没有对应事件时记录 `unmapped_references`，不强行选择距离最近的切片。

这两种策略只表示“含有分组证据或已有附近上下文”，不证明其他切片无关，也不保证远处的修复和验证已经选全。尤其错误消失后的验证可能不在已保存的窗口中，不能据此宣称证据链完整。后续可以增加选择策略，但本版不推断完整修复链。

## 内容输出策略

`--strategy` 决定哪些切片被选中；`--content-strategy` 决定如何展示选中与非选中切片。

- `selected-only`（默认）：只输出选中的完整切片，兼容已有行为。
- `selected-full-rest-collapsed`：输出该组输入轨迹的全部切片。选中切片不动；未选中切片仅缩起 Thinking/Reasoning 和 Tool Result 正文，保留其他事件内容及原始顺序，不做语义摘要。

缩起时移除对应正文/思考签名字段，保留角色、类别、索引、tool_use_id、is_error 等属性；添加 `collapsed_content`，记录隐藏字段、原长度及原切片路径。OpenCode 的结果正文位于 tool call 的 `tool_result` 内，只隐藏 output/error，保留 input/status。不会在一个可见字段中再复制隐藏正文。

`exported_slices` 是真正导出的全量输入清单，`exported_count` 是导出文件数，每项 `content_mode` 为 full 或 collapsed。`selected_count` 和 `excluded_count` 仍是选择层统计；在新内容策略中，excluded 表示“未选中为完整展示”，不表示文件被丢弃。新增 `collapsed_slice_count` 与 `collapsed_event_count`；事件数包含切片原有重叠，不是原始事件去重后的数。

在上面现有参数基础上增加：

```text
--content-strategy selected-full-rest-collapsed
```

需要新增内容策略时，在本脚本新增 `function(data, selected, source_path)` 并注册到 `CONTENT_STRATEGIES`；返回要输出的切片对象或 None。选中切片由统一流程按原文件复制，不能由内容策略修改。

## 命令

从脚本目录执行，输入目录指向现有数据包，输出使用新的目录：

```powershell
python select_group_slices.py --list-strategies

python select_group_slices.py `
  --groups strategy-grouping-four-anchors-v1\sessions-30\stack-site\groups.json `
  --group-id stack-site-fbd833c947fd `
  --session-ids claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba `
  --slices-dir C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-slices `
  --strategy group-context `
  --output group-slice-selection-check-v1
```

同一组有多条原始轨迹时，在一次调用中传入 `--session-ids t1 t2 t3`（替换成真实 ID）。数量没有预设上限；单条也作为集合处理。原来的 `--session-id` 参数保留为别名。Python 的 `run()` 第三个参数现在接受 ID 列表，也兼容原来的单个字符串，但统一返回批量结果。

输入必须是原始轨迹组，不是切片组。输出目录已存在则报错，避免覆盖和混入旧结果。无需 LLM 或 embedding 调用。

## 新增策略

新增一个函数并注册，不修改主流程：

```python
def strategy_new(group, session_id, candidates):
    # 根据 group 和该 Session 的候选切片构造自己的选择依据。
    # 返回多条证据；每条证据必须包含 reason 和 slice_ids。
    # 可以额外附带原始事件引用等 JSON 可序列化字段。
    return [{"reason": "实际选择原因", "slice_ids": [实际选中的切片ID]}]

SELECTION_STRATEGIES["new-strategy"] = strategy_new
```

`group` 是整个分组对象；函数必须按 `session_id` 限定原始证据。`candidates` 只包含本次 Session 的切片，每项提供 `slice_id`、`source_path`、核心边界和 `core_refs`（原始 index/part 的集合）。需要更丰富的选择时，策略可读取 `source_path` 对应的完整切片。主流程校验 ID、去重并统一输出，注册后即可使用 `--strategy new-strategy`。

## 验证

```powershell
python -m unittest test_select_group_slices.py
```

测试覆盖原始/投影索引区别、原始 part 匹配、核心区与重叠区、上下文跨切片选择、Session 隔离、未映射事件、扩展注册及原样输出。

批量版本新增验证：多条轨迹的切片集合汇总、同名切片文件跨 Session 不冲突、输入去重、不同输入顺序得到相同切片 ID 集合、逐轨迹统计与总统计一致、整批无效输入不产生部分输出。当前共 11 项测试通过。

2026-10-14 验证记录：9 项单元测试通过；上面的真实调用栈组命令已运行，该 Session 的 7 个候选切片中选中 `segment-07.json`，排除 6 个，未映射事件为 0。已核对输出切片与输入逐字节一致，以及选中数加排除数等于候选数。这是选择和输出机制验证，不是 Skill 提取效果验证。

结果：[selection.json](D:/PycharmProjects/CodeHarness/master_work/experiments/trace-segmentation/dynatic-split-session-test/group-slice-selection-check-v1/selection.json)。该目录已经存在，复跑示例时请更换 `--output`。

2026-10-14 批量版本真实验证：使用已有异常类型组 `exception-type-05b6f58afac2` 中的两个原始轨迹 ID，一次调用从合计 13 个候选切片中选出 2 个、排除 11 个，未映射事件为 0。两条轨迹分别为 6 选 1、7 选 1；已核对总统计、集合去重及两个输出文件均与原始切片逐字节一致。

批量结果：[selection.json](D:/PycharmProjects/CodeHarness/master_work/experiments/trace-segmentation/dynatic-split-session-test/group-slice-selection-batch-check-v2/selection.json)。这仍是批量入口与文件输出验证，不是 Skill 质量审查。

2026-10-14 新内容策略：新增 2 项测试，选择脚本共 13 项测试通过；与正文恢复的 4 项测试一起共 17 项通过。使用完整正文 LNK1105 组，导出 20 个文件：9 个保持原样，11 个缩略，缩起 502 个事件正文。新产物：[selection.json](D:/PycharmProjects/CodeHarness/master_work/experiments/trace-segmentation/dynatic-split-session-test/group-slice-selection-native-code-lnk1105-context-collapsed-v3/selection.json)。

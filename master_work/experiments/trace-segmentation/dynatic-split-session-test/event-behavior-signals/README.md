# 低成本事件证据信号

读取 runs/feature-analysis/event-token-frequency/events.jsonl 与 slice-events.json；无需模型或 embedding。
每个词在一个事件内最多计一次，大小写合并；仅用切片核心区间。按 user、assistant、unknown、tool 四通道计事件数，单通道计分封顶，再乘跨切片 IDF 与跨通道奖励。unknown_text 角色未明，单列通道，不能推断为用户输入。要求至少两个事件支持，双字词至少三个；常见英文虚词、纯数字、版本号、短十六进制串和过长词不参与排序。

`task_signals` 至少出现于 user、assistant 或 unknown；`tool_only_signals` 单列工具参数词。`action_terms` 是固定英文动词列表的命中情况，不是行为标签。`action_object_pairs` 要求动作词与候选特征词在文本中相距至多 6 个词项，且至少有两个事件支持；仅表示邻近，不表示语法关系或实际执行。工具调用类型及相邻工具调用转移直接计数。词频仅给出候选证据，不能单独证明任务完成或动作成功。中文仍沿用原始连续汉字分词，尚未做词语切分。

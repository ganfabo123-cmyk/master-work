# Runtime 详细日志

日志位于配置 `data_dir` 下的 `logs/runtime.jsonl`，UTF-8 JSONL，按事件追加并
flush/fsync。日志写入使用独立的线程/进程锁，不依赖管理快照发布成功。
字段 `ts` 为 UTC，`local_time` 为 UTC+08:00，方便查看 15 点等本地时间段。

## 要看的事件

| event | 含义 |
| --- | --- |
| bridge_request_received / bridge_trace_received | bridge 已收到调用及每个原始事件，早于 embedding provider 创建 |
| messages_received / trace_received | AgentSession 收到批次和原始事件；先记录整批，再处理，前一个事件失败不会隐藏后续到达事件 |
| trace_converted | 转换后的事件类型、正文和轨迹长度 |
| trigger_decision | 触发策略名称和 triggered；false 是策略未触发，不等于程序异常 |
| query_built | 实际查询文本及 top_k |
| retrieval_started | 实际 min_similarity、tau、m、top_k 等参数 |
| signature_decision | 签名匹配、当前通道策略、是否进行影子抽查 |
| embedding_started / embedding_similarity | embedding 执行和相似度结果，包括全部 35 个 skill 的过滤前分数 |
| routing_completed | 节点中心相似度、选择节点、是否全局回退、过滤后候选 |
| retrieval_completed | 检索执行成功、has_results、实际返回项及本次 embedding 诊断 |
| retrieval_failed | 检索执行失败、异常类型、原因、堆栈；若失败前已经算出分数，仍保留分数 |
| trace_completed / trace_failed | 单事件最终触发状态、结果状态、相似度及出错阶段 |
| trace_not_processed | 已到达，但因前一个事件异常没有继续处理；记录不可计算相似度的原因 |
| hint_decision | 管理系统是否生成并追加提示、提示正文及对应的最后事件 |
| messages_completed / messages_failed | 批次完成或失败 |
| bridge_completed / bridge_failed / bridge_invalid_input | bridge 返回状态或初始化、输入、处理错误 |

`request_id` 关联一次 bridge 调用；`batch_id` 关联 handle_messages 批次；
`trace_id` 关联单个被处理事件；`retrieval_id` 关联一次检索。bridge 的事件到达
记录通过 `request_id` 和 `input_index` 定位，处理日志通过同一 request_id 串联。
直接调用 AgentSession 没有 bridge 的 request_id，仍有 trace_id/batch_id。

## embedding 分数

`embedding.status=measured` 时有：

- `purpose`：`retrieval` 或仅供日志的 `diagnostic_only`。
- `query`、`model`、`elapsed_ms`、实际 `min_similarity`。
- `top_similarity`：全库最高余弦相似度。
- `candidates`：全部 35 个 skill 的 ID、名称、rank、节点、score、是否达到阈值。

检索返回空数组也会保存这些分数，因此能区分“本来没相似候选”和“阈值过滤”。
相似度不是概率。主通道若是纯签名检索，主返回项仍保留原来的 score=null，
日志中的 embedding 分数单独记录，不混入签名检索的效用反馈。

为满足未触发和纯签名场景也能检查分数的需要，非空消息正文会额外执行日志专用
embedding；这些调用增加耗时与成本，不改变触发判断、检索结果或 observations。
诊断调用失败不把“未触发”或正常的签名结果改成检索失败。

空文本、非法输入、策略/查询校验失败、API 不可用或上一个事件失败导致未处理
时，不能生成真实的数值。日志保留 `top_similarity=null`、空 candidates 和明确
reason/error_type，绝不填入虚构的 0 分。错误如发生在分数计算之后，已算出的
全部分数仍能在 retrieval_failed/trace_failed 中查看。

## 使用范围

只记录实际到达管理系统入口的事件。没有 bridge_request_received 时，应检查
上游插件是否调用，以及日志写入本身是否报错；不能从这里看到未被发送的事件。
hint_decision 证明管理系统返回了提示，不等于证明 UI 显示或模型实际收到提示。
插件只发送上次成功调用之后的新增会话事件，不在每步重放完整历史。
直接调用 handle_messages 时，仍处理调用者实际传入的整批事件。

没有独立消息正文的控制事件和流式片段仍完整记录接收、触发判断及完成状态；
不把其整个 JSON 协议结构当作查询执行 embedding。相似度状态为 unavailable，
top_similarity=null，reason=no_message_content。有正文的 assistant/message 读取
message.content 执行诊断，有正文的 user input/tool result 保留原检索与分数记录。
DSH 的 tool/result 即使内部 message.role=user，也按显式事件类型记录为 tool_result。

插件按 Agent 跟踪已成功送入 bridge 的会话事件范围，在新增事件中检测 tool/result，
因此其后的 step/end 不会阻止调用；bridge 失败时不推进范围，允许重试。
管理系统用本批最后一次触发检索的结果生成 hint_decision，source_trace_id 指向
该触发事件；尾部控制事件不会覆盖该结果。后续触发若返回空结果，不复用前面的命中。

配置加载失败时无法确定实验 data_dir，回退写入 managementRoot/data/logs。
非法 JSON 回退写入 bridge 所在目录的 data/logs。日志磁盘不可写时不会伪装成功。
结构字段中的 api_key、authorization 等会遮盖；不会记录 embedding 密钥配置。
原始 trace 正文保留完整内容，属于本地实验审计材料。

下一次 bridge 调用会通过新的 Python 进程加载日志代码，无需重编译 DSH 插件。
2026-10-16 的工具结果触发修复同时修改并重编译了插件；正在运行的 DSH 需要重启以加载它。
旧时间段未采集的事件和分数无法补回。

用户初始指令（完整任务要求）：

使用 GPT-5.6 Luna 完整扫描切片组的错误聚类质量。实验目录为 master_work/dynatic-split-session-test/error-clustering-v1。输入仅为 slices-97 下 native-code/groups.json（14组）、exception-type/groups.json（28组）、message-template/groups.json（147组），共189组；97个切片位于 C:/Users/35153/PycharmProjects/master-work/vibecoding-trace-data-bundle/dynatic-split-session-test/calibrated-confidence-length-banded-v3-slices，原始工具输出来源位于 C:/Users/35153/PycharmProjects/master-work/sessions。groups.json 含成员路径、事件索引、全部命中证据、附近上下文引用、hydrated_from。可阅读 manifest.json、error_clustering_experiment.py 理解解析和来源，但要独立从输入与原始证据评估，不以 assessment.md 结论为判断依据。

完整审查所有189组，先建立切片内容与工具输出索引，再逐组读取全部 evidence 和各成员错误附近处理过程；context 不足时回到切片和原始工具输出。仅在切片 start_event..end_event 范围评估证据充分性；切片之外的修复/验证明确标记缺失。辨别同码不同根因、预期异常、包装错误和输出代码文字。逐组评估 error_alignment（consistent/mixed/false_positive/insufficient）与 skill_evidence（usable/candidate/unsupported）。usable 必须有具体触发、可执行处理/判断、实际验证证据和限定适用范围；candidate 必须有具体经验线索；不能从常识补造修复。允许组混杂、单成员、多重归属；不同组支持同一经验时指出语义重复。

输出只写入 error-clustering-v1/audit-slices-luna/：audit.json、report.md、prompt.md。audit.json 包含 corpus、model、expected_group_count、reviewed_group_count、groups、summary；每组含 group_id、strategy、error_key、member_count、distinct_session_count、reviewed_member_ids、error_alignment、skill_evidence、reason、experience_outline（若有）、source_evidence（文件+原始事件索引+短引文）、issues。summary 按三策略统计全部状态、usable/candidate 比率及分母，说明语义重复与局限。report.md 给总体判断、策略对比、具体好坏组，并说明全量完成。核对189个 group_id 无遗漏无重复。不要修改算法或实验原始产物。

本次补充指令：

当前 preliminary 产物中的 experience_outline 过于模板化，source_evidence 只有错误没有具体修复和验证，不能支撑内容审查。请保留当前版本为 preliminary-audit.json / preliminary-report.md，然后修订 audit.json、report.md。逐个组给出针对该错误的具体诊断/修复动作及对应验证；usable 必须分别引用这两类来源片段与事件索引并说明关联。不能因为整条切片有 Edit 和 passing/ok 就判 usable；只有通用信号应降级 candidate/unsupported。尤其复核 0xC00000FD：对应切片 assistant_text 已有大结构堆栈占用分析；复核 CodeGenError：可能只是模块结构说明而非实际异常。核验每个 reviewed_member_id 的实际源内容，仍完整覆盖189组。prompt.md 保存完整实际收到的初始指令和本次补充指令。用户最新范围变化：

停止 message-template 策略的代理审查；最终 audit.json、report.md、summary 只覆盖 slices-97/native-code（14组）与 exception-type（28组），共42组。expected_group_count=reviewed_group_count=42。保留已经完成的旧初稿，不把被取消策略混入本次最终质量比率。不再运行消息模板审查。每个 usable 必须说明针对错误的具体动作与对应验证，引用切片范围内实际事件；通用修复/通过信号不足，不能机械关键词判定。prompt.md 保存原始完整提示词、补充指令和本次范围变化完整文本。

本次最终纠偏指令：继续只审查42组，停止消息模板。更正明确错误配对：UnicodeEncodeError 被配到重写 pygame 渲染器且 verification 只是 Read 返回源码/docstring，不能证明编码错误修复；0x00000460 是链接器1120返回状态，却被配到 AtomTable 栈溢出修复，问题不对应；LNK1107 的 action 只是 file/check/importlib 尝试，需核验实际重建与成功输出；IllegalArgumentException 如果只是移除失败探针测试，不能当作原问题经验。检查其他相似错配，无法建立错误根因—动作—验证关系时保守降级；保留真正对应的少数证据。每个 usable 必须有切片内具体动作与对应验证，不能把 README、Read、Todo 或无关 passing 当运行验证。完成后更新最终 audit.json、report.md，保留旧初稿，并再次核对42个 group_id。


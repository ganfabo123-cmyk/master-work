# 第四阶段：一致性、晋级回滚、收割审核

## 范围

仅管理名单中的35个B-selected skill。新增signature_mining.py，扩展既有signatures.py与管理流程。
未接入原检索程序，未运行远程API，未开启第五阶段维护窗口。

## 双通道证据与实际分流

signature-init构建55个不同的归一化字面模式（对应原始96条trigger声明），
初始化35个skill各自的通道状态和空审核队列。
实际数量以signature_index.json为准，不合并或删除任何skill。

正式observe导入时：

1. 接收调用方的query、同模型向量、全局embedding top-1和路由记录。
2. 未提供signature时，运行当前Aho-Corasick签名匹配；已提供时验证与实际匹配一致。
3. 记录signature_version，保留对应历史结果。
4. 更新每个skill的一致性证据和持久化状态；同事件重试幂等。

默认配置：至少20条不同的真实查询，晋级一致率>=95%；已晋级项低于90%回滚。
每个skill、每种样本类型分别使用最近100条不同查询，避免大流量类目挤掉其他类目的证据。
重复查询不增加证据；同一查询已有分歧时，后来重复成功不能洗掉该分歧。
窗口按日志的首次接收顺序，不按调用方可能回填的ts排序。

synthetic/fixture不会用于正式晋级。歧义和未命中保留语义兜底；一致性晋级针对唯一签名预测。
compare_channels的eligible是新晋级的95%门槛；已晋级项可在90%~95%区间保持，形成滞回。
source event IDs、计数、版本和前后状态写入channel_policy，便于追溯。

resolve_with_policy读取该策略，已晋级且唯一命中时不调用embedding回调；其他情况调用回调。
它是供消费方接入的分流函数，本阶段没有替原检索程序接线，也没有后台自动收集影子样本。
消费方仍需提供后续影子验证观测，才能发现已晋级项质量下降并回滚。

## 签名版本

版本指纹覆盖模型、维度、35项description指纹和归一化triggers。
候选通过审核导致triggers变化后，保守地令全部旧版本一致性证据失效、退回影子观察。
这是因为新增签名也可能改变其他skill的竞争关系；每个skill仍独立重新晋级。
旧日志保持不变，不把旧证据改挂到新版本；历史事件重试仍然幂等。
新事件不能冒用过期版本，当前策略引用旧版本或缺少足量证据会被快照校验拒绝。

## 收割

signature-mine只取当前语料版本、sample_kind=real的观测，以全局embedding top-1作为候选标签。
它是伪真值，不等于人工确认适用，因此任何候选都必须人审。

- 在原始查询上提取3~8词n-gram，以及机器错误码、error code数值、十六进制码、errno形态和引文。
- 默认至少3条不同查询支持；统计其他skill查询中出现的比例，超过5%不入队。
- 保存方法、支持事件ID、query ID、样本类型、原文片段与字符位置、跨skill计数。
- 现有trigger不重复提议；candidate ID由skill和归一化文本确定，重跑不重复入队。
- 单次最多处理配置中的50项候选，不输出虚构confidence。

候选可能是泛短语，数字型签名也可能多义；证据用于审核，不是自动批准理由。
无真实观测时返回0项，不借用测试流量补齐。

## 审核与存储

审核命令必须明确candidate ID、approve/reject、审核者、理由。命令调用本身就是该候选的审核动作。
不会在部署时替用户批准任何候选。

通过：检查候选版本及证据，更新管理副本frontmatter，重建签名映射，刷新策略并同代发布。
拒绝：记录原因，保留证据，不修改triggers。相同审核重试幂等，已作决定不能改写。
过期候选不能通过；重新收割可刷新待审候选证据后再审。

同代快照包含：

```text
manifest.json / state.json / vectors.json
observations.jsonl / ratings.jsonl
signature_index.json
review_queue.json
skills/<35个name>/SKILL.md
```

state.signature_management另外记录原始语料文件指纹。verify校验原始来源未发生外部修改，
同时校验管理副本与state原文一致。审核只改变管理副本triggers，不改变description、正文、向量或节点。
含引号与反斜杠的候选按JSON兼容的双引号字符串写入，加载后保持原文。
发布失败不会改变CURRENT；旧快照及旧管理副本仍可读。

## 本轮部署状态

正式初始化已运行：35个skill、8节点、55个不同字面模式；0观测、0评分、0候选、0个签名优先。
本轮测试数据仅写临时目录；没有自动批准候选或调用远程API。

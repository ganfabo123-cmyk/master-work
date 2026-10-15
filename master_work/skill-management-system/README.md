# Skill管理系统：已完成第一至第五阶段

已新增统一检索API和Agent Trace入口，见[INTEGRATION.md](INTEGRATION.md)。
可使用`api.SkillSystem`，或继续调用相邻固定入口的`PROGRAM.handle_raw_trace`。
原检索文件、固定入口及相关说明已先备份再接入，旧通用检索能力保留。

只管理`../dynamic-retrieval-test/skills_b/index.jsonl`中的35个B-selected skill。
支持本地语料与向量加载、聚类和节点维护，以及影子指标和效用反馈统计。
支持按维护窗口生成并执行归属修正与局部拆分计划；管理命令不运行检索或远程embedding请求。
不改写原语料、索引和缓存。

在本目录执行（纯Python标准库，Python 3.11及以上）：

```powershell
python -B manager.py initialize
python -B manager.py cluster
python -B manager.py verify
python -B -m unittest discover -s tests -v
```

也可在其他目录使用脚本绝对路径；配置内相对路径始终以配置文件所在目录解析。
`--config`可指定其他配置文件。

初始化读取名单、解析原文、验证description指纹并导入对应的35条本地向量。
任何名单、语料或向量错误都会阻止发布，不会调用服务自动修补。
来源索引中的sha256是提取时原文件指纹；管理状态另外保存当前文件指纹，
以及用于向量匹配的description指纹，三者互不替代。

数据位于`data/snapshots/generation-*/`，每代包含：

- `manifest.json`：名单、来源映射、模型及维度。
- `state.json`：35个skill的名称、description、triggers、正文、原文及指纹。
- `vectors.json`：仅名单内35项的向量、description指纹和生成时间。

`data/CURRENT`指向已发布的一代。各文件全部写入、回读校验成功后才原子切换指针；
失败不会发布部分数据。读者用`SnapshotStore.read()`读取同一代，不能自行挑选不同代文件。
重跑初始化生成新快照，保留旧代；本阶段不做快照清理。
管理命令与检索API共享写锁，具体并发边界见INTEGRATION.md。
`verify`回读完整快照并与当前来源对账，不需要访问原向量缓存。
来源内容或出处索引变化后，旧快照会明确报告过期。

frontmatter解析器仅支持当前语料的name、单行description及带引号的triggers列表；
遇到其他格式明确报错，不把它当作完整YAML解析器。

## 第二阶段：聚类和节点维护

`clustering.py`实现归一化description向量上的球形二分k-means，保存拆分谱系。
输入按skill ID排序，固定随机种子；并列情况采用确定顺序。
本次候选k为2、3、4、5、6、8；这是配置中的有限候选集合，不代表穷举或全局最优。
每个k做4轮独立bootstrap配对采样，将两份聚类都投影到同一全体样本后计算ARI。
完整采样成功且平均ARI不低于0.5的候选，按cosine silhouette最高者选取。
无候选通过时回退B=1；显式k=1同样可用。
这些配置是暂定几何参数，尚未经过影子查询或任务效果标定。

`nodes.py`保存成员、计数、单位成员向量之和、算术均值和归一化质心。
节点归属必须覆盖全部35项，每项有1到2个不同归属，禁止空节点。
初始硬聚类后，根据硬质心做一轮软分配：第二归属的cosine距离不超过0.15时双挂，
随后以最终成员重算质心。不反复重分配，避免本阶段引入循环抖动。
primary归属用于保证覆盖，不受第二归属阈值限制。

成员增减按单位向量增减节点向量和；最后一名成员移出时删除空节点。
所有节点更新都先在副本完成，整体校验通过后才替换和发布。
若向量抵消导致零质心，明确拒绝该变更，不伪造质心。

可执行命令：

```powershell
# 自动几何选型；显式B=1骨架则使用cluster --k 1
python -B manager.py cluster
# 将一项的归属覆盖为1到2个现有节点（参数为实际ID）
python -B manager.py assign --skill skill:<name> --nodes <node_id> [<second_node_id>]
# 只对成员数 > 2 * target_size 的节点各做一次局部二分
python -B manager.py recluster
# 显式指定一个节点局部二分
python -B manager.py recluster --node <node_id>
```

局部二分只替换指定节点，保留其成员在其他节点的归属，保存拆分前后成员及原因。
初始target_size为ceil(35/初始节点数)。第五阶段已将路由质量下降接入维护计划。
节点状态、初次选型报告、谱系和变更记录均保存在同代`state.json`的`clustering`字段中；
每次快照读取和发布都会以保存向量重新验证节点不变量。
初次选型指标不冒充成员手工调整后的重评结果。

`cluster`会重新生成全体聚类；`initialize`会重新初始化无聚类的第一阶段状态。
两者均保留旧快照；日常节点维护请使用assign/recluster，避免重置当前分组。

## 第三阶段：影子评估与效用反馈

协议及统计口径见[PHASE3_PROTOCOL.md](PHASE3_PROTOCOL.md)。

```powershell
python -B manager.py feedback-init
python -B manager.py observe --input <observations.jsonl>
python -B manager.py rate --input <ratings.jsonl>
python -B manager.py shadow-report
python -B manager.py calibrate
python -B manager.py feedback-report
python -B manager.py rebuild-feedback
```

观测、评分分别保存在同代快照的`observations.jsonl`与`ratings.jsonl`，统计保存在
`state.json`的`feedback`字段。发布点仍为CURRENT，日志和统计共同发布。
旧代快照没有这些字段时仍可读取；`feedback-init`初始化空日志并保留现有节点。
相同事件ID及相同内容的重复导入不产生新计数；内容冲突或同一命中的再次评分会报错。

每次读取会从事实日志回放核对统计；本规模下导入和验证采用完整回放及完整快照，
不是面向大日志的流式写入实现。`rebuild-feedback`能从完好的事实日志恢复损坏的派生统计，
不修补损坏事实。历史快照和日志不原地改写；读改写入口使用锁串行执行。

第四阶段已接入签名晋级、收割与审核；第五阶段已接入反馈归属修正、内容修订队列及维护窗口。

## 可恢复真跑演练

见[LIVE_TRIAL_REPORT.md](LIVE_TRIAL_REPORT.md)，本次已真实运行并恢复沙箱。
`live_trial.py`中的检索仅为演练适配器，不改动原检索程序。
`signatures.py`提供独立签名匹配与双通道比较；`maintenance.py`提供基于查询位置与评分的
归属建议和执行函数；第五阶段另提供正式维护计划和整批执行入口。

```powershell
# 新运行会调用真实embedding API；既有运行复用保存的向量
python -B live_trial.py --run-dir runs/<new-run> --stop-after embeddings
python -B live_trial.py --run-dir runs/<new-run>
# 可选：额外一次真实API调用，检验两个通道的实际并发
python -B live_trial.py --run-dir runs/<new-run> --probe-dual
# 恢复沙箱初始状态，保留证据和旧快照
python -B live_trial.py --run-dir runs/<new-run> --restore-sandbox
```

真实调用读取相邻dynamic-retrieval-test已有配置，密钥不写入检查点或结果。
固定测试查询和适用范围在远程调用前保存；评分明确标为synthetic。
断点恢复校验查询清单、基线和正式数据指纹；不会把不同运行的数据拼接。

## 强制一致的实际切换测试

此前仅验证晋级资格，现已在signatures.py补充`update_channel_policy`和`resolve_with_policy`。
前者将每个skill的shadow/signature_first状态保存到快照；后者读取该状态实际选择通道。
已晋级且唯一签名命中时完全不调用embedding回调；未命中、歧义或未晋级时调用昂贵通道。

```powershell
python -B forced_switch_trial.py --run-dir runs/<new-forced-run>
```

该脚本明确伪造两个通道一致的证据，全部标为synthetic，不调用远程API。
沙箱显式allow_simulation=True后验证19条不切换、20条完全一致后切换、落盘回读仍生效、
命中时embedding调用为0、未命中和歧义兜底，以及22条中2条不一致后的回滚。
模拟策略在默认调用下不生效；真实策略仍要求真实观测。脚本在finally恢复沙箱初始状态，保留证据。
这证明状态切换和分流代码可运行，不证明实际签名质量，也没有给原检索程序接线。

## 第四阶段：正式签名管理

协议及管理规则见[PHASE4_SIGNATURES.md](PHASE4_SIGNATURES.md)。

```powershell
python -B manager.py signature-init
python -B manager.py signature-report
python -B manager.py signature-refresh
python -B manager.py signature-mine
python -B manager.py signature-queue
python -B manager.py signature-review --candidate <candidate_id> --decision approve --reviewer <name> --reason <reason>
python -B manager.py signature-review --candidate <candidate_id> --decision reject --reviewer <name> --reason <reason>
```

正式observe导入会执行便宜的本地签名匹配、记录签名版本并更新通道状态。
调用方仍提供embedding基准结果；该入口不调用远程API。
已提交的签名结果会检查实际匹配是否一致，旧事件重试保留历史签名版本。

审核通过后，当前快照的`skills/<name>/SKILL.md`是更新过的管理副本；
原始skills_b保持只读。管理副本、signature_index.json、review_queue.json与通道状态同代发布。
外部消费应读取CURRENT对应的管理副本或state字段，不应回读原始skills_b期待看到审核变更。

## 第五阶段：正式维护事务与防抖

规则与验证见[PHASE5_MAINTENANCE.md](PHASE5_MAINTENANCE.md)。

```powershell
python -B manager.py maintenance-init
python -B manager.py maintenance-plan
python -B manager.py maintenance-apply --plan <plan_id>
python -B manager.py maintenance-report
python -B manager.py maintenance-review --case <case_id> --decision resolved --reviewer <name> --reason <reason>
```

维护命令仅在显式执行时运行，不创建后台定时任务。
计划生成后可查看完整动作和依据；执行会核对源数据指纹、窗口时间、数量限额及所有节点不变量，
整批通过才发布。真实观测不足时不会用测试数据补齐。

本轮已复用历史真实embedding观测完成正式维护沙箱演练，新增API调用为0，证据见
`runs/maintenance-20261015-01/`。沙箱已恢复，正式部署的首个维护窗口为0动作。

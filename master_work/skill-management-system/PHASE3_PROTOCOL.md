# 第三阶段：输入协议与统计边界

本系统接收调用方已产生的观测，不执行查询embedding、全局检索或节点路由。
以上描述为第三阶段管理接口边界；现新增检索层负责执行查询，见INTEGRATION.md。
新观测可带channel=signature，此时唯一实际签名命中的score为null。
未抽样的纯签名消费query_vector及baseline_top1为null，只累计消费和效用，
不参与向量质心、签名比较、路由评估或候选收割。已抽样则保留实际向量及独立evaluation。
全局top-1是调用方提供的伪真值，不是人工相关性真值；影子路由命中率不等于实际任务成功率。

## 观测JSONL

每行一个对象，以下字段均必填。

| 字段 | 格式及含义 |
| --- | --- |
| event_id | 一次观测的非空唯一ID；重试沿用原ID |
| query | 非空原文 |
| query_vector | 同模型的1024维有限非零数值数组，保留输入值，累计查询质心时归一化 |
| model | text-embedding-v4 |
| baseline_top1 | 全局向量检索top-1的skill:<name> |
| selected_nodes | 实际搜索的无重复节点ID列表 |
| hits | 按排名排列的命中列表；每项为skill_id、score、rank、node_id；可以为空 |
| parameters | 对象：k、tau、m；k为历史节点数，m为实际束宽，tau为[-1,1]余弦阈值 |
| ts | 带时区的ISO时间 |
| sample_kind | real / synthetic / fixture，必须显式标注 |
| mode | regular / exploration，探索样本单独统计 |
| purpose | evaluation / consumption；离线评估不进入效用计数 |
| global_fallback | 布尔值；全局兜底时selected_nodes必须记录全部节点 |

hit中的rank必须从1连续递增，score必须是[-1,1]有限数值；同一skill只能出现一次。
node_id必须属于selected_nodes，skill必须属于该历史节点。
selected_nodes至少包含m个节点。本系统验证引用与格式，不反向猜测实际使用的路由算法。

可选context由系统在导入时附加，包含模型、维度、35项description指纹、历史节点成员、
corpus_id及layout_id。参数实验使用其他布局时，调用方可提供同语料的完整context；
格式参考`shadow.context_for(snapshot)`。历史布局不随当前节点移动而改变。
query_id由query和原始query_vector确定，不依赖event_id。

## 评分JSONL

每行一个对象：rating_id、event_id、skill_id、rank、value、ts。
value仅为good或bad。event_id必须引用已有consumption观测，skill_id/rank必须引用实际命中。
系统附加原始query，调用方若提供query则必须一致。
同rating_id同内容是幂等重试；相同ID不同内容拒绝。
同一(event_id, skill_id, rank)只能评分一次，不能通过新rating_id重复投票或覆盖旧评。

## 影子指标与参数评估

- 路由覆盖：被搜索节点的成员并集是否包含baseline_top1，双挂成员按skill ID去重。
- 报告整体及per-skill路由命中率、平均搜索节点数、去重候选规模、全局兜底率和漏失事件。
- 同一条件重复观测同一query时先求该query的均值，再对query等权汇总；事实记录仍全部保留。
- 按corpus_id、layout_id、样本类型、探索模式、用途和(k,tau,m)分组。
- 标定只比较同语料、同查询集合、同基准标签、同类型/模式/用途的已有实验格点。
- 帕累托前沿同时考虑召回率、搜索节点数和候选规模；达到target_recall后优先取候选规模较小者。
- 不生成未记录参数组合的成绩，也不自动应用推荐配置。没有观测时输出NOT_EVALUATED。

## 效用与查询质心

仅consumption观测计入R，评分分别计入G/B。R是被召回次数，不冒充有真值分母的召回率。
各语料版本、样本类型、探索模式分别累计，避免测试样本或探索样本混入真实常规统计。
所有35项都保留计数，包括没有被召回的项。

按skill保存单位查询向量和、样本数、算术均值及归一化查询质心。
没有样本时为NO_SAMPLES；相反方向抵消时为ZERO_SUM，不伪造方向。
同时按排名保存R/G/B，按历史布局、节点及排名保存节点基线；报告相对节点均值及其他成员均值的差值。

可用率=G/(G+B)，没有评分时为null。Wilson下界使用配置中的z（默认1.96），
默认G+B至少20才标为证据充足；零评分不当作差评。
本阶段只生成统计，不根据低可用率移动节点或自动修改内容。

## 持久化与恢复

同代快照同时包含manifest/state/vectors及两份事实JSONL；完整校验后才切换CURRENT。
批次中有错误则整批不发布。状态可从事实日志回放重建；单纯重复导入不会发布新代。
旧快照保留。完整快照与回放面向当前小规模管理，不承诺大日志下的常数时间导入。

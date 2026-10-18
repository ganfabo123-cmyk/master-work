# 统一检索API与Agent接入

入口为api.SkillSystem。agent.py负责Agent事件，retrieval.py执行检索，storage.py保存快照，
已有管理模块处理统计、审核和维护。新系统独立拥有Trace协议和embedding传输实现。

```python
import sys
sys.path.insert(0, r"D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system")
from api import SkillSystem, EmbeddingApiClient, EmbeddingApiConfig

# endpoint和api_key由调用方已有配置提供，不在代码或日志保存密钥。
provider = EmbeddingApiClient(EmbeddingApiConfig(
    endpoint=endpoint, model="text-embedding-v4", api_key=api_key), dimension=1024)
system = SkillSystem(embedding=provider)
session = system.agent_session()  # 每个Agent会话独立创建
result = session.handle_raw_trace({"role": "user", "content": "实际问题"})
```

主线：Trace → converter → trajectory → trigger_strategy → query_builder → retrieve。
默认沿用原策略：字符串和常见user事件转换为user_input，最新user_input或
tool_result触发，
使用其原文而不拼接历史。列表文本块边界空白沿用旧转换器strip行为。
非触发事件仍加入轨迹，但不读写管理库、不调用embedding；空查询返回empty_query。
会话轨迹仅保存在内存，不自动恢复Agent会话。

触发策略可以读取完整轨迹，也能按工具失败触发：

```python
from api import RetrievalQuery
session = system.agent_session(
    trigger_strategy=lambda t: t.latest_event.event_type == "tool_result",
    query_builder=lambda t: RetrievalQuery(t.latest_event.content, top_k=3),
    retrieval_options={"tau": .5, "m": 1, "signature_audit_rate": .1},
)
```

converter必须返回api.TraceEvent，trigger返回bool，query_builder返回api.RetrievalQuery。
filters暂不支持，非空时明确报错。query.top_k控制截断。返回带类型的RetrievalResult；
保留not_triggered、empty_query、completed等状态，正常空命中为completed。
固定35项管理库缺失、损坏或未初始化时抛出异常。系统只返回结果，不自动注入Prompt，
也不实现Runtime网络订阅。

也可以直接查询并反馈：

```python
retrieved = system.retrieve("实际问题", top_k=3)
system.feedback(event_id=retrieved["event_id"],
    skill_id=retrieved["items"][0]["skill_id"], rank=1,
    value="good", rating_id="由消费方生成且重试时沿用的ID")
```

retrieve返回dict；Trace入口返回RetrievalResult。结果均携带event_id、输入和发布快照代、
context及签名版本。Trace结果的这些字段在metadata中，命中含skill_id、rank、node_id和channel。
签名命中的score为None。session.feedback同样可提交评分；没有真实效果判断不能自动标good。
同rating_id同内容重试不新增计数；冲突或换ID重复评价同一命中报错。
每次retrieve是新消费尝试，目前没有查询请求去重键；成功发布后响应丢失时应核对事实日志。

## 查询与闭环

唯一签名命中且正式策略已晋级signature_first时走签名通道，模拟策略不用于生产。
未命中、歧义或未晋级时调用一次查询embedding；35条description向量直接来自快照。
按质心取至少m个节点并加入达到tau者；全部节点低于tau时全局兜底。
节点成员去重后余弦排序，过滤min_similarity并截取top_k；局部无合格结果时再次全局兜底。

每次embedding使用同一查询向量计算全局35项top-1作为影子基准，保存evaluation及
实际consumption两份记录；evaluation不增加R/G/B。
晋级签名默认以0.1概率抽样复查：一致时仍返回签名，分歧时本次改用向量结果，
并刷新后续晋级和回滚策略。未抽中时完全不调用embedding，向量及baseline_top1为null。
纯签名消费和评分进入R/G/B，但不产生查询向量计数、路由指标或签名一致性证据。
几何归属维护只能使用实际采集的查询向量。

tau=.5、m=1、min_similarity=.9、signature_audit_rate=.1均为当前默认值，
由retrieve参数或session.retrieval_options覆盖，没有宣称真实流量标定。
audit_rate=0关闭复查后不会获得新的签名退化比较证据。
参数评估只比较已记录格点，不自动应用推荐值或暗中扫描参数网格。
签名收割、人工审核和维护窗口仍用原管理命令显式执行，没有后台定时器。

## 一致性和成本

API和manager读改写入口共享线程锁和操作系统文件锁。另一进程占锁时明确报错，请重试。
进程退出后操作系统释放锁。当前锁覆盖读取、embedding、计算及发布，因此查询只使用
同一输入快照；下次查询重新读取CURRENT，管理变更无需重启Agent即可生效。
不要绕过这些入口并发调用底层SnapshotStore.publish，也不要并行运行写正式库的试验脚本。
当前35项规模使用串行查询、完整快照和事实回放，并计算全局影子基准，不承诺高并发吞吐。
provider模型和维度必须与快照一致；本次需要embedding而没有provider时明确报错。
原语料、出处索引和缓存不改写。

## 旧程序保留

相邻dynamic-retrieval-test固定入口仍提供PROGRAM.handle_raw_trace；默认工厂接入本系统。
原developer_trace_converter、developer_should_retrieve和developer_build_query继续生效，
并桥接回旧RetrievalResult/Query/Hit/Document类型。原通用检索类、解析器和旧策略保留，
create_legacy_program()可显式创建原策略。

完整旧版位于backups/legacy-retrieval-20261015-180607/，17个文件逐字节校验，哈希见
BACKUP_MANIFEST.json。包含旧代码、固定入口、试跑脚本、说明、skills_tests和缓存。
没有复制.env或密钥；备份可独立运行，远程调用时从环境提供原embedding配置。

## 本次文件变更

| 状态 | 文件 | 目的 |
| --- | --- | --- |
| 新增 | api.py | 对外导出统一API和协议类型 |
| 新增 | agent.py | 可替换触发策略、查询构造和Agent会话入口 |
| 新增 | agent_protocol.py | 从旧版保留独立Trace、轨迹和返回协议 |
| 新增 | embedding_client.py | 从旧版保留独立HTTP embedding传输 |
| 新增 | retrieval.py | 快照读取、双通道分流、路由、影子记录和评分API |
| 新增 | transactions.py | 管理命令和检索API共享写入互斥 |
| 新增 | tests/test_retrieval_api.py | 13项集成回归，写入仅用临时库 |
| 新增 | backups/legacy-retrieval-20261015-180607/ | 旧版17文件及哈希清单、独立运行说明 |
| 新增 | INTEGRATION.md | 接入说明及边界 |
| 新增 | runs/integration-20261015-01/result.json | 本次验证结果与原语料保护证据 |
| 修改 | manager.py | 管理读改写入口加锁，初始化输入仍先校验 |
| 修改 | shadow.py | 允许无向量签名消费，隔离路由评估 |
| 修改 | feedback.py | 无向量消费累计效用但不累计几何样本 |
| 修改 | signatures.py | 无向量消费不冒充双通道比较证据 |
| 修改 | signature_mining.py | 收割只使用有实际向量基准的观测 |
| 修改 | README.md、PHASE3_PROTOCOL.md | 更新入口和协议说明 |
| 修改 | ../dynamic-retrieval-test/retrieval_program.py | 默认接入管理系统，保留旧工厂及三处策略钩子，桥接返回类型 |
| 修改 | ../dynamic-retrieval-test/dynamic_retrieval_test.py | 更新固定入口说明，调用形式不变 |
| 新增 | ../dynamic-retrieval-test/MANAGED_SKILL_INTEGRATION.md | 当前入口与旧版说明 |

验证：完整73项测试通过，30个Python文件通过语法检查；包含本地HTTP embedding端到端、
Agent自定义触发、签名短路/抽样回滚、评分幂等、线程及跨进程互斥、旧版独立运行。
未调用收费API，未启动真实外部Agent会话，未提交Git；正式CURRENT及零观测/评分状态未变。
35份B-selected原文、出处索引和原向量缓存哈希保持一致。


详细事件日志见 [RUNTIME_LOGGING.md](RUNTIME_LOGGING.md)。日志位于各配置 data_dir/logs/runtime.jsonl，覆盖事件到达、触发、检索结果、过滤前全部 embedding 分数和异常。未触发及纯签名路径的诊断也会调用 embedding，增加耗时与成本。

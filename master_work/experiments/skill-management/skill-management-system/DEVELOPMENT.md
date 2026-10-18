# Skill 检索与管理系统开发文档

更新时间：2026-10-15。代码基线：本地提交 `518d061`。
本文根据当前代码、配置及正式快照整理，供后续开发和 Agent 接入使用。

## 1. 系统定位与当前状态

系统统一负责 **检索、存储和管理**，范围固定为出处索引中的 **35 个 B-selected skill**。
对外提供本地 Python API；内部保留 Agent 事件处理、查询执行、快照存储及管理维护的职责边界。
实现使用 Python 3.11 及以上版本和标准库，没有必须启动的服务或数据库。

主线：

```text
Agent raw trace → 事件转换 → 轨迹累计 → 触发策略 → 查询构造
    → 读取管理快照 → 签名分流 / embedding与节点检索 → 返回正文
    → 消费观测 + 抽样影子评估 → 评分 → 统计
    → 签名晋级回滚 / 候选审核 / 归属维护计划 → 发布新快照
```

本次文档编写时回读确认：

| 项目 | 状态 |
| --- | --- |
| 正式 CURRENT | `generation-k6wuooue` |
| skill / description 向量 | 35 / 35 |
| embedding 空间 | `text-embedding-v4`，1024 维 |
| 当前节点 | 8 个，覆盖全部35项 |
| 正式观测 / 评分 | 0 / 0 |
| 签名优先 skill | 0，当前均处于影子观察阶段 |
| 维护窗口 | 已执行1个零动作窗口 |
| 正式快照校验 | PASS |
| 最近完整代码回归 | 73项通过，记录见第12节；本轮文档编写未重跑 |

代码闭环已经落地；真实 Agent 流量的检索质量、节省成本和任务效果仍待验证。
后台定时维护、Runtime 自动订阅、Prompt 注入及无限增删语料均未启用。

## 2. 产物路径与取用规则

### 2.1 主要产物的绝对路径

| 产物 | 绝对路径 | 说明 |
| --- | --- | --- |
| 系统根目录 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\` | 本系统代码、配置、数据及演练证据 |
| 本开发文档 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\DEVELOPMENT.md` | 交接及API总说明 |
| 统一 API | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\api.py` | 对外导出类及协议类型 |
| Agent 事件入口 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\agent.py` | 会话、触发策略、查询构造、结果转换 |
| 事件与返回协议 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\agent_protocol.py` | TraceEvent、Trajectory、RetrievalQuery、RetrievalResult等 |
| 查询执行 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\retrieval.py` | 签名/向量分流、节点路由、观测和评分API |
| 管理入口 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\manager.py` | 管理函数和CLI |
| 主配置 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\config.json` | 来源路径、模型及管理阈值 |
| 当前快照指针 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\data\CURRENT` | 唯一发布点；内容为generation目录名 |
| 正式快照根 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\data\snapshots\` | 保留各代，不原地改写 |
| 当前正式代 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\data\snapshots\generation-k6wuooue\` | 仅为本次核对值，运行时必须读取CURRENT |
| 原始语料 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\dynamic-retrieval-test\skills_b\` | 35个目录，各含SKILL.md；本系统不改原文 |
| 出处索引 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\dynamic-retrieval-test\skills_b\index.jsonl` | 35个name是唯一名单来源 |
| 原始向量缓存 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\dynamic-retrieval-test\embedding_cache.json` | 初始化导入；运行检索复用快照向量，无需重读此缓存 |
| 固定兼容入口 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\dynamic-retrieval-test\dynamic_retrieval_test.py` | 导出PROGRAM.handle_raw_trace |
| 原检索模块 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\dynamic-retrieval-test\retrieval_program.py` | 默认接入本系统，保留通用框架、开发者钩子和旧工厂 |
| 旧版完整备份 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\backups\legacy-retrieval-20261015-180607\` | 17个原始文件及哈希清单、运行说明 |
| 测试 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\tests\` | 各阶段及接入回归 |
| 演练与部署证据 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\runs\` | 真跑、强制一致、维护演练及部署结果 |

`<name>`、`<generation>`、`<node_id>`等写法均为占位符，不是可直接访问的文件名。

### 2.2 名单、指纹与向量的取用规则

1. 仅取 `index.jsonl` 的35个唯一 `name`，来源必须为 `arm=B-selected`。
2. skill ID统一为 `skill:<name>`；节点ID与skill ID是不同命名空间。
3. 原缓存仅导入对应35条 `entries["skill:<name>"]`，不扩大语料范围。
4. 导入前验证模型、维度及 `entry.sha256 == sha256(当前解析出的description文本)`。
5. description指纹按解析后文本的UTF-8内容计算；不能用文件全文指纹替代。
6. 向量必须是1024维有限、非布尔、非零数值；验证不通过则拒绝初始化，不自动远程修补。
7. 出处索引的sha256记录原始提取产物；当前全文另存content_sha256，二者不混用。
8. 用户检索、签名竞争和维护均保留35个独立skill，不因相似而合并或删除。

原 `embedding_cache.json` 为可重建缓存，仍被Git忽略。旧版备份中的缓存为完整恢复目的已显式入库。
新检索只生成查询向量，不重新嵌入35份description，也不改写原缓存。

## 3. 模块职责与开发边界

以下文件均位于上述系统根目录。

| 文件 | 职责 |
| --- | --- |
| api.py | 公开API导出，不新增业务逻辑 |
| agent.py / agent_protocol.py | 事件转换、会话轨迹、触发/查询策略契约、统一结果 |
| retrieval.py | 一次查询的执行、实际消费和evaluation记录、评分接口 |
| embedding_client.py | 独立HTTP embedding传输，支持常见兼容响应和Ollama embeddings响应 |
| corpus.py / models.py | 名单、frontmatter、正文、指纹和基础类型 |
| embeddings.py | 本地description向量导入与数值校验 |
| clustering.py | 球形二分k-means、silhouette、bootstrap/ARI选型 |
| nodes.py | 成员归属、双挂、质心、局部拆分及独立节点 |
| shadow.py | 观测规范化、路由覆盖和已有参数格点评估 |
| feedback.py | 观测/评分幂等导入、事实回放及效用统计 |
| signatures.py | Aho-Corasick匹配、版本、比较、晋级与回滚策略 |
| signature_mining.py | 候选提取、原文证据、人工审核及管理副本触发词更新 |
| maintenance.py | 内容队列、归属计划、冷却窗口、限额和整批执行 |
| storage.py | 同代校验、物理文件写入及CURRENT原子发布 |
| transactions.py | API和管理函数共享线程锁、操作系统文件锁 |
| manager.py | 配置解析、管理命令编排、来源对账 |

查询层负责产生事实；管理层根据事实改变后续快照。不要在工具或调用方各自实现另一套节点或签名策略。
不要绕过统一写入入口并发调用底层publish。

## 4. 存储与数据结构

### 4.1 一代完整快照

```text
D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\data\
  CURRENT
  WRITER.lock                     # 首次加锁时创建，不入Git；不是事实日志
  snapshots\<generation>\
    manifest.json
    state.json
    vectors.json
    observations.jsonl
    ratings.jsonl
    signature_index.json
    review_queue.json
    maintenance_queue.json
    maintenance_log.jsonl
    skills\<name>\SKILL.md       # 35份管理副本
```

所有文件属于同一代。读者通过 `SnapshotStore.read()` 整体读取，不能跨代拼接。
构造、写入、fsync、回读校验全部通过后，才原子替换CURRENT。
失败不发布部分状态；可能留下未发布目录，当前没有自动清理机制。

### 4.2 核心对象字段

| 对象 | 结构 |
| --- | --- |
| manifest.json | version、created_at、model、dimension、members列表；成员含skill_id/source_path/provenance |
| state.skills | 按skill_id映射；字段见下表 |
| vectors.json | version、entries；entries按skill_id映射，每条含skill_id/sha256/vector/embedded_at |
| state.clustering | version、vector_space、assignments、nodes、lineage、changes、config、selection_report、target_size |
| state.feedback | version、options、observation_count、rating_count、cohorts |
| state.signature_management | options及原始来源全文指纹source_content_sha256等 |
| state.channel_policy | 每项shadow/signature_first模式、比较证据、阈值、签名版本和转换历史 |
| state.maintenance | 窗口序号、时间、options、成员与拆分冷却状态 |

`state.skills[skill_id]`：

| 字段 | 含义 |
| --- | --- |
| skill_id / name | 稳定ID和frontmatter名称 |
| description / triggers | 用于向量匹配的描述、字面触发词列表 |
| body / full_content | 去除frontmatter的正文、完整SKILL.md文本 |
| source_path / provenance | 原始绝对路径及出处索引记录 |
| description_sha256 / content_sha256 | 当前描述指纹及当前管理全文指纹 |

`nodes[node_id]`保存members、count、vector_sum、mean、centroid。
节点质心来自**成员单位description向量**；反馈查询质心来自**实际单位查询向量**，二者不可替代。
assignments必须覆盖35项，每项1到2个不同节点；不允许空节点或伪造零向量质心。

### 4.3 日志和审核队列

| 文件 | 结构与用途 |
| --- | --- |
| observations.jsonl | 每行一条规范化evaluation或consumption事实；event_id唯一 |
| ratings.jsonl | 每行一条评分；rating_id唯一，并绑定实际event_id/skill_id/rank |
| signature_index.json | version、signature_version、patterns；可重建字面模式映射 |
| review_queue.json | version、candidates、decisions；含支持查询、片段位置和人工决定 |
| maintenance_queue.json | version、plans、content_reviews、reviews |
| maintenance_log.jsonl | 已执行窗口的动作、结果、当时配置及前后布局证据 |

原始来源只读。审核新增trigger写入当前代管理副本及state，description、正文、向量和节点保持不变。
读取时校验物理SKILL.md副本与state.full_content一致。
`.gitattributes`对data、runs和backups禁用换行转换，避免Git恢复时破坏字节级证据。

## 5. 公开 Python API

### 5.1 导入与初始化

当前目录名含连字符，尚未发布成pip包；调用方先把系统根目录加入模块搜索路径。

```python
import os
import sys

SYSTEM_ROOT = r"D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system"
sys.path.insert(0, SYSTEM_ROOT)

from api import SkillSystem, EmbeddingApiConfig, EmbeddingApiClient

embedding = EmbeddingApiClient(
    EmbeddingApiConfig(
        endpoint=os.environ["DYNAMIC_RETRIEVAL_EMBEDDING_API_URL"],
        model="text-embedding-v4",
        api_key=os.environ.get("DYNAMIC_RETRIEVAL_EMBEDDING_API_KEY"),
        timeout_seconds=60.0,
        use_system_proxy=False,
    ),
    dimension=1024,
)
system = SkillSystem(embedding=embedding)
```

此直接API示例从进程环境读取配置，**不会自动加载.env**。调用方需要自行注入环境或显式传值。
兼容旧入口则继续使用原retrieval_program的.env加载逻辑。
构造provider和system本身不发网络请求；首次实际需要embedding的查询才请求服务。

公开导出：SkillSystem、AgentSession、EmbeddingApiConfig、EmbeddingApiClient、TraceEvent、
Trajectory、RetrievalQuery、RetrievalResult、RetrievalStatus、RetrievalHit、RetrievalDocument。

### 5.2 SkillSystem 构造函数

```python
SkillSystem(config_path=None, *, embedding=None, config=None)
```

| 参数 | 含义 |
| --- | --- |
| config_path | 默认取系统根目录config.json；相对路径以调用方工作目录定位配置文件 |
| embedding | provider对象；需暴露model、dimension和embed(texts) |
| config | 可选已解析配置字典；传入时优先于config_path，应使用manager.load_config生成 |

配置文件中的corpus_root/index_path/embedding_cache/data_dir相对路径，以配置文件目录解析。
直接传config不能照搬带相对路径的原始JSON字典，应先解析。
系统初始化/聚类等部署动作由管理命令完成，构造SkillSystem不会自动重置管理库。

### 5.3 直接查询

```python
system.retrieve(
    query, *, top_k=3, min_similarity=0.9, tau=0.5, m=1,
    signature_audit_rate=0.1, sample_kind="real", mode="regular"
) -> dict
```

| 参数 | 校验与行为 |
| --- | --- |
| query | 非空字符串；保留原文，不在检索层拼接历史 |
| top_k | 正整数，最多返回此数量；签名短路当前只返回唯一1项 |
| min_similarity | [-1,1]有限数，向量命中最低余弦分数 |
| tau | [-1,1]有限数，节点纳入及兜底阈值 |
| m | 正整数，不大于当前节点数；节点候选至少包含前m项 |
| signature_audit_rate | [0,1]；已晋级签名的抽样复查概率，0关闭，1每次复查 |
| sample_kind | real / synthetic / fixture；演练必须显式标明，不伪装真实流量 |
| mode | regular / exploration；分开统计，不自动生成探索流量 |

这些默认查询参数是暂定值，不代表真实流量标定结论；它们由函数参数控制，不是config.json中的同名配置。

返回字段：

| 字段 | 类型 / 含义 |
| --- | --- |
| event_id | str；本次consumption事实ID，提交评分时引用 |
| query / channel | 原文；实际返回通道embedding或signature |
| snapshot_generation | 本次查询使用的输入快照代 |
| published_generation | 本次观测发布后的快照代 |
| context | model、dimension、description指纹、历史node_members、corpus_id、layout_id |
| signature_version | 模型/维度/描述/trigger共同确定的签名版本 |
| signature | status=unique/ambiguous/miss、top1及含matches的candidates |
| embedding_called | 本次是否实际获得查询向量 |
| signature_audited | 本次是否抽中了已晋级签名复查 |
| global_fallback | 实际消费通道是否全局兜底；签名返回时为false |
| items | 命中列表；可为空，字段如下 |

每条item字段：skill_id、rank、score、node_id、name、description、body、full_content。
向量score为余弦值；签名score为None，不把字面命中伪装成余弦高分。
双挂skill按ID去重；node_id从被搜索且含该skill的节点中按稳定顺序选取。

每次调用都会生成新的event_id并发布事实，即使items为空；没有调用方请求ID去重功能。
若成功发布后响应丢失，直接重跑会成为另一次消费，应先根据事实日志核对。

### 5.4 评分反馈

```python
system.feedback(*, event_id, skill_id, rank, value, rating_id) -> dict
```

| 参数 | 含义 |
| --- | --- |
| event_id | 已存在且purpose=consumption的观测 |
| skill_id / rank | 必须精确匹配该次实际返回的命中 |
| value | good或bad；由真实消费效果判断，不根据分数自动打分 |
| rating_id | 调用方稳定ID；重试必须沿用 |

成功返回 `{"status": "PASS", "added": 1, "duplicates": 0}`；同内容重试返回added=0、duplicates=1。
重试沿用原评分时间。同rating_id内容冲突，或换ID对同一(event_id,skill_id,rank)重复投票，都会报错。
评分改变R/G/B派生状态，不直接执行节点移动或修改正文。

```python
found = system.retrieve("实际问题")
if found["items"]:
    chosen = found["items"][0]
    # 只有在消费后确认有效时执行；rating_id由调用方保存。
    system.feedback(event_id=found["event_id"], skill_id=chosen["skill_id"],
                    rank=chosen["rank"], value="good", rating_id="stable-feedback-id")
```

### 5.5 创建 Agent 会话

```python
system.agent_session(**strategies) -> AgentSession

AgentSession(system, *, trace_converter=developer_trace_converter,
             trigger_strategy=developer_should_retrieve,
             query_builder=developer_build_query, retrieval_options=None)
```

每个Agent对话单独创建session。SkillSystem可共享，写入由统一锁串行执行。
session公开trajectory、trace_converter、trigger_strategy、query_builder和retrieval_options。

```python
session.handle_raw_trace(raw_trace) -> RetrievalResult
session.feedback(**rating) -> dict   # 转发system.feedback
```

handle_raw_trace先更新轨迹，再触发和构造查询。它不会负责从Runtime网络订阅事件，调用方需要逐条传入。
不触发或查询为空时不访问管理库、不调用embedding、不生成消费观测。
query.top_k覆盖retrieval_options中的top_k，其余查询选项通过retrieval_options传入。
当前query.filters非空会抛ValueError，不静默忽略过滤条件。

### 5.6 Trace、查询和结果对象

| 类型 | 字段 |
| --- | --- |
| TraceEvent | event_type: str；content: Any；metadata: dict |
| Trajectory | raw_events、events、metadata；latest_event属性；append(raw,event) |
| RetrievalQuery | query_text: str；top_k=5；filters={}；metadata={} |
| RetrievalDocument | retrieval_content、full_content；document_id/source_path/source_type/title；metadata |
| RetrievalHit | document；score/rank/matched_content；metadata |
| RetrievalResult | status；query；items；strategy_name；reason；metadata |

注意：RetrievalQuery类型本身默认top_k=5；默认Agent查询构造器取环境变量
DYNAMIC_RETRIEVAL_TOP_K，未配置时为3；直接retrieve默认也是3。

| RetrievalStatus | 值 | 当前入口行为 |
| --- | --- | --- |
| NOT_TRIGGERED | not_triggered | 触发策略返回false |
| EMPTY_QUERY | empty_query | 构造查询为空白 |
| COMPLETED | completed | 检索已完成，包括正常零命中 |
| NO_MATERIALS | no_materials | 通用协议保留；当前固定35项Agent入口不会正常返回此状态，库异常直接报错 |

Agent命中document.document_id为skill_id，source_type为managed_skill，source_path当前为None。
matched_content是去除frontmatter的正文。原始来源路径需要从同代manifest/state查询。
结果metadata携带直接查询返回的版本、通道及event_id等信息；命中metadata另含skill_id/node_id/channel。
如需JSON，可使用dataclasses.asdict(result)再json.dumps；RetrievalStatus继承str枚举。

### 5.7 自定义触发策略：必须保留的 Agent 接入点

```python
from api import TraceEvent, RetrievalQuery

def convert(raw):
    return TraceEvent(event_type=raw["type"], content=raw.get("content", ""))

def should_retrieve(trajectory):
    latest = trajectory.latest_event
    return latest is not None and latest.event_type == "tool_failure"

def build_query(trajectory):
    latest = trajectory.latest_event
    return RetrievalQuery(query_text=latest.content, top_k=3)

session = system.agent_session(trace_converter=convert,
    trigger_strategy=should_retrieve, query_builder=build_query)
```

converter必须返回api.TraceEvent；trigger必须返回bool；query_builder必须返回api.RetrievalQuery。
trigger和query_builder可读取完整轨迹及metadata，用于工具失败、阶段变化等调用方策略。
系统没有默认启用这些额外触发条件；默认仍为最新用户输入触发、原文查询。
列表文本块转换会strip块边界空白，沿用原行为；直接字符串查询保留原文。
策略异常直接抛出，不伪装成零命中；目前同一个session不保证多线程同时handle的安全性。

### 5.8 embedding provider 契约

```python
class Provider:
    model = "text-embedding-v4"
    dimension = 1024

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...
```

当前查询调用embed([query])，要求返回恰好一条1024维有限非零向量。
provider声明模型/维度必须与快照一致；声明相符不代表系统能核实第三方模型的真实来源。
没有provider时，未抽样的已晋级签名仍可返回；只要需要embedding就明确报错。
默认抽样率0.1意味着签名场景仍可能需要provider。

内置配置签名：

```python
EmbeddingApiConfig(endpoint, model, api_key=None, batch_size=32,
                   timeout_seconds=60.0, min_similarity=0.9,
                   use_system_proxy=False, extra_headers={})
EmbeddingApiClient(config, dimension=1024)
EmbeddingApiClient.embed(texts)
```

endpoint推荐传完整embeddings地址；传其他地址时会按已有规则补全。
默认禁用系统代理。远程请求体为model和input；查询路径只发送query，不发送skill正文。
直接SkillSystem API的min_similarity由retrieve参数决定，不自动读取provider.config.min_similarity；
旧兼容工厂会把该配置值桥接为session检索选项。

## 6. 检索、影子比较与晋级回滚

### 6.1 查询执行顺序

1. 加写锁，读取同一代完整快照及当前策略。
2. Aho-Corasick匹配大小写归一后的trigger；按不同命中模式数和总长度排序，同强度则歧义。
3. 唯一命中且该skill为正式signature_first时，按概率决定是否抽样复查。
4. 其他情况调用查询embedding；全局35项top-1作为影子伪真值。
5. 以节点质心选候选，至少保留前m个及所有达到tau的节点；全低于tau则全局兜底。
6. 候选成员去重、向量排序及分数过滤；局部没有合格项时再全局兜底。
7. 抽样签名与全局top-1一致则返回签名；分歧则本次返回向量检索结果。
8. 观测、派生统计和刷新后的通道策略共同发布，然后返回结果。

embedding路径目前仍计算全局35项基准，不承诺局部路由已经减少全部向量计算成本。
签名短路省掉的是未抽样请求的远程embedding调用；仍有快照读取、校验和完整发布成本。

### 6.2 观测两种用途及无向量记录

| 实际路径 | 保存记录 | 统计边界 |
| --- | --- | --- |
| embedding | 1条consumption和1条evaluation | 消费增加R；evaluation不增加R/G/B |
| 签名未抽样 | 1条consumption，vector/baseline为null | 增加消费与评分；不产生几何/比较证据 |
| 签名抽样一致 | 签名consumption及embedding evaluation | 签名score仍为null；使用实际查询向量 |
| 签名抽样分歧 | embedding consumption及evaluation | 本次不返回已发现分歧的签名结果 |

evaluation ID为消费event_id加`:evaluation`。两条记录不会把同一查询重复算作独立比较证据。
未抽样签名的selected_nodes仅是该skill归属的一个稳定节点，用于消费归属审计，不冒充路由评估。

### 6.3 晋级与回滚默认值

| 参数 | 默认值 |
| --- | ---: |
| min_samples | 20条不同真实查询 |
| promotion_threshold | 0.95 |
| rollback_threshold | 0.90 |
| window_size | 每skill、每样本类型最近100条不同查询 |

新晋级要求至少20条真实独立查询且一致率≥95%；已晋级项在90%～95%之间保留，低于90%回滚。
synthetic/fixture不能用于正式晋级。重复查询不扩充独立样本，同查询已有分歧不会被重跑成功洗掉。
窗口按日志接收顺序，而非调用方ts排序。比较与路由覆盖均不是人工语义正确率或任务成功率。
签名版本覆盖模型、维度、35项description指纹及triggers；审核改变triggers后，旧比较证据失效并重新观察。

## 7. 观测与评分导入协议

API通常自动生成观测；离线实验或其他调用方可通过管理接口导入JSONL。

| 观测字段 | 含义 |
| --- | --- |
| event_id / query / ts | 稳定事件ID、查询原文、带时区ISO时间 |
| model / query_vector | 模型和实际向量；仅合法签名消费可为null向量 |
| baseline_top1 | 全局向量top-1；未抽样签名消费为null |
| selected_nodes / hits | 实际搜索或消费归属节点；命中含skill_id/score/rank/node_id |
| parameters | k、tau、m；k必须对应该历史布局节点数 |
| sample_kind / mode / purpose | real/synthetic/fixture；regular/exploration；evaluation/consumption |
| global_fallback | 布尔；向量全局兜底时记录全部节点 |
| context / query_id | 导入时可附加；保存后保留历史语料和布局 |
| signature / signature_version | 字面匹配证据及版本；管理导入可补齐并验证 |
| channel | 可选embedding/signature；旧观测省略时沿用向量契约 |

rank从1连续、同skill不重复、节点引用合法。签名通道只能记录唯一实际消费命中，score为null。
query_id由查询原文及原始向量共同确定；未抽样签名用null向量，但不会参与双通道比较。
同event_id同内容重试幂等，不同内容拒绝。不同布局或语料的评估按context分开统计。

评分JSONL字段：rating_id、event_id、skill_id、rank、value、ts，可附query但必须一致。
value为good/bad，只能绑定consumption的实际命中。API评分与JSONL导入使用同一幂等约束。

## 8. 管理 Python 接口与 CLI

### 8.1 管理函数

以下从manager模块导入，目前不属于api.py的导出列表。

```python
from pathlib import Path
from manager import load_config, verify, feedback_operation
cfg = load_config(Path(r"D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\config.json"))
report = verify(cfg)
```

| 函数签名 | 作用 |
| --- | --- |
| load_config(path: Path) | 配置读取、校验和路径解析 |
| initialize(config) | 从原始名单和缓存创建基础快照 |
| verify(config, snapshot=None) | 全量快照校验及原始来源对账 |
| cluster(config, k=None) | 重新生成全体聚类；k为空时几何选型 |
| manage_nodes(config, operation, skill_id=None, node_ids=None, node_id=None) | assign或recluster |
| feedback_operation(config, operation, records=None) | 反馈初始化、观测/评分导入、统计、参数评估及重建 |
| signature_operation(config, operation, candidate_id=None, decision=None, reviewer=None, reason=None) | 签名初始化、报告、刷新、收割、队列及审核 |
| maintenance_operation(config, operation, plan_id=None, case_id=None, decision=None, reviewer=None, reason=None, now=None) | 维护初始化、计划、执行、报告及内容队列决定 |

records为已解析的JSON对象列表。now仅用于程序化维护接口，须为带时区ISO时间；CLI没有--now选项。
管理函数返回Python对象；CLI成功打印JSON并退出0，捕获的OSError/ValueError打印FAIL并退出1。
跨进程锁竞争在Windows可抛RuntimeError，当前CLI不会把所有此类异常统一转为FAIL JSON。

### 8.2 CLI总表

所有命令入口的绝对路径为：
`D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\manager.py`。
以下示例先进入该目录，以避免重复长路径：

```powershell
Set-Location 'D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system'
python -B manager.py verify
```

| operation | 参数 / 行为 |
| --- | --- |
| initialize | 创建基础快照；会重置当前高级状态，非日常启动命令 |
| cluster | 可带--k整数；重新生成全局布局 |
| verify | 只读完整对账 |
| assign | --skill skill:名称 --nodes 节点 [第二节点] |
| recluster | 可带--node；省略时处理规模超限节点 |
| feedback-init | 初始化空反馈结构，不清空已有事实 |
| observe / rate | --input JSONL绝对路径或当前目录相对路径 |
| shadow-report / calibrate / feedback-report | 路由、参数及效用报告 |
| rebuild-feedback | 完好事实回放重建派生统计并发布 |
| signature-init | 初始化签名索引和审核结构 |
| signature-report / signature-refresh | 比较报告 / 按证据刷新策略 |
| signature-mine / signature-queue | 候选收割 / 队列 |
| signature-review | --candidate ID --decision approve或reject --reviewer 人名 --reason 理由 |
| maintenance-init | 初始化正式维护状态 |
| maintenance-plan | 保存计划及证据，返回plan_id |
| maintenance-apply | --plan ID；校验后整批执行 |
| maintenance-report | 窗口、计划过期状态及内容队列 |
| maintenance-review | --case ID --decision resolved或dismissed --reviewer 人名 --reason 理由 |

所有operation均可带--config配置路径。手工assign/recluster属于显式管理操作，
不能把它们当作具备维护窗口限额和冷却规则的maintenance-apply替代品。

## 9. 聚类、反馈、收割和维护设计

### 9.1 聚类和参数评估

球形二分k-means处理单位description向量，固定seed=42，max_iterations=50。
候选k=[2,3,4,5,6,8]；每候选4轮bootstrap配对计算ARI，平均稳定性至少0.5后按silhouette选择。
无合格候选回退B=1。初始软分配第二归属最大cosine距离0.15，随后重算最终质心。
当前8节点只是几何选型结果，部分节点混合，具体成员解释见CLUSTERING_RESULT.md。

calibrate只比较同语料、同查询集合、同基准标签、同样本/模式/用途的已观测参数格点。
同时考察路由覆盖、搜索节点数和去重候选规模；target_recall默认0.95。
没有观测时NOT_EVALUATED；不会生成未运行格点成绩，也不会自动应用推荐值。

### 9.2 效用反馈

R=被召回次数，G/B=消费方好/差评；R不是有真值分母的召回率。
可用率G/(G+B)，Wilson下界z=1.96，默认至少20条评分才认为证据足量。
按语料版本、样本类型、常规/探索分组，保留按rank和历史节点的同伴基线。
查询向量和、均值和质心仅累计实际有向量的消费记录；无样本NO_SAMPLES，抵消为ZERO_SUM。

### 9.3 签名收割与人工审核

当前语料的真实查询，以全局embedding top-1为候选标签；该标签只是伪真值。
提取3～8词n-gram、机器码、error code、十六进制码、errno及引文模式。
至少3条不同查询支持，其他skill查询中的出现比例不超过0.05，单次最多处理50项。
保存事件ID、query_id、原文片段位置、方法与跨skill计数，不生成虚构confidence。
approve/reject必须给candidate ID、审核者和理由；不自动批准。
审核只改管理副本triggers，已决定记录不可随意覆盖；过期候选须重新收割后审核。

### 9.4 正式维护窗口

| 配置 | 默认值 | 用途 |
| --- | ---: | --- |
| min_feedback_samples | 20 | 反馈判断门槛 |
| good_wilson_lower | 0.65 | 几何迁移的效用下界 |
| low_usability | 0.5 | 低于该值进入内容队列 |
| relative_margin | 0.1 | 同节点同rank足量同伴中落后超过此差值进入内容队列 |
| move_margin | 0.03 | 查询质心对新旧节点的优势门槛 |
| dual_min_similarity / dual_max_gap | 0.55 / 0.04 | 双挂边界 |
| orphan_similarity | 0.45 | 远离全部节点时考虑独立成簇 |
| max_moves_per_window | 3 | move/attach/isolate合计上限 |
| max_splits_per_window | 1 | 局部拆分上限 |
| cooldown_windows / min_new_feedback | 2 / 5 | 至少隔2个执行窗口且新增5条未使用评分 |
| min_window_seconds | 3600 | 相邻窗口最小间隔 |
| route_window_queries | 20 | 前后质量窗口各20条不同查询 |
| route_drop / route_recall_target | 0.1 / 0.95 | 下降至少10个百分点且近期低于目标时考虑拆分 |

动作含move、attach、isolate、content_review及局部拆分。节点规模严格大于2×target_size也可触发拆分。
低效用优先进入内容队列，不通过换节点掩盖内容问题；不同分组目的地冲突则暂缓。
质量拆分只用当前布局、同参数、常规evaluation，不混旧布局或消费兜底。
计划绑定输入指纹；新观测、评分、签名或布局等变化会使旧计划过期。
整批深副本执行，任一动作或发布失败不切换CURRENT；已执行计划重试不重复动作。
内容队列resolved是人工声明，不自动改正文，也不证明修复效果。

## 10. 部署、锁及恢复

### 10.1 已部署环境的日常启动

直接使用已有CURRENT及API，先verify即可。不要把initialize/cluster放进Agent启动流程。
新配置路径或迁移环境还需保持35项来源和模型空间一致。

### 10.2 空库初始化顺序

仅当确实要创建新库时，先准备35项原文、索引和有效缓存，再执行：

```powershell
Set-Location 'D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system'
python -B manager.py initialize
python -B manager.py cluster
python -B manager.py feedback-init
python -B manager.py signature-init
python -B manager.py maintenance-init
python -B manager.py verify
```

需要隔离新库时复制配置并修改data_dir，然后每条命令明确--config；不要误对正式库初始化。
原缓存重建脚本：`D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\dynamic-retrieval-test\precompute_embeddings.py`，
重建会涉及独立的远程调用与配置，不属于普通检索启动步骤。

### 10.3 并发与故障

API和manager共享每data_dir的线程锁与操作系统文件锁。锁覆盖读取、网络、计算、发布全过程，
保证一次查询不跨代，同时意味着当前查询串行，不能承诺高并发。
同进程其他线程等待锁；跨进程占锁时非阻塞报错，由调用方重试。进程退出后系统释放锁。
WRITER.lock文件存在本身不代表仍被占用；不要通过删除锁文件强制抢占。
manager中的部分报告也进入该锁，不能假定所有报告命令都可与长查询并行。

| 情况 | 当前行为 |
| --- | --- |
| 非法query/参数/评分/向量/版本 | ValidationError，继承ValueError；不发布新代 |
| 非法触发函数或构造器返回类型 | TypeError；不冒充正常零命中 |
| provider缺失或模型维度不符 | 需要embedding时明确报错 |
| 网络或provider异常 | 向上传递，未完成查询不发布消费事实 |
| 写文件或原子切换失败 | CURRENT保留原代，可能遗留未发布目录 |
| 派生反馈损坏、事实完好 | rebuild-feedback回放恢复 |
| 原始事实损坏 | 不自动修补；保留证据后选择已校验恢复点 |

当前完整回放及完整快照发布面向35项规模，不是O(1)日志追加实现。
没有自动快照清理、后台维护、跨机器事务、服务端HTTP API或查询幂等请求键。

### 10.4 读取恢复点

```python
from pathlib import Path
from storage import SnapshotStore

store = SnapshotStore(Path(r"D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\data"))
current = store.read()
```

同代历史文件必须整体保留。当前没有专用rollback CLI；恢复应停写并取得同一写锁，
完整校验拟恢复历史代后再原子替换CURRENT，而不是逐个覆盖state/vectors/日志。
SnapshotStore._read_generation是内部辅助接口，不是公开稳定API。
若回到旧反馈快照，之后的事实不会自动合并回来，不能把回指针视为无损撤销。

## 11. 旧检索兼容与独立价值

当前固定入口仍为 `PROGRAM.handle_raw_trace(raw_trace)`，默认工厂使用管理系统检索。
原retrieval_program的developer_trace_converter、developer_should_retrieve、developer_build_query继续生效。
兼容工厂在新旧协议类型之间桥接，返回原模块的RetrievalResult、Query、Hit及Document类型。
每Agent会话应单独调用create_developer_program，不应共享全局PROGRAM的轨迹。
PROGRAM.feedback或program.system.feedback接收实际评分。

原通用DynamicRetrievalProgram、材料解析器、查询和检索策略接口仍保留，
create_legacy_program可创建原skills_tests策略实例。通用框架后续可用于其他材料检索。

旧版备份目录的BACKUP_MANIFEST.json记录17个文件的SHA256；包含旧代码、固定入口、运行脚本、
设计/工作文档、skills_tests及缓存。未复制.env或密钥；独立运行时从环境提供旧embedding配置。
备份中的原create_developer_program仍创建旧程序，不依赖新管理系统。

## 12. 验证证据及后续开发注意点

以下为已发生的历史运行，不代表本次文档编写重新执行：

| 证据 | 绝对路径 / 结论 |
| --- | --- |
| 首次聚类说明 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\CLUSTERING_RESULT.md` |
| 可恢复真跑 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\runs\live-20261015-01\`；40查询真实embedding，评分为synthetic |
| 强制一致切换 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\runs\forced-switch-20261015-01\`；故意构造一致结果的模拟测试，不是效果证据 |
| 维护恢复演练 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\runs\maintenance-20261015-01\`；复用查询向量和模拟评分，完成迁移、幂等及恢复 |
| 第五阶段正式部署 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\runs\phase5-deployment-20261015-01\result.json` |
| 接入完整验证 | `D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system\runs\integration-20261015-01\result.json`；73项通过，60.120秒 |

接入验证包含：自定义Agent触发、非触发零调用、签名短路、抽样一致/分歧和回滚、评分幂等、
快照更新、失败不发布、线程及跨进程锁、本地HTTP完整链路、旧入口类型兼容及备份独立运行。
接入轮次新增收费API调用为0，真实外部Agent会话NOT_RUN；早期真跑另有真实API记录，二者不可混为一谈。

后续验证命令：

```powershell
Set-Location 'D:\PycharmProjects\CodeHarness\master_work\experiments\skill-management\skill-management-system'
python -B -m unittest discover -s tests -q
python -B manager.py verify
```

测试使用临时库；部分生产门槛测试在临时目录故意构造real标签以验证规则，不能当正式真实流量。
部分测试依赖本地原始缓存和既有正式基线，迁移机器时需准备相应输入。
live_trial.py等真跑脚本不是普通回归：新运行可调用收费API，旧检查点还会验证保护指纹。
原入口接入改动后，早期固定指纹演练可能拒绝恢复；不要修改历史指纹以绕过保护，应新建隔离运行。

开发顺序建议：先在独立data_dir接入实际Agent事件与真实评分，再评估参数和签名复查率。
若以后要增删skill、修改description、扩展过滤、异步吞吐或服务化，应先定义数据迁移及协议，
不要直接绕开35项名单、不变量或同代发布机制。

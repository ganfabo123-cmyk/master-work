# 领域聚类流水线运行说明

本文是当前版本的可执行流程。目标是把大量轨迹先用本地、无模型的统计方法压缩成少量领域候选，再用一次小输入的 LLM 调整领域名称、合并关系和混合簇，最后把结果交给 Skill 抽取流程。

## 总体数据流

```text
原始切片 JSON
  ↓ token_frequency.py
每切片 token 频率与出现区间
  ↓ unsupervised_domain_graph.py
数学粗簇 domains.json / assignments.json
  ↓ analyze_slice_openings.py + tool_operation_objects.py
首句证据与文件/工具证据
  ↓ build_domain_feature_cards_v2.py
精简特征卡片 domain-feature-cards.json
  ↓ build_trajectory_behavior_graphs.py + compress_behavior_profiles.py
领域行为图与少量行为原型
  ↓ clean_skill_traces.py
面向 Skill 抽取的清洗轨迹
  ↓ classify_cluster_outcomes.py
领域内成功/失败结果分组
  ↓ LLM（llm-domain-normalization-prompt-v2.md）
领域归一化 JSON
  ↓ apply_llm_domain_normalization.py
最终领域簇 domains.json / summary.json
  ↓ 后续 Skill 抽取 LLM
按领域选择性展开轨迹并抽取 Skill
```

数学阶段不调用 embedding，也不依赖人工领域词典。LLM 只看簇卡片、行为原型和少量代表轨迹，不逐条阅读 97 个切片。

Skill 抽取前还要经过一次独立的轨迹清洗：去掉元数据 record、无正文 tool result、重复事件、长代码块和环境 ID；保留用户意图、助手决策、工具名称、文件目标、命令、任务列表、错误或测试结果。清洗不会改变领域成员关系，只改变发送给 Skill 抽取 LLM 的文本。

在领域簇内部，还可以运行结果状态划分：

```powershell
python master_work/dynatic-split-session-test/classify_cluster_outcomes.py `
  --slices-dir "$SLICES" `
  --domains "$BASE/unsupervised-domain-complete-v6/domains.json" `
  --output "$BASE/cluster-outcome-classification-v1"
```

它只看每条切片末段的 20 个有正文事件，比较成功/失败词和错误/测试结果证据，避免把中途失败但最终修复的轨迹直接判为失败。输出保留 `success`、`failure` 和 `unresolved`；`unresolved` 不强行归入任一类。

## 0. 输入约定

输入是动态切片目录，每个 `segment-*.json` 至少包含：

```json
{
  "start_event": 1,
  "end_event": 12,
  "events": [
    {"category": "user_text", "text": "..."},
    {"category": "tool_call", "tool_name": "...", "arguments": {}}
  ]
}
```

当前数据目录示例：

```powershell
$ROOT = "C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering"
$BUNDLE = "C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle"
$BASE = "$ROOT\master_work\dynatic-split-session-test"
$SLICES = "$BUNDLE\dynatic-split-session-test\sliced-sessions"
Set-Location $ROOT
```

## 1. 生成切片级 token 统计

```powershell
python master_work/dynatic-split-session-test/token_frequency.py `
  --slices-dir $SLICES `
  --output "$BASE/token-frequency-banded-v3-exclusive-no-symbols"
```

输入：原始切片目录。

输出：

- `segments/*.json`：每个切片的 token 频率；
- `summary.json`：切片数量、分词规则和统计口径；
- `token-set-decomposition/`：按全局出现率划分的 token 集合。

默认不计独立符号，保留大小写；参数值和正文计数，参数键、工具名和事件类型只作为元数据。该结果是后面所有领域统计的唯一词频输入。

## 2. 生成事件、首句和工具证据

事件级统计用于检查词来自哪类事件；它不是领域聚类的第二套标签。

```powershell
python master_work/dynatic-split-session-test/event_token_frequency.py `
  --slices-dir $SLICES `
  --output "$BASE/event-token-frequency"

python master_work/dynatic-split-session-test/event_behavior_signals.py `
  --input-dir "$BASE/event-token-frequency" `
  --output-dir "$BASE/event-behavior-signals"

python master_work/dynatic-split-session-test/tool_operation_objects.py `
  --input-dir $SLICES `
  --output-dir "$BASE/tool-operation-signals"

python master_work/dynatic-split-session-test/analyze_slice_openings.py `
  --stats-dir "$BASE/token-frequency-banded-v3-exclusive-no-symbols/segments" `
  --output-dir "$BASE/slice-opening-analysis"
```

主要输出：

- `event-token-frequency/events.jsonl`：事件类别和事件级词频；
- `tool-operation-signals/slice-tool-signals.jsonl`：每个切片的操作、文件类型和目标文件；
- `slice-opening-analysis/slice-opening-analysis.json`：首事件、首个正文事件和第一句文本。

这些文件只提供证据，不直接决定簇名。

## 3. 无监督数学粗聚类

当前冻结基线是 `unsupervised-domain-complete-v6` 的参数。可复现命令为：

```powershell
python master_work/dynatic-split-session-test/unsupervised_domain_graph.py `
  --slice-dir "$BASE/token-frequency-banded-v3-exclusive-no-symbols/segments" `
  --output "$BASE/unsupervised-domain-complete-v6" `
  --max-terms 300 `
  --edge-threshold 0.55 `
  --min-support 3 `
  --min-coverage 0.03
```

输入：每切片 token 频率 JSON。

内部处理：

1. 保留高信息量 token；
2. 按切片出现率计算稀有度，公共词自动降权；
3. 计算 token 共现相似度；
4. 用 complete-linkage 风格的非传递词团生成候选领域；
5. 将包含词团证据的切片加入候选簇，允许一个切片进入多个簇；
6. 用 `min-support` 和 `min-coverage` 丢弃证据过少的候选簇。

输出：

- `domains.json`：粗簇、词团、成员切片和信息覆盖度；
- `assignments.json`：每个切片到粗簇的相对匹配；
- `residual-terms.json`：未被粗簇解释的高频词；
- `summary.json`：参数和覆盖统计。

当前 97 条切片得到 8 个数学粗簇。这个阶段只负责发现和保留证据，不负责给簇起最终领域名。

## 4. 生成给 LLM 的精简特征卡片

```powershell
python master_work/dynatic-split-session-test/build_domain_feature_cards_v2.py
```

脚本固定读取：

- `unsupervised-domain-complete-v6/domains.json`；
- `token-frequency-banded-v3-exclusive-no-symbols/segments/`；
- `slice-opening-analysis/slice-opening-analysis.json`；
- `tool-operation-signals/slice-tool-signals.jsonl`。

输出：

`domain-feature-cards-v2/domain-feature-cards.json`

每个卡片只保留：

- `core_terms`：粗簇原始核心词经过全语料 IDF 重排后的核心词；
- `extended_terms`：按 TF-IDF 排名的扩展词；
- `distinctive_terms`：簇内有支持且全局稀有的词；
- `generic_terms`：至少半数切片出现的通用词；
- `representative_inputs`：按核心词命中排序的代表首句；
- `file_tool_evidence`：操作、文件类型和目标文件证据；
- `overlaps`：与其他簇的成员 Jaccard 重叠；
- `support`、`session_count`、`information_coverage` 和成员 ID。

词的排序使用语料自动计算的：

```text
term_weight = term_frequency × (log((N + 1) / (document_frequency + 1)) + 1)
```

因此不需要预设 Python、Kernel、Web 等词典。卡片中的 `generic_terms` 还会明确暴露一个簇被通用词污染的程度。

## 5. 把卡片喂给 LLM

在需要观察行为结构时，可以在卡片之后生成廉价轨迹图：

```powershell
python master_work/dynatic-split-session-test/build_trajectory_behavior_graphs.py
```

输入：数学粗簇成员和原始切片事件。

输出目录：`trajectory-behavior-graphs-v1/`

- `Dxxx.json`：每个领域的有向加权行为图；节点是事件类别/工具，边是相邻事件转移；
- `Dxxx.md`：同一张图的 Mermaid 可视化；
- `slice-profiles.jsonl`：每条轨迹的短序列、行为签名、事件数量、操作和文件类型；
- `summary.json`：领域数和画像数量。

这一步不命名“索引优化”或“样式调整”等语义行为，只保留可观察的操作结构。连续重复事件会折叠，图中节点和边按出现次数排序。后续可以用 `slice-profiles.jsonl` 做领域内部的序列聚类，也可以直接把某个 `Dxxx.json` 和少量代表轨迹交给 LLM。

## 6. 将轨迹压缩成行为原型

如果一个领域仍然包含几十条轨迹，继续运行：

```powershell
python master_work/dynatic-split-session-test/compress_behavior_profiles.py
```

输入：`trajectory-behavior-graphs-v1/slice-profiles.jsonl` 和数学粗簇成员。

内部使用 Jaccard 相似度比较四类廉价特征：

- 折叠后的事件/工具序列节点；
- 已提取的操作类型；
- 文件类型；
- 轨迹规模分箱。

输出目录：`behavior-prototypes-v1/`。每个领域最多保留 8 个行为原型；每个原型包含成员数量、代表切片 ID、公共操作、文件类型和序列节点。当前 50 条轨迹的领域大约会压缩成 5～8 个原型，同时保留所有成员 ID，便于回溯。

这一步仍然不命名语义行为，只做结构去重和代表性选择。

## 7. 把卡片和行为原型喂给 LLM

提示词文件：

[llm-domain-normalization-prompt-v2.md](./llm-domain-normalization-prompt-v2.md)

发送给 LLM 的信息只有：

1. 全部粗簇卡片；
2. 对应领域的行为图或行为原型；
3. 卡片字段含义和归一化规则；
4. 要求严格返回 JSON。

LLM 需要完成的工作：

- 判断哪些粗簇是同一个二级领域；
- 给合并后的领域起名字；
- 从输入卡片中选择核心词和证据；
- 标记混合簇或证据不足簇；
- 给出可继续拆分的维度。

LLM 不允许：

- 凭空增加卡片中没有的技术名；
- 用通用词单独命名领域；
- 输出没有校准依据的 confidence、概率或分数；
- 直接改写成员切片内容。

当前可行性测试中由 GPT-5.6 Luna 执行这一步，输出：

`llm-domain-normalization-v3/normalized-domains.json`

## 8. 将 LLM 结果重新绑定到数学簇成员

```powershell
python master_work/dynatic-split-session-test/apply_llm_domain_normalization.py `
  --domains "$BASE/unsupervised-domain-complete-v6/domains.json" `
  --normalization "$BASE/llm-domain-normalization-v3/normalized-domains.json" `
  --output "$BASE/llm-assisted-domain-v3"
```

这个脚本不重新猜成员，只根据 LLM 给出的 `source_clusters` 合并原数学簇成员，因此领域名变化不会丢失原始轨迹证据。

输出：

- `llm-assisted-domain-v3/domains.json`：最终领域、来源粗簇、核心词、成员切片和拆分提示；
- `llm-assisted-domain-v3/summary.json`：领域数、混合簇数、覆盖数和重叠数。

当前结果为 3 个归一化领域和 1 个混合簇：Kernel/Boot、C++/Parser/Lexer、Web UI，D001 保留为混合簇。领域之间允许成员重叠，这是为了保留证据，不强行做互斥分配。

## 9. 后续 Skill 抽取

最终 Skill 抽取不直接读取 97 条轨迹。推荐顺序是：

1. 先读取 `llm-assisted-domain-v3/domains.json`；
2. 用领域名、核心词、代表首句和文件/工具证据形成领域摘要；
3. 只展开该领域的成员切片 ID；
4. 对混合簇和低信息簇跳过或单独处理；
5. LLM 输出领域 Skill、适用条件、典型输入和操作模式。

因此第 1～6 步都可以在海量轨迹上本地批量执行；第 7 步只做一次小输入的领域归一化，第 9 步才对选中的代表轨迹做 Skill 抽取。

## 三层实验产物

统一入口：`three-layer-products-v1/manifest.json`。

```text
97 条原始切片
  → 3 个 LLM 归一化粗领域：llm-assisted-domain-v3/
  → 8 个数学细领域：unsupervised-domain-complete-v6/
  → 每个细领域 success / failure / unresolved：cluster-outcome-classification-v1/
```

3 个粗领域也生成了对应的结果划分：`cluster-outcome-classification-broad-v1/`。由于粗领域由多个细簇合并而来，粗领域之间允许轨迹重叠；细领域结果用于明天的 Skill 抽取主输入。

## 复现检查清单

- 输入切片是否包含 `events`、`start_event` 和 `end_event`；
- token 统计的切片数量是否等于预期；
- 粗簇输出是否同时生成 `domains.json`、`assignments.json` 和 `summary.json`；
- 特征卡片是否包含首句和工具/文件证据；
- LLM 是否只返回提示词规定的 JSON 字段；
- 应用 LLM 结果后，成员数量是否与来源粗簇一致；
- `mixed_or_unresolved` 是否被保留，而不是被静默丢弃。

参数变化时，输出目录应使用新版本号，不能覆盖 `unsupervised-domain-complete-v6` 或 `llm-assisted-domain-v3`，以便比较覆盖率、簇数和卡片质量。

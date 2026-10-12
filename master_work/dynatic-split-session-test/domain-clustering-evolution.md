# 领域聚类演进记录

## 目标

当前目标是把 97 个轨迹切片整理成领域簇，例如 Kernel、Python、Frontend、Android、PostgreSQL 等。这里的“领域”指技术、平台、产品或子系统层面的主题，不要求簇内轨迹执行相同操作。

聚类结果最终会交给 LLM 做 Skill 或领域知识抽取，因此算法允许保留少量噪声，但不能过早丢失领域证据。低置信度或混合切片可以被放弃，领域簇自身需要保留足够完整的证据。

## 第一阶段：事件和切片级廉价统计

最初从切片整体统计词频，随后把粒度下沉到具体事件类型：`user_text`、`assistant_text`、`tool_call`、`tool_result` 和 `record`。

这一阶段得到的经验是：

- 事件类型、工具操作、文件路径和词频可以提供廉价的领域信号；
- `record` 和 `tool_result` 不能简单丢弃，它们包含项目名和技术线索；
- 通用词和协议字段会造成大量噪声；
- 词频可以发现领域候选，但无法处理同义词、父子领域和项目名与技术领域的区别。

## 第二阶段：原始 embedding 聚类

使用已有的 1024 维事件 embedding 对切片做加权平均。没有使用人工的事件到数字标量映射，也没有使用手工类别编码。

随后加入了数据驱动的词稀有度：

```text
rarity(p) = ((1-p)^2) / ((1-p)^2 + p^2)
```

其中 `p` 是一个词出现在多少条切片中的比例。越稀有的词贡献越大，所有切片都出现的词贡献接近零。

事件来源也加入了软权重：`record` 较低，`tool_result` 居中，其余事件较高。这个版本得到 4 个粗领域簇，但发现 embedding 更擅长识别项目和技术领域，不能自动保证领域层级统一。

## 第三阶段：递归领域切分

对粗簇计算簇内余弦相似度平均值作为执行度，并递归切分高相似度簇。随后加入轨迹数量惩罚：

```text
size_penalty = 1 / (1 + alpha * log2(member_count))
```

规模惩罚可以拆开大型混合簇，但过大的 `alpha` 会产生大量小簇。当前递归版本说明：规模惩罚可以改善粒度，但不能解决领域命名、父子层级和泛词污染。

## 第四阶段：无监督领域词团

为了避免依赖人工领域词典，构造了轨迹—词项矩阵：

```text
轨迹 × token/ngram
```

使用 TF-IDF 和词项共现关系发现候选领域词团。曾尝试过普通连通分量，但 `server`、`page`、`index` 等桥接词会把多个领域串成一个巨型簇。

随后改用非传递的 complete-linkage 词团。结果可以自动发现：

```text
kernel, boot, GOP, framebuffer
cpp, parser, lexer
icon, html, styles, CSS
```

但阈值高会漏掉领域，阈值低会造成碎片化。因此无监督词团适合作为候选领域发现器，而不是最终领域树生成器。

## 第五阶段：信息完整度和特征卡片

为了让 LLM 不必阅读每个簇的全部切片，为每个簇生成特征卡片。卡片包含：

- 核心词团；
- 更宽的高频词列表；
- 词的轨迹支持数；
- 完整词频分布；
- 代表性首句；
- 命中的核心词；
- 成员轨迹 ID；
- session 数和信息完整度。

特征词不是人工填写，而是从簇内词频、TF-IDF 和共现关系中自动提取。LLM 只接收卡片，不接收全部原始轨迹。

## 第六阶段：LLM 辅助领域归一化

纯数学方法难以判断以下关系：

- D003、D004、D006 是否都属于 Frontend；
- Kernel、UEFI、GOP 是同级领域还是父子领域；
- `page`、`session`、`index` 是否只是泛词；
- 一个粗簇是否明显混合多个领域。

因此增加一次低成本 LLM 调用。LLM 只处理簇特征卡片，输出：

- 领域名称；
- 来源粗簇；
- 核心词；
- `keep`、`merge` 或 `parent_of` 关系；
- 混合簇；
- 可继续拆分的维度。

不输出没有校准依据的 `confidence`、概率或分数。

当前提示词见：

[llm-domain-normalization-prompt-v2.md](./llm-domain-normalization-prompt-v2.md)

提示词的主要约束是：只能使用卡片证据；不能引入卡片中没有的技术名；通用词不能单独定义领域；证据不足时进入 `mixed_clusters` 或 `unresolved_clusters`。

## 当前 LLM 归一化结果

GPT-5.6 Luna 对 8 个粗簇生成了 3 个粗领域层：

```text
domain-kernel-boot
  source: D002

domain-parser-lexer
  source: D007

domain-web-ui
  source: D003, D004, D005, D006, D008

mixed: D001
```

这个结果适合作为父领域层。Web/UI 仍然需要后续按平台、页面结构和样式进一步细分；Kernel 仍可能拆为内核实现、启动/ISO 和 GOP/framebuffer。

## 当前基线和限制

当前基线是“无监督粗簇 + 特征卡片 + 一次 LLM 归一化”，不是纯数学最终领域树。

已知限制：

1. 项目名、技术名和通用实现词仍可能混在一起；
2. 一个轨迹可以属于多个领域，成员支持数存在重叠；
3. Web/UI 父领域目前偏宽；
4. D001 仍是混合簇，应保留为未利用数据；
5. 参数扫描可以发现覆盖—纯度前沿，但不能单独决定最终领域层；
6. 领域命名和父子关系需要 LLM 处理，不能靠余弦阈值完全解决。

## 当前推荐流程

```text
原始轨迹
→ 事件词频和工具信号
→ TF-IDF / 共现发现粗领域词团
→ 信息完整度筛选
→ 生成宽特征卡片
→ 一次 LLM 领域归一化
→ 数学算法保留成员、合并关系和混合簇
→ 只把必要的领域簇交给后续 LLM Skill 抽取
```

这条流程的重点是：数学方法负责低成本覆盖和证据保留，LLM 负责少量语义归一化，而不是逐条阅读轨迹。

完整的可执行命令、输入输出约定、LLM 喂入字段和结果回写步骤见：

[domain-clustering-pipeline.md](./domain-clustering-pipeline.md)

当前新增的廉价行为图产物位于 `trajectory-behavior-graphs-v1/`：它描述事件/工具的顺序结构，不尝试直接给行为命名，可用于领域内部的进一步序列聚类。此前尝试的 `strong/medium/weak` 分层 packet 暂不纳入主流程，因为它没有解决粗簇成员混杂的根因。

## 第七阶段：将二级领域作为实际粗领域

经过检查，一级父领域对后续处理过于宽泛，因此实际交给 LLM 的粗领域层使用二级候选领域，而不是一级父领域。

当前可用的二级粗领域大致为：

```text
Kernel / Boot
C++ / Parser / Lexer
UI Layout / Interaction
Frontend Styling / HTML / Icon / CSS
Web / Android
```

`Page Structure` 可以作为低质量候选，`D001` 作为混合或未利用簇。当前二级领域数量大约为 5～7 个，适合让 LLM 做下一步领域判断和 Skill 抽取。

这并不要求数学聚类完全正确。允许存在以下情况：

- 一个轨迹同时属于多个粗领域；
- Web 和 Android 在同一个候选领域中；
- CSS、HTML、Icon 等相近领域暂时重叠；
- 少量混合簇被保留但不进入主要 Skill 抽取流程。

原因是 LLM 可以在特征卡片层面完成合并、拆分和异常判断。算法的重点是减少 LLM 需要阅读的原始轨迹数量，并保留充分的领域证据。

## 第八阶段：LLM 提示词和可行性结果

为避免给 LLM 增加无科学依据的字段，提示词不再要求 `confidence`、概率或分数。LLM 只输出：

- 领域名；
- 来源粗簇；
- 核心词；
- `keep`、`merge` 或 `parent_of` 关系；
- 混合簇；
- 继续拆分提示；
- 证据词或代表短语。

提示词要求所有核心词和证据必须来自输入卡片，不允许凭空增加技术名。提示词文件为：

[llm-domain-normalization-prompt-v2.md](./llm-domain-normalization-prompt-v2.md)

GPT-5.6 Luna 对当前 8 个粗簇生成了以下归一化结果：

```text
domain-kernel-boot
  source: D002

domain-parser-lexer
  source: D007

domain-web-ui
  source: D003, D004, D005, D006, D008

mixed
  source: D001
```

随后由第二个算法保留成员轨迹和来源关系，生成 3 个归一化领域、1 个混合簇。由于粗簇允许多领域归属，领域之间存在重叠，这是有意保留的信息，不视为重复数据。

## 当前可用性结论

当前版本已经可以作为 LLM 前置领域筛选器使用：

```text
数学粗聚类
→ 宽特征卡片
→ 一次 LLM 领域归一化
→ 二级领域作为实际粗领域
→ LLM 选择性展开轨迹并抽取 Skill
```

当前不宣称数学聚类已经得到完美领域树。它的可用目标是：

- 把大多数轨迹路由到少量可解释的领域候选；
- 保留足够词项、代表首句和成员 ID；
- 允许混合簇和未利用轨迹存在；
- 让 LLM 只处理领域卡片和必要的轨迹子集。

在当前 97 条轨迹上，这个流程已经足够进行可行性测试。后续优化重点应放在二级领域的合并/细分和 LLM 需要展开的轨迹选择，而不是继续追求一次纯数学聚类完全正确。

## 第九阶段：领域内成功/失败结果划分

为了让 Skill 抽取同时看到“正确完成路径”和“失败后的修复路径”，在领域聚类之后增加结果状态层。该层不重新聚类，也不依赖 embedding，而是读取每条切片末段的 20 个有正文事件：

```text
成功证据：passed、success、fixed、resolved、verified、completed 等
失败证据：error、failed、exception、traceback、fatal、not working 等
```

中途出现错误但末段出现修复和验证证据的轨迹，按末段结果处理。没有决定性证据的轨迹保留为 `unresolved`，不伪造成功或失败标签。

当前产物：

- 3 个 LLM 归一化粗领域及其结果划分：`cluster-outcome-classification-broad-v1/`；
- 8 个数学细领域及其结果划分：`cluster-outcome-classification-v1/`；
- 三层产物入口：`three-layer-products-v1/manifest.json`。

当前三层结构为：

```text
97 条切片
  → 3 个归一化粗领域
  → 8 个数学细领域
  → 每个细领域 success / failure / unresolved
```

这一层的意义不是宣称文本词命中等于真实成功，而是先把明显的成功证据、失败证据和没有结果证据的轨迹分开，为下一步 Skill 抽取提供对照样本。

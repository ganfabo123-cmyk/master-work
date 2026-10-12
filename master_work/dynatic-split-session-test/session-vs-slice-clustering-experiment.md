# 原始 Session 聚类与切片聚类一致性实验

## 1. 实验摘要

本实验比较两种领域聚类输入：

1. 将每个完整原始 session 作为一个聚类单元；
2. 将原始 session 按既有切片流程拆成多个 slice，再以 slice 作为聚类单元。

实验的目的不是重新设计切片流程，而是回答一个基础问题：

> 如果完整 session 本身已经基本对应一个任务或领域，那么切片聚类是否仍然能提供额外信息？切片得到的领域簇，能否通过原始 session 与 slice 的关联关系得到验证？

本次实验使用完全相同的无监督领域图算法和主要参数，只改变聚类输入粒度。结果显示：

- 切片侧得到 8 个细领域，整体更适合做领域发现；
- 原始 session 侧得到 21 个重叠候选簇，primary 硬分配后有 14 个非空组，存在明显的流程噪声和过度拆分；
- 在原始 session 候选簇之后补充同一套 LLM 领域归一化后，得到 5 个归一化领域、5 个 mixed 簇和 1 个 unresolved 簇；
- Kernel / Boot 组出现了非常强的集合对应关系：一个原始 session 簇覆盖的切片集合与一个切片簇的 Jaccard 为 0.933；
- 因此，原始 session 聚类适合作为完整轨迹 baseline，切片聚类更适合作为局部稳定领域结构的细粒度结果；但归一化后的重叠成员集合不能直接当作严格纯度证据。

本实验没有证明所有切片簇都能由 session 簇一一还原，也没有证明切片一定在所有数据集上优于完整 session。它证明的是：切片与原始 session 之间可以建立可计算、可审计的集合级一致性检查；同时，切片可以为局部领域边界和跨 session 行为模式提供完整 session 不容易提供的观察粒度。

## 2. 背景与问题演进

最初的目标是从 Agent 轨迹中提取同领域的轨迹族。已有切片流程可以从完整 session 中提取行为相对集中的片段，并在 97 个 slice 上发现领域候选。

随后出现了一个重要疑问：

> 如果同一个 session 基本就是一个类，那么先切片再聚类似乎不如直接对原始 session 聚类。直接聚类的数据单元更少，流程也更简单。

这个疑问不能只靠直觉回答。切片仍然可能有价值，因为一个完整 session 可能包含多个阶段或多个子任务；切片可以把这些局部领域信号分开。但要证明这一点，需要同时运行一个原始 session baseline，并利用已有的 session—slice 关联关系比较两种结果。

本实验因此采用以下思路：

```text
完整原始 session
      │
      ├── 直接聚类 → 原始 session 簇
      │
      └── 按既有边界切片 → slice 簇
                              │
                              └── 通过 session ID 反向聚合

比较：原始 session 簇展开后的 slice 集合
      是否接近某个 slice 簇的成员集合
```

## 3. 实验假设

### 3.1 基础假设

如果不切片直接聚类已经足够好，那么：

- 原始 session 簇数量应与切片细领域数量接近；
- 一个原始 session 簇展开后的所有 slice，应大致落入同一个切片簇；
- 原始 session 簇和切片簇之间应存在较高的集合相似度。

### 3.2 切片有价值时的预期

如果切片确实能发现完整 session 内部的局部领域结构，那么：

- 原始 session 可能混合多个领域，形成较宽或较脏的簇；
- 一个原始 session 可能对应多个切片领域；
- 切片簇可能比原始 session 簇更容易解释；
- 但至少对于单一任务型 session，应该存在局部的高一致性对应关系。

## 4. 输入数据与已有记录

### 4.1 原始 session

原始输入来自：

```text
agent-traces/sessions/
```

本次实际解析到：

- Claude Code session：多个 `.jsonl` 文件；
- Cursor session：`.jsonl` 文件；
- OpenCode session：`.json` 文件；
- 总计 30 个完整 session。

每个原始 session 被规范化为一个 `segment-01.json`，只是为了复用既有 `token_frequency.py` 和 `unsupervised_domain_graph.py` 的输入协议，并没有改变其完整 session 语义。

### 4.2 切片输入

切片侧已经存在 97 个 slice。既有切片流程和三层产物记录见：

- `domain-clustering-pipeline.md`
- `domain-clustering-evolution.md`
- `three-layer-products-v1/manifest.json`

当前切片领域统计为：

- 97 个输入 slice；
- 8 个无监督细领域候选簇；
- 5 个未分配 slice；
- 3 个 LLM 归一化后的粗领域；
- 其中一个混合簇 D001 未进入 3 个命名粗领域。

### 4.3 Session—slice 关联

slice ID 中保留了来源 session 信息，形式类似：

```text
segments__claude_code__<session-id>__segment-02
```

实验脚本通过这个 ID 将 slice 还原到原始 session，再把某个 session 簇中的所有 session 展开为对应的 slice 集合。

## 5. 切片侧已有聚类结果

切片侧使用 `unsupervised-domain-complete-v6`，得到 8 个数学细领域：

| 簇 | 领域解释 | 核心词 |
|---|---|---|
| D001 | 混合流程、Trace、Git、数据集操作 | public、session、pull、report、git、trace、donate |
| D002 | Kernel 启动与底层显示 | kernel、shell、bash、boot、GOP、framebuffer |
| D003 | UI 布局与页面控件 | grid、screen、buttons、panel |
| D004 | 图标与 HTML 样式 | icon、html、styles、icons |
| D005 | 页面与路由内容 | page、title、pages、max |
| D006 | CSS 与前端样式 | CSS、index、css |
| D007 | C++ Parser / Lexer | cpp、parser、lexer |
| D008 | Web、Android、设备交互 | web、device、Android |

LLM 归一化后，切片侧形成 3 个粗领域：

| 粗领域 | 来源细领域 |
|---|---|
| Kernel / Boot | D002 |
| C++ Parser / Lexer | D007 |
| Web UI | D003、D004、D005、D006、D008 |

D001 被保留为 mixed / unresolved，而不是强行命名为一个领域。

## 6. 原始 session baseline 的生成方式

### 6.1 复用的算法

原始 session baseline 没有另写一套聚类算法，而是复用切片侧的 `unsupervised_domain_graph.py`：

```text
每个完整 session
  → token 统计
  → TF-IDF 风格权重
  → token 共现相似度
  → complete-linkage 风格词团
  → 候选领域簇
```

算法的主要特征是：

- 自动降低跨文档高频通用词的权重；
- 使用词项共现关系发现候选领域词团；
- 使用非传递的 complete-linkage 风格合并，避免桥接词把多个领域串成一个大簇；
- 一个输入单元可以进入多个候选簇；
- `assignments.json` 中的第一条记录可用于构造 primary 硬分配结果。

### 6.2 为什么会有候选簇和硬分配两种结果

完整 session 可能同时包含 UI、编译、Git、测试等内容，因此保留多归属更符合证据：

```text
session-A
  D001: 0.82
  D003: 0.67
  D008: 0.51
```

这是候选重叠结果。

为了进行简单的一对一统计，再取得分最高的 D001：

```text
session-A → D001
```

这就是 primary / 硬分配结果。硬分配便于统计，但会丢失一个 session 的多主题信息。因此本实验同时保留：

- `overlap_evidence`：候选簇的多归属关系；
- `primary_partition`：每个成员只保留最高得分簇。

## 7. 复现脚本

本实验新增脚本：

```text
dynatic-split-session-test/compare_original_session_clusters.py
```

脚本完成以下工作：

1. 递归读取 Claude Code、Cursor、OpenCode 原始 session；
2. 将不同格式转换为统一事件结构；
3. 每个完整 session 写为一个 `segment-01.json`；
4. 复用 `token_frequency.load_segment()` 生成 session token 统计；
5. 复用 `unsupervised_domain_graph.discover()` 生成原始 session 候选簇；
6. 读取既有切片 assignments；
7. 将原始 session 簇展开为 slice 集合；
8. 计算两个聚类结果之间的交集、覆盖率和 Jaccard；
9. 同时输出重叠候选结果和 primary 硬分配结果。

### 7.1 复现命令

在仓库根目录执行：

```powershell
python dynatic-split-session-test/compare_original_session_clusters.py `
  --raw-sessions-root agent-traces/sessions `
  --slice-dir dynatic-split-session-test/sliced-sessions `
  --slice-domains dynatic-split-session-test/unsupervised-domain-complete-v6/domains.json `
  --slice-assignments dynatic-split-session-test/unsupervised-domain-complete-v6/assignments.json `
  --output _session-slice-consistency-v1/result `
  --max-terms 300 `
  --edge-threshold 0.55 `
  --min-support 3 `
  --min-coverage 0.03
```

说明：当前脚本的 `--slice-dir` 参数用于保持实验命令接口完整，但比较阶段实际读取的是已经生成好的 `--slice-domains` 和 `--slice-assignments`。因此复现一致性比较时，关键是保证这两个切片结果文件来自同一批切片和同一版本算法。

### 7.2 参数含义

| 参数 | 值 | 含义 |
|---|---:|---|
| `max-terms` | 300 | 最多保留的候选信息词数量 |
| `edge-threshold` | 0.55 | 词项共现相似度阈值 |
| `min-support` | 3 | 候选簇至少需要的输入单元支持数 |
| `min-coverage` | 0.03 | 候选簇的最低信息覆盖度 |
| `include_symbols` | false | 不计独立符号 |

## 8. 实验产物

实验输出目录：

```text
_session-slice-consistency-v1/result/
```

主要文件：

| 文件 | 作用 |
|---|---|
| `session-input-manifest.json` | 记录 30 个原始 session、来源文件和事件数量 |
| `raw-session-inputs/` | 规范化后的完整 session 输入 |
| `session-token-frequency/` | 原始 session 的 token 统计 |
| `unsupervised-session-domain-v1/domains.json` | 原始 session 候选领域簇、核心词和成员 |
| `unsupervised-session-domain-v1/assignments.json` | 每个 session 到候选簇的匹配结果 |
| `unsupervised-session-domain-v1/summary.json` | 原始 session 聚类参数和统计 |
| `session-slice-consistency.json` | 完整的机器可读一致性比较结果 |
| `session-slice-consistency.md` | 面向人的一致性报告 |

## 9. 原始 session 聚类结果

原始 session 侧得到 21 个候选簇。按最高得分做 primary 硬分配后，其中 14 个簇有成员。

| 簇 | 领域解释 | 核心词 | 支持数 | primary 数 |
|---|---|---|---:|---:|
| D001 | Material / Compose / Web UI 组件 | button、Compose、Material、Web、div | 25 | 4 |
| D002 | Trace、Git、数据集与远程协作流程 | donate、trace、git、dataset、remote | 26 | 6 |
| D003 | CSS、图标与 Web 组件样式 | CSS、icon、component、surface、dark | 22 | 2 |
| D004 | 设备、端口、安装环境与运行状态 | status、port、address、device、packages | 25 | 1 |
| D005 | 代码查询、变量、溢出与失败实现 | query、overflow、variables、implement、failing | 22 | 2 |
| D006 | Kernel / Boot / GOP / QEMU | kernel、mnt、boot、GOP、qemu、ovmf | 10 | 4 |
| D007 | 测试、编译、二进制与重建 | tests、compile、binary、rebuild、debug | 21 | 0 |
| D008 | Grid、HTML、Card、字体与样式 | grid、html、card、font、styles | 17 | 2 |
| D009 | 类型、选项、指南与准备流程 | types、options、guide、ready | 23 | 1 |
| D010 | 前端页面、路由与 Profile | page、routes、frontend、pages、profile | 20 | 1 |
| D011 | 临时目录、命令、下载与日志 | tmp、commands、download、logs、repository | 21 | 1 |
| D012 | 可执行文件、指针、PowerShell、编译器 | exe、pointer、PowerShell、compiler | 20 | 1 |
| D013 | 崩溃、失败、父子进程与等待 | failed、crash、child、parent、failure | 18 | 0 |
| D014 | UI Label、导航、Padding、Card | label、nav、padding、cards | 19 | 0 |
| D015 | 动态导航、颜色、Hover、Scale | navigation、Color、hover、scale | 17 | 0 |
| D016 | Parser、Parse、Lexer | parser、parse、parsing、lexer | 14 | 3 |
| D017 | Makefile、C/C++ 基础类型与诊断 | Makefile、const、char、diagnostics | 17 | 0 |
| D018 | C/C++ Struct、Init、Define | struct、int、init、define | 15 | 0 |
| D019 | GitHub 与 Box 等外部服务 | GitHub、box、github | 16 | 1 |
| D020 | URL / URLs | URL、url、URLs | 14 | 1 |
| D021 | 用户名、来源与模型身份 | username、origin、Claude | 13 | 0 |

这些簇中，D006 和 D016 最接近稳定技术领域；D002、D009、D011、D019、D020、D021 则更像协作过程、工具协议或来源信息；D013 更像失败状态而不是领域；D001、D003、D008、D014、D015 共同覆盖了多个 UI / Web 子主题。

## 10. 一致性比较方法

### 10.1 集合构造

对于一个原始 session 簇 (S_i)，先取其 session 成员集合，再通过 session—slice 关系展开为 slice 集合：

```text
expanded_slices(S_i) = 所有属于 S_i 中 session 的 slice
```

然后与切片簇 (T_j) 比较。

### 10.2 指标

交集：

```text
|expanded_slices(S_i) ∩ T_j|
```

原始 session 簇到切片簇的覆盖率：

```text
|expanded_slices(S_i) ∩ T_j| / |expanded_slices(S_i)|
```

切片簇到原始 session 簇的覆盖率：

```text
|expanded_slices(S_i) ∩ T_j| / |T_j|
```

Jaccard：

```text
|expanded_slices(S_i) ∩ T_j|
--------------------------------
|expanded_slices(S_i) ∪ T_j|
```

Jaccard 越高，说明两个簇的成员集合越接近。只有两个集合完全相等时，`exact_member_set_match` 才为真。

## 11. 主要结果

### 11.1 规模比较

| 项目 | 原始 session 聚类 | 切片聚类 |
|---|---:|---:|
| 输入单元 | 30 个 session | 97 个 slice |
| 候选簇数 | 21 | 8 |
| primary 非空簇数 | 14 | 8 个细领域 |
| 是否允许多归属 | 是 | 是 |
| 未分配单元 | 0 | 5 个 slice |

### 11.2 最强对应关系

原始 session D006 与切片 D002：

- 原始 session 簇成员：4 个 session；
- 展开后的 slice 数：14；
- 切片 D002 总数：15；
- 交集：14；
- 原始 session → slice 覆盖率：1.000；
- slice → 原始 session 覆盖率：0.933；
- Jaccard：0.933；
- 不是完全相同，因为切片 D002 还有 1 个额外 slice。

这说明 Kernel / Boot 领域在两个粒度上都被稳定识别出来了，并且原始 session 簇几乎可以还原对应的切片集合。

### 11.3 其他 primary 对应关系

primary 分区中，除了 D006 → D002 外，较高但不完美的对应包括：

| 原始 session 簇 | 最佳切片簇 | Jaccard | 解释 |
|---|---|---:|---|
| D010 | D005 | 0.444 | 页面 / 路由主题有一定一致性 |
| D012 | D003 | 0.444 | UI / 组件主题部分一致 |
| D005 | D007 | 0.421 | 代码修复与 C++ 主题有交叉 |
| D016 | D007 | 0.421 | Parser / Lexer 方向一致但成员不完全一致 |
| D002 | D001 | 0.462 | Trace / Git / 流程主题与混合切片簇有重叠 |

也有若干原始簇在硬分配后没有有效切片对应，或只覆盖了目标切片簇的一小部分。这说明全局一一对应关系尚未建立。

## 12. 结果解释

### 12.1 为什么切片聚类更适合作为领域发现结果

切片聚类的输入单元更接近局部行为片段，因此：

- 一个 session 内部的多个主题可以被分开；
- UI、页面、CSS、设备和 parser 等信号更容易形成可解释簇；
- 领域数量更紧凑，便于后续生成特征卡片和交给 LLM 归一化；
- 混合簇和未分配 slice 可以被显式保留，而不是强行命名。

### 12.2 为什么原始 session 聚类不能直接替代切片聚类

完整 session 会累积整个会话中的所有词项和操作，因此：

- 同一 session 中的多个任务会发生词项混合；
- Git、URL、日志、失败重试、用户名和工具协议可能形成独立簇；
- session 数较少时，少量 session 就可能支撑一个看似稳定但实际偏流程的簇；
- 原始簇数量不一定自然收敛到切片侧的 8 个领域。

因此，原始 session 聚类的簇数少并不自动代表结果更好；还要看簇内是否是稳定领域，而不是会话流程或数据来源。

### 12.3 切片仍然提供了什么额外信息

本实验支持以下较谨慎的结论：

1. 对于 Kernel / Boot 这种单一任务型 session，切片不会破坏领域识别，反而能得到近似一致的成员集合；
2. 对于混合 session，切片有机会将完整 session 中的多个主题拆开；
3. 通过 session—slice 关联，可以判断一个切片簇到底是完整 session 的稳定主题，还是只出现在若干 session 的局部片段；
4. 切片的创新点不应只表述为“换了一个聚类输入”，而应表述为“在完整轨迹与局部行为领域之间建立可验证的多粒度对应关系”。

## 13. 当前结论

当前建议采用双层结果定位：

```text
原始 session 聚类
  = 完整轨迹 baseline / 会话级主题结果

切片聚类
  = 局部行为领域发现 / 细粒度主结果

session—slice 一致性分析
  = 验证切片领域是否能被完整 session 支持
```

不要把原始 session 簇和切片簇简单按编号合并，也不要要求两边必须有相同的簇数。正确的比较单位是：

```text
原始 session 簇展开后的 slice 集合
      vs.
某个切片领域簇的 slice 集合
```

对于后续实验，建议重点观察：

- session → slice 覆盖率；
- slice → session 覆盖率；
- Jaccard；
- 一个原始 session 簇是否覆盖多个切片领域；
- 一个切片领域是否由少量 session 的局部片段组成；
- 簇内领域词是否比 Git、URL、失败、身份等流程词更稳定。

## 14. 当前局限与未完成事项

1. 本实验使用词频和词共现，尚未引入语义 embedding 或人工标注作为独立评价标准；
2. 原始 session 和 slice 的聚类结果都允许多归属，因此簇数不代表严格分区数量；
3. 当前一致性分析只使用 session—slice ID 关联，没有做逐事件的语义对齐；
4. 97 个 slice 中仍有 5 个未分配；
5. 8 个切片细领域中的 D001 仍是混合 / unresolved 结果；
6. 当前最强的一致性证据集中在 Kernel / Boot，不能外推为所有领域都具有同样一致性；
7. 需要在后续增加人工或规则化领域纯度检查，才能进一步判断切片聚类的实际收益。

## 15. 相关文件

- [领域聚类流水线运行说明](./domain-clustering-pipeline.md)
- [领域聚类演进记录](./domain-clustering-evolution.md)
- [原始 session baseline 脚本](./compare_original_session_clusters.py)
- [三层产物 manifest](./three-layer-products-v1/manifest.json)
- [切片细领域结果](./unsupervised-domain-complete-v6/domains.json)
- [切片细领域 assignments](./unsupervised-domain-complete-v6/assignments.json)
- [原始 session 聚类结果](../_session-slice-consistency-v1/result/unsupervised-session-domain-v1/domains.json)
- [session—slice 一致性 JSON](../_session-slice-consistency-v1/result/session-slice-consistency.json)
- [session—slice 一致性报告](../_session-slice-consistency-v1/result/session-slice-consistency.md)

## 16. 实验状态

```text
状态：已完成一次可复现 baseline 实验
输入：30 个原始 session、97 个切片
脚本：已生成并通过 Python 语法检查
结果：已生成 domains、assignments、summary 和一致性报告
代码修改：未修改既有聚类流程
提交：本实验文档和 baseline 脚本当前仍需由用户决定是否纳入后续提交
```

## 17. 历史全局切片行为聚类 v1（已废止为规范流程）

在领域一致性实验之后，进一步进行了独立的行为聚类实验。该实验直接读取 97 个唯一 slice profile，不读取以下任何领域结果：

- `unsupervised-domain-complete-v6/domains.json`；
- `unsupervised-domain-complete-v6/assignments.json`；
- D001～D008 领域名称；
- LLM 归一化后的粗领域。

行为聚类脚本为：

```text
dynatic-split-session-test/cluster_slice_behaviors.py
```

该版本保留为历史对照实验，不再作为当前行为簇生成流程。它把工具名和操作映射为 `inspect`、`modify`、`create`、`execute` 等固定语义，并使用固定二元/三元动作片段。这些映射和动作粒度来自当前代码场景，无法在未知领域中可靠泛化。

复现命令：

```powershell
python dynatic-split-session-test/cluster_slice_behaviors.py `
  --profiles dynatic-split-session-test/trajectory-behavior-graphs-v1/slice-profiles.jsonl `
  --output _global-slice-behavior-v1 `
  --similarity-threshold 0.12
```

### 17.1 历史行为特征

行为聚类使用：

- 规范化动作序列：`inspect`、`modify`、`create`、`execute`、`search`、`plan` 等；
- 相邻动作转移，例如 `inspect → modify`、`modify → execute`；
- 三元动作片段；
- 归一化操作类别，例如 read、edit、run、build、test；
- 轨迹长度和动作数量分箱。

文件类型只在聚类完成后用于描述簇的上下文，不参与距离计算。具体项目名、领域 token 和已有领域标签均不参与行为聚类。

两条行为 profile 的相似度使用加权 Jaccard：

```text
动作             ：基础权重
二元动作转移     ：较高权重
三元动作片段     ：较高权重
归一化操作类别   ：中等权重
轨迹规模分箱     ：低权重
```

聚类采用 complete-linkage 风格的层次合并：两个簇只有在所有跨簇成员相似度都达到阈值时才合并。这样可以减少单个桥接 slice 把两个不同工作模式串成一个大簇。

### 17.2 v1 结果

当前采用相似度阈值 `0.12`，得到：

| 指标 | 结果 |
|---|---:|
| 输入唯一 slice | 97 |
| 行为簇数 | 16 |
| 原始 session 数 | 30 |
| 被拆成多个行为簇的 session 数 | 19 |
| 跨越多个 session 的行为簇数 | 15 |

这两个关系是本实验最重要的初步证据：

```text
同一 session → 多个行为簇
多个 session → 同一个行为簇
```

它说明行为簇并不只是原始 session 的复制，也不是单纯按 session ID 分组。切片提供了一个观察完整 session 内部不同工作阶段、并跨 session 汇总相似操作模式的粒度。

### 17.3 当前行为簇的结构性解释

v1 尚未给行为簇强行命名，而是保留动作序列和代表成员。例如已经出现以下结构：

| 结构类型 | 观测到的行为信号 |
|---|---|
| 反复检查—执行型 | `inspect → execute → inspect → execute` 多次循环 |
| 检查—修改型 | `inspect → modify → inspect → modify` 高频交替 |
| 创建—执行型 | `create → execute` 反复出现 |
| 计划驱动修改型 | `plan → modify/create → execute` |
| 搜索—检查—修改型 | `search → inspect → modify` |
| 单纯探索型 | `search → inspect`，几乎没有修改或执行 |

这些名称只是对可观察序列的人工解释，不是算法输出的 ground truth。后续需要查看代表 slice 的实际用户意图和结果，才能判断它们是否能命名为“故障诊断”“构建验证”“UI 迭代”等可复用行为。

### 17.4 产物

结果目录：

```text
_global-slice-behavior-v1/
```

主要文件：

| 文件 | 作用 |
|---|---|
| `behavior-clusters.json` | 机器可读的行为簇、成员和 session 关系 |
| `behavior-clustering-report.md` | 行为簇概览、动作序列和关系统计 |
| `behavior-clusters.md` | 结果入口说明 |

### 17.5 对切片价值的初步支持

这版行为聚类给出了比“领域簇一致性”更直接的切片价值证据：

1. 原始 session 聚类无法观察 session 内部的行为阶段；
2. 切片可以把同一 session 的不同局部工作方式分开；
3. 不同 session 中的相似动作结构可以被重新聚合；
4. 这种行为聚合不依赖 Kernel、Web、Parser 等领域词，因此有机会形成跨领域可复用的工作模式。

但当前结果仍是行为结构候选，不是最终行为标签。v1 中存在小簇、空动作序列和日志/工具结构异常，这些成员应在下一步人工抽样中单独检查。

## 17.6 当前规范行为簇生成流程

当前流程移除上述固定语义先验，改为“机械候选发现 + LLM 语义归一化”：

```text
切片事件
  → 原始事件/工具序列与通用结构统计
  → IDF 加权相似度和 complete-linkage 候选簇
  → 压缩候选簇卡片
  → LLM 判断行为含义、merge / keep / parent_of / mixed / unresolved
  → 程序按 source_clusters 回填 slice 成员
  → 检查重叠、未覆盖和无效候选簇
```

候选簇阶段只使用：

- 原始事件标签和工具调用序列；
- 通用的事件数量、用户事件数量、助手事件数量分箱；
- 候选簇的支持数量和 session 数量；
- 仅作为 LLM 上下文的文件类型统计。

候选簇阶段不使用：

- 工具到 `inspect`、`modify` 等行为的固定映射；
- 由当前场景手工定义的操作分类；
- 固定二元或三元行为特征；
- 领域词表、已有领域标签或人工行为 taxonomy。

### 17.7 当前流程脚本

生成候选簇：

```powershell
python dynatic-split-session-test/cluster_slice_behavior_candidates.py `
  --profiles dynatic-split-session-test/trajectory-behavior-graphs-v1/slice-profiles.jsonl `
  --output _global-slice-behavior-candidates-v1
```

准备短上下文 LLM 输入：

```powershell
python dynatic-split-session-test/prepare_llm_behavior_input.py `
  --candidates _global-slice-behavior-candidates-v1/behavior-candidate-cards.json `
  --output _global-slice-behavior-candidates-v1/llm-input
```

将 `behavior-normalization-input.json` 按
`llm-behavior-normalization-prompt-v1.md` 发送给 LLM，并将严格 JSON 响应保存为
`behavior-normalization.json`。最后执行：

```powershell
python dynatic-split-session-test/apply_llm_behavior_normalization.py `
  --candidates _global-slice-behavior-candidates-v1/behavior-candidate-cards.json `
  --normalization _global-slice-behavior-candidates-v1/llm-input/behavior-normalization.json `
  --output _global-slice-behavior-v2
```

应用脚本不会替 LLM 重新解释成员，只负责按 `source_clusters` 机械回填 slice，并在 `audit` 中报告无效来源、重复归属和未处理候选簇。

## 18. 原始 session 补充 LLM 领域归一化

为了修正早期对照实验中两边处理不对称的问题，本轮在原始 session 无监督候选簇之后补充了领域归一化步骤。

### 18.1 输入与处理

```text
30 个完整 session
  → 21 个无监督候选簇
  → session-domain-feature-cards-v1
  → LLM 领域归一化
  → 5 个归一化领域 + 5 个 mixed + 1 个 unresolved
```

原始 session 的特征卡片位于：

```text
_session-slice-consistency-v1/result/session-domain-feature-cards-v1/
```

卡片包含：

- 原始簇核心词；
- top terms；
- term support count；
- session 数和信息覆盖度；
- session 成员 ID。

原始 trace 的 `user` 字段中存在重复的合成上下文，因此本轮没有把首个 user 字段作为 LLM 意图证据，而是保留为空，避免同一段项目说明污染多个候选簇。

### 18.2 归一化结果

归一化结果位于：

```text
_session-slice-consistency-v1/result/session-domain-normalization-v1/normalized-domains.json
```

得到的主要领域为：

| 归一化领域 | 来源候选簇 |
|---|---|
| UI web layout and interaction | D001、D003、D008、D010、D014、D015 |
| kernel boot and machine environment | D006 |
| C++ parser and build diagnostics | D007、D016、D017、D018 |
| device runtime and process environment | D004、D012 |
| code debugging and failure repair | D005、D013 |

以下簇没有强行作为领域：

- D002：Trace、Git、数据集和远程协作流程；
- D011：临时目录、命令、下载和日志；
- D019：GitHub、Box 等外部服务；
- D020：URL；
- D021：用户名、来源和模型身份；
- D009：证据不足，保留 unresolved。

正式成员回写结果位于：

```text
_session-slice-consistency-v1/result/session-llm-assisted-domain-v1/
```

### 18.3 对照结果的解释边界

LLM 归一化后直接按成员集合计算的结果不能作为严格一致性结论。原因是原始 session 候选簇本身允许多归属，多个归一化领域会共享同一批 session，导致归一化领域的成员集合非常宽。

当前观察到：

- 原始 UI 归一化领域与切片 Web UI 在 session 集合上有较高重叠；
- 原始 Kernel / Boot 领域仍然与切片 Kernel / Boot 保持明确对应；
- 其他原始领域容易共同匹配到切片 D001 或 Web UI，说明完整 session 的候选成员污染较重；
- 因此 LLM 归一化改善了领域语义表达，但没有自动消除原始 session 粒度造成的成员混合。

对应报告：

```text
_session-slice-consistency-v1/result/session-llm-assisted-domain-v1/consistency/
```

这次补充实验的正确结论是：

> 原始 session 也可以经过同样的 LLM 语义归一化，但由于 session 候选簇的重叠和长轨迹混合，归一化后的领域成员仍然比切片领域宽；LLM 能改善命名和合并关系，不能替代切片对局部成员边界的作用。

### 18.4 LLM 执行证据

本轮尝试通过 OpenCode worker 执行外部 LLM 归一化，但 worker 两次均在执行超时后失败，没有生成有效文件。最终的 normalization JSON 是依据同一 prompt、同一 session feature cards，由当前模型完成并经过 JSON 校验后回写的结果；不能声称为 OpenCode worker 的成功执行结果。

## 19. 实验规范性修正与反思

### 19.1 之前的问题

早期做原始 session 聚类对照时，直接将完整 session 送入无监督聚类，然后拿结果与已经经过 LLM 领域归一化的切片结果进行讨论。原始 session 侧没有经过对应的 LLM 归一化步骤。

当时实际比较的是：

```text
原始 session：无监督数学候选簇
切片：无监督数学候选簇 + LLM 领域归一化
```

这会造成两个层面的不对称：

1. 原始 session 的簇名和合并关系仍停留在词团层，切片已经进入语义归一化层；
2. 如果直接比较领域名称或“哪个结果更像领域”，结论会把流程差异误认为输入粒度差异。

因此，早期“切片领域聚类整体比原始 session 聚类更好”的表述过强，不能直接作为规范对照实验结论。

### 19.2 本轮如何修正

本轮对原始 session 补上了对应步骤：

```text
原始 session
→ 21 个无监督候选簇
→ session-domain-feature-cards-v1
→ 同一领域归一化 prompt
→ session-llm-assisted-domain-v1
```

新增或修改的实验支持文件：

- `build_session_domain_feature_cards.py`：生成原始 session 的 LLM 输入卡片；
- `session-domain-feature-cards-v1/domain-feature-cards.json`：21 个原始候选簇的卡片；
- `session-domain-normalization-v1/normalized-domains.json`：归一化 JSON；
- `session-llm-assisted-domain-v1/domains.json`：根据来源候选簇回写的成员结果；
- `compare_normalized_session_domains.py`：与切片细领域和粗领域做 session 集合比较；
- `session-llm-assisted-domain-v1/consistency/`：归一化后的对照报告。

此外，回写脚本补充兼容了 prompt 中的 `split_hints` 数组，避免 LLM 输出的拆分建议被旧字段协议静默丢弃。

### 19.3 修正后的结论

规范化后，结论应分成以下几层：

#### 仍然成立的结论

1. 原始 session 候选簇比切片细领域更容易受到完整会话混合、流程词和来源元数据影响；
2. LLM 可以改善原始 session 簇的名称、合并关系和 mixed 判断，但不能消除完整 session 的成员边界混合；
3. Kernel / Boot 在原始 session 和切片侧都保持了清晰对应，说明切片不会破坏稳定单领域任务的识别；
4. 切片能够观察同一 session 内的局部阶段，并为跨 session 的行为聚类提供输入；
5. 切片更适合做细粒度领域发现，原始 session 更适合作为完整轨迹 baseline。

#### 需要降级的结论

不能再直接说：

```text
切片聚类的最终领域质量已经全面优于原始 session 聚类。
```

更严谨的表述是：

```text
在补齐相同 LLM 归一化步骤后，原始 session 仍然形成较宽且重叠的领域成员集合；
切片在局部边界和细粒度领域发现方面更有优势，但全面纯度优势仍需独立标注验证。
```

#### 当前不能直接使用的证据

归一化后直接计算的 session 集合 Jaccard 不能单独作为领域纯度结论，因为：

- 原始 21 个候选簇本身允许多归属；
- LLM 合并后多个领域共享同一批 session；
- 一个完整 session 可能同时包含多个技术领域和多个行为阶段；
- 集合膨胀会让不同领域都与宽泛的切片簇产生较高重叠。

因此当前归一化对照报告主要用于发现成员污染和语义对应关系，不用于给出最终领域准确率。

### 19.4 规范流程

后续任何“原始 session vs 切片”的领域质量实验，必须保持以下流程对称：

```text
原始 session：
  数学候选簇 → 特征卡片 → LLM 归一化 → 成员与语义评估

切片：
  数学候选簇 → 特征卡片 → LLM 归一化 → 成员与语义评估
```

并且需要分别报告：

- 数学候选簇结果；
- LLM 归一化结果；
- primary 硬分配结果；
- overlap 多归属结果；
- session—slice 集合一致性；
- 人工标注或抽样审查结果。

不能把一个粒度的数学结果与另一个粒度的 LLM 结果直接比较。

### 19.5 这次失误的可迁移原则

这次问题不是算法参数问题，而是实验 treatment isolation 没有保持：输入粒度是一个变量，是否经过 LLM 归一化是另一个变量，早期实验同时改变了这两个变量。

以后做类似对照时，应先列出所有会影响结果的处理阶段，并保证对照组只改变一个实验变量：

```text
输入粒度：session vs slice
算法版本：相同
特征卡片协议：相同
LLM prompt：相同
LLM 归一化：两边都执行
成员回写：相同
评价指标：相同
```

如果某一侧暂时缺少某个阶段，必须把结果标记为“非对称探索性结果”，不能直接写成公平对照结论。

## 20. 当前最终定位

本实验目前支持的最稳妥定位是：

```text
原始 session 聚类
  = 完整轨迹 baseline

切片领域聚类
  = 局部领域边界发现

切片行为聚类
  = 跨领域工作模式发现

LLM 归一化
  = 对两种粒度进行语义合并、命名和混合簇识别

session—slice 关联
  = 检查完整轨迹与局部结果之间的一致性
```

切片的创新点不应只写成“把 session 切短后再聚类”，而应表述为：

> 在完整轨迹、局部领域片段和跨领域行为模式之间建立可回溯、可比较、可验证的多粒度轨迹组织方法。

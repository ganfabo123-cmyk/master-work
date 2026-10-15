# Skill 可行性实验：从数学模型重建到强标识分组与质量审查

记录日期：2026-10-13。本文按讨论先后记录，不推算具体发生时刻。

记录范围：从对原始轨迹、切片和领域提取结果产生疑问，重新建立数学模型，到少量标注、可识别信息、错误分组实验、双代理审查、通用策略入口、四类锚点实验，以及原始调用栈/配置修改/依赖变化组的逐组质量审查。

本阶段的目标是可行性验证。本文区分用户已明确的目标、讨论中的假设、已实现的实验、人工判断和仍未验证的结论，不把过程记录当作生产算法规范。

后续追加：四类简单策略已经实现并跑完，见第 15 节；三类原始组的质量审查已完成，最新结果见第 16 节。前文“尚未运行”描述的是讨论当时状态。

## 1. 为什么重新讨论问题

此前经历了切片、领域划分、目标/执行逻辑聚类、Skill 潜空间和多个版本的候选生成。用户逐步明确：最终需要可靠、可复用的经验；数量可以少，不能为了数量输出不可用 Skill。组可以混杂，也允许轨迹重叠归属，但应尽量保全同一经验的贡献证据。

三代理独立保守提取实验的保留记录为：

| 实验 | 输入口径 | 保留记录 |
|---|---|---:|
| A | 30 个 Session 对应的 117 个展开片段 | 6 |
| B | 97 个切片 | 7 |
| C | 8 个细领域，314 次重叠成员读取 | 7 |

这些是各代理输出的记录数，不是完整真实 Skill 数，也不是统一金标质量统计。用户因此质疑：经过长期切片与聚类，是否还不如直接让 LLM 阅读原始轨迹。

当时的讨论判断是：现有结果尚未证明聚类提升了单条 Skill 的质量；但海量场景仍不能让 LLM 逐条或完整分批处理所有原始轨迹。随后讨论不再停留于“原始还是聚类谁更好”，而开始明确分组到底应该保留什么。

**后来发现的重要输入区别：**早期 A 实验虽然称为“完整 Session”，实际读取的是 `context-expanded-sessions` 的文本/工具调用投影，并未保留完整工具结果正文。错误分组实验期间，用户补充了真正的原始文件，才直接读取工具输出。因此不能把早期 A 结果当作完整原始轨迹上的金标上限。

前期工作和独立提取结果见：

- [前期工作日志](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/behavior-clustering-worklog-2026-10-13.md)。
- [三代理独立保守提取汇总](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/skill-extraction-v3-independent-conservative/summary.md)。

## 2. 第一次数学建模：单条轨迹贡献一个 Skill

用户设原始轨迹集合为 $T$，理想情况下可提取的经验集合为 $S=\{s_1,\ldots,s_n\}$。最初每条轨迹取值为 $0$ 或 $j$：无贡献，或贡献于 Skill $s_j$。

设 $T_i$ 为所有能贡献于 Skill $s_i$ 的轨迹。理想的预提取组 $B_i$ 满足：

$$
T_i\subseteq B_i\subseteq T_i\cup T_0
$$

即同一 Skill 的贡献证据聚在一起，组中可以有无贡献的轨迹。

这一讨论明确了分组价值：LLM 可以围绕一项经验组合互补证据，减少不同经验的干扰。它也纠正了助手此前把方向主要转到“只挑少量轨迹阅读”的偏移。用户要解决的仍包括证据组织和划分，而不是仅靠筛选绕过这个问题。

严格模型的难点：没有贡献标签时，便宜特征不一定能识别跨语言、跨项目的共同经验；同样的工具序列也不代表同样的经验。

## 3. 第二次数学建模：多 Skill 贡献与允许噪声

用户将单条轨迹的贡献改为集合：

$$
C(t)\subseteq S
$$

$C(t)=\varnothing$ 表示没有可利用贡献；$C(t)=\{s_2,s_5\}$ 表示可以贡献两项经验。

定义：

$$
T_i=\{t:s_i\in C(t)\}
$$

对非空组 $B_i$，要求至少 $X\%$ 的成员贡献于 Skill $s_i$。记 $x=X/100$：

$$
\frac{|B_i\cap T_i|}{|B_i|}\geq x
$$

其余成员是“对 $s_i$ 无贡献”，仍可能贡献其他 Skill。一个轨迹可以同时属于多个组。

讨论中补充了证据充分性：高相关比例本身不足以保证能提取。如果问题、关键处理、验证被拆到不同组，每组都可能相关，但没有一个组拥有完整经验链。理想情况下，对 $s_i$ 至少有一个充分证据子集 $E_i\subseteq T_i$ 被包含在某个 $B_i$ 中。

这里的 $X$ 是组内贡献比例，不是模型自信度，也不是可用组占全部组的比例。当前实验尚未固定统一的 $X$，也没有所有轨迹的贡献金标。

## 4. 映射 F：先表示，再自动分组

用户提出：是否存在映射 $F$，将每条轨迹 $t$ 转换为向量空间中的点 $c_t$，自动寻找若干中心，使向量分组对应理想的 $B_i$。

$$
c_t=F(t)
$$

讨论确认这条路线在条件上成立：如果同一经验的贡献证据在表示中形成可识别结构，自动分组就有机会恢复相应的候选组。中心和中心数量可以由算法选择，但不会因为有了向量，就自动得到正确的 Skill 类。

用户进一步问：是否需要预设“每一维代表什么”，类似用某一维表示是否有毛、是否属于哺乳类。

回答区分了两种坐标：

- 人为可解释特征：事件、词项、操作、顺序等可观察信息的统计取值。
- 学习到的特征：组合多个输入信息的潜在坐标，不要求每一维有人工命名，更不要求一维对应一个 Skill。

一种讨论中的表示方式为：

$$
F(t)=W\phi(t)
$$

$\phi(t)$ 是便宜的原始特征，$W$ 是可以学习的变换。此处是学习思路，不是已训练的新模型。

核对现有 V5/V6 代码后确认：已有向量利用事件角色、前中后位置、稀有度、操作关系和顺序，再用 NMF 学习潜在因子。这些训练目标主要反映统计结构，没有直接收到“哪些证据共同贡献于可用 Skill”的监督。尤其部分所谓“问题→动作”关系实际来自早期词和中期操作的组合，不能直接当作因果关系。

本阶段没有修改或重训 V5/V6，也没有实现新的中心选择或度量学习。

## 5. 用户接受少量标注，但要求服务于大规模数据

用户明确允许标注，要求比例 $Y$ 尽可能小，例如标注 1000 个 vibecoding 场景，结果应能服务 10 万条原始轨迹。

讨论从完全无监督转向：用少量标注学习贡献关系，之后低成本应用到未标注数据。

拟议标注包括：具体经验、支持它的原文位置、哪些轨迹贡献同一经验、单轨迹的多重贡献。未知关系不能直接当作负例。

训练思路是让已确认相关的证据在表示中更接近，已确认不同的证据更容易区分。标注样本应覆盖不同项目和任务；“前 $Y\%$”应理解为预算限制，不宜机械取时间最早的一批。验证需要包含未见项目和未见经验，避免只记住已标注的 Skill 名。

**尚未证明 1% 标注足够。** 样本比例不是难度的唯一决定因素；输入是否保留有用信息、标签是否覆盖贡献关系、目标分布是否变化，都影响可行性。标注和训练目前均未启动。

## 6. 从“标多少”转向“需要什么信息”

用户提出：标注本质上是用标签对抗信息不确定性。若只统计 Read/Write/Test 流程，关键字已经足够；难点是 Skill 任务需要哪些信息，以及原始轨迹本身能提供多少。

讨论将经验链整理为：

$$
触发条件/问题\rightarrow诊断与决策\rightarrow具体处理\rightarrow结果与适用边界
$$

便宜处理可以提取错误文本、退出码、命令、文件变化、代码差异、助手解释、测试结果和用户反馈。困难主要在于关联是否成立：某个修改是否针对该问题，后面的通过是否验证该修改，先后发生是否足以支持因果解释。

这一讨论说明：仅给向量增加维度不一定减少不确定性。需要先保留真实观察，再检验这些观察之间的联系，不能把“后期事件”自动叫作有效验证。

## 7. 目标收敛：先提取特定、容易识别的经验

用户重新表述 Skill：从海量轨迹中提取可靠、可复用的经验。此前尝试用便宜算法通用地回收所有可利用知识，目标过大。可以先选择某类容易获取且能够抽象为经验的信息。

首先讨论了“同一检查失败→针对性处理→同一检查通过”的修复经验。但它仍涉及处理归因，因此继续寻找更容易确定主题的入口。

用户提出错误标识 $e_i$：若能低成本识别同类错误，就可以将相应处理过程组织成 $B_i$，供 LLM 提取针对该错误的经验。

错误的优势是：具体失败表现、相关对象或约束、后续处理入口、可比较的结果，以及部分系统自带的稳定错误码。它提供了比通用工具操作更明确的组织依据。

同时保留边界：同码不一定同根因；异常类型可能很宽；退出状态可能只是底层错误的包装；只有报错不等于拥有完整经验。

本阶段目标因此收敛为：**先验证错误标识能否形成值得消费的经验候选组，再考虑深化。** 不要求所有轨迹有用，也不要求每个错误组只输出一条 Skill。

## 8. 已实现：三种简单错误识别与分组策略

用户要求对最初 30 个轨迹和 97 个切片做最小实验，不引入复杂聚类算法。

实际流程：

```text
读取事件正文
→ 正则识别错误信息
→ 生成标准化分组键
→ 相同键直接归组
→ 保存成员、命中原文和来源
```

| 策略 | 规则 | 示例键 |
|---|---|---|
| native-code | 编号族/来源标识加原生码；另识别非普通退出状态 | `ms-linker:LNK1105`、`typescript:TS1484` |
| exception-type | 报错结构中的完整异常名称 | `exception:ModuleNotFoundError` |
| message-template | 规范化错误消息中的路径、位置、引号参数等 | `ModuleNotFoundError: No module named <arg>` |

原生码识别支持 TS、CS、LNK、NETSDK、部分 C/E 编号、符号码、SQLSTATE 等格式。没有预先列全具体错误码与 Skill 的对应词典，但确实预设了诊断格式的解析规则；不声称识别所有语言、工具或错误体系。

负数/十六进制退出状态按 32 位表示统一，例如 `-1073741571` 统一为 `0xC00000FD`。普通 0～255 的退出状态不直接作为这一类分组键。不能把这种数值归一化理解为已判定根因。

过滤元数据、工具调用代码正文、源码摘录和通过的负例测试；用户/助手的错误报告与实际工具输出分别标记。过滤并不完美，后续仍发现源码中的错误类型声明误报。

同一个 Session/切片允许进入多个错误组。没有 embedding、LLM 调用、中心搜索或容量控制，也没有自动修复成功判断。

### 8.1 输入恢复是本次实验的重要步骤

开始时发现：97 切片中的 `tool_result` 只有原始事件索引，没有正文；117 个展开片段也只有文本与调用。

用户随后提供原始目录 `C:/Users/35153/PycharmProjects/master-work/sessions`。

实验仅选择既有清单中的 30 个 Session：29 个 JSONL，1 个 OpenCode JSON。原始组直接读取这些文件；切片按 `source_index + source_part_index` 回填工具结果，仅统计 core 区间，避免边界重叠重复计数。

原始文件中仍有 59 个工具结果没有可读取正文，程序记录缺失，不推测其状态。

### 8.2 实验统计

| 策略 | 原始组数 | 原始命中成员 | 切片组数 | 切片命中成员 | 切片最大组 |
|---|---:|---:|---:|---:|---:|
| 错误码/退出状态 | 14 | 9/30 | 14 | 13/97 | 9 |
| 异常类型 | 28 | 14/30 | 28 | 22/97 | 5 |
| 标准消息模板 | 159 | 19/30 | 147 | 39/97 | 8 |

上述包括工具输出与文本报告。只统计有实际工具输出支持的错误键，两套输入均为 12、26、121 个。

三策略不能相加作为唯一错误数，更不能相加作为 Skill 数。同一底层问题可能同时出现在原生码、包装退出状态和异常类型组中。

### 8.3 已完成的程序验证

- 10 个识别与解析测试通过。
- 两次完整运行的 31 个自动生成文件逐字节一致。
- 检查当时三策略的 390 个分组、487 条成员归属，来源路径存在。
- 两套输入的 396 条去重后“策略—错误键—工具输出证据”记录完全对应。

396 是已检测证据的对应性，不是全部真实错误的召回率，也不能证明切片未损失任何 Skill。

## 9. 双 Luna 审查：范围调整与评审失误

用户要求两个独立 GPT-5.6 Luna：一个审原始组，一个审切片组。初始范围分别为 201 和 189 个组。

用户在审查中认为标准消息模板组太杂，明确停止该策略的代理审查。两个代理被中断并更新范围：每侧只审原生码 14 组、异常类型 28 组，共 42 组。消息模板产物保留，但不进入最终分母。

父代理检查初稿及复核稿时发现明显错配：

- 把 DLL 错误配到无关的指针修改。
- 把源码/docstring、README 中的 passing 当作实际验证。
- 把链接错误配到 AtomTable 栈溢出修复。
- 把删除失败探针后的构建成功当作原问题修复。

这些案例被退回更正，初稿保留供审计。审查过程揭示：脚本整理证据可以减少读取负担，但“附近有 fix/pass”不能替代内容关联判断。

最终两份 JSON 都覆盖各自 42 个输入组，组 ID 无重复无遗漏，声明的成员 ID 与输入一致；原始侧 222 条、切片侧 334 条来源引用的文件存在。

**这些结构核验不等于全部语义判断正确。** 两代理对 Skill 可用性的意见仍明显不同；完整 Session 包含对应切片证据，因此不能凭“切片判可用、原始判不可用”的审查差异，直接断言切片更好。最终自动审查标签尚未形成可信金标。

## 10. 后续人工核对：已有值得消费的具体组

用户随后询问原始与切片、原生码与异常类型的比较，以及是否存在符合贡献比例模型的组。父代理回到原始文件检查具体处理过程。

### 10.1 LNK1105：最明确的多成员候选

原始组包含 5 个 Session，切片组包含 9 个切片。按“有明确针对文件占用的处置”作保守贡献判断：至少 4/5 个原始成员、7/9 个切片成员可以贡献该经验。其余成员中还存在同类错误和诊断线索，没有因此判为独立成功案例。

核对到两个不同项目中的完整链：

| 来源 | 关键原始事件索引（零基） | 证据 |
|---|---|---|
| Yggdrasil，Session `39082932-131c-40a9-872d-1d3ac8ed1fd6` | 966→967→968→969 | 报错、运行进程占用解释、停止进程并重建、链接输出 `Built` |
| FrostCore，Session `6a7964ed-6f92-4eee-ae5e-3f91a6445833` | 575→576→577→580 | 报错、文件占用解释、终止测试进程并重建、实际测试输出 135/0 与 101/0 |

因此该组可以送入 LLM 总结有条件的文件占用诊断/释放/重建经验。部分成员的终止或查找占用尝试没有解决问题，可以贡献失败边界，不应编造成成功案例。

### 10.2 其他核对到的提取入口

| 错误组 | 具体经验与证据线索 |
|---|---|
| `0xC00000FD` | 大型结构按值复制导致栈溢出；Session `479c5e9f...` 的 324 定位局部拷贝，333 实际全套输出，334 汇总 10/10 套件、144/144 测试通过 |
| `LNK1107` | Windows 外部库链接涉及 `.lib`、DLL 与目标兼容性；Session `4222016d...` 的 253～284 有具体处理，288 有 bridge smoke test 输出 |
| `LNK2019` | 全局符号定义位于未参与测试链接的 `main.cpp`；Session `c99032e9...` 的 975～984 有报错、定义位置分析、inline 定义修改与后续运行；之后的栈错误是另一个问题，不能要求它抹掉链接修复证据 |
| `TS1484` | type-only import 修改；Session `4130c9a7...` 的 217 报错、218/221 修改、254～256 重新类型检查及结果 |
| `ECONNRESET` | Android WebView 调试连接失败后的进程/转发重建与重试；Session `da5d32d6...` 的 686 失败、688 解释、689 重试、690 `connected:true` 与截图保存 |

这些是提取入口与来源证据，尚未成为本轮正式生成并验收的 Skill 文件。

### 10.3 6/14、约 43% 的正确含义

用户澄清：问的是“原始轨迹 × 错误码”这个实验的可用组占比，不是某个组内的成员贡献比例。

讨论中给出的保守判断是：上述六个错误组已找到具体处理与验证线索，至少 6/14（约 43%）值得送去提取。它与 $X$ 的分母不同：

- $X$：某个组内贡献于一项经验的成员比例。
- 6/14：选定实验中已人工确认提取入口的组数占比。

**43% 不是从 Luna 标签统计得到的正式可用率，不是完整 14 组的统一验收结果，不是 Skill 精确率，也不是六个已经验收的 Skill。** 包装错误码有语义重复，剩余组也没有全部被证明无用。论文中只能把它写作当前人工核对的保守可行性观察，不能作为最终指标。

## 11. 从错误扩展到天然强标识信息

用户希望寻找像“巴巴罗萨计划”一样，一出现就能明确定位主题的标识，而不是笼统说任务目标、配置变化等信息。

讨论过 API、协议字段、环境变量、具体命令等标识，例如 `std::unique_ptr`、`Alpine.initTree`、`PYTHONIOENCODING`。用户指出：如果要提前填写这些词，仍然需要词典。

随后转向“结构中天然有类型的名字”：

- 测试报告中的套件/测试名。
- 调用栈中的模块/类/函数名。
- 依赖清单中的包名和版本。
- 结构化调用中的接口与操作名。
- 配置修改中的完整配置键。

区别是：预设解析格式，从实际数据收集名字；不预设哪些具体名字属于哪些领域。强身份标识仍不等于共同 Skill，项目私有测试、通用函数名和包装框架均可能造成过碎或过宽。

目前用户重点选择测试用例和调用栈继续讨论，尚未实现实验。

## 12. 已拟定、尚未运行：四种测试/调用栈分组策略

| 策略 | 自动提取的分组键 | 主要用途与边界 |
|---|---|---|
| T1 完整测试身份 | 项目标识＋测试文件/类＋用例名 | 同项目跨 Session 聚合同一行为；防止不同项目同名测试误并 |
| T2 断言对象与条件 | 可确认归属的完整符号＋比较操作＋预期条件 | 名称不同但检查对象/条件相同的测试；必须保留比较方向、类型和有意义常量 |
| S1 异常抛出位置 | 异常类型＋模块/类＋抛出函数 | 比异常名称更具体；抛出点不保证是根因 |
| S2 相邻调用关系 | 异常类型＋调用者→被调用者，或三相邻帧 | 聚合同一调用边界；通用框架组合不能单独作为强依据 |

拟议公共规则：

1. 优先使用真实失败、测试新增/修改、明确点名执行的测试。全套输出中的顺带 PASS 作为验证材料，不自动给会话挂所有测试主题。
2. 区分实际失败、预期异常和文本提及。
3. 不把不同测试、不同目标的后续通过自动配给当前问题。
4. 栈顺序按语言格式归一；行号与绝对工作区路径用于回溯，不直接决定同组关系；保留符号归属，避免仅凭 `run/execute` 之类通用名字跨项目合并。
5. 每次测试/异常事件先形成可回溯记录，再将 Session 或切片关联到组；允许重叠。
6. 四策略分别试验，不先引入复杂向量或未经验证的综合分数。

尚未确认现有 30/97 输入能解析出多少这些结构，也没有 T1/T2/S1/S2 的脚本、产物、覆盖率或 Skill 提取结果。

字段来源与解析讨论参考：[JUnit 报告](https://docs.junit.org/5.13.1/user-guide/index.html)、[Playwright 报告](https://playwright.dev/docs/test-reporters)、[Python 栈帧](https://docs.python.org/3/library/traceback.html)、[Java 栈帧](https://docs.oracle.com/en/java/javase/26/docs/api/java.base/java/lang/StackTraceElement.html)。这些用于说明可提取字段，不证明本项目的分组效果。

## 13. 本周可行性阶段的状态

当前已确认的方向是：先围绕低成本、天然强标识的信息组织候选证据，接受利用率有限，检验是否能持续提取可靠可复用经验。

| 工作 | 当前状态 |
|---|---|
| 多贡献、允许噪声、允许重叠的数学模型 | 已讨论明确，贡献标签未建立 |
| 少量标注学习 F | 接受作为可行路线，未标注、未训练 |
| 原始 30/切片 97 的错误分组 | 已实现、运行、测试与归档 |
| 错误组质量审查 | 已形成两个 Luna 报告；仍有语义评审局限 |
| 具体错误组的人工原文核对 | 已确认部分值得消费的证据集合 |
| 基于这些错误组正式生成并验收 Skill | 尚未开展 |
| 深化错误识别和修复关系 | 可以继续研究，尚无本轮新实现 |
| 测试用例与调用栈分组 | 后续已运行 T1/S1 的简单实现，见第 15 节；T2/S2 仍停留在设计 |
| 通用策略入口与配置/依赖分组 | 已实现并归档四类实验，见第 15 节 |
| 原始调用栈/配置/依赖组的质量审查 | 已人工核对全部 68 组，24 组有可提取经验，见第 16 节；尚未生成 Skill 正文 |

后续可以做的小实验是：对选定错误组正式提取并检查 Skill，或对现有输入试跑测试/调用栈分组。当前用户指令是记录过程，本文不将这些讨论自动升级为实现任务。

可行性判断应围绕实际经验与证据：分组是否关联具体问题，充分证据是否在组内，可执行经验是否产生，适用边界是否合理。中心数量、相似度、错误命中数和通用成功词都不能替代这些检查。

## 14. 产物与复现入口

仓库实际目录：`C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering`。

原始目录：`C:/Users/35153/PycharmProjects/master-work/sessions`。

切片目录：`C:/Users/35153/PycharmProjects/master-work/vibecoding-trace-data-bundle/dynatic-split-session-test/calibrated-confidence-length-banded-v3-slices`。

| 内容 | 路径入口 |
|---|---|
| 错误识别与直接分组脚本 | [error_clustering_experiment.py](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error_clustering_experiment.py) |
| 识别/解析测试（初期错误实验 10 项，四类实验扩展到 25 项） | [test_error_clustering_experiment.py](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/test_error_clustering_experiment.py) |
| 实验命令与产物说明 | [README.md](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/README.md) |
| 实际参数和筛选规则 | [manifest.json](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/manifest.json) |
| 六组实验统计 | [summary.json](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/summary.json) |
| 原始错误码组 | [sessions-30/native-code/groups.json](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/sessions-30/native-code/groups.json) |
| 原始异常类型组 | [sessions-30/exception-type/groups.json](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/sessions-30/exception-type/groups.json) |
| 切片错误码组 | [slices-97/native-code/groups.json](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/slices-97/native-code/groups.json) |
| 切片异常类型组 | [slices-97/exception-type/groups.json](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/slices-97/exception-type/groups.json) |
| 程序验证 | [validation.json](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/validation.json) |
| 初期实验抽查 | [assessment.md](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/assessment.md) |
| 原始组 Luna 审查 | [audit-sessions-luna/report.md](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/audit-sessions-luna/report.md) |
| 切片组 Luna 审查 | [audit-slices-luna/report.md](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/audit-slices-luna/report.md) |
| 审查过程与局限汇总 | [audit-summary.md](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/audit-summary.md) |
| 审查结构核验 | [audit-validation.json](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error-clustering-v1/audit-validation.json) |

每种策略目录中的 `groups.json` 保存全部成员和证据；`report.md` 提供可读展示；`residual.json` 保存该策略未命中的成员。`occurrences.jsonl` 和 `input-units.json` 位于各输入目录下。两个审查目录也保存逐组 `audit.json`、完整 `prompt.md` 及初稿。

标准消息模板的两个目录仍保留在 `error-clustering-v1/sessions-30/message-template/` 与 `slices-97/message-template/`，但用户已经停止其代理审查，不作为当前重点。

从脚本所在目录复现已有错误实验：

```powershell
python error_clustering_experiment.py `
  --expanded-sessions-dir C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\context-expanded-sessions `
  --slices-dir C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-slices `
  --raw-sessions-root C:\Users\35153\PycharmProjects\master-work\sessions `
  --output error-clustering-v1
```

此命令重新生成三策略本地分组，不会调用 Luna，也不代表恢复已经取消的消息模板审查；`--output` 指向已有目录时会重写分组产物。对照实验应选择新的输出目录。

本次文档整理仅新增此文件；没有更改算法、重跑实验或执行 Git 提交/推送。

## 15. 后续执行：四类锚点策略的首次运行

在四类实验前，用户先要求把错误脚本升级为通用策略分组入口：后续新增策略时，在同一个程序增加函数并注册，用参数选择，不另外新写脚本。实现保留 `error_clustering_experiment.py` 历史名称，策略接收整条输入单元，公共流程负责扫描、来源回溯、分组和输出；`--strategies` 选择策略，`--list-strategies` 列出注册项，默认仍兼容原三种错误策略。经用户明确授权，脚本、测试、使用说明三个文件提交为 `bdde10d`（`Add extensible strategy grouping entry point`）。该提交是通用入口恢复点，不包含后来追加的四类策略与实验产物。

使用说明：[strategy-grouping.md](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/strategy-grouping.md)。

用户随后要求：“四个都跑一手，结果归档记录，记录完停”。在同一个通用程序中追加 `test-case`、`stack-site`、`config-change`、`dependency-change`，直接按各自锚点键分组，没有另起实验脚本。

原始 30 个 Session 和 97 个切片都已完成四类处理：

| 策略 | 原始组数 | 切片组数 | 原始命中成员 | 切片命中成员 |
|---|---:|---:|---:|---:|
| 测试用例 | 216 | 216 | 6/30 | 10/97 |
| 调用栈 | 19 | 19 | 8/30 | 11/97 |
| 配置修改 | 26 | 26 | 3/30 | 3/97 |
| 依赖变化 | 23 | 23 | 5/30 | 6/97 |

原始侧全部是单 Session 组，切片侧仅一个测试组有同一 Session 的两个切片；四类没有形成跨 Session 多成员组。目前只验证天然标识提取与可回溯分组，不声称得到共同 Skill。

测试 231 次命中中，207 次为具名测试定义改动，24 次为具名失败。依赖 23 条中，18 条旧版本未知、3 条明确版本变化、2 条新增记录；切片其中一条新增只证明局部片段声明变化。组数不能当作失败数、版本升级数或 Skill 数。

记录入口：[四类实验记录](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/strategy-grouping-four-anchors-v1/experiment-record.md)。

统计入口：[summary.json](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/strategy-grouping-four-anchors-v1/summary.json)。

验证入口：[validation.json](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/strategy-grouping-four-anchors-v1/validation.json)。

归档内保存两侧四类的成员、事件证据、residual、报告，以及通用脚本和测试的源代码快照/SHA-256。25 项测试通过，39 个自动文件复跑一致，568 个组与 569 条成员归属完成结构核验。未进行 LLM 审查、Skill 提取或后续优化；按用户要求记录完成后停止。

## 16. 后续审查：原始调用栈、配置修改、依赖变化组

用户随后指定：“只看调用栈、配置修改、依赖变化这几组，审查可提取 Skill 组/总组占比，就看原始组数”。本次只审查 `sessions-30` 下这三个策略的全部 68 组，没有审查测试组或切片组。由父代理直接核对原始 JSONL，没有派发新子代理，没有重跑分组，没有修改算法。

### 16.1 审查过程和判定口径

按每组锚点追溯原始 Session，阅读相关诊断、修改/执行操作和实际工具输出。计入可提取组的要求是：能形成与该锚点相关的具体、可迁移经验，并有对应实施与相关验证证据。单 Session 可以支持经验，不要求两个独立 Session。

只有声明、伴随改动、通用缺包安装、未经验证的诊断，或单纯关闭检查，不计入本次分子。某个阶段验证通过可以支持限定范围的经验，不等于整个工程成功。例如：

- CP1252 编码修复后输出恢复，但仍有 Tkinter 线程清理错误；只计输出编码经验。
- F-Droid 在提前 checkout 后越过 `SOURCE_DATE_EPOCH=None` 的失败点，但仍有后续构建问题；不计作完整发布成功。
- 生成文件定向排除后 lint 通过，但 bundler 仍失败；只计 lint 与生成文件职责边界经验。
- Pseudo-OS 修改 `module/moduleResolution` 后只有 esbuild 成功记录，没有原 TypeScript 问题的对应检查；这两组保留为候选，不计入可提取分子。

### 16.2 结果与具体经验入口

| 原始策略 | 可提取组 | 总组 | 占比 |
|---|---:|---:|---:|
| 调用栈 | 12 | 19 | 63.2% |
| 配置修改 | 3 | 26 | 11.5% |
| 依赖变化 | 9 | 23 | 39.1% |
| 合计 | 24 | 68 | 35.3% |

调用栈中核对到的入口包括 dataclass 继承字段与 keyword-only 构造、错误解释器定位、损坏的 pipx 环境重建、Svelte SCSS 预处理、Groovy/ASM 与 JDK 兼容、PropertyLens 初始化顺序，以及 WebView 调试端点就绪检测。

配置组中，Solid 的 `jsx`/`jsxImportSource` 配套与生成文件 lint 排除有可提取依据。其余多数是项目重建的伴随变更、模板字段或检查规则删除。IceBerg 删除旧工程后重建 Solid 工程，算法保存的旧 tsconfig 历史快照不一定是新文件的即时前态；不能把每个字段差异解释成一次独立修复。

依赖组中，可提取入口包括 JDK 升级时分析工具链配套、JUnit launcher 补齐、Android inset 处理、WebView 本地资源装配、非交互式 Solid/Vite 初始化。多数其他组仅记录初始声明；后端依赖安装完成或前端类型检查通过，不能替代相应后端功能验证。

### 16.3 指标边界与归档

**24 是可提取组数，不是 24 个不同 Skill，也不是已生成并验收的 Skill 数。** 同一经验可支持多个锚点组，例如 Solid 初始化同时支持两个配置组和三个依赖组，JDK 配套更新支持三个依赖组。此次没有去重统计不同 Skill 数量，也没有实际产出 Skill 正文。

68 组全部只有一个原始 Session，因此不能据此判断跨 Session 共性，不能把单成员组的表面纯度当成贡献比例模型验证，更不能推导 Skill 损失率。与第 10 节错误码的 6/14 观察也不能直接作为公平优劣排名：锚点类型、分组粒度和审查覆盖范围不同。

本次观察是：调用栈在当前样本中更容易提供故障位置、处理和验证的完整线索；配置 diff 与依赖声明本身的信息较薄，需要原始上下文才能判断是否承载具体经验。这是本轮人工审查结论，尚未证明对其他数据集成立。

完整逐组审查、组 ID、理由、适用范围与原始事件索引：[audit-original-three-anchors-v1.md](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/strategy-grouping-four-anchors-v1/audit-original-three-anchors-v1.md)。原始索引采用零基 JSONL 行索引，查看文件对应第 `索引 + 1` 行。

分组输入入口：

- [原始调用栈组](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/strategy-grouping-four-anchors-v1/sessions-30/stack-site/groups.json)。
- [原始配置修改组](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/strategy-grouping-four-anchors-v1/sessions-30/config-change/groups.json)。
- [原始依赖变化组](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/strategy-grouping-four-anchors-v1/sessions-30/dependency-change/groups.json)。

审查记录已核对全部 68 个组 ID、原始来源文件存在性和分子/分母统计。本次工作过程更新只修改本文；核对文档链接、统计与审查报告一致，没有运行算法、测试、模型调用或 Git 提交/推送。

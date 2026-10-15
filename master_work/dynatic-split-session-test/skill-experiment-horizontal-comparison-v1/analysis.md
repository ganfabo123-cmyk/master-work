# Skill 实验横向比较报告
本报告逐条审查实验 A/B/C 的全部原始 Skill 记录：A 25 条、B 48 条、C（D001–D008）181 条，共 254 条。只分析已有 JSON，不修改代码，不调用 embedding。
## 统一质量标准
- `high_value`：证据具体、解决链清楚、可迁移。
- `usable_narrow`：有真实价值但适用范围较窄或证据不完整。
- `generic_or_weak`：主要是泛化流程、工具顺序或项目特例。
- `unsupported`：来源证据不足或无法复核。

单个 Session 或单个切片可以独立形成 Skill，不因来源数量少自动降级。本报告中，若导出记录的 `source.key_evidence` 为空，则判为 `unsupported`，因为当前记录无法复核具体轨迹；这与“来源数量少”是两个独立判断。
## 统计总表
| 实验 | raw | high_value | usable_narrow | generic_or_weak | unsupported | 去重家族 | 输入 rejected/weak |
|---|---:|---:|---:|---:|---:|---:|---:|
| A：原始 30 条 Session 直接提取 | 25 | 18 (72.0%) | 7 (28.0%) | 0 (0.0%) | 0 (0.0%) | 25 | 8 |
| B：97 个切片直接提取 | 48 | 31 (64.6%) | 14 (29.2%) | 2 (4.2%) | 1 (2.1%) | 48 | 2 |
| C：8 个细领域独立提取 | 181 | 111 (61.3%) | 43 (23.8%) | 7 (3.9%) | 20 (11.1%) | 46 | 189 |

`rejected/weak` 是各输入实验单独列出的未入 `skills` 的候选，不并入 raw 质量分母。C 的 189 条是 D001–D008 的候选拒绝数之和，也反映了领域间重复读取带来的候选规模。
## 输入与覆盖
- A 读取 30 个 Session、118 个切片文件；导出 25 条 Skill，覆盖去重后 18 个 Session。
- B 读取 97 个切片、30 个 Session；导出 48 条 Skill，覆盖 41 个切片、23 个 Session。
- C 的 8 个领域合计导出 181 条 Skill、46 个语义家族；领域摘要报告的切片覆盖并集为 38，跨领域求和为 125，Session 覆盖并集为 21、求和为 83。这说明 C 的领域输入有重叠，不能把 181 条当成 181 个独立 Skill。
## 横向结论与重复关系
A 与 B 共享 25 个家族，A 没有 B 独有家族；B 与 C 共享 46 个家族，B 有 2 个家族未在 C 出现（字段语义追溯、阈值批处理终止条件）。C 的 181 条记录折合 46 个家族，raw/家族比为 3.93，属于明显的重复与拆散。
C 中重复最多的家族如下：

| 家族 | 标题 | C 记录数 |
|---|---|---:|
| S10 | 用户指出本地字体后先检查资产和编译路径 | 7 |
| S44 | 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 | 7 |
| S01 | 把多阶段需求转成明确的本轮范围与排除项 | 6 |
| S11 | 用新数组引用触发响应式系统更新 | 6 |
| S12 | 让窗口打开和进程清理具备幂等生命周期 | 6 |
| S04 | 用阶段专属测试套件证明阶段完成后再更新文档 | 5 |
| S06 | 把可嵌入库与 CLI 分离并提供窄的纯 C ABI | 5 |
| S07 | 让头文件、实现文件和构建目标的边界可检查 | 5 |
| S08 | 用对象大小和拷贝路径定位启动期栈溢出 | 5 |
| S09 | 用路由事实和请求生命周期排查前端 404 | 5 |

A 的优势是证据完整且家族较稳定，缺点是粒度较粗、召回较窄。B 同时保留 A 的 25 个家族并新增 23 个家族；48 条中 47 条有非空证据，粒度、覆盖和可复核性最均衡。C 对领域内发现单来源 Skill 很有帮助，但同一家族在多个 D 域反复生成，且有 20 条空证据记录；它更适合做候选召回和反例审查，入库前必须跨域去重并复核 evidence。
## 推荐
B（97 个切片直接提取）最适合作为下一轮默认提取输入；它在不引入 C 的跨领域重复的前提下，把 A 的 25 个家族保留下来并扩展到 48 个家族，且 47/48 条记录有可定位 evidence。C 适合做领域召回和单来源发现，但必须先做跨域去重与空 evidence 复核；A 适合做高层稳定 Skill 基线，覆盖窄且容易漏掉切片内新增能力。
## 代表性实例
### A
代表性较高：

- `S08`（用对象大小和拷贝路径定位启动期栈溢出），high_value，来源 `479c5e9f-a299-457f-8459-5948adf8aa8e`；有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。
- `S23`（外发轨迹前做公开性核验、脱敏复查和信任边界停机），high_value，来源 `2965219c-42ad-45af-889c-4581ecbe0103`；有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。
- `S25`（状态型解释器先建立状态再按要求的顺序执行），high_value，来源 `07b57159-218e-4330-a64e-0ec4b4355056`；有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。

代表性较低：

- `S10`（用户指出本地字体后先检查资产和编译路径），usable_narrow，来源 `09d9abe9-0a02-4bd1-8129-3b864695079d`；有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。
- `S11`（用新数组引用触发 Alpine 等响应式系统更新），usable_narrow，来源 `09d9abe9-0a02-4bd1-8129-3b864695079d`；有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。
- `S21`（清理工程时只删除可证明的派生物并同步构建入口），usable_narrow，来源 `4222016d-1932-4abb-94b3-463203bd8876`；有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。

### B
代表性较高：

- `S28`（先解除测试前置阻塞再判断功能级失败），high_value，来源 `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8/segment-01.json`；有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。
- `S33`（先读取外部 API 的真实 payload 再建模和渲染），high_value，来源 `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-03.json`；有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。
- `S43`（用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求），high_value，来源 `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json`；有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。

代表性较低：

- `S15`（迁移低级启动/显示路径时以运行时事实校验协议兼容性），unsupported，来源 `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358/segment-02.json`；source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。
- `S35`（对第三方移动应用采用构建门槛、静态扫描、真机行为和清理闭环），generic_or_weak，来源 `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-09.json`；有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。
- `S42`（固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间），generic_or_weak，来源 `claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f/segment-01.json`；有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。

### C
代表性较高：

- `D004-001`（用路由事实和请求生命周期排查前端 404），high_value，来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`；有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。
- `D008-011`（修改本地化源文件时保持格式并只重新生成派生消息），high_value，来源 `segments__claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b__segment-02`；有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。
- `D001-001`（把多阶段需求转成明确的本轮范围与排除项），high_value，来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`；有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。

代表性较低：

- `D003-009`（迁移低级启动/显示路径时以运行时事实校验协议兼容性），unsupported，来源 `segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-04`；source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。
- `D004-013`（固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间），generic_or_weak，来源 `segments__claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f__segment-01`；有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。
- `D001-011`（用新数组引用触发响应式系统更新），unsupported，来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`；source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。

## 逐条审查索引
下表覆盖全部 254 条 raw Skill 记录。`source` 是首个来源切片或 Session；完整来源列表、证据摘录和判级理由见同目录 `analysis.json`。

| 组 | 域 | skill_id | 家族 | 标题 | 类别 | 来源数 | evidence | 判断理由 |
|---|---|---|---|---|---|---:|---|---|
| A |  | `S01` | S01 | 把多阶段需求转成明确的本轮范围与排除项 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `07b57159-218e-4330-a64e-0ec4b4355056`。|
| A |  | `S02` | S02 | 在训练数据切分前保留对话角色和来源元数据 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a`。|
| A |  | `S03` | S03 | 按硬件能力选择精度并用梯度累积保留上下文长度 | `usable_narrow` | 0 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a`。|
| A |  | `S04` | S04 | 用阶段专属测试套件证明阶段完成后再更新文档 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `39082932-131c-40a9-872d-1d3ac8ed1fd6`。|
| A |  | `S05` | S05 | 用语法审计和多版本矩阵实现兼容性 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `07b57159-218e-4330-a64e-0ec4b4355056`。|
| A |  | `S06` | S06 | 把可嵌入库与 CLI 分离并提供窄的纯 C ABI | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `92833a43-c30d-4b44-8447-c32ee17d6e6e`。|
| A |  | `S07` | S07 | 让头文件、实现文件和构建目标的边界可检查 | `usable_narrow` | 0 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `39082932-131c-40a9-872d-1d3ac8ed1fd6`。|
| A |  | `S08` | S08 | 用对象大小和拷贝路径定位启动期栈溢出 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `479c5e9f-a299-457f-8459-5948adf8aa8e`。|
| A |  | `S09` | S09 | 用路由事实和请求生命周期排查前端 404 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `c84c0ad3-c368-40df-87b1-5ef9effe237a`。|
| A |  | `S10` | S10 | 用户指出本地字体后先检查资产和编译路径 | `usable_narrow` | 0 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `09d9abe9-0a02-4bd1-8129-3b864695079d`。|
| A |  | `S11` | S11 | 用新数组引用触发 Alpine 等响应式系统更新 | `usable_narrow` | 0 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `09d9abe9-0a02-4bd1-8129-3b864695079d`。|
| A |  | `S12` | S12 | 让窗口打开和进程清理具备幂等生命周期 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `09d9abe9-0a02-4bd1-8129-3b864695079d`。|
| A |  | `S13` | S13 | 用同源代理消除前端运行时后端地址分歧 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `c84c0ad3-c368-40df-87b1-5ef9effe237a`。|
| A |  | `S14` | S14 | 把多分辨率界面布局变成运行时几何而非编译期常量 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `4222016d-1932-4abb-94b3-463203bd8876`。|
| A |  | `S15` | S15 | 迁移低级启动/显示路径时以运行时事实校验协议兼容性 | `usable_narrow` | 0 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `17c2cf98-e64a-43c6-932e-fa7efcade358`。|
| A |  | `S16` | S16 | 用已知工作实现对照并缩小退出崩溃的最小路径 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `f93127ef-dec9-4d58-964b-ee660964ec4d`。|
| A |  | `S17` | S17 | 从参考源解析资源并用结构性计数验证结果 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `07b57159-218e-4330-a64e-0ec4b4355056`。|
| A |  | `S18` | S18 | 对高影响操作实施分层开关、精确确认和公开警告 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `07b57159-218e-4330-a64e-0ec4b4355056`。|
| A |  | `S19` | S19 | 把不同部署/政策要求隔离为独立实现并保留切换边界 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `07b57159-218e-4330-a64e-0ec4b4355056`。|
| A |  | `S20` | S20 | 敏感配置采用加密存储、分离盐和可验证的初始化流程 | `usable_narrow` | 0 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `07b57159-218e-4330-a64e-0ec4b4355056`。|
| A |  | `S21` | S21 | 清理工程时只删除可证明的派生物并同步构建入口 | `usable_narrow` | 0 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `4222016d-1932-4abb-94b3-463203bd8876`。|
| A |  | `S22` | S22 | 构建后恢复派生文件并保持 PR 只含意图变更 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `2965219c-42ad-45af-889c-4581ecbe0103`。|
| A |  | `S23` | S23 | 外发轨迹前做公开性核验、脱敏复查和信任边界停机 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `2965219c-42ad-45af-889c-4581ecbe0103`。|
| A |  | `S24` | S24 | 从配置和迁移代码追溯字段语义再解释数据 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `comparia-voting-fields-anon`。|
| A |  | `S25` | S25 | 状态型解释器先建立状态再按要求的顺序执行 | `high_value` | 0 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `07b57159-218e-4330-a64e-0ec4b4355056`。|
| B |  | `S01` | S01 | 把多阶段需求转成明确的本轮范围与排除项 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json`。|
| B |  | `S02` | S02 | 在训练数据切分前保留对话角色和来源元数据 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-01.json`。|
| B |  | `S03` | S03 | 按硬件能力选择精度并用梯度累积保留上下文长度 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-02.json`。|
| B |  | `S04` | S04 | 用阶段专属测试套件证明阶段完成后再更新文档 | `high_value` | 3 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6/segment-04.json`。|
| B |  | `S05` | S05 | 用语法审计和多版本矩阵实现兼容性 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json`。|
| B |  | `S06` | S06 | 把可嵌入库与 CLI 分离并提供窄的纯 C ABI | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json`。|
| B |  | `S07` | S07 | 让头文件、实现文件和构建目标的边界可检查 | `usable_narrow` | 2 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6/segment-01.json`。|
| B |  | `S08` | S08 | 用对象大小和拷贝路径定位启动期栈溢出 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json`。|
| B |  | `S09` | S09 | 用路由事实和请求生命周期排查前端 404 | `high_value` | 3 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json`。|
| B |  | `S10` | S10 | 用户指出本地字体后先检查资产和编译路径 | `usable_narrow` | 2 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-01.json`。|
| B |  | `S11` | S11 | 用新数组引用触发响应式系统更新 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-05.json`。|
| B |  | `S12` | S12 | 让窗口打开和进程清理具备幂等生命周期 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-05.json`。|
| B |  | `S13` | S13 | 用同源代理消除前端运行时后端地址分歧 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json`。|
| B |  | `S14` | S14 | 把多分辨率界面布局变成运行时几何而非编译期常量 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-02.json`。|
| B |  | `S15` | S15 | 迁移低级启动/显示路径时以运行时事实校验协议兼容性 | `unsupported` | 2 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358/segment-02.json`。|
| B |  | `S16` | S16 | 用已知工作实现对照并缩小退出崩溃的最小路径 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json`。|
| B |  | `S17` | S17 | 从参考源解析资源并用结构性计数验证结果 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json`。|
| B |  | `S18` | S18 | 对高影响操作实施分层开关、精确确认和公开警告 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json`。|
| B |  | `S19` | S19 | 把不同部署/政策要求隔离为独立实现并保留切换边界 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json`。|
| B |  | `S20` | S20 | 敏感配置采用加密存储、分离盐和可验证初始化 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-03.json`。|
| B |  | `S21` | S21 | 清理工程时只删除可证明的派生物并同步构建入口 | `usable_narrow` | 2 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json`。|
| B |  | `S22` | S22 | 构建后恢复派生文件并保持 PR 只含意图变更 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json`。|
| B |  | `S23` | S23 | 外发轨迹前做公开性核验、脱敏复查和信任边界停机 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json`。|
| B |  | `S24` | S24 | 从配置和迁移代码追溯字段语义再解释数据 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__comparia-voting-fields-anon/segment-01.json`。|
| B |  | `S25` | S25 | 状态型解释器先建立状态再按要求顺序执行 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json`。|
| B |  | `S26` | S26 | 按阶段建立提取边界并以不变量约束低级运行时 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833/segment-01.json`。|
| B |  | `S27` | S27 | 用索引调试过程中的数据结构不变量和旧二进制隔离 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json`。|
| B |  | `S28` | S28 | 先解除测试前置阻塞再判断功能级失败 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8/segment-01.json`。|
| B |  | `S29` | S29 | 把跨写入和查询的类型转换集中到单一绑定点 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8/segment-01.json`。|
| B |  | `S30` | S30 | 跨 C 后端与 JS 用户态时先复用现有能力再新增绑定 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-01.json`。|
| B |  | `S31` | S31 | 用权限边界和已知程序定位用户态退出故障 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json`。|
| B |  | `S32` | S32 | Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json`。|
| B |  | `S33` | S33 | 先读取外部 API 的真实 payload 再建模和渲染 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-03.json`。|
| B |  | `S34` | S34 | 用游标和 IntersectionObserver 实现可恢复的分页加载 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-03.json`。|
| B |  | `S35` | S35 | 对第三方移动应用采用构建门槛、静态扫描、真机行为和清理闭环 | `generic_or_weak` | 1 | present | 有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。 来源 `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-09.json`。|
| B |  | `S36` | S36 | 审查 APK 前先验证发布物身份与包类型 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-10.json`。|
| B |  | `S37` | S37 | 把持续集成失败拆成 schema 门槛和构建工具链分别修复 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-10.json`。|
| B |  | `S38` | S38 | 遵循仓库既有元数据约定，避免为单个条目过度引入新 schema | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json`。|
| B |  | `S39` | S39 | 修改本地化源文件时保持格式并只重新生成派生消息 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b/segment-01.json`。|
| B |  | `S40` | S40 | 安装外部 Skill 前先识别其实际形态 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__da6566ff-0116-4424-bb59-660623f9eb31/segment-01.json`。|
| B |  | `S41` | S41 | 静态部署项目先核对构建输出目录和托管根目录 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__11ef2190-67e2-4707-8212-ab12ebffdbc2/segment-01.json`。|
| B |  | `S42` | S42 | 固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间 | `generic_or_weak` | 1 | present | 有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。 来源 `claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f/segment-01.json`。|
| B |  | `S43` | S43 | 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json`。|
| B |  | `S44` | S44 | 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-01.json`。|
| B |  | `S45` | S45 | 把固定资源约束写成可检查的不变量并将大型工作区移出栈 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd/segment-02.json`。|
| B |  | `S46` | S46 | 解释内核最小系统时先分清 kernel、PID 1 和 userspace 责任 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632/segment-01.json`。|
| B |  | `S47` | S47 | 对阈值型批处理在下一次抓取前检查终止条件 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `claude_code__674e0f5c-c481-4830-b2ef-3e1e069a2b7f/segment-01.json`。|
| B |  | `S48` | S48 | 把数据驱动的内容分组放在服务端 load，保持组件只负责呈现 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-03.json`。|
| C | D001 | `D001-001` | S01 | 把多阶段需求转成明确的本轮范围与排除项 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D001 | `D001-002` | S02 | 在训练数据切分前保留对话角色和来源元数据 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-02`。|
| C | D001 | `D001-003` | S03 | 按硬件能力选择精度并用梯度累积保留上下文长度 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-02`。|
| C | D001 | `D001-004` | S04 | 用阶段专属测试套件证明阶段完成后再更新文档 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`。|
| C | D001 | `D001-005` | S05 | 用语法审计和多版本矩阵实现兼容性 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D001 | `D001-006` | S06 | 把可嵌入库与 CLI 分离并提供窄的纯 C ABI | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D001 | `D001-007` | S07 | 让头文件、实现文件和构建目标的边界可检查 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-02`。|
| C | D001 | `D001-008` | S08 | 用对象大小和拷贝路径定位启动期栈溢出 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D001 | `D001-009` | S09 | 用路由事实和请求生命周期排查前端 404 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D001 | `D001-010` | S10 | 用户指出本地字体后先检查资产和编译路径 | `usable_narrow` | 2 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-01`。|
| C | D001 | `D001-011` | S11 | 用新数组引用触发响应式系统更新 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D001 | `D001-012` | S12 | 让窗口打开和进程清理具备幂等生命周期 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D001 | `D001-013` | S13 | 用同源代理消除前端运行时后端地址分歧 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D001 | `D001-014` | S14 | 把多分辨率界面布局变成运行时几何而非编译期常量 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-05`。|
| C | D001 | `D001-015` | S15 | 迁移低级启动/显示路径时以运行时事实校验协议兼容性 | `unsupported` | 2 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-02`。|
| C | D001 | `D001-016` | S17 | 从参考源解析资源并用结构性计数验证结果 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D001 | `D001-017` | S18 | 对高影响操作实施分层开关、精确确认和公开警告 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`。|
| C | D001 | `D001-018` | S19 | 把不同部署/政策要求隔离为独立实现并保留切换边界 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`。|
| C | D001 | `D001-019` | S20 | 敏感配置采用加密存储、分离盐和可验证初始化 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-03`。|
| C | D001 | `D001-020` | S21 | 清理工程时只删除可证明的派生物并同步构建入口 | `usable_narrow` | 2 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`。|
| C | D001 | `D001-021` | S22 | 构建后恢复派生文件并保持 PR 只含意图变更 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D001 | `D001-022` | S23 | 外发轨迹前做公开性核验、脱敏复查和信任边界停机 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D001 | `D001-023` | S25 | 状态型解释器先建立状态再按要求顺序执行 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D001 | `D001-024` | S26 | 按阶段建立提取边界并以不变量约束低级运行时 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-01`。|
| C | D001 | `D001-025` | S27 | 用索引调试过程中的数据结构不变量和旧二进制隔离 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D001 | `D001-026` | S28 | 先解除测试前置阻塞再判断功能级失败 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-01`。|
| C | D001 | `D001-027` | S29 | 把跨写入和查询的类型转换集中到单一绑定点 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-01`。|
| C | D001 | `D001-028` | S32 | Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D001 | `D001-029` | S33 | 先读取外部 API 的真实 payload 再建模和渲染 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-03`。|
| C | D001 | `D001-030` | S34 | 用游标和 IntersectionObserver 实现可恢复的分页加载 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-03`。|
| C | D001 | `D001-031` | S35 | 对第三方移动应用采用构建门槛、静态扫描、真机行为和清理闭环 | `generic_or_weak` | 1 | present | 有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。 来源 `segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-09`。|
| C | D001 | `D001-032` | S36 | 审查 APK 前先验证发布物身份与包类型 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-10`。|
| C | D001 | `D001-033` | S37 | 把持续集成失败拆成 schema 门槛和构建工具链分别修复 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-10`。|
| C | D001 | `D001-034` | S38 | 遵循仓库既有元数据约定，避免为单个条目过度引入新 schema | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D001 | `D001-035` | S39 | 修改本地化源文件时保持格式并只重新生成派生消息 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b__segment-02`。|
| C | D001 | `D001-036` | S40 | 安装外部 Skill 前先识别其实际形态 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__da6566ff-0116-4424-bb59-660623f9eb31__segment-01`。|
| C | D001 | `D001-037` | S41 | 静态部署项目先核对构建输出目录和托管根目录 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__11ef2190-67e2-4707-8212-ab12ebffdbc2__segment-01`。|
| C | D001 | `D001-038` | S43 | 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D001 | `D001-039` | S44 | 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`。|
| C | D001 | `D001-040` | S45 | 把固定资源约束写成可检查的不变量并将大型工作区移出栈 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-02`。|
| C | D001 | `D001-041` | S46 | 解释内核最小系统时先分清 kernel、PID 1 和 userspace 责任 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-01`。|
| C | D001 | `D001-042` | S48 | 把数据驱动的内容分组放在服务端 load，保持组件只负责呈现 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-03`。|
| C | D002 | `D002-001` | S01 | 把多阶段需求转成明确的本轮范围与排除项 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D002 | `D002-002` | S02 | 在训练数据切分前保留对话角色和来源元数据 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-02`。|
| C | D002 | `D002-003` | S03 | 按硬件能力选择精度并用梯度累积保留上下文长度 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-02`。|
| C | D002 | `D002-004` | S05 | 用语法审计和多版本矩阵实现兼容性 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D002 | `D002-005` | S06 | 把可嵌入库与 CLI 分离并提供窄的纯 C ABI | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D002 | `D002-006` | S07 | 让头文件、实现文件和构建目标的边界可检查 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-02`。|
| C | D002 | `D002-007` | S08 | 用对象大小和拷贝路径定位启动期栈溢出 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D002 | `D002-008` | S10 | 用户指出本地字体后先检查资产和编译路径 | `usable_narrow` | 2 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-01`。|
| C | D002 | `D002-009` | S11 | 用新数组引用触发响应式系统更新 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D002 | `D002-010` | S12 | 让窗口打开和进程清理具备幂等生命周期 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D002 | `D002-011` | S15 | 迁移低级启动/显示路径时以运行时事实校验协议兼容性 | `unsupported` | 2 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-02`。|
| C | D002 | `D002-012` | S16 | 用已知工作实现对照并缩小退出崩溃的最小路径 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d__segment-02`。|
| C | D002 | `D002-013` | S17 | 从参考源解析资源并用结构性计数验证结果 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D002 | `D002-014` | S21 | 清理工程时只删除可证明的派生物并同步构建入口 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e__segment-02`。|
| C | D002 | `D002-015` | S22 | 构建后恢复派生文件并保持 PR 只含意图变更 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D002 | `D002-016` | S23 | 外发轨迹前做公开性核验、脱敏复查和信任边界停机 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D002 | `D002-017` | S25 | 状态型解释器先建立状态再按要求顺序执行 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D002 | `D002-018` | S26 | 按阶段建立提取边界并以不变量约束低级运行时 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-01`。|
| C | D002 | `D002-019` | S27 | 用索引调试过程中的数据结构不变量和旧二进制隔离 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D002 | `D002-020` | S28 | 先解除测试前置阻塞再判断功能级失败 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-01`。|
| C | D002 | `D002-021` | S29 | 把跨写入和查询的类型转换集中到单一绑定点 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-01`。|
| C | D002 | `D002-022` | S30 | 跨 C 后端与 JS 用户态时先复用现有能力再新增绑定 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d__segment-01`。|
| C | D002 | `D002-023` | S31 | 用权限边界和已知程序定位用户态退出故障 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d__segment-02`。|
| C | D002 | `D002-024` | S36 | 审查 APK 前先验证发布物身份与包类型 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-10`。|
| C | D002 | `D002-025` | S37 | 把持续集成失败拆成 schema 门槛和构建工具链分别修复 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-10`。|
| C | D002 | `D002-026` | S38 | 遵循仓库既有元数据约定，避免为单个条目过度引入新 schema | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D002 | `D002-027` | S39 | 修改本地化源文件时保持格式并只重新生成派生消息 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b__segment-02`。|
| C | D002 | `D002-028` | S44 | 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`。|
| C | D002 | `D002-029` | S46 | 解释内核最小系统时先分清 kernel、PID 1 和 userspace 责任 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-01`。|
| C | D003 | `D003-001` | S01 | 把多阶段需求转成明确的本轮范围与排除项 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02`。|
| C | D003 | `D003-002` | S04 | 用阶段专属测试套件证明阶段完成后再更新文档 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02`。|
| C | D003 | `D003-003` | S09 | 用路由事实和请求生命周期排查前端 404 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D003 | `D003-004` | S10 | 用户指出本地字体后先检查资产和编译路径 | `usable_narrow` | 2 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-01`。|
| C | D003 | `D003-005` | S11 | 用新数组引用触发响应式系统更新 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D003 | `D003-006` | S12 | 让窗口打开和进程清理具备幂等生命周期 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D003 | `D003-007` | S13 | 用同源代理消除前端运行时后端地址分歧 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D003 | `D003-008` | S14 | 把多分辨率界面布局变成运行时几何而非编译期常量 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02`。|
| C | D003 | `D003-009` | S15 | 迁移低级启动/显示路径时以运行时事实校验协议兼容性 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-04`。|
| C | D003 | `D003-010` | S16 | 用已知工作实现对照并缩小退出崩溃的最小路径 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d__segment-02`。|
| C | D003 | `D003-011` | S30 | 跨 C 后端与 JS 用户态时先复用现有能力再新增绑定 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d__segment-02`。|
| C | D003 | `D003-012` | S31 | 用权限边界和已知程序定位用户态退出故障 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d__segment-02`。|
| C | D003 | `D003-013` | S32 | Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D003 | `D003-014` | S35 | 对第三方移动应用采用构建门槛、静态扫描、真机行为和清理闭环 | `generic_or_weak` | 1 | present | 有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。 来源 `segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-09`。|
| C | D003 | `D003-015` | S39 | 修改本地化源文件时保持格式并只重新生成派生消息 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b__segment-01`。|
| C | D003 | `D003-016` | S42 | 固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间 | `generic_or_weak` | 1 | present | 有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。 来源 `segments__claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f__segment-01`。|
| C | D003 | `D003-017` | S43 | 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D003 | `D003-018` | S44 | 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`。|
| C | D003 | `D003-019` | S48 | 把数据驱动的内容分组放在服务端 load，保持组件只负责呈现 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-03`。|
| C | D004 | `D004-001` | S09 | 用路由事实和请求生命周期排查前端 404 | `high_value` | 3 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D004 | `D004-002` | S10 | 用户指出本地字体后先检查资产和编译路径 | `usable_narrow` | 2 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-01`。|
| C | D004 | `D004-003` | S11 | 用新数组引用触发响应式系统更新 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D004 | `D004-004` | S12 | 让窗口打开和进程清理具备幂等生命周期 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D004 | `D004-005` | S13 | 用同源代理消除前端运行时后端地址分歧 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D004 | `D004-006` | S18 | 对高影响操作实施分层开关、精确确认和公开警告 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`。|
| C | D004 | `D004-007` | S19 | 把不同部署/政策要求隔离为独立实现并保留切换边界 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`。|
| C | D004 | `D004-008` | S21 | 清理工程时只删除可证明的派生物并同步构建入口 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`。|
| C | D004 | `D004-009` | S32 | Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D004 | `D004-010` | S33 | 先读取外部 API 的真实 payload 再建模和渲染 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-03`。|
| C | D004 | `D004-011` | S34 | 用游标和 IntersectionObserver 实现可恢复的分页加载 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-03`。|
| C | D004 | `D004-012` | S41 | 静态部署项目先核对构建输出目录和托管根目录 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__11ef2190-67e2-4707-8212-ab12ebffdbc2__segment-01`。|
| C | D004 | `D004-013` | S42 | 固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间 | `generic_or_weak` | 1 | present | 有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。 来源 `segments__claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f__segment-01`。|
| C | D004 | `D004-014` | S43 | 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D004 | `D004-015` | S44 | 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`。|
| C | D004 | `D004-016` | S48 | 把数据驱动的内容分组放在服务端 load，保持组件只负责呈现 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-03`。|
| C | D005 | `D005-001` | S01 | 把多阶段需求转成明确的本轮范围与排除项 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D005 | `D005-002` | S04 | 用阶段专属测试套件证明阶段完成后再更新文档 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`。|
| C | D005 | `D005-003` | S05 | 用语法审计和多版本矩阵实现兼容性 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D005 | `D005-004` | S06 | 把可嵌入库与 CLI 分离并提供窄的纯 C ABI | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D005 | `D005-005` | S07 | 让头文件、实现文件和构建目标的边界可检查 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-02`。|
| C | D005 | `D005-006` | S08 | 用对象大小和拷贝路径定位启动期栈溢出 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D005 | `D005-007` | S09 | 用路由事实和请求生命周期排查前端 404 | `high_value` | 3 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D005 | `D005-008` | S10 | 用户指出本地字体后先检查资产和编译路径 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`。|
| C | D005 | `D005-009` | S11 | 用新数组引用触发响应式系统更新 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D005 | `D005-010` | S12 | 让窗口打开和进程清理具备幂等生命周期 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D005 | `D005-011` | S13 | 用同源代理消除前端运行时后端地址分歧 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D005 | `D005-012` | S14 | 把多分辨率界面布局变成运行时几何而非编译期常量 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02`。|
| C | D005 | `D005-013` | S15 | 迁移低级启动/显示路径时以运行时事实校验协议兼容性 | `unsupported` | 2 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-02`。|
| C | D005 | `D005-014` | S17 | 从参考源解析资源并用结构性计数验证结果 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D005 | `D005-015` | S22 | 构建后恢复派生文件并保持 PR 只含意图变更 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D005 | `D005-016` | S23 | 外发轨迹前做公开性核验、脱敏复查和信任边界停机 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D005 | `D005-017` | S25 | 状态型解释器先建立状态再按要求顺序执行 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D005 | `D005-018` | S27 | 用索引调试过程中的数据结构不变量和旧二进制隔离 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D005 | `D005-019` | S32 | Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D005 | `D005-020` | S33 | 先读取外部 API 的真实 payload 再建模和渲染 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-03`。|
| C | D005 | `D005-021` | S34 | 用游标和 IntersectionObserver 实现可恢复的分页加载 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-03`。|
| C | D005 | `D005-022` | S38 | 遵循仓库既有元数据约定，避免为单个条目过度引入新 schema | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D005 | `D005-023` | S39 | 修改本地化源文件时保持格式并只重新生成派生消息 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b__segment-01`。|
| C | D005 | `D005-024` | S42 | 固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间 | `generic_or_weak` | 1 | present | 有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。 来源 `segments__claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f__segment-01`。|
| C | D005 | `D005-025` | S43 | 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D005 | `D005-026` | S44 | 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`。|
| C | D005 | `D005-027` | S48 | 把数据驱动的内容分组放在服务端 load，保持组件只负责呈现 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-03`。|
| C | D006 | `D006-001` | S01 | 把多阶段需求转成明确的本轮范围与排除项 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02`。|
| C | D006 | `D006-002` | S04 | 用阶段专属测试套件证明阶段完成后再更新文档 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`。|
| C | D006 | `D006-003` | S06 | 把可嵌入库与 CLI 分离并提供窄的纯 C ABI | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D006 | `D006-004` | S08 | 用对象大小和拷贝路径定位启动期栈溢出 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D006 | `D006-005` | S09 | 用路由事实和请求生命周期排查前端 404 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D006 | `D006-006` | S10 | 用户指出本地字体后先检查资产和编译路径 | `usable_narrow` | 2 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-01`。|
| C | D006 | `D006-007` | S11 | 用新数组引用触发响应式系统更新 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D006 | `D006-008` | S12 | 让窗口打开和进程清理具备幂等生命周期 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`。|
| C | D006 | `D006-009` | S13 | 用同源代理消除前端运行时后端地址分歧 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D006 | `D006-010` | S14 | 把多分辨率界面布局变成运行时几何而非编译期常量 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02`。|
| C | D006 | `D006-011` | S18 | 对高影响操作实施分层开关、精确确认和公开警告 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`。|
| C | D006 | `D006-012` | S19 | 把不同部署/政策要求隔离为独立实现并保留切换边界 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`。|
| C | D006 | `D006-013` | S21 | 清理工程时只删除可证明的派生物并同步构建入口 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`。|
| C | D006 | `D006-014` | S26 | 按阶段建立提取边界并以不变量约束低级运行时 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-01`。|
| C | D006 | `D006-015` | S27 | 用索引调试过程中的数据结构不变量和旧二进制隔离 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D006 | `D006-016` | S32 | Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D006 | `D006-017` | S33 | 先读取外部 API 的真实 payload 再建模和渲染 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-03`。|
| C | D006 | `D006-018` | S34 | 用游标和 IntersectionObserver 实现可恢复的分页加载 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-03`。|
| C | D006 | `D006-019` | S41 | 静态部署项目先核对构建输出目录和托管根目录 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__11ef2190-67e2-4707-8212-ab12ebffdbc2__segment-01`。|
| C | D006 | `D006-020` | S42 | 固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间 | `generic_or_weak` | 1 | present | 有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。 来源 `segments__claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f__segment-01`。|
| C | D006 | `D006-021` | S43 | 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`。|
| C | D006 | `D006-022` | S44 | 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`。|
| C | D006 | `D006-023` | S45 | 把固定资源约束写成可检查的不变量并将大型工作区移出栈 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-02`。|
| C | D007 | `D007-001` | S01 | 把多阶段需求转成明确的本轮范围与排除项 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D007 | `D007-002` | S04 | 用阶段专属测试套件证明阶段完成后再更新文档 | `high_value` | 3 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`。|
| C | D007 | `D007-003` | S05 | 用语法审计和多版本矩阵实现兼容性 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D007 | `D007-004` | S06 | 把可嵌入库与 CLI 分离并提供窄的纯 C ABI | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D007 | `D007-005` | S07 | 让头文件、实现文件和构建目标的边界可检查 | `usable_narrow` | 2 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-01`。|
| C | D007 | `D007-006` | S08 | 用对象大小和拷贝路径定位启动期栈溢出 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D007 | `D007-007` | S14 | 把多分辨率界面布局变成运行时几何而非编译期常量 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02`。|
| C | D007 | `D007-008` | S17 | 从参考源解析资源并用结构性计数验证结果 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D007 | `D007-009` | S21 | 清理工程时只删除可证明的派生物并同步构建入口 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e__segment-02`。|
| C | D007 | `D007-010` | S25 | 状态型解释器先建立状态再按要求顺序执行 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`。|
| C | D007 | `D007-011` | S26 | 按阶段建立提取边界并以不变量约束低级运行时 | `high_value` | 2 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-01`。|
| C | D007 | `D007-012` | S27 | 用索引调试过程中的数据结构不变量和旧二进制隔离 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`。|
| C | D007 | `D007-013` | S45 | 把固定资源约束写成可检查的不变量并将大型工作区移出栈 | `unsupported` | 1 | empty | source.key_evidence 为空，当前导出记录无法复核具体轨迹证据；单来源本身不是降级理由。 来源 `segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-02`。|
| C | D008 | `D008-001` | S02 | 在训练数据切分前保留对话角色和来源元数据 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-02`。|
| C | D008 | `D008-002` | S03 | 按硬件能力选择精度并用梯度累积保留上下文长度 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-02`。|
| C | D008 | `D008-003` | S07 | 让头文件、实现文件和构建目标的边界可检查 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-02`。|
| C | D008 | `D008-004` | S10 | 用户指出本地字体后先检查资产和编译路径 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`。|
| C | D008 | `D008-005` | S22 | 构建后恢复派生文件并保持 PR 只含意图变更 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D008 | `D008-006` | S23 | 外发轨迹前做公开性核验、脱敏复查和信任边界停机 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D008 | `D008-007` | S35 | 对第三方移动应用采用构建门槛、静态扫描、真机行为和清理闭环 | `generic_or_weak` | 1 | present | 有轨迹动作，但主要是项目局部 UI、供应链步骤或工具流程，难形成独立通用解决链。 来源 `segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-09`。|
| C | D008 | `D008-008` | S36 | 审查 APK 前先验证发布物身份与包类型 | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-10`。|
| C | D008 | `D008-009` | S37 | 把持续集成失败拆成 schema 门槛和构建工具链分别修复 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-10`。|
| C | D008 | `D008-010` | S38 | 遵循仓库既有元数据约定，避免为单个条目过度引入新 schema | `usable_narrow` | 1 | present | 有真实轨迹证据和工程价值，但依赖特定技术栈、部署条件或较窄的适用前提。 来源 `segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`。|
| C | D008 | `D008-011` | S39 | 修改本地化源文件时保持格式并只重新生成派生消息 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b__segment-02`。|
| C | D008 | `D008-012` | S44 | 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 | `high_value` | 1 | present | 有可定位轨迹证据，且把具体问题/约束连接到决策与验证，形成可迁移解决链。 来源 `segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`。|

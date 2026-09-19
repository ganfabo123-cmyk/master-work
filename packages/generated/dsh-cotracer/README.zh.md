[English](README.md) | 中文

# @deepseek-ai/dsh-cotracer

CoTracer 是基于假设驱动的多智能体调试（trace）编排插件。它注册一个 `cotracer-trace` 技能，并通过其 `cordis.yml` 组合，在其旁边加载三个基础设施插件：`dsh-explorer-agent`（只读仓库探索）、`dsh-experiment-state`（共享实验树，带 `executor` 参数）和 `dsh-detector`（调查子代理加上共享的 `experimentExecutor` 服务）。加载技能后，主代理自行驱动组合工具集，从"仓库 + 问题"递归收敛到根因；当输入不完整时，技能引导 `ask_user_question` 追问。

## 插件形态

与 `dsh-cordis-sub-agent` 形态相同：**一份 SKILL.md（普通目录匹配；模型在识别到 trace 任务时加载它）+ 一个工具集（由被组合的插件贡献）+ 程序侧胶水（组合这三个插件并将 detector 执行器接入 `experiment_create`）**。插件本身不注册任何工具；所有工具都来自被组合的插件，模型按技能描述进行编排——没有状态机或工作流硬编码。

## 组合

`cordis.yml`（用于 `dsh web --patch`）和 `cordis.acceptance.yml`（用于验收）都通过 `insert:` + `file://` 直接 URL 加载四个插件：

- `cotracer`：本插件；注册 `cotracer-trace` 技能。
- `explorer-agent`：注册 `explorer` 工具（由主代理和 Detector 子代理共享）。
- `experiment-state`：注册 `experiment_create` / `experiment_update` / `experiment_get` / `experiment_list`；`experiment_create` 的 `executor` 参数决定谁运行实验。
- `detector`（`persona: false`）：只注册 `delegate_experiment` 工具和共享的 `experimentExecutor` 服务；它不为主代理注册 Detector 身份段。

主代理组合不加载 Detector persona，因此主代理保持自己的身份；每个 Detector 子代理由 executor 服务以 Detector persona 启动。

## 工具

- `explorer`：让一个只读的 Explorer 子代理在给定目录内回答调查问题，返回基于证据的答案（路径加语义发现）。用于侦察和缩小搜索空间。
- `experiment_create`：创建一个实验。`executor` 参数：
  - `detector`：插件通过共享服务自动为该实验启动一个 Detector 子代理，并等待其回写（status/result/evidence）。
  - `self`（默认）：实验只是记录；调用者自行调查并用 `experiment_update` 回写。
  子实验（带 `parent_id`）自动继承并追加父级的 `shared_info`（累积的祖先上下文加新发现），因此同一仓库中的相似问题不会被重复勘察；它还继承父级的 `executor`，因此递归通过主代理或 detector 自然流转。
- `experiment_update`：回写 status/evidence/result/shared_info/executor。
- `experiment_get` / `experiment_list`：聚合实验树，使主代理能够剪枝假设并缩小范围。
- `ask_user_question`：当仓库或问题缺失时追问；随标准 preset 的 `tool-ask-user` 提供。

## 技能：cotracer-trace

`skills/dsh-cotracer/SKILL.md` 描述完整流程：

1. **输入收集**：要求提供仓库和问题；如果任一缺失或含糊，在开始前用 `ask_user_question` 提问——绝不猜测。
2. **侦察**：用 `explorer` 加上对仓库的直接读取/搜索来收集初始证据。
3. **假设**：生成 2-4 个可证伪的竞争假设（假设 + 可证伪问题 + 范围 + shared_info）。
4. **实验**：每个假设一次 `experiment_create`；选择 `executor`（detector 自动委派，self 直接调查）。
5. **聚合**：用 `experiment_get` / `experiment_list` 读取树，丢弃或下调被否定的假设，合并兼容的假设，缩小搜索空间，并为下一轮中不确定的区域提出更细粒度的假设。
6. **收敛**：当某个假设拥有确证证据且没有（或已解释）矛盾证据时，停在根因处。
7. **输出**：根因 + 证据 + 实验树摘要 + 修复建议。

## 模型体验

### 系统提示词

技能以普通运行时技能注册（`source: 'runtime'`），一旦可见即可加载；插件不注册 persona 段，也不改变主代理的身份。

### Token 影响

固定成本是工具 schema；`explorer`、带 `executor: "detector"` 的 `experiment_create` 和 `delegate_experiment` 各自启动一个花费自身模型预算的子代理；技能正文在加载时注入。实验结果 JSON 返回到主代理的上下文中。

### KV 缓存影响

没有固定前缀：插件不追加任何每请求文本；子代理会话相互独立。

## 要求

- `explorer-agent` 需要一个具备 `toolFilter` 能力的 `subagents` provider（进程内 `spawn`/`fork`）以及 `read`/`glob`/`grep` 工具。
- detector 的 executor 服务和 `delegate_experiment` 需要具备 `outputSchema` 支持的 `subagents` `spawn` provider。
- `experiment-state` 必须共享进程（实验树是进程内存）。
- dsh web 基础 profile 已提供这些；验收 overlay 显式添加它们（见 `cordis.acceptance.yml`）。

## 已知限制与待办工作

- **实验树是进程内存**：实验状态随进程消亡，插件重载时被清除；无跨会话持久化。
- **`executor: "detector"` 同步等待**：`experiment_create` 阻塞直到 Detector（及其递归子级）回写；一次长时间的调查会占用一次工具调用。
- **范围边界是引导而非强制**：Detector 的范围限制是 persona/工具描述层面的引导，主代理自身的执行也是如此；没有文件系统策略围栏。
- **Detector 是只读基线**：它不携带运行时 trace 或插桩工具；更丰富的调查工具可在后续版本挂载到同一角色上。
[English](README.md) | 中文

# @deepseek-ai/dsh-detector

Detector 是基于假设驱动的多智能体调试器中的调查子代理：它回答一个局部范围内的实验问题（`question`），将证据与结论写回共享的实验树，并且——当问题过大、无法在其自身范围内直接回答时——递归地将问题拆分为子实验，将每个子实验委派给一个子 Detector，再把子结论汇总进自己的回答。

Detector 一次只调查一个实验。它的输入是实验的结构化信息（`experiment_id`、`hypothesis`、`question`、`scope`、`shared_info`），由 [`@deepseek-ai/dsh-experiment-state`](../dsh-experiment-state/README.md) 定义；实验字段名称与回写语义遵循该插件的真实投影，该投影是唯一权威。本包将这一角色交付为一个智能体预设（包含 `agent.cordis.yml` 和 `preset.yml` 的目录），外加一个提供 Detector 人设与 `delegate_experiment` 工具的函数插件。

这是假设驱动调试器消融研究的只读基线：Detector 在其 `scope` 内阅读代码并写入实验树，但不携带任何调查工具（运行时追踪、插桩、断点等）。后续版本会在同一角色上挂载源自单智能体追踪论文的工具，而本基线是对照组。

## 组成结构

```text
packages/generated/dsh-detector/
├── agent.cordis.yml   # 检测器智能体预设：本插件 + dsh-experiment-state
├── preset.yml         # 预设清单的展示元数据
├── cordis.yml         # 验证覆盖层：将角色加载进宿主组合
├── cordis.acceptance.yml
└── src/index.ts       # 函数插件：人设部分 + delegate_experiment 工具
```

预设组合只包含角色插件与 `dsh-experiment-state`。宿主组合已经提供文件系统工具（读取/搜索）、`ctx.subagents` 服务与进程内 `spawn` 提供器；预设不得重复加载它们，因为重复的根领域服务或重复的工具注册会导致挂载失败。该组合每进程挂载一次（常驻挂载），每个子 Detector 都通过子代理服务的 `composeFrom` 加入同一组合，因此实验状态存储是整个递归调查共享的单一实例。

## 用法

### 作为智能体预设（生产路径）

协调器插件（一个单独的、尚在规划中的包，不是本包）将此目录注册为智能体预设根，创建根实验，并以实验的结构化信息作为第一条用户消息启动一个 Detector。无法直接回答的 Detector 会自行创建子实验，并通过 `delegate_experiment` 委派它们，因此递归内部无需更多接线。

### 直接验证覆盖层

```sh
pnpm dsh web --patch ./packages/generated/dsh-detector/cordis.yml
```

根智能体变为一个 Detector：人设取代部署人设，`experiment_create`、`experiment_update` 与 `delegate_experiment` 出现在其工具集中。用此方式手动演练角色。真实编排会改挂载预设目录；覆盖层是自包含的验证/演示形式。

## 工具

### `delegate_experiment`

为一个子实验生成一个子 Detector，并等待其结构化结论。

| 参数 | 类型 | 必填 | 含义 |
|---|---|---|---|
| `experiment_id` | string | 是 | `experiment_create` 返回的子实验 id。 |
| `hypothesis` | string | 是 | 该子实验调查的疑似原因。 |
| `question` | string | 是 | 子 Detector 必须回答的可证伪问题。 |
| `scope` | string[] | 是 | 子 Detector 可以查看的目录/文件。 |
| `shared_info` | string | 否 | 传递给子 Detector 的附加信息。 |

该工具通过 `ctx.subagents.start` 在配置的提供器上启动子代理，要求结构化输出模式（`{ status, conclusion, evidence }`），通过 `toolFilter` 对子代理隐藏 `experiment_get`/`experiment_list`，并以 `{ experiment_id, status, conclusion, evidence }` 的形式返回子代理的裁决。子 Detector 继承相同的角色组合，因此可以进一步递归。

## 配置

| 字段 | 默认值 | 含义 |
|---|---|---|
| `provider` | `spawn` | 子 Detector 启动所用的 `ctx.subagents` 提供器名称。 |
| `maxDepth` | `3` | 委派给子 Detector 的递归预算：非负安全整数，或传 `'provider-managed'` 表示不设上限。提供器会按调用方智能体自身的深度强制执行该上限。 |

## 实验结构契约（人设）

人设注册为 order-0 提示段，名为 `detector:persona`——位于部署人设所在的位置，因此在部署人设为空的场景中它就是首个身份段。该名字刻意不同于 `deployment:persona`（那个槽位只能从更深的 scope 覆盖，绝不能在全局层重复注册），因此预设挂载与直接 overlay 两种加载方式都不会发生层冲突。加入该预设的每个智能体都会读到它。它定义了 Detector 如何使用实验数据：

- `question` 是任务：调查必须回答的可证伪问题。`hypothesis` 是背景，绝不是结论。`scope` 是严格的调查边界：超出它的读写都是违规。`shared_info` 是可选的附加上下文。`experiment_id` 是回写目标，也是子实验的 `parent_id`。
- 调查使用 `scope` 内的文件系统读取/搜索工具。可以编写临时实验脚本，但只能写入系统临时目录或 `test` 目录；不得修改源文件。
- 可直接回答的问题通过 `experiment_update` 一次性回写：`evidence`（可独立成立的事实句，支持或反驳）、`result`（回答 `question` 的结论）与 `status`（`confirmed` / `rejected` / `completed`，与 experiment-state 生命周期一致）。
- 过大问题用 `experiment_create` 拆分（`parent_id` = 自身的 `experiment_id`），每个子实验通过 `delegate_experiment` 委派，收集到的子裁决在回写前汇总进 Detector 自己的 `evidence` 与 `result`。
- 不使用 `experiment_get` 与 `experiment_list`；实验树仅通过回写条目维护。

确切的人设文本位于 `src/index.ts`，是本文档所概括的契约。

## 递归与共享实验树

预设组合内的 experiment-state 存储是整个递归的单一实例：常驻挂载只应用一次 `dsh-experiment-state`，每个被委派的子代理都通过 `composeFrom` 加入同一组合。因此父 Detector 能看到其子代理回写的子实验，实验树作为一个连贯的整体结构生长。递归由 `Config.maxDepth` 与提供器的深度强制机制约束。

## 模型体验

### 系统提示词

#### 模型看到的内容

对于该预设上的智能体，Detector 人设取代部署人设，宿主组合的全局工具指导保持不变。人设文本是稳定的散文；它不是按请求动态求值的。

#### Token 影响

每次请求的固定成本：人设部分加上可见工具（`delegate_experiment`、`experiment_create`、`experiment_update` 以及继承的文件系统工具）的 schema。子 Detector 的对话是独立的会话，各自承担自己的 token。

#### KV 缓存影响

在智能体生命周期内前缀稳定：预设组合在智能体的第一次请求之前安装一次，智能体运行期间绝不重读。委派调用的结构化输出 schema 注册在子代理自己的作用域内，不触及父级前缀。

### 行为说明

- 未正常结束的子运行（取消、失败、达到 token 上限、拒绝）会以指明原因的工具错误形式呈现；子代理的部分输出不被视为成功。
- 始终未提交结构化值的子代理会报错，因为结构化输出运行时要求恰好一次 `structured_output` 调用才能结束。

## 已知限制与延期工作

- **对根 Detector 而言，`experiment_get`/`experiment_list` 的隐藏是软性的。** 每个被委派的子代理都会获得对这两个读取工具的硬性 `toolFilter` 拒绝。根 Detector 自身的工具集仍然暴露它们（experiment-state 插件注册了全部四个工具）；人设禁止使用它们，而硬性隐藏需要在 `dsh-experiment-state` 中增加配置项，或由协调器插件做智能体作用域的 `ctx.tools.restrict`。
- **根实验必须在本预设的存储内创建。** 存储位于预设的常驻挂载中；由独立的 `dsh-experiment-state` 实例（例如加载进宿主组合的那个）创建的实验，对 Detector 的回写不可见。协调器插件必须在运行 Detector 的同一组合中创建根实验，否则存储必须提升为共享服务。
- **临时脚本的放置只是人设指导，不是强制。** 智能体拥有写入工具；限制在临时/测试目录只是一条声明的规则，不是运行时闸门。
- **本基线不附带任何调查工具。** 运行时追踪、插桩及其他单智能体追踪工具延期到挂载在该角色上的后续版本。
- **这里不包含任何协调器逻辑。** 创建根实验、启动根 Detector、注入实验数据与汇总顶级裁决都属于规划的协调器插件，而不是本包。
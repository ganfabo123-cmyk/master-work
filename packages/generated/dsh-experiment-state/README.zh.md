[English](README.md) | 中文

# @deepseek-ai/dsh-experiment-state

面向基于假设的多智能体调试的共享外部实验树状态。该插件本身不是调试智能体：
它把调试过程记录为结构化实验，因此任何智能体都不必在聊天上下文中携带调试
历史。

主智能体（协调者）在怀疑某个原因时，会调用 `experiment_create`，传入假设、
可证伪的问题、调查可以查看的目录范围，以及可选的共享信息（例如提前收集的
调查结果）。随后，调查智能体在该范围内工作，并通过 `experiment_update` 写回
其证据和结论。实验会引用父实验（`parent_id`），因此细化假设会创建子实验——
整个调试会话就是一棵实验树。`experiment_get` 和 `experiment_list` 让协调者
汇总状态，并决定下一步修剪或细化哪些内容。

存储位于进程内存中：同一进程内的每个智能体读写同一棵树，不会向磁盘写入
任何内容。

## 使用方法

在 `dsh web` 中加载该插件：

```sh
pnpm dsh web --patch ./packages/generated/dsh-experiment-state/cordis.yml
```

让智能体调试某个问题；当它怀疑某个原因时，会创建实验、派发调查，并读回
证据以收敛到根因。

该插件没有配置。

### 工具

注册了四个工具，全部以缩进 JSON 形式返回实验。

- `experiment_create` —— 必填 `hypothesis`、`question`、`scope`（非空路径列表）；
  可选 `shared_info`、`parent_id`。当必填字段为空、scope 为空或父 id 未知时，
  会明确报错。
- `experiment_update` —— 必填 `id`；可选参数 `status`（`pending`、`running`、
  `completed`、`rejected`、`confirmed`）、`evidence`（字符串列表，替换当前列表）、
  `result`、`shared_info` 中至少提供一个。
- `experiment_get` —— 必填 `id`；返回实验及其直接子实验（一层），以便看到
  细化后的假设。
- `experiment_list` —— 无参数；按创建顺序返回所有实验。每个条目都携带
  `parent_id`；空的 `parent_id` 表示根实验，因此可以重建整棵树。

实验字段：`id`、`hypothesis`、`question`、`scope`、`shared_info`、`status`、
`evidence`、`result`、`parent_id`、`created_at`、`updated_at`。

## 模型体验

### 插件交互

#### 模型看到的内容

四个工具 schema，以及每次调用时渲染出的实验 JSON。该插件自身不进行任何模型
工作：参数在本地校验，存储的记录被投影为 JSON，因此工具结果是模型从该插件
看到的唯一文本。

#### Token 影响

没有额外的 provider 调用。成本是提示词中的四个工具 schema 和每次调用的 JSON
结果（受上述字段约束；`experiment_list` 会返回所有实验）。

#### KV 缓存影响

无：该插件从不发起 provider 请求，因此请求前缀不受影响。

## 已知限制与待办工作

- 存储是进程本地内存：实验状态随进程一同消亡，仅在一次进程生命周期内可跨
  工具调用和子智能体存活，并在插件重载时被清空。
- 这棵树在整个进程中共享；实验没有按智能体划分的访问限制。
- `parent_id` 在创建时固定；实验不能被重新指定父级、删除或归档。
- 子视图只展开一层；更深的树需要用 `experiment_get` 逐 id 追踪。
- 该插件只记录状态：假设生成、实验选择、证据聚合和搜索空间细化属于编排
  智能体，不属于本插件。
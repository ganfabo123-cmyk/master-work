# Prompt Builder 重构复盘

## 这次连续出现的两个错误

### 第一次：把提示词放进 Agent 类

客服 Agent 类中曾直接保存整段系统提示词。这样 Agent 同时承担了能力声明和提示词内容两个职责：新增或修改 Prompt 时必须改 Agent，Prompt 也无法独立组织、复用或审查。

正确边界是：Agent 只声明 `prompt_builder`、工具名单和候选 Skill；提示词正文只属于对应的 Prompt Builder。

### 第二次：把 Prompt Builder 过度抽象为 role/rules/output 参数

第一次修正后，又在基类中规定所有 Prompt 都必须通过 `role`、`rules`、`output` 调用通用组装方法。这把一个示例结构错误地升级成了框架约束。

它会阻止领域 Builder 自由表达自己的需求，例如：多个 Developer Message、Few-shot 对话、结构化输入块、领域专用动态参数、不同的消息顺序，或根本不需要 Role/Rules/Output 的 Prompt。子类变成填表，而不是 Prompt 的实际拥有者。

## 根因

没有先区分“接口统一”与“内容统一”。

- 接口只需要统一为：`prompt_builder(task) -> Prompt`。
- Prompt 内容结构不应该统一；它属于每个领域 Builder。

基类的价值是让 Runtime 将所有 Builder 当成同一种可调用能力，而不是规定它们怎样构造消息。

## 修正后的约束

1. `BasePromptBuilder` 只提供 `__call__` 与抽象 `build(task)` 协议。
2. 任何领域 Prompt Builder 可以拥有任意构造参数，并直接返回任意合法的 `Prompt`。
3. 领域 Builder 不得被要求调用父类的 Prompt 拼装方法。
4. Agent 类只持有 Builder 实例，不保存提示词正文。
5. 旧 Runtime 的 `build_task_prompt(task, system_prompt)` 是临时兼容函数，不是新 Builder 的基础设施；后续 Runtime 改造时应直接调用 `Agent.prompt_builder(task)`。

## 后续修改前的检查问题

- 新 Builder 能否完全不调用基类内容方法？
- 它能否增加自己的构造参数和任意数量、顺序的 Message？
- Agent 类是否只声明能力，而没有提示词正文？
- 是否因为兼容旧代码而错误限制了新抽象？

若任一答案是否定的，说明抽象仍然把领域能力压进了框架模板，不能合入。

# Agent Note: 按 cwd 隔离的事实记忆

Status: implemented

[English](2026-08-17-cwd-scoped-fact-memory.md) | 中文

## 问题

[关键词经验记忆](../architecture/2026-08-16-keyword-experience-memory.md)插件按需召回可复用的任务经验，但它没有位置存放关于用户或工作空间的稳定事实——名字、偏好、项目约定——这些是 Agent 本应直接知道的信息。事实不是召回形态：它们体量小、是当前状态，且每一轮都想要，而不是等某个以后的机会用关键词检索。没有它们，模型会在每个 Session 里反复询问同一个用户身份或项目约束。

## 决策

`@deepseek-ai/dsh-memory` 在经验记忆之外新增按 cwd 隔离的事实记忆。一条 `FactMemory` 记录包含规范化键、值以及 Harness 生成的 ISO 8601 时间。事实按绝对 cwd 存储：每个 cwd 对应配置的 `factsDir`（默认为 `$DSH_HOME/memory-facts`）下的一个 Markdown 文件，文件名是该绝对路径的 16 位十六进制 SHA-256 摘要，因此主机路径不会泄露到文件名中，且每个 cwd 与其它 cwd 完全隔离。

`MemoryService.rememberFact` 对键做去空格与转小写后按键 upsert；`forgetFact` 按规范化键删除并报告是否删除了内容；`facts` 列出当前 cwd 的完整集合。模型工具为 `fact_remember` 和 `fact_forget`，两者都以 `exec.agent.session.header.cwd` 为作用域，没有会话 cwd 时直接失败。每次装配都会通过 `system-prompt/assemble` 瀑布贡献把当前 cwd 的事实注入为一个 system-prompt Section，读取 agent loop 注册的 `assembly.variables.cwd`（cwd 变量），因此事实每一轮都会出现，记住或忘记后立即更新，无需重启。`maxFacts`（默认 100）限制每个 cwd 注入的数量。

事实文件的持久化规则与经验存储相同：原子替换、Owner 专属权限，以及每个 cwd 独立的进程内串行写队列，保证并发 remember 不会丢失事实；忘记后清空的存储会删除对应文件。

## 备选方案

- **复用经验记录/关键词检索承载事实**——否决：事实必须每轮都出现，而不是选择性召回；走检索路径只会在模型猜对关键词时才能看到，等于隐形。
- **把事实放进带 scope 标签的全局 `memory.md`**——否决：经验文件是追加式并按关键词索引；把按键 upsert 的事实混入会耦合两种完全不同的读写模式，也无法形成硬性的 cwd 隔离。
- **用固定静态 system-prompt Section 注入**——否决：静态 Section 无法知道当前 cwd 或实时事实集合；`system-prompt/assemble` 瀑布每轮重新求值，注入才能保持最新且无需重配插件。

## 后果

插件现在提供两种记忆：按需召回的经验记忆与常驻的按 cwd 事实记忆。事实成本很低（每轮几行简短的 `key: value`，受 `maxFacts` 限制），并在下一次装配立即生效。代价是第二套持久化格式和第二条写队列，两者都与现有存储同构；事实键按设计不区分大小写（统一小写），隔离严格按绝对 cwd——在 `D:/a` 保存的事实对 `D:/b` 或写法不同的等价路径不可见。

包测试覆盖事实往返、按 cwd 隔离、并发 remember、无会话 cwd 时的工具执行以及注入 Section 渲染。
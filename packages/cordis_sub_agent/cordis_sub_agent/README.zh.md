# dsh-cordis-sub-agent

[English](README.md) | 中文

dsh-cordis-sub-agent 负责在 DeepSeek Harness monorepo 内开发插件。每个任务
独占一个生成 workspace package：packages/generated/<plugin-name>/。

## 开发流程

submit_plugin_metadata
  -> task_id
  -> prepare_plugin_reading(task_id)
  -> Read Agent 返回 JSON 阅读清单
  -> Main Agent 根据清单读取、编写、build/test，并在同一 pluginRoot 修复
  -> document_development（Documentation Agent：只处理 README）
  -> verify_development（前台执行工程命令）
  -> start_acceptance（临时验收配置 + fresh DSH）
  -> send_acceptance_message
  -> stop_acceptance
  -> 永久集成

packages/generated/<plugin-name>/ 匹配仓库现有的 packages/*/* workspace glob，
因此刷新 workspace install 后，插件可以正常使用 workspace:* 依赖。普通开发阶段
不会修改根 pnpm-workspace.yaml。

普通插件的 canonical reference 位于 packages/examples/plugin-reference/。应先读取
它来理解标准插件入口、配置、Tool、service、持久化、生命周期、测试和文档结构。
packages/examples/ 下其他 package 是 agent-spine、ACP 和 JSON-RPC 组合架构参考。

## 工具

- `submit_plugin_metadata`：提交需求阶段的插件输入/输出 schema、块加箭头的执行过程，以及详细插件文档；创建 `packages/generated/<plugin-name>/`，并返回内存中的 `task_id` 和 `plugin_root`。
- prepare_plugin_reading：只接收该 `task_id`，将存储的元数据发给只读 Read Agent，并返回阅读清单。
- get_development_task：返回当前进程内 V3 task 的 metadata、阅读计划、文档、验证、验收、证据与错误。
- document_development：Main Agent 完成代码和本地检查后调用 Documentation Agent。
- verify_development：前台执行确定性的 typecheck/build/test/文档检查，并返回完整命令输出。
- start_acceptance、send_acceptance_message、stop_acceptance：运行和控制 fresh DSH 验收进程。
- discard_development：停止验收进程并删除任务专属 pluginRoot；新任务只能认领此前不存在的插件目录。

## 所有权与写入边界

验收通过前，普通任务只能永久写入 pluginRoot 和 Harness 管理的临时验收 YAML。
Read Agent 只负责调查并返回 JSON 阅读清单。Main Agent 根据清单读取真实仓库，负责业务源码、本地 build/test 和失败修复。Documentation Agent 只能
修改 pluginRoot 内的 README.md、README.zh.md、README.i18n.yaml，不能修改业务源码、
测试、package 配置或仓库根文件。

验收使用临时 composition 文件。验收失败后保留同一个 pluginRoot，Main Agent 可以
继续修复并重新验证。放弃任务时删除 pluginRoot 和临时验收资源。验收通过后删除
临时 YAML，再进入永久集成阶段；只有 DSH 实际需要时才允许修改根级集成配置。

## 完成条件

工程验证是证据，不等同于行为验收。完成任务还需要 fresh runtime 验收成功，以及
所需的用户验收交互；用户验收输入必须原样转发。

## Model Experience

Main Agent 能看到提交的 metadata、Read Agent JSON 阅读清单、任务事实、证据和工具目录，
根据清单读取真实仓库，并直接负责实现、本地命令和失败修复。Documentation Agent 作为一次性文档子任务接收
实现上下文，只能处理 README 三件套。

## Known Limitations and Deferred Work

文档检查验证结构和命令结果，但不判断翻译质量。V3 task 仅在当前 DSH 进程内有效；
进程重启后 task id 失效，但已创建的目录保留。

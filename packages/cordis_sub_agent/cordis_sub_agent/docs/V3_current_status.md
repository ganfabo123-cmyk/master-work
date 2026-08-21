# cordis_sub_agent V3 当前状态

本文记录 V3 工具化迁移的当前实现状态。V3 已不再保留旧版 V2 的持久化任务状态机。

## V3 目标

V3 不再由插件状态机强制 Main Agent 按固定顺序开发插件。插件提供阶段性工具，skill 说明各阶段应使用哪个工具；Main Agent 根据用户需求、仓库事实和工具返回结果决定下一步。

## 已连通的 V3 工具链

```text
submit_plugin_metadata
→ task_id + plugin_root
→ prepare_plugin_reading(task_id)
→ Read Agent JSON reading plan
→ Main Agent read / write / repair
→ document_development(task_id)
→ Documentation Agent
```

### submit_plugin_metadata

需求拆解提交工具接收：

- 插件名称与简要描述。
- 输入 schema 与输出 schema；每个字段都有 `name`、`type`、`required`、`description`。
- 由 blocks 和 arrows 表示的简要执行过程；每个 block 与 arrow 都有 `description`。
- 基于简要流程展开的详细插件文档。

工具会安全创建 `packages/generated/<plugin-name>/`，并返回：

- `task_id`
- `plugin_root`
- 已验证的 metadata

同一份记录仅保存在当前 DSH 进程的内存中，包含 `task_id`、`metadata`、`plugin_root`、阅读计划、文档结果、验证结果、验收关联与证据。进程退出后 task id 失效，但已创建的目录保留。

### prepare_plugin_reading

该工具只有 `task_id` 参数。它从 metadata task store 读取需求拆解结果，将其包装成 Reader Agent 的用户需求提示，并等待 Reader Agent 通过 `reader_conclusion` 返回：

- `mustRead`
- `recommendedRead`
- `confirmedFacts`
- `risks`
- `irrelevantOrAvoid`

它不创建骨架、不写插件代码、不运行 build/test；成功后会将阅读计划写回同一 V3 task。

### document_development

该工具也接受 metadata `task_id`。它从内存记录中取得 `plugin_root`，并将该目录作为既有 Documentation Agent 的工作目录。Documentation Agent 仍仅可修改：

- `README.md`
- `README.zh.md`
- `README.i18n.yaml`

它不能修改业务源码、测试、package 配置或仓库根配置。

## 已迁移的工程与验收工具

以下工具都接受 `submit_plugin_metadata` 返回的 V3 `task_id`：

| 工具 | 作用 |
| --- | --- |
| `verify_development` | 从 V3 task 取得 `plugin_root` 和插件名，执行工程检查，并保存完整验证结果与证据。 |
| `start_acceptance` | 仅消费 V3 task 中成功的验证产物；启动后记录 active `acceptance_id`。 |
| `stop_acceptance` | 通过 acceptance session 回查 V3 task，清除 active id 并记录验收结论与证据。 |
| `get_development_task` | 返回 V3 metadata、阅读计划、文档、验证、验收、证据与错误。 |
| `discard_development` | 停止 task 的 active acceptance，并删除由该 task 在创建时独占的 generated 目录。 |

`send_acceptance_message` 仍只依赖 `acceptance_id`，无需 task-id 迁移。

## 尚未提供专用封装的阶段

源码开发与修复目前仍由 Main Agent 使用普通读写和前台命令工具完成。V3 尚未提供独立的“开发实现工具”，也未要求新增一个强制编排器。

## 当前边界

V3 已从需求拆解连通到 real-host acceptance 与受管清理。它仍采用“仅内存”的 task 策略：DSH 重启后 task id 和运行中的 acceptance session 都不再可用，已创建的目录不会自动删除。目录在提交 metadata 时必须不存在，避免新 task 认领或删除既有 generated 插件目录。

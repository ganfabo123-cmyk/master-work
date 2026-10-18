# 三组实验恢复备份

- `initial-broken/`：供后续恢复的未修复故障代码。
- `managed-current/`：本次三个 managed 目录的原样副本；其中 epilog-tests 已含宏修复，不要用它恢复宏错误。
- `manifest.json`：每个文件的 SHA256、大小和来源。

恢复方法：先备份目标目录当前代码，再把 `initial-broken/<实验名>/` 中的文件覆盖到 `fixtures/<实验名>/managed/` 或 `baseline/`。恢复后新建 DSH 会话。
只覆盖备份包含的文件，不清空目标目录。依赖与构建产物未打包，沿用现有 node_modules 和工具链。插件 yml 按目标实验原配置保留，勿用 managed 配置覆盖 baseline。

预期故障：epilog-tests 编译出现 17 个宏重定义错误；epilog-solver 测试 18/22 通过、4 项失败；job-board 出现 14 个 TypeScript 错误。
当前操作未恢复或修改任何活动实验目录。

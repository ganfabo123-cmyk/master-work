# 可复现故障实验环境

三组均使用原始 trace 中的故障源码。baseline、managed 使用相同普通任务提示词；managed 额外接入 skill 管理系统。

| 环境 | 两组共用的提示词 | 正常入口 | 真实错误 |
| --- | --- | --- | --- |
| epilog-tests | 编译并运行 Epilog 的原子表测试。 | ./build.bat | _reg___LINE__ / _test_body___LINE__ 重定义 |
| job-board | 检查 Job Board 前端的 TypeScript 类型。 | npx tsc --noEmit | 原轨迹全部 14 条 TS1484、TS6133、TS2554 诊断 |
| epilog-solver | 构建并运行 Epilog 求解器测试。 | ./build.bat | 原始三处 expected dot / got operator dot 解析错误 |

每组目录为 `<name>/baseline` 和 `<name>/managed`。两组源码哈希一致，依赖和输出目录独立。managed 下的 skill-runtime-hint.cordis.yml 已指向各自独立的 skill-management-runs/<name>-managed/config.json。

例如在 epilog-tests/managed 启动 `pnpm dsh web --patch ./skill-runtime-hint.cordis.yml`；baseline 在对应目录执行 `pnpm dsh web`。

提示词不透露错误、修复方法或 skill。项目中没有 run_task、故障注入脚本、native/controlled 模式或预设成功分支。错误由真实工具产生。

## 验证范围

六个副本各正常执行三次，共 18 次，全部重现各自目标故障。Epilog 原编译输出被截断，仅保存六条原子测试诊断；这六条位置和错误文本全部匹配。本地完整输出是 17 条，不能声称原记录未保存的诊断也逐字一致。

临时应用原轨迹修复后，Job Board 完整类型检查退出 0；Epilog 原子测试编译前端检查退出 0，未验证完整链接和运行。两者已按字节恢复故障源码，保持实验初始状态。

未运行 DSH 模型实验，未验证 skill 推荐效果。源码出处、真实日志、验收结果均在 ../fixture-evidence/。

旧 Epilog exe 占用和 Iceberg 目录故障未通过指定错误验收，已移入 ../fixture-evidence/unaccepted-environments/，不用于本轮实验。

## 本轮替换 MyDatabase

MyDatabase 没有对应的 B-selected skill，已移出实验组。文件保存在 ../fixture-evidence/excluded-environments/mydatabase/；原位置有被旧会话占用的空目录，已经没有项目文件。

新增 epilog-solver/baseline、epilog-solver/managed，使用同一个普通提示词：构建并运行 Epilog 求解器测试。

目标错误为 `expected '.', got operator '.'`，对应 skill：

- fix-lexer-dot-followed-by-nonspace
- fix-lexer-dot-after-concatenated-literals
- preserve-separator-space-in-concatenated-prolog-fixture-strings

原始来源是 c99032e9… 第 1128 行。三条原始解析诊断及调试状态均逐字匹配（忽略原日志 ANSI 高亮）。源码不是人为改坏，而是原轨迹报错前的 Write/Edit 快照。

该原始快照完整运行结果为 18/22（4 FAILED）：三项失败来自此解析问题，另一项是原记录中独立存在的 assert 查询问题。临时应用原轨迹三处字符串修复后，解析错误消失、结果变为 21/22；不宣称整个求解器测试已经修复。故障源码随后按字节恢复。复现这个目标错误和完整修复测试套件是不同的验证范围。

当前三组：epilog-tests、job-board、epilog-solver。各组 managed 的配置和数据目录独立；两组工作区源码一致。当前三组故障复现结果见 ../fixture-evidence/validation.json，未运行 DSH 模型实验或验证实际推荐命中。

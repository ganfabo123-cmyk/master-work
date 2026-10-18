# 当前目标故障复现：PASS

当前三组为 epilog-tests、job-board、epilog-solver。六个副本各正常运行三次，共 18 次，均匹配原始记录中保存的目标错误。对应项目源码哈希一致。

验收：validation.json；日志：*-attempt-*.log；出处：*-sources.json。历史失败验收保留在 original-target-validation.json，没有覆盖成成功。

## 原案例调查

### Epilog exe 占用

c99032e9… 第 371 行报 LNK1105 / 1224；第 375 行停止 epilog，376 行同一编译命令成功。533–535 行再次出现这个对照。Windows 官方将 1224 定义为文件存在打开的用户映射节：
https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--1000-1299-

本轮 epilog-lock-diagnosis.json 验证：运行期间实际报 LNK1104，停止后退出 0。确认本机也受进程占用影响，但发生阶段和诊断不同。原记录未给出准确链接器版本和内核句柄快照，无法确定错误码差异的具体成因。此前文件映射、MSVC 14.44 / 14.50 的尝试也未稳定复现目标。这个案例不用于当前实验。

### Iceberg 缓存目录

860618e1… 第 80 行 typecheck 成功；84 行启动 dev 清理目录时报 ENOTEMPTY。92–94 行显示残留 +types 无法进入；98、109 行报 EPERM/scandir；119 行删除报 Access denied。106 行 takeown 提示文件系统不支持 ACL，未明确文件系统名称；不能断言是 FAT32/exFAT，也不能断言缺少 ACL 就是根因。

本机 D: 为 NTFS。普通打开目录句柄不阻止启动；delete-pending 状态产生 EPERM，未产生指定的最初 ENOTEMPTY。Node 22.20.0 也已试验。原模型尝试吞掉依赖内部的删除异常，但验证被用户中断，随后转用 SolidJS，不能当作原错误已经修复。原记录不足以确定造成不可访问目录的底层原因。这个案例不用于当前实验。

未通过的两个目录已移入 unaccepted-environments/；临时占用进程已停止。

## 新案例

### epilog-tests

原轨迹 c99032e9… 第 947 行。tests/test_framework.hpp 中 ##__LINE__ 未先展开再拼接，各个 TEST 因而得到相同标识符，导致重定义。源码恢复自原 Write/Edit。原输出被截断，六条已保存的原子表测试诊断的位置及文本全部匹配；本地完整输出 17 条，其余不能声称与缺失的原输出逐字一致。

### job-board

原轨迹 4130c9a7… 第 218 行。六条 TS1484（类型导入）、七条 TS6133（未使用变量）、一条 TS2554（React 19 useRef 缺少初值）。全部 14 条相对路径、行列、错误码和文本逐字匹配，无额外 TypeScript 错误。源码从原记录恢复，路由由真实 tsr CLI 生成，依赖用 package-lock.json 固定。tsconfig 未在原记录中出现，按原诊断恢复必要编译选项；不声称整机或依赖状态逐字节一致。

### mydatabase（本轮已移出实验组）

原轨迹 c84c0ad3… 第 241 行。Vite 8.0.14，原始组件的 PageView.svelte:171:2 和 PageList.svelte:106:2 均报 Expected a valid CSS identifier。

## 修复验证与范围

job-board-original-fix.json：临时应用原轨迹的 12 次 Edit 后，完整 tsc 退出 0。epilog-tests-original-fix.json：临时应用原轨迹宏修复后，原子测试编译前端检查退出 0，不代表完整链接或运行通过。两者已按字节恢复故障源码。

准备和验收脚本在本目录，不作为模型任务入口。新两组 managed 各有独立 config/data。未修改管理系统代码或阈值，未运行 DSH 模型对照实验，未验证推荐命中与模型修复能力。

## MyDatabase 替换记录

MyDatabase 虽能复现，但 35 个 B-selected skill 中没有对应内容，故本轮移出实验组。项目文件归档到 excluded-environments/mydatabase/。源目录因旧会话持有而留下空目录，没有残留项目文件。移除前验收在 validation-before-mydatabase-removal.json。

替代项 epilog-solver 从 c99032e9… 的第 1127 行命令之前恢复 .cpp/.hpp；1128 行原始诊断可核对。恢复工具为 restore_solver.py，源码出处在 epilog-solver-sources.json。普通入口 build.bat 仅执行原始编译命令并运行真实求解器测试，没有模式和故障注入。

直接对应 skill 是 fix-lexer-dot-followed-by-nonspace（及两个同类 skill）。三条解析错误和 DEBUG 状态与原记录逐字匹配，比较前仅移除原记录的 ANSI 高亮。原始快照另外含独立 assert 查询失败；完整运行是 18/22，并未隐藏这一项。

epilog-solver-original-fix.json 记录了临时应用原始第 1137、1148、1153 行 Edit 的结果：三项解析失败消除，测试为 21/22，剩余 assert 失败。这里仅验证目标错误可消除，未将完整测试套件标为通过。源文件已按字节恢复，临时修复产生的 exe 移出了模型工作区。

两个副本使用独立工作区；managed 使用 skill-management-runs/epilog-solver-managed/config.json 和独立 data，插件 overlay 已写好。管理系统代码和阈值没有修改。三组 base/managed 的当前故障验收仍以 validation.json 为准。

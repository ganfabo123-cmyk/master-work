# Skill 管理系统可行性实验数据

本文档记录三组 fixture 在 baseline 与 managed 两种处理方式下的成本和效果。
当前已录入 Job Board；Epilog 两组保留待补记录位。成本数据以运行界面截图为准，效果数据以实验报告为准。

## 记录口径

- **managed**：接入 skill 管理系统的实验。
- **baseline**：不接入 skill 管理系统的对照实验。
- **成本**：轮数、步数、LLM 用时、工具调用用时、首 token 平均耗时、生成速度、缓存命中率、输入 token、输出 token。
- **效果**：任务是否完成、验证命令及结果、错误是否消除、是否运行了运行时测试。
- 未提供或报告之间不一致的数据不补猜，标为“待核对”。

## 总表

| 实验组 | managed 成本 | baseline 成本 | managed 效果 | baseline 效果 | 状态 |
|---|---|---|---|---|---|
| Job Board | 2 轮 / 15 步；LLM 5m10s；工具 35.5s；首 token 9.4s；35 tok/s；缓存 94%；输入 583K；输出 5.9K | 3 轮 / 20 步；LLM 5m36s；工具 11.4s；首 token 4.7s；38 tok/s；缓存 95%；输入 510K；输出 9.3K | `npx tsc --noEmit`：0 错误，exit 0；报告称 14 个错误全部消除 | 报告称 `tsc --noEmit`：0 错误，exit 0；另称 Vitest 因沙箱 EPERM 无法启动 | 已录入，存在报告口径矛盾 |
| Epilog solver | 1 轮 / 20 步；LLM 14m14s；工具 35m24s；首 token 8s；37 tok/s；缓存 93%；输入 874K；输出 25.7K | 2 轮 / 20 步；LLM 16m26s；工具 8.8s；首 token 15s；27 tok/s；缓存 93%；输入 753K；输出 18.3K | 22/22 通过；修改测试输入拼接和 assert 深拷贝 | 22/22 通过；修改 lexer 和 assert 深拷贝 | 已录入；managed 工具时间含人工等待，不宜直接比较 |
| Epilog tests | 1 轮 / 15 步；LLM 4m54s；工具 13.3s；首 token 13.3s；40 tok/s；缓存 95%；输入 535K；输出 3.8K | 1 轮 / 14 步；LLM 7m45s；工具 10.3s；首 token 17.9s；35 tok/s；缓存 92%；输入 400K；输出 7.5K | 报告称原子表测试 17/17 通过；删除临时 exe 被拦截 | 修复 2 个文件后原子表测试 17/17 通过 | 已录入，需核对 managed 结果对应的源码/二进制版本 |

## Job Board

### 成本

#### managed

来源：运行界面截图 `C:\Users\Lenovo\AppData\Local\Temp\codex-clipboard-fb765e54-4a31-45c7-90b0-fa4aff0481c6.png`。

| 指标 | 数值 |
|---|---:|
| 轮数 | 2 |
| 步数 | 15 |
| LLM 用时 | 5m10s |
| 工具调用用时 | 35.5s |
| 首 token 平均 | 9.4s |
| 生成速度 | 35 tok/s |
| 缓存命中率 | 94% |
| 输入 token | 583K |
| 输出 token | 5.9K |

#### baseline

来源：运行界面截图 `C:\Users\Lenovo\AppData\Local\Temp\codex-clipboard-52e917fb-ec39-4e36-a6bf-2d070eb0d63f.png`。

| 指标 | 数值 |
|---|---:|
| 轮数 | 3 |
| 步数 | 20 |
| LLM 用时 | 5m36s |
| 工具调用用时 | 11.4s |
| 首 token 平均 | 4.7s |
| 生成速度 | 38 tok/s |
| 缓存命中率 | 95% |
| 输入 token | 510K |
| 输出 token | 9.3K |

### 效果：managed

实验报告结论：Job Board 前端 TypeScript 类型检查完成，`npx tsc --noEmit` 清零，exit 0，无错误输出；报告称原有 14 个错误全部消除，未新增错误。

报告列出的修复范围：

- `src/components/ui.tsx`：React 类型导入补 `type` 修饰符。
- `src/context/auth.tsx`：`ReactNode` 使用类型导入。
- `src/routes/__root.tsx`：移除未使用的 `Outlet`。
- `src/routes/auth/register.tsx`：移除未使用的 `Select`。
- `src/routes/employer/post-job.tsx`：移除未使用的 `user` 解构。
- `src/routes/jobs/$id.tsx`：移除未使用的 `BASE_URL`，清理 `applied` 状态相关代码。
- `src/routes/jobs/index.tsx`：移除未使用的 `Link` 和 navigate，并修正 `useRef` 初始化类型。

验证范围：

- 已做静态类型检查，报告称修复前后分别运行，结果从 14 个错误到 0 个。
- 未验证 dev server、登录、投递申请等运行时行为。
- 报告正文一处称“本次修改 6 个文件”，但列出的文件共有 7 个，待核对。

### 效果：baseline

提供的 baseline 报告包含两段结论：

- 一段称 Vitest 无法运行，原因是当前沙箱禁止 spawn 子进程（EPERM），Vite/Rolldown 无法启动；
- 另一段称类型检查 `tsc --noEmit` 已通过，结果为 0 错误、exit 0。

因此当前只确认报告中记录了“类型检查通过”的结果；Vitest 是否实际运行成功、以及 baseline 的完整验证范围，需要回看原始 trace 或运行日志后再定稿。

## Epilog solver

### 成本：managed

来源：运行界面截图 `C:\Users\Lenovo\AppData\Local\Temp\codex-clipboard-34cfefed-ea1e-4cfd-85a4-c8bc6d2eaed7.png`。

| 指标 | 数值 |
|---|---:|
| 轮数 | 1 |
| 步数 | 20 |
| LLM 用时 | 14m14s |
| 工具调用用时 | 35m24s |
| 首 token 平均 | 8s |
| 生成速度 | 37 tok/s |
| 缓存命中率 | 93% |
| 输入 token | 874K |
| 输出 token | 25.7K |

备注：本轮 managed 运行期间模型长时间等待用户回答，工具调用时间包含这段人工等待，不能作为正常工具执行耗时与 baseline 直接比较。

### 成本：baseline

来源：运行界面截图 `C:\Users\Lenovo\AppData\Local\Temp\codex-clipboard-baa1f6d5-6f00-4420-8640-d2300b133a58.png`。

| 指标 | 数值 |
|---|---:|
| 轮数 | 2 |
| 步数 | 20 |
| LLM 用时 | 16m26s |
| 工具调用用时 | 8.8s |
| 首 token 平均 | 15s |
| 生成速度 | 27 tok/s |
| 缓存命中率 | 93% |
| 输入 token | 753K |
| 输出 token | 18.3K |

### 效果：managed

报告结论：修改后完整构建并运行全部求解器测试，`22/22 PASS`，exit code 0。

修改内容：

- `tests/test_solver.cpp`：在 3 处相邻字符串拼接中补分隔空格，避免句点被拼成 operator；删除遗留 `[DEBUG two-body]` 输出。
- `engine/builtins.cpp`：`bi_assert` 将断言的 head/body 从 query arena 深拷贝到持久 clause arena，修复 assert 后的悬空引用。
- `build/tests/test_solver.exe`：重新生成的构建产物。

该方案保留 lexer 的既定行为，只修复测试输入和持久化生命周期问题。

### 效果：baseline

报告结论：修改后完整构建并运行全部求解器测试，`22/22 PASS`，exit code 0。

修改内容：

- `parser/lexer.cpp`：将句点统一识别为 `TOK_DOT`。
- `engine/builtins.cpp`：增加 `copy_for_assert`，将 assert 子句深拷贝到 clause arena。

报告称 `[DEBUG two-body] loaded=3` 为测试文件原有调试输出。该组改变了 lexer 行为，与 managed 的“修输入字符串”路径不同，因此两组虽然都通过，修复内容不能视为同一实现。

## Epilog tests

### 成本：managed

来源：运行界面截图 `C:\Users\Lenovo\AppData\Local\Temp\codex-clipboard-8834d3ec-3b0a-40f0-82a8-7a92cdf43110.png`。

| 指标 | 数值 |
|---|---:|
| 轮数 | 1 |
| 步数 | 15 |
| LLM 用时 | 4m54s |
| 工具调用用时 | 13.3s |
| 首 token 平均 | 13.3s |
| 生成速度 | 40 tok/s |
| 缓存命中率 | 95% |
| 输入 token | 535K |
| 输出 token | 3.8K |

### 成本：baseline

来源：运行界面截图 `C:\Users\Lenovo\AppData\Local\Temp\codex-clipboard-50a6ee99-e207-49d3-96da-917f17753418.png`。

| 指标 | 数值 |
|---|---:|
| 轮数 | 1 |
| 步数 | 14 |
| LLM 用时 | 7m45s |
| 工具调用用时 | 10.3s |
| 首 token 平均 | 17.9s |
| 生成速度 | 35 tok/s |
| 缓存命中率 | 92% |
| 输入 token | 400K |
| 输出 token | 7.5K |

### 效果：managed

报告称：原子表测试此前已经完成，结果为 `17/17 tests passed`，本轮未改变测试结果。模型尝试删除上一轮为主程序链接验证生成的临时文件 `build\epilog_check.exe`，但删除操作被保护策略拦截，因此停止尝试；该临时文件仍在磁盘上。

需要注意：当前报告没有提供本轮重新编译的完整输出。由于本实验目录刚从未修复备份恢复，managed 的“此前已通过”可能对应旧的构建产物或旧源码状态，需用当前源码重新运行 `build.bat` 后才能作为严格的 managed 效果证据。

### 效果：baseline

报告称：原子表测试最终 `17/17 tests passed`，exit code 0。baseline 从编译失败状态开始，修改了两个文件：

- `tests/test_framework.hpp`：增加两级宏拼接，使 `__LINE__` 正确展开，消除 17 个测试宏重定义错误；
- `build.bat`：原子表测试只链接 `internals/atoms.cpp`，避免与测试自身的 `main()` 发生 `g_verbose` 定义冲突。

验证范围：只完成原子表测试的完整编译和真实运行；其余 6 个测试未运行。该组结果证明 baseline 模型能够定位并修复原始编译阻塞，但它不再是“完全不修改代码”的纯运行对照。

## 后续补录字段

每组实验补录时至少需要：原始提示词、fixture 路径、managed/baseline 标识、成本截图或 trace、最终任务结果、验证命令及 exit code、运行时测试范围、skill 触发情况，以及异常或环境限制。

## 会话完成后的 Agent 定性评价

本轮三次会话结束后，Agent 对推荐 skill 的共同评价为：

- skill 质量高；
- 检索与管理机制巧妙；
- 推荐内容对完成任务有用。

同时反馈了当前系统的主要体验问题：

- 实际命中率偏低；
- 未命中的概率明显高于命中概率；
- 未命中时仍会频繁追加推荐提示，造成上下文打断；
- 纯文本提示不会阻塞任务执行，但会消耗模型注意力。

这部分是三轮会话后的定性反馈，尚未换算为正式命中率、未命中率或注意力成本数值。后续应结合 runtime 日志中的 `triggered`、`has_results`、`top_similarity` 和 hint 记录，分别统计“触发率、有效命中率、无结果率和提示开销”。

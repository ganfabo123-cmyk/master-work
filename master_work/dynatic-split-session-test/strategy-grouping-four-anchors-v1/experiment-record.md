# 测试、调用栈、配置修改、依赖变化：第一轮可行性实验

日期：2026-10-13。按用户要求实现四个简单策略、运行原始 30 个 Session 与 97 个切片、归档记录后停止。没有调用 LLM/embedding，没有派代理审查，没有生成 Skill。

## 输入与版本

- 通用程序：`error_clustering_experiment.py`，版本 `strategy-grouping-v2`。
- 实际原始输入：`C:/Users/35153/PycharmProjects/master-work/sessions`，使用既有清单选定的 29 个 JSONL 与 1 个 OpenCode JSON。
- 清单：`C:/Users/35153/PycharmProjects/master-work/vibecoding-trace-data-bundle/dynatic-split-session-test/context-expanded-sessions/index.json`。
- 切片：`C:/Users/35153/PycharmProjects/master-work/vibecoding-trace-data-bundle/dynatic-split-session-test/calibrated-confidence-length-banded-v3-slices`。
- 切片正文只使用 core 区间；工具输出及 cwd 从对应原始事件恢复。局部文件快照仅来自当前 Session/切片，不从其他切片借用历史内容。

## 四个简单规则

| 参数名 | 分组依据 | 纳入条件 |
|---|---|---|
| `test-case` | 项目/文件/类归属＋测试名称 | 实际具名失败，或 Write/Edit 改动文本中的具名测试定义 |
| `stack-site` | 异常类型＋完整抛出位置符号 | 实际工具运行输出中可解析的 Python、Java/JS 栈；去掉行号的分组影响 |
| `config-change` | 明确配置文件身份/声明 schema＋完整键路径 | 配置命名惯例的 JSON/JSONC/TOML，已观察到修改前后两份可解析快照 |
| `dependency-change` | 包管理体系＋完整包名 | npm、Cargo、PyPI 声明或 Gradle 坐标/插件版本的 Write/Edit 记录 |

符号、测试名、配置键、包名均从数据提取。预设的是日志/文件语法和通用命名格式，没有填写领域或 Skill 关键词词典。

测试不因为全套 PASS 给会话挂所有测试主题；没有可识别用例名的源码位置断言不强行归组。源码或成功负例测试里的异常栈不作为运行失败。配置不把任意 JSON 当配置，也不从孤立 Edit 片段猜完整键路径。依赖缺少修改前版本时明确标为未知。

## 运行结果

| 输入 | 策略 | 组数 | 命中成员 | residual | 多成员组 | 跨 Session 组 | 最大组 |
|---|---|---:|---:|---:|---:|---:|---:|
| 原始 30 | 测试 | 216 | 6/30 | 24 | 0 | 0 | 1 |
| 原始 30 | 调用栈 | 19 | 8/30 | 22 | 0 | 0 | 1 |
| 原始 30 | 配置修改 | 26 | 3/30 | 27 | 0 | 0 | 1 |
| 原始 30 | 依赖变化 | 23 | 5/30 | 25 | 0 | 0 | 1 |
| 切片 97 | 测试 | 216 | 10/97 | 87 | 1 | 0 | 2 |
| 切片 97 | 调用栈 | 19 | 11/97 | 86 | 0 | 0 | 1 |
| 切片 97 | 配置修改 | 26 | 3/97 | 94 | 0 | 0 | 1 |
| 切片 97 | 依赖变化 | 23 | 6/97 | 91 | 0 | 0 | 1 |

每侧合计 284 个策略组，但不能作为 284 项经验：不同策略可以关联同一事件，一条 Session 可以属于很多组。两套输入四类分组键均相同，处理上下文与快照完整度不一定相同。

### 测试口径

每侧 231 次命中中，207 次来自具名测试定义的写入/修改，24 次来自实际具名失败。216 是两类触发的合并键数，不是 216 个失败测试，也不是可用 Skill 数。

仅按解析支持的具名身份归组，因此没有识别所有测试报告、Java 注解测试或不具名 C++ 断言。测试身份在不同日志格式中的表示仍可能产生别名；不做模糊语义合并。

### 依赖口径

| 类型 | 原始命中 | 切片命中 |
|---|---:|---:|
| 旧版本未知的声明 | 18 | 18 |
| 明确版本变化 | 3 | 3 |
| 已观察前后快照中的新增 | 2 | 1 |
| 局部片段新增声明 | 0 | 1 |

23 个依赖组中，18 个来自旧状态未知的声明，不能说它们已经发生了版本升级。另 5 条有变化/新增记录；切片的一条新增仅能确认局部文本，不证明全项目此前未依赖这个包。未解析全部锁文件、所有包管理体系或安装命令。

### 当前观察边界

四类均生成了可以回溯的锚点记录。但原始侧全部是单 Session 组，切片侧仅一个测试组含同一 Session 的两个切片。**本轮尚未形成跨 Session 的共同候选组，不能据此声称发现可迁移 Skill 或满足贡献比例 X。**

目前结果更接近细粒度的证据索引。原因和可用性留待后续用户指定的审查；本轮不追加粗化、合并、标注或 LLM 提取。

## 归档结构

```text
strategy-grouping-four-anchors-v1/
  manifest.json
  summary.json
  README.md
  experiment-record.md
  validation.json
  strategy-details.json
  algorithm/
    error_clustering_experiment.py
    test_error_clustering_experiment.py
    snapshot.json
  sessions-30/
    input-units.json
    occurrences.jsonl
    test-case/           groups.json / residual.json / summary.json / report.md
    stack-site/          同上
    config-change/       同上
    dependency-change/   同上
  slices-97/
    同样四类产物
```

`groups.json` 保存全部成员、命中来源、附近事件引用和策略专属信息。配置有旧/新值，依赖有旧/新版本与操作口径，调用栈有帧列表，测试有触发方式与名称。Markdown 每组只展示部分证据，完整来源通过原始文件和事件指针回溯。

程序与测试快照已复制到 `algorithm/`，`snapshot.json` 保存 SHA-256。未改动已有错误分组或 Luna 审查目录。

## 验证

- 25 项测试通过，覆盖原有错误规则、注册/选策略、测试身份隔离、栈顺序、预期异常排除、完整配置路径、未知依赖基线等。
- 完整复跑的 39 个自动生成文件逐字节一致。
- 核验两侧 568 个组、569 条成员归属；组 ID 无重复，分组键与证据一致，成员/证据路径存在。
- 每个输入成员都在相应策略的某个组或 residual 中，不强迫入组。
- 这是结构和重复运行验证，不是语义质量、Skill 数量或实际召回率验证。

## 复现

从通用脚本所在目录执行，后续对照应使用新的 output 目录：

```powershell
python error_clustering_experiment.py `
  --expanded-sessions-dir C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\context-expanded-sessions `
  --slices-dir C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-slices `
  --raw-sessions-root C:\Users\35153\PycharmProjects\master-work\sessions `
  --output strategy-grouping-four-anchors-v1 `
  --strategies test-case stack-site config-change dependency-change
```

本轮只增加四个策略并运行、归档、记录；按用户要求到此停止，没有提交或推送。

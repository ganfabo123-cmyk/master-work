# 通用策略分组入口

实现文件仍是 [error_clustering_experiment.py](C:/Users/35153/PycharmProjects/master-work/dynamic-trace-segmentation-clustering/master_work/dynatic-split-session-test/error_clustering_experiment.py)，保留历史名称与调用接口。后续测试、调用栈、配置、依赖策略都在这个文件中增加函数，不另起实验脚本。

## 选择策略

从脚本所在目录执行：

```powershell
python error_clustering_experiment.py --list-strategies
```

当前已注册 `native-code`、`exception-type`、`message-template`。只运行前两种：

```powershell
python error_clustering_experiment.py `
  --expanded-sessions-dir C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\context-expanded-sessions `
  --slices-dir C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-slices `
  --raw-sessions-root C:\Users\35153\PycharmProjects\master-work\sessions `
  --output strategy-grouping-error-check `
  --strategies native-code exception-type
```

省略 `--strategies` 时，兼容旧命令，仍运行原有三种错误策略。取消消息模板的人工审查不等于删除其代码；需要排除生成时显式选择前两种。

策略名来自注册表，未知名称会报错；`--list-strategies` 不需要输入路径，也不读取数据。

## 增加函数及注册

每个策略函数接收整个 `unit`，返回若干命中记录：

```python
def strategy_new(unit):
    """写明该策略的分组依据。"""
    matches = []
    # 在这里遍历 unit["events"] 或关联多个事件。
    # 每次可靠识别后，追加如下记录：
    # matches.append({
    #     "group_key": 实际提取的分组键,
    #     "event_position": 锚点在 unit["events"] 中的零基位置,
    #     "evidence_line": 原文证据,
    #     "label": 可读名称,  # 可选，默认使用 group_key
    # })
    return matches


STRATEGY_REGISTRY["new-strategy"] = strategy_new
```

实现后即可使用 `--strategies new-strategy`。不需要修改 `scan()`、`group()`、`run()` 或命令行参数定义。上面仅是扩展接口说明，没有注册空壳测试/调用栈策略。

必需字段是 `group_key`、`event_position`、`evidence_line`。`event_position` 是列表位置，不是原始事件索引。函数可额外返回旧值、新值、版本、栈帧等 JSON 可序列化证据，通用流程会保留。

函数可读取：

- `unit_id`、`session_id`、`source_paths`。
- 每个事件的 `channel`、`text`、`tool_name`、`command`、`arguments`。
- 原始 `source_index`、`source_part_index`、文件路径及 JSON 指针。
- 整个事件序列，用于跨事件关联；工具结果可按现有方式从原始文件回填。

函数负责自己的过滤规则。错误策略使用的源码、PASS、Read/Search 等过滤不会先删掉其他策略可能需要的输入。策略应把输入视为只读数据。

## 通用流程负责什么

读取和回填 → 调用选定函数 → 附加来源与附近事件引用 → 按策略和 `group_key` 归组 → 输出报告、统计和 residual。

同一成员可以贡献多个键，也可以进入多个策略的组。未命中的成员保留在对应策略的 residual 中。相同键不自动证明相同 Skill，附近事件也不自动构成修复与验证链。

输出目录名称随实际输入数量生成，例如 `sessions-30`、`slices-97`；不再把输入数量锁死为 30/97。当前读取格式与双输入对照方式仍沿用既有数据包。

## 兼容性

- 历史 `detect()`、`scan()`、`run()` 的旧调用仍可用。
- 分组 ID 与错误识别规则保留。
- 输出新增通用 `group_key`；错误策略保留 `error_key` 别名，其他策略不用错误专属字段。
- 汇总新增 `group_key_comparison`；选择错误策略时仍保留对应 `error_key_comparison`。
- 未选中的策略函数不会执行，也不会为其生成目录。
- 使用新的 `--output` 目录进行对照，已有输出目录不会自动清除旧策略目录。因此同目录历史文件不能代替本次 `manifest.json` 的策略清单。

本轮仅把三种现有错误策略迁入通用入口，未实现测试、调用栈、配置修改或依赖变化识别。

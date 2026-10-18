# 通用策略分组

30 个 Session 与 97 个切片；运行策略：test-case, stack-site, config-change, dependency-change。

| 输入 | 策略 | 组数 | 有命中成员 | 多成员组 | 跨 Session 组 | 最大组 | 工具输出证据 |
|---|---|---:|---:|---:|---:|---:|---:|
| sessions-30 | test-case | 216 | 6/30 | 0 | 0 | 1 | 24 |
| sessions-30 | stack-site | 19 | 8/30 | 0 | 0 | 1 | 19 |
| sessions-30 | config-change | 26 | 3/30 | 0 | 0 | 1 | 0 |
| sessions-30 | dependency-change | 23 | 5/30 | 0 | 0 | 1 | 0 |
| slices-97 | test-case | 216 | 10/97 | 1 | 0 | 2 | 24 |
| slices-97 | stack-site | 19 | 11/97 | 0 | 0 | 1 | 19 |
| slices-97 | config-change | 26 | 3/97 | 0 | 0 | 1 | 0 |
| slices-97 | dependency-change | 23 | 6/97 | 0 | 0 | 1 | 0 |

分组允许重叠，不合并三种策略，也不强迫无错误命中的成员入组。JSON 保留全部命中的来源与上下文引用；单条证据展示最多 2000 字符，完整原文可回溯。Markdown 每组展示最多三个例子。

策略命中率不是准确率或 Skill 可用率。旧错误策略保留 error_key 别名，其他策略统一使用 group_key。

复现命令：

```powershell
python error_clustering_experiment.py --expanded-sessions-dir "C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\context-expanded-sessions" --slices-dir "C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-slices" --output "C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\strategy-grouping-four-anchors-v1" --strategies test-case stack-site config-change dependency-change --raw-sessions-root "C:\Users\35153\PycharmProjects\master-work\sessions"
```

`--list-strategies` 列出注册函数；`--strategies` 选择策略，省略时运行历史三种错误策略。

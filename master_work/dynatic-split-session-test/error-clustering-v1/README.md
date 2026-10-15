# 最小错误分组实验

30 个 Session 与 97 个切片，三种策略分别直接按错误键分组。

| 输入 | 策略 | 组数 | 有命中成员 | 多成员组 | 跨 Session 组 | 最大组 | 工具输出证据 |
|---|---|---:|---:|---:|---:|---:|---:|
| sessions-30 | native-code | 14 | 9/30 | 3 | 3 | 5 | 80 |
| sessions-30 | exception-type | 28 | 14/30 | 9 | 9 | 4 | 122 |
| sessions-30 | message-template | 159 | 19/30 | 8 | 8 | 5 | 194 |
| slices-97 | native-code | 14 | 13/97 | 3 | 3 | 9 | 80 |
| slices-97 | exception-type | 28 | 22/97 | 10 | 9 | 5 | 122 |
| slices-97 | message-template | 147 | 39/97 | 9 | 8 | 8 | 194 |

分组允许重叠，不合并三种策略，也不强迫无错误命中的成员入组。JSON 保留全部命中的来源与上下文引用；单条证据展示最多 2000 字符，完整原文可回溯。Markdown 每组展示最多三个例子。

策略的命中率不是准确率；异常类型可能过宽，消息模板可能过碎，同码也可能有多种修复。

复现命令：

```powershell
python error_clustering_experiment.py --expanded-sessions-dir "C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\context-expanded-sessions" --slices-dir "C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-slices" --output "C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\error-clustering-v1" --raw-sessions-root "C:\Users\35153\PycharmProjects\master-work\sessions"
```

如有原始文件，可追加 `--raw-sessions-root <目录>`，直接读取选定的 30 个 JSONL 并回填切片工具结果。

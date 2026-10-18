# 切分后恢复事件正文

记录日期：2026-10-14。

实现：[calibrated_confidence_segmentation.py](D:/PycharmProjects/CodeHarness/master_work/experiments/trace-segmentation/dynatic-split-session-test/calibrated_confidence_segmentation.py)。

## 处理顺序

切分依据与供下游阅读的内容分开处理：先沿用原有事件表示和切分规则，切完后按原始 `source_index`、`source_part_index` 补回 Tool Result 和 Thinking/Reasoning 正文。

已保存边界时，使用 `--reuse-segments`，直接重新导出原有切片，不重算边界，不读取 embedding 文件，也不调用 embedding 服务。复用模式只依赖 Python 标准库。原来计算新边界的模式仍使用已有 embedding 文件；指定原始轨迹参数时，也在计算边界之后才补正文。

恢复规则：

- Claude Code 的 Tool Result：恢复原始 `content`，保留结构化内容和 `is_error` 等结果字段，不截断。
- Thinking/Reasoning：正文恢复到 `text`，保留 signature 等原始辅助字段，不截断。
- OpenCode：调用及输出原本存放在同一 tool part；把完整 `state` 恢复到该事件的 `tool_result` 字段，不新增事件，从而保留原有坐标。
- 原始索引或 part 类型不匹配时直接报错，不猜内容。
- 切片边界、事件数量、顺序、类别、核心区及重叠区保持不变；其他事件按原投影保留。本步骤不是把原始轨迹的全部元数据重新展开。

原始内容按索引直接读取；报告记录原始文件位置和 SHA256，便于回查。没有另存一份重复的长正文。输出使用新目录，原切片及已有实验输入保持不变。

## 执行命令

从脚本目录执行：

```powershell
python calibrated_confidence_segmentation.py `
  --reuse-segments C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-segments.json `
  --raw-sessions-root C:\Users\35153\PycharmProjects\master-work\sessions `
  --source-report C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\toolcall-report.json `
  --output C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-full-content-segments.json `
  --output-dir C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-full-content-slices
```

此命令本次已执行，输出已存在；再次运行需换用新的输出路径。

## 本次产物与验证

- [恢复正文后的 97 个切片](C:/Users/35153/PycharmProjects/master-work/vibecoding-trace-data-bundle/dynatic-split-session-test/calibrated-confidence-length-banded-v3-full-content-slices)。
- [恢复后的切分报告](C:/Users/35153/PycharmProjects/master-work/vibecoding-trace-data-bundle/dynatic-split-session-test/calibrated-confidence-length-banded-v3-full-content-segments.json)。
- [原始来源与恢复统计](C:/Users/35153/PycharmProjects/master-work/vibecoding-trace-data-bundle/dynatic-split-session-test/calibrated-confidence-length-banded-v3-full-content-slices/payload-restoration.json)。
- [完整导出核查](C:/Users/35153/PycharmProjects/master-work/vibecoding-trace-data-bundle/dynatic-split-session-test/calibrated-confidence-length-banded-v3-full-content-slices/payload-verification.json)。

30 个 Session、97 个切片；按原始 part 去重共恢复 4,957 项：4,262 个 Tool Result、690 个 Thinking、2 个 Reasoning、3 个 OpenCode 工具状态。

逐切片核对边界、结构、事件顺序与原始坐标未变；恢复字段与对应原始 part 一致；97 个导出文件与报告一致。15 项测试通过（4 项正文恢复测试、11 项切片选择测试）。未计算新的 embedding，未重算切分边界，未恢复已停止的 LLM 对照实验。

后续切片选择脚本只需把 `--slices-dir` 指向本次新目录，即可选择包含正文的切片。

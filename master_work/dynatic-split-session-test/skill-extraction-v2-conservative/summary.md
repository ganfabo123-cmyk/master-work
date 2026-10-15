# Skill Extraction v2 Conservative — 三组汇总

你是一个 Skill 提取器。请只根据当前提供的轨迹内容，提取少量但真正可用的 Skill。目标不是覆盖尽可能多的内容，而是只保留能够指导其他类似任务的具体经验。一个 Skill 只有同时满足：轨迹有明确问题/触发条件/约束；有具体判断/决策/解决动作；不是简单读取/修改/运行/测试流水线；有可核对结果/验证方式/完成条件；去掉项目名、文件名和技术栈专有名词后仍可迁移。

三组输入独立处理；提取阶段不跨组去重，不调用 embedding。

| 组别 | 实际读取 | 缺失 | raw Skill | discarded | 覆盖 |
|---|---:|---:|---:|---:|---|
| A-session | 30 Session（另含 117 个分段 + 1 个 index/元数据文件） | 0 | 12 | 21 | 11 个来源 |
| B-slice | 97 切片 | 0 | 16 | 34 | 20 个来源 |
| C-domain | 314 次领域成员读取 | 0 | 43 | 327 | 8 个领域 |

总 raw Skill：71
总 discarded：382

## 实际读取范围

- A：读取 manifest 中全部 30 个 Session，并逐个读取其 context-expanded-sessions 下全部 118 个 JSON 文件（117 个 segment-*.json 与 1 个 index/元数据文件）；未读取其他实验组输入。
- B：递归逐个读取 97 个 segment-*.json（声明 97）；所属 Session 目录 30 个；不读取完整 Session 或领域输入。
- C：D001-D008 分别读取各自 domains.json members；不跨领域合并输入或去重。

## 产物

- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\A-session\analysis.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\A-session\analysis.md
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\B-slice\analysis.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\B-slice\analysis.md
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\summary.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\summary.md
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D001\analysis.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D001\analysis.md
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D002\analysis.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D002\analysis.md
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D003\analysis.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D003\analysis.md
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D004\analysis.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D004\analysis.md
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D005\analysis.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D005\analysis.md
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D006\analysis.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D006\analysis.md
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D007\analysis.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D007\analysis.md
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D008\analysis.json
- C:\Users\35153\PycharmProjects\master-work\dynamic-trace-segmentation-clustering\master_work\dynatic-split-session-test\skill-extraction-v2-conservative\C-domain\D008\analysis.md

可以，这 8 篇我按“直接 PDF 优先”给你整理一下。前几篇基本都能直接点开 PDF；个别 IEEE/ACM 的可能受校园网/机构权限影响，我给了官方页或可访问版本。

1. **D-Bot: Database Diagnosis System using Large Language Models** — PVLDB 2024
   [直接 PDF](https://www.vldb.org/pvldb/vol17/p2514-li.pdf?utm_source=chatgpt.com)
   这个就是你刚看完的那篇，正式 PVLDB 版本。([VLDB][1])

2. **DBA-Bench: A Production-Fidelity Benchmark for LLM-Based Database Operations Agents** — 2026
   [arXiv PDF](https://arxiv.org/pdf/2607.22165?utm_source=chatgpt.com)
   [arXiv 论文页](https://arxiv.org/abs/2607.22165?utm_source=chatgpt.com)
   目前是预印本，核心是 106 个真实风格数据库运维/诊断场景。([arXiv][2])

3. **DBPA: A Benchmark for Transactional Database Performance Anomalies** — SIGMOD 2023
   [ACM 官方 PDF](https://dl.acm.org/doi/pdf/10.1145/3588926?utm_source=chatgpt.com)
   [作者项目页 / Benchmark 代码](https://github.com/hjhhsy120/DBPA?utm_source=chatgpt.com)
   ACM PDF 可能需要校园网/机构权限；DBPA 本身定义了 9 类性能异常，而且代码和复现脚本是公开的。([Shiyue Huang][3])

4. **AutoSD: Explainable Automated Debugging via Large Language Model-driven Scientific Debugging** — EMSE 2025
   [Springer 直接 PDF（Open Access）](https://link.springer.com/content/pdf/10.1007/s10664-024-10594-x.pdf?utm_source=chatgpt.com)
   [作者 PDF 镜像](https://coinse.github.io/publications/pdfs/Kang2025sn.pdf?utm_source=chatgpt.com)
   这篇你下一篇就建议看它，是真正意义上的 hypothesis → experiment → observation → conclusion。

5. **OpDiag: Unveiling Database Performance Anomalies Through Query Operator Attribution** — TKDE 2025
   [IEEE 官方页](https://ieeexplore.ieee.org/document/10960743?utm_source=chatgpt.com)
   [可读 PDF 页面](https://www.modb.pro/doc/145287?utm_source=chatgpt.com)
   DOI 是 **10.1109/TKDE.2025.3557049**。这篇主要看它怎么把“数据库故障诊断”收敛成“异常指标 → query → operator”的具体定位问题。([墨天轮][4])

6. **DBSherlock: A Performance Diagnostic Tool for Transactional Databases** — SIGMOD 2016
   [作者主页直接 PDF](https://web.eecs.umich.edu/~mozafari/php/data/uploads/sigmod_2016.pdf?utm_source=chatgpt.com)
   这个链接是最干净的公开全文。([密歇根大学电子工程与计算机科学系][5])

7. **PinSQL: Pinpoint Root Cause SQLs to Resolve Performance Issues in Cloud Databases** — ICDE 2022
   [直接 PDF](https://openreview.net/attachment?id=hAgIuiTWVk4&name=pdf&utm_source=chatgpt.com)
   [IEEE 官方页](https://ieeexplore.ieee.org/document/9835371/?utm_source=chatgpt.com)
   OpenReview 这个就是完整论文 PDF，不是 slides。([OpenReview][6])

8. **ExpeL: LLM Agents Are Experiential Learners** — AAAI 2024
   [AAAI 官方 PDF](https://ojs.aaai.org/index.php/AAAI/article/view/29936/31635?utm_source=chatgpt.com)
   [AAAI 论文页](https://ojs.aaai.org/index.php/AAAI/article/view/29936?utm_source=chatgpt.com)
   这篇重点给你工作二看：experience pool、跨任务 insight extraction、experience recall。([AAAI Publications][7])

你现在如果按研究价值排，我建议阅读顺序直接定成：

**D-Bot（已读） → AutoSD → DBA-Bench → DBPA → DBSherlock → ExpeL → OpDiag → PinSQL。**

其中你下一篇**就看 AutoSD**。你刚刚已经把 D-Bot 提炼成“诊断路径空间上的搜索问题”，现在立刻看 AutoSD，正好可以判断你所谓的“假设—实验”到底和已有 Scientific Debugging 差在哪。

[1]: https://www.vldb.org/pvldb/vol17/p2514-li.pdf?utm_source=chatgpt.com "D-Bot: Database Diagnosis System using Large Language Models"
[2]: https://arxiv.org/pdf/2607.22165 "DBA-Bench: A Production-Fidelity Benchmark for LLM-Based Database Operations Agents"
[3]: https://hjhhsy120.github.io/publication/2023-dbpa?utm_source=chatgpt.com "DBPA: A Benchmark for Transactional Database Performance Anomalies - Shiyue Huang"
[4]: https://www.modb.pro/doc/145287?utm_source=chatgpt.com "TKDE2025_OpDiag_Unveiling_Database_Performance_Anomalies_Through_Query_Operator_Attribution_GoldenDB.pdf - 墨天轮文档"
[5]: https://web.eecs.umich.edu/~mozafari/php/data/uploads/sigmod_2016.pdf?utm_source=chatgpt.com "DBSherlock: A Performance Diagnostic Tool for"
[6]: https://openreview.net/attachment?id=hAgIuiTWVk4&name=pdf&utm_source=chatgpt.com "PinSQL: Pinpoint Root Cause SQLs to Resolve Performance Issues in Cloud Databases"
[7]: https://ojs.aaai.org/index.php/AAAI/article/view/29936/31635 "ExpeL: LLM Agents Are Experiential Learners"

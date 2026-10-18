# master_work 实验目录

本目录按“数据来源—实验代码—运行结果—报告与复现环境”分区。文件搬迁记录见 [RESTRUCTURE-MOVES-20261017.json](RESTRUCTURE-MOVES-20261017.json)。实验原文和运行快照均保留；归档导入数据单独存放，不覆盖本地版本。

## 目录导航

- `data/raw/agent-traces/`：Hugging Face 下载的原始轨迹数据。作为输入只读保留。
- `experiments/trace-segmentation/dynatic-split-session-test/`：动态切片、聚类分析代码、测试、方法说明及其历史版本结果。为保留旧脚本和产物之间已有的相对引用，项目内部结果目录保持原位；项目整体已从根目录归入切片与聚类主题区。
- 当前聚类主入口：`experiments/trace-segmentation/dynatic-split-session-test/strategy_clustering.py`。它按可插拔策略提取 `group_key` 后分组；错误码是默认典型策略，调用栈、测试用例、配置变化和依赖变化等策略通过同一入口选择。旧的 `error_clustering_experiment.py` 仅作为兼容模块保留。
- 当前端到端入口：`experiments/trace-segmentation/dynatic-split-session-test/trajectory_to_skills.py`。复制同目录的 `config.example.json` 为 `config.json` 后，直接运行 `python trajectory_to_skills.py`，结果写入配置的 `skills/` 输出目录。
- `experiments/trace-segmentation/runs/behavior-clustering/`：原来散落在根目录的聚类参数、候选和图版本结果；保留原目录名以对应旧记录。
- `experiments/trace-segmentation/imported/20261017/`：压缩包中的其他分支聚类实验数据，单独导入。
- `experiments/skill-management/`：`dynamic-retrieval-test/`（通用检索入口和 35 个 B 组 Skill）、`skill-management-system/`（管理系统源码与当前状态）、`runs/`（每个 fixture 独立的管理数据和配置）。检索程序与管理系统保持同级，配置中的相对路径仍有效。
- `experiments/skill-extraction/runs/`：本地 Skill 抽取运行结果，标准化目录为 `20261014-210632-local/`。外部分支原始 ZIP 保留在 `archives/imports/20261017/source/`；其解压副本与本地结果 2,128 个文件逐一 SHA-256 一致，已删除重复解压目录，导入清单仍保留。
- `experiments/retrieval-feasibility/`：可复现 fixture、备份、证据和已退役 fixture。
- `reports/`：实验总结、工作日志、方法说明和报告参考材料。
- `academic/`：开题报告及其评议材料。
- `archives/`：原始压缩包与数据包；`imports/20261017/source/` 保留用户提供的 RAR、其中两份 ZIP 和来源说明，`manifests/` 保存文件清单和来源总量，压缩包 SHA-256 记录在 `IMPORT-RECEIPT.json`。

## 运行入口

管理系统主目录：`experiments/skill-management/skill-management-system/`。

DSH 管理系统 overlay：仓库中的 `harness/deepseek-harness/skill-runtime-hint.cordis.yml`。三个复现环境的 cwd 位于 `experiments/retrieval-feasibility/fixtures/<fixture>/<managed|baseline>/`；对应独立运行配置位于 `experiments/skill-management/runs/<fixture>-managed/config.json`。运行配置明确写入新的语料、运行目录绝对路径，插件管理根路径也已同步更新。

## 来源与边界

- 20261017 RAR 原件仅复制归档，不改写；两个内含 ZIP 分别解压到聚类导入区和 Skill 运行导入区。
- 新旧来源并列保留，目录名带 `imported/日期` 的内容是外部分支快照，不和本地运行结果合并。聚类项目快照与本地项目有 599 个同路径同哈希文件、9 个同路径内容差异；压缩包独有 2,794 个文件，本地独有 1,885 个文件。Skill 运行快照与本地运行的 2,128 个文件逐一 SHA-256 一致。比较数字和归档哈希见 `archives/imports/20261017/IMPORT-RECEIPT.json`。
- `RESTRUCTURE-MOVES-20261017.json` 记录本次迁移前后路径。后续新增实验应放在对应 `experiments/<主题>/runs/` 下，并在该主题 README 或总目录登记输入与参数。

# 切片、聚类与 Skill 生成

本目录的主入口是 `trajectory_to_skills.py`：它把原始轨迹、动态切片、embedding、策略聚类和 Skill 提取串成一条流水线。历史实验脚本仍可单独运行，旧运行结果的目录结构不改。

## 运行

1. 复制 `config.example.json` 为 `config.json`，填入 embedding 和 Skill 提取服务配置。
2. 设置输入轨迹目录和输出目录。默认 embedding 比例为 `1.0`，即对全部轨迹做 embedding。
3. 在本目录执行：

```powershell
python trajectory_to_skills.py
```

不再从命令行传参数；运行时配置全部来自 `config.json`。配置文件已被 `.gitignore` 忽略，避免把密钥提交进仓库。

生成完成后，注册到管理系统：

1. 复制 `registry-config.example.json` 为 `registry-config.json`，确认上游输出目录、管理系统配置和 embedding 密钥环境变量。
2. 执行：

```powershell
python register_skills.py
```

注册器会在 `registered/runs/<batch-id>/` 中构造独立语料、索引、description 向量缓存和管理快照；`initialize`、`cluster`、`verify` 全部成功后，才激活管理系统配置。失败批次保留在该目录中，不切换当前管理快照。

## 流水线与 A/B/C

原始轨迹先被归一化为事件，再按 `embedding.ratio` 和固定 `seed` 选择轨迹并完成 embedding。随后动态切片读取这些 embedding，策略聚类对完整轨迹和切片分别运行，生成可回溯的分组证据。最后，聚类组进入 Skill 提取，主结果写入输出目录的 `skills/`。

`extraction.inputs` 可选择以下三种输入：

- `A`：原始完整轨迹。
- `B`：折叠后的原始轨迹，加上被选中的完整切片。
- `C`：只使用被选中的完整切片。

旧提取器内部仍使用 `A-original`、`C-context-collapsed`、`B-selected` 这些历史目录名，主入口会将它们映射回用户语义的 A/B/C，并把非主方案放在 `alternatives/` 下。

中间产物保存在 `output/stages/`，包括归一化轨迹、embedding、切片、聚类、提取输入和 API 审计结果；顶层 `manifest.json` 记录本次运行的配置摘要和各阶段路径。

外部分支快照单独放在 `../imported/20261017/`。原始轨迹统一从 `master_work/data/raw/agent-traces/sessions/` 读取。实验数据与代码路径入口见 `master_work/README.md`。

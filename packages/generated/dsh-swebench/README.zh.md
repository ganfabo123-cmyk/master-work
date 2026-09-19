[English](README.md) | 中文

# @deepseek-ai/dsh-swebench

将本地 SWE-bench Lite 用例的 Docker 运行时环境封装在三个高层工具加一个工作流技能之后，使 cotracer 之类的追踪型智能体可以像对待本地执行环境一样处理这些用例：用普通文件系统工具读取和编辑主机端用例仓库，通过 `swb_run` 在用例真实评测容器内运行任意命令或模型编写的测试脚本，并通过 `swb_eval` 用官方黑盒 FAIL_TO_PASS / PASS_TO_PASS 判定验证修复结果。

该插件负责全部 Docker 细节——镜像标签、只读绑定挂载、一次性 `--rm` 容器、conda 激活、`git apply --no-index` 与 CRLF 防御——模型无需接触它们。主机仓库是读写工作区；只有执行过程经由 Docker。

## 插件形式

函数插件，注册三个工具（`swb_list_cases`、`swb_run`、`swb_eval`）与一个运行时技能（`swe-bench`），通过 `cordis.yml` 组合。需要 `subprocess` 服务（运行 docker CLI）以及标准的 `tools` / `skills` 服务；dsh web 基础 profile 提供全部三个。

## 工具

### swb_list_cases

列出本地用例（来自基准的 `manifest.json`）：`instance_id`、主机仓库路径、基础提交、派生的评估镜像标签、该镜像是否已存在于本地，以及仓库的官方测试运行器（Astropy 用 `pytest`，Django 用 `runtests`）。

### swb_run

`swb_run(instance_id, command, workdir?)` 将主机仓库当前状态（包括智能体刚写入或编辑的文件）复制进容器，激活用例的 conda 环境，并在 `workdir`（默认 `/testbed`）中运行 `command`。返回完整的 `stdout`、`stderr` 和 `exit_code`。用它运行用例的测试、探针脚本，或任何针对真实环境的 Python / shell 命令。它从不触及官方的 gold 或测试补丁。

### swb_eval

`swb_eval(instance_id)` 运行官方的 SWE-bench 验证黑盒。在容器内，它获取该实例的官方 `test_patch`（用 curl，从不离开容器），以 CRLF 防御 + `git apply --no-index` 将其应用到复制的仓库，并通过仓库的官方运行器运行每一个 FAIL_TO_PASS 与 PASS_TO_PASS 节点。返回每组的结构化数量、失败的测试节点名称，以及 `resolved` 标志（所有 FAIL_TO_PASS 通过，且无 PASS_TO_PASS 回归）。测试源码与断言细节被刻意隐藏，以保持基准的诚实性；请改用 `swb_run` 调试你自己的脚本。

## 技能：swe-bench

`skills/swe-bench/SKILL.md` 描述了修复循环：阅读 issue、探索并编辑主机仓库、用 `swb_run` 复现与调试，然后以 `swb_eval` 验证，直到 `resolved: true`。该技能是一个普通运行时技能；追踪型智能体在识别出 SWE-bench 用例任务时加载它。

## 配置

```yaml
plugins:
  swebench:
    casesRoot: 'D:\PycharmProjects\CodeHarness\github_rep\swe-bench-lite-10'
```

`casesRoot` 是持有 `manifest.json` 的基准根目录；其默认值为上面的路径。注册表在每次工具调用时重建，因此更改 `casesRoot` 或更新 manifest 无需重载插件即可生效。

## 前置条件

- 从 dsh web 主机可访问的 Docker daemon，且已拉取用例评估镜像。镜像标签遵循官方约定 `swebench/sweb.eval.x86_64.<instance id with __ → _1776_>:latest`。
- 基准 manifest 位于配置的 `casesRoot`；每个用例仓库是一个 Windows git 分离头 worktree，检出在其 `base_commit`，且 `core.autocrlf=true`（CRLF 文件）。插件在容器内处理该布局：主机仓库以只读方式挂载于 `/host-testbed`，复制进 `/testbed`（排除 `.git`），补丁在 CRLF 防御后以 `git apply --no-index` 应用。
- `swb_eval` 需要容器侧对 SWE-bench 数据集端点的网络访问（主机可以离线）；`swb_run` 不需要任何网络。

## 模型体验

### 系统提示 / 工具

模型能看到三个工具 schema，并可加载 `swe-bench` 技能。没有 persona 部分；智能体保持自己的身份。

### Token 影响

固定成本是工具 schema。`swb_run` 返回完整命令输出（调试信息不截断）；`swb_eval` 仅返回数量与失败测试名称，因此一次较长的官方运行几乎不增加提示文本。

### KV Cache 影响

无固定前缀：插件不附加任何逐请求文本。

## 已知限制与待办工作

- 每次工具调用都会启动一个一次性容器：每次调用都有固定的冷启动开销，且较长的 `swb_eval` 运行（数十个测试节点）可能耗时数分钟。
- `swb_eval` 仅获取数据集端点的 10 行 Lite 页（offset 0, length 10）；该窗口之外的用例无法解析。
- 评测判定通过官方运行器的退出码按节点计数；集合级的不稳定（例如依赖环境的 Django locale）会被报告为失败节点而非重试。
- 测试节点逐个运行（astropy `pytest -q <node>`、Django `runtests.py <label>`）；整套运行尚未批处理。
- 主机仓库是唯一事实来源：容器内编辑永远不会写回（容器对主机挂载是只读的）；编辑必须在主机侧进行。
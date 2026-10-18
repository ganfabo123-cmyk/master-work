# CoWorker

一个面向学习、可迁移到任意领域的最小 Agent Harness 模板。它刻意只实现单 Agent 的完整闭环，不提前引入多 Agent、Memory、MCP Server、远程环境或复杂模型路由。

## 已有闭环

```text
Task → Agent → Prompt / Tools → LLMClient → Trace → Assistant Message
```

- `agents/`：每个 Agent 声明自己的 Prompt Builder、工具、Skill 候选和模型。
- `prompts/`：Prompt as Code；每个领域 Builder 自己构造系统提示词与用户提示词。
- `tools.py`：每个工具只定义为一个 `@tool` 函数，注册、schema、校验从函数推导。
- `skills/`：按需加载的工作流和验证说明；示例 Skill 不绑定任何业务领域。
- `llm.py`：模型协议的统一边界；内置 `DemoLLMClient` 用于学习与测试。
- `orchestrator.py`：只调度 `agent.run()`、创建 Trace Session 并返回类型化结果。
- `trace.py`：JSONL 是事实源，同时生成便于查看的 Markdown。

## 从原始轨迹生成并注册 Skills

仓库中的 Skill 生产流程位于
`master_work/experiments/trace-segmentation/dynatic-split-session-test/`。
它把原始 Agent 轨迹转换成可交给 Skill 管理系统使用的 Skill 集合，完整链路如下：

```text
原始轨迹
  → 轨迹读取与事件标准化
  → 按比例选择轨迹并生成 embedding
  → 动态切片
  → 按配置的聚类策略聚类
  → 构造 A/B/C 三种上下文
  → 提取 Skill
  → 输出生成结果
  → 注册层整理为管理系统可读取的 corpus
  → 生成索引和 Skill 描述 embedding
  → 调用管理系统 initialize / cluster / verify
```

### 两个阶段的职责

第一阶段由 `trajectory_to_skills.py` 完成。输入是目录中的 `.jsonl` 轨迹或 OpenCode `.json` 轨迹，程序会标准化事件、按配置比例选择轨迹、生成 embedding、切片、聚类并提取 Skill。默认对 100% 的轨迹做 embedding；比例可以在配置文件中调整。

聚类输入可以配置为三种方式：

- `A`：原始完整轨迹；
- `B`：原始轨迹加折叠后的切片上下文；
- `C`：只使用切片。

当前默认输出是 `C`，但三种结果都会保留在输出目录中，方便比较。聚类策略也在配置文件中选择，默认是当前主流程使用的 native-code 策略。

第二阶段由 `register_skills.py` 完成。它读取第一阶段的 `manifest.json` 和主 Skill 索引，把生成的 Skill 复制到一个带版本号的注册批次中，补齐管理系统需要的索引和描述 embedding，然后调用现有管理系统的命令完成初始化、聚类和校验。注册层不会修改管理系统源码；只有整个批次校验成功后，才会更新管理系统的活动配置。

### 使用方式

在仓库根目录执行：

```powershell
cd master_work/experiments/trace-segmentation/dynatic-split-session-test
copy config.example.json config.json
```

编辑 `config.json`，至少确认以下配置：

- `input`：原始轨迹目录；
- `output`：本次运行的输出目录；
- `embedding.api_key`：embedding 服务密钥；
- `embedding.ratio`：参与 embedding 的轨迹比例，默认 `1.0`；
- `clustering.strategy`：聚类策略；
- `extraction.inputs`：需要准备的输入分支，默认是 `A`、`B`、`C`；
- `extraction.primary_input`：最终主输出使用的分支，默认是 `C`；
- `extraction.api.api_key`：Skill 提取模型密钥。

配置完成后运行生成阶段：

```powershell
python trajectory_to_skills.py
```

生成结果主要位于：

- `output/skills/`：当前主流程生成的 Skill；
- `output/alternatives/`：其他 A/B/C 分支的结果；
- `output/stages/`：切片、聚类、提取等中间产物；
- `output/manifest.json`：本次运行的状态、主分支和产物索引。

确认生成结果后，配置注册层：

```powershell
copy registry-config.example.json registry-config.json
```

编辑 `registry-config.json`，确认 `source_output` 指向上一步的输出目录，
并确认 `manager_config` 和 `registry_root` 指向 Skill 管理系统的配置文件和注册目录。
注册阶段还需要设置 `DASHSCOPE_API_KEY`，用于生成管理系统所需的 Skill 描述 embedding。

运行注册：

```powershell
python register_skills.py
```

成功后可以在 `registry_root/runs/<batch-id>/` 查看版本化批次，在
`registry_root/ACTIVE.json` 查看当前激活批次。管理系统的 `config.json` 会被切换到这个已校验的批次；失败批次会保留用于排查，但不会被激活。

### 当前限制与排查入口

当前管理系统要求一个完整的 35 个 Skill corpus。注册层会严格校验 Skill 数量、索引字段、`B-selected` 分支标记和 embedding 维度；数量或格式不满足要求时会直接失败，不会静默丢弃或补齐 Skill。

更细的配置字段、产物格式和故障排查说明见
`master_work/experiments/trace-segmentation/dynatic-split-session-test/README.md`。

## 快速开始

```powershell
python -m pip install -e ".[dev]"
CoWorker
```

`CoWorker` 启动终端交互会话。输入问题与当前 Agent 持续对话，输入 `exit` 或 `quit` 退出；完整会话 Trace 写入 `traces/`。

恢复已有会话：

```powershell
CoWorker /resume session_YYYYMMDD_HHMMSS_xxxxxx
```

恢复会加载该 session 已记录的 Agent 消息历史，并继续追加到同一个 Trace。

## 用它创建新领域 Harness

1. 在 `src/coworker/prompts/` 增加该领域的 Prompt Builder。
2. 在 `src/coworker/tools.py` 或领域模块中增加唯一的 `@tool` 函数。
3. 在 `skills/<领域名>/SKILL.md` 写 Workflow 与 Validation。
4. 为真实模型实现 `LLMClient.generate()`；Runtime、Trace、Context 与 ToolRegistry 保持复用。

当确实出现跨任务记忆、远程环境或多 Agent 编排需求时，再在现有接口外添加；不要为未来假设预建平台。

## 真实示例：客服 Harness

客服示例的 Agent 声明位于 `src/coworker/agents/customer_service.py`，虚构知识库放在 `data/*.md`。真实模型根据问题决定是否调用 `search_customer_knowledge`，通用 Runtime 负责执行调用并保留 Trace。

客服 Agent 只维护自己的 Prompt Builder、工具名单和候选 Skill；对应 Prompt 与工具分别位于 `prompts/customer_service.py` 和 `tools.py`。新增领域 Agent 时，按同样方式新增一个 Agent 类即可。不存在客服专用运行入口或 CLI；所有 Agent 必须复用同一个通用 Runtime 入口。

# Harness 上层能力实现规范

## 1. 目标

本规范说明如何使用以下七项基础设施：

```text
Prompt
Tool / MCP
Skill
Trace
LLM 基础设施
Context 调度
Runtime
```

实现 Harness 常见的上层能力：

```text
Task
Agent
Environment / Workspace
Validation
Session / State
Memory
Result / Artifact
Multi-Agent Orchestrator
```

这些上层能力默认不需要各自建设独立框架。

核心原则：

> 上层能力应优先通过数据对象、Tool、Skill、Context 和 Runtime 组合实现，只有出现独立且复杂的确定性逻辑时，才拆成单独模块。

---

# 2. 基础设施与上层能力的关系

```text
Prompt
负责将任务和动态数据表达给模型。

Tool / MCP
负责模型对外部环境的真实操作。

Skill
负责描述一类任务的执行方法和验证条件。

Context
负责决定本轮调用实际向模型提供哪些信息。

LLM
负责统一调用模型并返回标准结果。

Runtime
负责驱动模型调用、工具执行、状态更新和终止判断。

Trace
负责记录整个执行过程。
```

上层能力只是这些基础设施的组合：

| 上层能力              | 主要由什么实现                         |
| ----------------- | ------------------------------- |
| Task              | 数据对象 + Prompt + Runtime         |
| Agent             | 配置对象 + Prompt + Runtime         |
| Environment       | Tool / MCP + Runtime 配置         |
| Validation        | Skill + Tool / Script + Runtime |
| Session / State   | Runtime State + Trace Session   |
| Memory            | Tool / MCP + Context            |
| Result / Artifact | Runtime 返回值 + Tool + Trace      |
| Orchestrator      | Runtime 组合 + Prompt + Context   |

---

# 3. 通用实现原则

任何上层能力都按照以下规则实现。

## 3.1 静态方法写在 Prompt 或 Skill 中

例如：

```text
如何分析任务
如何修复测试
如何验证结果
什么情况下检索记忆
什么情况下创建子任务
```

属于模型需要理解和执行的方法，应写在 Prompt 或 Skill 中。

## 3.2 真实操作写成 Tool

例如：

```text
读取文件
写入文件
执行命令
保存记忆
搜索记忆
创建子任务
读取任务结果
```

需要访问真实程序状态或产生副作用的能力，应写成 Tool。

每个 Tool 仍然只能有一个唯一的 `@tool` 函数。

## 3.3 外部能力通过 MCP 接入

如果能力由外部扩展提供：

```text
数据库
浏览器
远程代码环境
外部记忆服务
任务管理服务
```

应由 MCP Server 暴露，Skill 只说明什么时候使用相应 MCP Tool。

## 3.4 确定性控制写在 Runtime

例如：

```text
最大轮数
Tool Call 执行
错误重试
验证未通过时禁止结束
子任务执行顺序
任务状态切换
```

这些不能只写在 Prompt 或 Skill 中，必须由 Runtime 的普通代码控制。

## 3.5 动态信息进入 State，需要时再进入 Context

Runtime 可以保存完整状态，但 Context 只选择当前模型调用需要的信息。

禁止把整个 State 对象直接序列化给模型。

## 3.6 所有关键行为进入 Trace

上层能力不单独维护一份执行历史。

Task、Environment、Validation、Memory 和 Orchestrator 的实际行为都应转换成现有 Trace 事件，或者在现有事件的 `raw_content`、`parsed_content` 中记录。

---

# 4. Task 的实现

## 4.1 Task 是什么

Task 表示 Runtime 当前需要完成的目标。

最小形式可以只是一段字符串：

```python
task = "修复登录接口中的 Token 判断错误"
```

任务需要结构化信息时，可以使用简单数据对象：

```python
@dataclass(frozen=True, slots=True)
class Task:
    description: str
    inputs: dict[str, object]
    expected_result: str | None = None
```

不需要专门建设：

```text
Task Registry
Task 数据库
Task Service
Task 状态机框架
```

## 4.2 Task 如何进入 Harness

```text
Task
  ↓
Runtime 创建 AgentState
  ↓
Prompt Builder 接收必要字段
  ↓
Context Builder 组装本轮 messages
  ↓
LLM 执行
```

Prompt Builder 只接收实际需要的字段：

```python
prompt = implement_task(
    task=task.description,
    repository_context=repository_context,
    expected_result=task.expected_result,
)
```

不能直接传入完整 `Task` 或 `AgentState`，然后无差别注入全部内容。

## 4.3 Task 如何记录

任务级信息直接使用 Trace 中已有的：

```text
session_id
task
status
start_time
end_time
error
```

不需要再维护一份独立任务日志。

## 4.4 什么时候需要独立 Task 系统

只有出现以下需求时再增加：

```text
大量任务并发
任务持久化队列
复杂任务依赖
跨进程 Worker
任务取消和恢复
```

普通本地 Harness 不需要。

---

# 5. Agent 的实现

## 5.1 Agent 是配置，不是另一套框架

一个 Agent 可以表示为：

```python
@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    model: str
    prompt_builder: Callable[..., Prompt]
```

需要限制可用 Skill 或 Tool 时，可以增加：

```python
@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    model: str
    prompt_builder: Callable[..., Prompt]
    skill_names: tuple[str, ...] = ()
    mcp_servers: tuple[str, ...] = ()
```

这些字段只是引用已有能力，不重复定义 Prompt、Skill 或 Tool。

## 5.2 Agent 如何执行

所有 Agent 共用同一个 Runtime：

```python
result = await runtime.run(
    agent=coder_agent,
    task=task,
)
```

禁止为每个 Agent 单独实现：

```text
PlannerRuntime
CoderRuntime
ReviewerRuntime
```

不同 Agent 的差异应主要来自：

```text
Prompt Builder
模型选择
可用 Skill
可用 Tool / MCP Server
```

## 5.3 Agent 的动态信息

以下内容不属于 `AgentSpec`：

```text
当前消息
当前轮次
最近 Tool Result
当前错误
最终结果
```

这些属于 Runtime State。

---

# 6. Environment / Workspace 的实现

## 6.1 Environment 是真实操作目标

对于 Coding Harness，Environment 通常包括：

```text
项目根目录
当前工作目录
文件系统
命令执行环境
环境变量
Git 仓库
```

非生产级 Harness 不需要单独定义完整 Environment 框架。

## 6.2 最小表示

Runtime 启动时接收 Workspace 配置：

```python
@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path
    cwd: Path
```

它只负责保存当前执行位置。

## 6.3 Environment 操作全部通过 Tool

例如：

```text
read_file
write_file
list_files
search_code
run_command
git_diff
```

这些 Tool 内部根据当前 Workspace 执行操作。

模型不应直接操作：

```python
Path(...)
subprocess.run(...)
os.chdir(...)
```

模型只能产生 Tool Call。

## 6.4 远程环境通过 MCP

如果未来需要：

```text
Docker
远程服务器
浏览器
云端代码空间
```

可以接入相应 MCP Server：

```text
Agent
  ↓
MCP Client
  ↓
Remote Environment MCP Server
```

Skill 和 Runtime 不需要知道远程环境内部如何实现。

## 6.5 什么时候抽象 Environment 接口

只有需要在多种后端之间切换时再增加：

```python
class Environment(Protocol):
    ...
```

只有本地 Workspace 时，Tool 直接使用 Workspace 配置即可。

---

# 7. Validation 的实现

## 7.1 Validation 分为两部分

```text
验证方法
由 Skill 描述。

验证闭环
由 Runtime 强制执行。
```

Skill 中写：

```markdown
# Validation

只有以下条件全部满足时才能完成：

1. 原始失败测试通过；
2. 相关回归测试通过；
3. 没有新增静态检查错误。
```

## 7.2 验证操作通过 Tool 或 Script 执行

例如：

```text
run_command("pytest tests/test_login.py")
run_command("ruff check src/")
validate_json(...)
check_file_exists(...)
```

固定且复杂的验证逻辑可以放入 Skill 的 `scripts/`，通过现有命令 Tool 执行。

需要模型主动选择并传入结构化参数时，可以由 MCP Server 提供专用验证 Tool。

## 7.3 Runtime 负责禁止错误结束

Runtime 必须保证：

```text
模型声明完成
    ↓
检查是否已经得到要求的验证证据
    ├── 已得到：允许结束
    └── 未得到：继续执行或返回失败
```

不能只依赖模型说：

```text
“任务已经完成”
```

## 7.4 验证证据如何保存

验证证据直接来自已有 Tool Result：

```text
执行命令
退出码
stdout
stderr
生成文件
Schema 校验结果
```

这些结果已经进入 Trace，因此不需要再建设一份验证日志。

Runtime 只需要保存对应的 Tool Call ID 或 Tool Result 引用：

```python
validation_evidence_ids: list[str]
```

## 7.5 不需要独立 Validator 系统

只要满足：

```text
Skill 定义验证条件
Tool 执行验证操作
Runtime 检查验证是否完成
Trace 保存验证证据
```

就已经形成完整验证闭环。

---

# 8. Session 与 State 的实现

## 8.1 State 保存当前运行状态

最小状态：

```python
@dataclass(slots=True)
class AgentState:
    task: Task
    messages: list[Message]
    turn_count: int
    status: Literal[
        "running",
        "completed",
        "failed",
    ]
    final_result: object | None
    error: str | None
```

Runtime 直接修改该对象。

## 8.2 Trace 保存历史事实

```text
State
回答“现在运行到哪里”。

Trace
回答“之前实际发生了什么”。
```

State 可以修改和覆盖。

Trace 只能追加记录。

## 8.3 Session 不需要单独系统

现有 Trace 已经以 `session_id` 表示一次完整任务。

因此对于本地 Harness：

```text
Runtime State
+
Trace Session
=
完整 Session 能力
```

不需要额外建设：

```text
Session Manager
Session 数据库
Session Service
```

## 8.4 什么时候持久化 State

只有需要程序重启后继续执行时，才将 State 保存为：

```text
state.json
```

不需要恢复时，State 只存在于内存即可。

---

# 9. Memory 的实现

## 9.1 Memory 不是默认必需能力

只有需要跨任务保存信息时才实现，例如：

```text
项目固定事实
历史架构决定
用户偏好
过去任务经验
```

## 9.2 Memory 存储通过 Tool 实现

例如：

```python
@tool
def save_memory(...) -> ...:
    ...
```

```python
@tool
def search_memory(...) -> ...:
    ...
```

如果使用外部记忆服务，则由 MCP Server 暴露：

```text
memory.search
memory.save
memory.update
```

Memory Tool 仍然遵守统一工具规范，一个工具只有一个唯一函数。

## 9.3 何时读写记忆由 Skill 或 Runtime 决定

Skill 可以写：

```markdown
任务开始时，根据任务描述、相关文件和当前错误搜索历史经验。

任务验证通过后，只保存未来仍然可能复用的事实和经验。
```

确定性写入时机也可以由 Runtime 固定：

```text
任务结束
    ↓
执行 Memory 提炼
    ↓
调用 save_memory
```

## 9.4 记忆如何进入模型

Memory Tool 返回的全部内容不应自动放进 Prompt。

正确过程：

```text
Memory Tool 返回候选记忆
    ↓
Context Builder 选择相关记忆
    ↓
注入本轮 messages
```

Memory 负责保存和搜索。

Context 负责决定模型看到哪些记忆。

## 9.5 Trace 与 Memory 的区别

```text
Trace
保存完整、客观的执行事实。

Memory
保存提炼后、未来可能复用的信息。
```

可以根据 Trace 生成 Memory，但不能直接把完整 Trace 当成 Memory 注入模型。

---

# 10. Result 与 Artifact 的实现

## 10.1 Result 是 Runtime 的返回值

最小结果：

```python
@dataclass(frozen=True, slots=True)
class AgentResult:
    status: Literal[
        "completed",
        "failed",
    ]
    content: object | None
    error: str | None
    session_id: str
```

不需要复杂 Result 框架。

## 10.2 Artifact 是 Tool 产生的外部结果

例如：

```text
代码文件
Markdown 报告
JSON 数据
图片
测试日志
补丁文件
```

这些都由现有 Tool 写入 Workspace。

例如：

```text
write_file
copy_file
render_report
```

Skill 的 `assets/` 可以提供模板，Agent 通过 Tool 将其复制或填充到目标位置。

## 10.3 Result 如何引用 Artifact

Runtime 只需要返回文件路径：

```python
@dataclass(frozen=True, slots=True)
class AgentResult:
    status: str
    content: object | None
    artifact_paths: tuple[str, ...]
    error: str | None
    session_id: str
```

无需将整个文件内容复制进 Result。

## 10.4 Artifact 如何记录

文件创建和修改本身已经是 Tool Result，应进入 Trace。

因此不需要独立 Artifact 历史系统。

---

# 11. Multi-Agent Orchestrator 的实现

## 11.1 只有真正使用多 Agent 时才实现

单 Agent Harness 不需要 Orchestrator。

多 Agent Orchestrator 负责：

```text
任务拆分
Agent 选择
执行顺序
结果传递
最终汇总
```

## 11.2 Orchestrator 复用同一个 Runtime

```text
主 Runtime
    ↓
创建子 Task
    ↓
调用同一个 Runtime 执行子 Agent
    ↓
获取 AgentResult
    ↓
传回主 Agent
```

示例：

```python
planner_result = await runtime.run(
    agent=planner,
    task=planning_task,
)

coder_result = await runtime.run(
    agent=coder,
    task=Task(
        description="根据计划实现代码",
        inputs={
            "plan": planner_result.content,
        },
    ),
)
```

不需要单独实现第二套 Agent Loop。

## 11.3 任务拆分方式

语义拆分可以通过 Prompt：

```python
@prompt
def decompose_task(...) -> Prompt:
    ...
```

拆分结果使用 Pydantic 结构化输出：

```python
class SubTask(BaseModel):
    description: str
    agent_name: str
    dependencies: list[str]
```

确定性的依赖检查和执行顺序由 Orchestrator 普通代码完成。

## 11.4 Agent 之间如何传递信息

禁止默认传递另一个 Agent 的完整 State 和完整消息历史。

应传递：

```text
子任务描述
必要输入
结构化结果
Artifact 路径
验证证据摘要
```

这些内容由 Context Builder 注入目标 Agent。

## 11.5 多 Agent Trace

所有 Agent 共用同一个：

```text
session_id
```

每个 Agent 使用自己的：

```text
agent_name
```

现有 Trace 目录已经可以表达：

```text
session
├── planner.jsonl
├── coder.jsonl
└── reviewer.jsonl
```

不需要另一套多 Agent 日志格式。

---

# 12. 完整组合关系

```text
用户任务
    ↓
Task 数据对象
    ↓
Runtime 创建 State 和 Trace Session
    ↓
AgentSpec 选择 Prompt、模型和可用能力
    ↓
Skill 提供任务 Workflow 和 Validation
    ↓
Context 组装 Task、Skill、历史和必要 Memory
    ↓
LLM 返回文本、结构化结果或 Tool Call
    ↓
Tool / MCP 操作 Environment、Memory 和 Artifact
    ↓
Trace 记录模型与工具的真实执行
    ↓
Runtime 检查 Validation 和终止条件
    ↓
返回 AgentResult
```

多 Agent 时：

```text
Orchestrator
    ↓
创建多个 Task
    ↓
重复调用同一个 Runtime
    ↓
汇总多个 AgentResult
```

---

# 13. 最终实现原则

```text
1. Task 是数据，不是平台。

2. Agent 是配置，不是另一套 Runtime。

3. Environment 主要通过 Tool 或 MCP 操作。

4. Validation 由 Skill 描述、Tool 执行、Runtime 强制。

5. Session 由 Runtime State 和 Trace Session 共同实现。

6. Memory 由 Tool 存取、Context 注入，不直接修改 Prompt。

7. Artifact 由 Tool 生成，Runtime 只返回路径。

8. Orchestrator 只负责组合多个 Runtime 调用。

9. 所有真实副作用都必须经过 Tool 或 MCP。

10. 所有确定性控制流都必须写在 Runtime 或普通代码中。

11. 所有模型需要理解的方法都写在 Prompt 或 Skill 中。

12. 所有关键执行结果都进入现有 Trace。

13. 不因为一个能力有名字，就必须为它建设独立框架。

14. 只有当某项能力产生复杂、稳定且无法由现有基础设施表达的逻辑时，才升级为独立模块。
```

最终，一个非生产级 Harness 的上层能力，本质上只是：

```text
少量数据对象
+
一组 Tool / MCP 能力
+
若干 Skill 工作流
+
一个统一 Runtime
```

而不是在七项基础设施之外再建设八套平行系统。

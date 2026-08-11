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

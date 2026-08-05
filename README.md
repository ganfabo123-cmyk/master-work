# CodeHarness

一个面向学习、可迁移到任意领域的最小 Agent Harness 模板。它刻意只实现单 Agent 的完整闭环，不提前引入多 Agent、Memory、MCP Server、远程环境或复杂模型路由。

## 已有闭环

```text
Task → Prompt → Context → LLMClient → ToolRegistry → Runtime → Trace → AgentResult
```

- `prompts/`：Prompt as Code；每个逻辑提示词是一个函数。
- `tools.py`：每个工具只定义为一个 `@tool` 函数，注册、schema、校验从函数推导。
- `skills/`：按需加载的工作流和验证说明；示例 Skill 不绑定任何业务领域。
- `llm.py`：模型协议的统一边界；内置 `DemoLLMClient` 用于学习与测试。
- `context.py`：决定每轮真正发送给模型的 messages。
- `runtime.py`：唯一 Agent Loop，处理模型、工具、终止条件和验证证据。
- `trace.py`：JSONL 是事实源，同时生成便于查看的 Markdown。

## 快速开始

```powershell
python -m pip install -e ".[dev]"
python -m codeharness
pytest
```

演示不会调用外网或真实模型：第一次返回 `inspect_task` 工具调用，第二次返回最终文本。运行后可在 `traces/` 查看完整事实记录。

## 用它创建新领域 Harness

1. 在 `src/codeharness/prompts/` 增加该领域的 Prompt Builder。
2. 在 `src/codeharness/tools.py` 或领域模块中增加唯一的 `@tool` 函数。
3. 在 `skills/<领域名>/SKILL.md` 写 Workflow 与 Validation。
4. 为真实模型实现 `LLMClient.generate()`；Runtime、Trace、Context 与 ToolRegistry 保持复用。

当确实出现跨任务记忆、远程环境或多 Agent 编排需求时，再在现有接口外添加；不要为未来假设预建平台。

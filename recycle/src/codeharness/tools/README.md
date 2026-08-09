# 工具层

这里存放 Agent 自己拥有的工具实现。一个领域工具文件对应一个 Agent 的工具类；工具层只实现可观察动作和参数校验，不负责 Prompt、Agent 选择、ROOM 调度或最终回答。

## 目录职责

- `registry.py`：共享的 schema、参数校验和调用机制。
- `base.py`：`BaseAgentTools`，在实例化时接收 `agent_name`。
- `utils.py`：Markdown 检索、狼人杀动作构造等不直接暴露给模型的复用实现。
- `<agent_name>.py`：某个具体 Agent 的工具类，例如 `customer_service.py`、`werewolf_player.py`。

## 新增一个 Agent 工具文件

1. 新建与 Agent 对应的文件，例如 `tools/document_reviewer.py`。
2. 定义以 `Tools` 结尾的工具类，并继承 `BaseAgentTools`。
3. 工具类由 Agent 创建时传入 `agent_name`。工具方法内部使用 `self.agent_name`，不要把 `agent_name` 作为模型可调用参数。
4. 每个公开工具方法必须有 docstring、返回类型，以及 `Annotated[类型, Field(description=...)]` 形式的业务参数。
5. 将需要暴露给模型的绑定方法注册到该 Agent 自己的 `ToolRegistry`；不要把领域工具注册为全局默认工具。非公开实现放入 `utils.py`。
6. 在仓库根目录运行格式检查。

```python
from typing import Annotated

from pydantic import Field

from .base import BaseAgentTools


class DocumentReviewerTools(BaseAgentTools):
    def inspect_document(
        self,
        document_id: Annotated[str, Field(description="要检查的文档唯一标识。")],
    ) -> str:
        """读取当前 Agent 有权检查的文档摘要。"""
        return f"{self.agent_name} is inspecting {document_id}"
```

若某个 Agent 需要长期记忆，其工具类直接使用 `self.agent_name` 调用 `codeharness.memory` 的存取 API，并把存、列、取三个方法定义为该 Agent 的公开工具。

## 字段格式

每个公开工具方法的业务参数都必须使用明确类型和非空说明：

```python
outcome: Annotated[
    Literal["成功", "失败"],
    Field(description="经验结果，只能是 成功 或 失败。"),
]
```

不允许使用裸类型、`Any`、缺少 `Field`，或缺少 `description` 的参数。

## 格式检查

从仓库根目录执行：

```powershell
python -m codeharness.tools.check_tool_files
```

检查器会验证工具文件中的 `*Tools` 类、继承关系、公开工具方法的 docstring 与返回类型，以及每个业务参数的 `Annotated[类型, Field(description=...)]` 格式。

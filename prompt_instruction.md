# Agent App 提示词规范

## Prompt as Code：一个提示词对应一个函数

---

# 1. 提示词必须存放在函数中，并通过函数调用

## 1.1 核心原则

每个逻辑提示词都必须定义为一个独立的 Prompt Builder 函数：

```text
N 个逻辑提示词
=
N 个 Prompt Builder 函数
```

标准形式：

```python
@prompt
def plan_code_change(
    task: str,
    repository_context: str,
) -> Prompt:
    developer = """
    ...
    """

    user = f"""
    ...
    """

    return Prompt(
        messages=(
            Message(
                role="developer",
                content=developer,
            ),
            Message(
                role="user",
                content=user,
            ),
        )
    )
```

使用提示词时，直接调用对应函数：

```python
prompt = plan_code_change(
    task="增加原子文件写入功能",
    repository_context=repository_context,
)
```

提示词函数负责生成本次模型调用所需要的完整消息。

---

## 1.2 一个函数就是一个完整提示词

一个 Prompt Builder 函数中应当包含：

```text
提示词名称
动态参数
Developer Message
User Message
消息组装方式
```

对应关系如下：

| 信息       | 来源         |
| -------- | ---------- |
| 提示词名称    | 函数名        |
| 动态参数名称   | 函数参数名      |
| 动态参数类型   | 参数类型注解     |
| 固定提示词    | 函数体中的字符串   |
| 动态内容注入方式 | 函数体中的字符串组装 |
| 最终消息列表   | 函数返回值      |

例如：

```python
@prompt
def review_code(
    task: str,
    code: str,
) -> Prompt:
    developer = """
    # Role

    You are a code reviewer.

    # Task

    Review the supplied code against the requested task.
    """

    user = f"""
    # Requested task

    {task}

    # Code

    {code}
    """

    return Prompt(
        messages=(
            Message(
                role="developer",
                content=developer,
            ),
            Message(
                role="user",
                content=user,
            ),
        )
    )
```

---

## 1.3 不要把提示词拆成多个事实源

不推荐：

```python
REVIEW_PROMPT = """
You are a code reviewer.
"""


def build_review_prompt(
    task: str,
    code: str,
) -> Prompt:
    ...
```

也不推荐：

```text
代码中一份提示词
配置文件中一份提示词
数据库中一份提示词
远程 Prompt 平台中再维护一份
```

否则同一个提示词会分散在多个位置，修改时容易遗漏。

正确方式：

```python
@prompt
def review_code(
    task: str,
    code: str,
) -> Prompt:
    developer = """
    You are a code reviewer.
    """

    ...
```

提示词的完整定义始终可以通过一个函数直接找到。

---

## 1.4 按职责组织提示词文件

提示词可以按照 Agent 或功能拆分：

```text
app/
└── prompts/
    ├── planner.py
    ├── explorer.py
    ├── coder.py
    ├── reviewer.py
    └── summarizer.py
```

例如：

```python
# prompts/planner.py

@prompt
def plan_task(...) -> Prompt:
    ...
```

```python
# prompts/reviewer.py

@prompt
def review_change(...) -> Prompt:
    ...
```

不要把所有提示词都放进一个巨大的文件：

```text
all_prompts.py
```

也不需要为每一句提示词都创建单独文件。

通常一个 Agent 或一类相近职责对应一个文件即可。

---

# 2. 提示词必须支持动态参数注入

## 2.1 动态内容通过函数参数传入

提示词中的动态内容必须来自函数参数：

```python
@prompt
def summarize_document(
    document: str,
    requirements: list[str],
) -> Prompt:
    ...
```

调用时传入当前数据：

```python
prompt = summarize_document(
    document=document_content,
    requirements=[
        "保留核心结论",
        "使用 Markdown",
    ],
)
```

不要通过全局变量隐式读取动态数据：

```python
CURRENT_DOCUMENT = "..."


@prompt
def summarize_document() -> Prompt:
    user = CURRENT_DOCUMENT
```

这种形式无法从函数签名看出提示词依赖哪些数据。

---

## 2.2 所有动态参数必须具有类型注解

推荐：

```python
@prompt
def plan_task(
    task: str,
    repository_context: str,
    constraints: list[str],
    previous_error: str | None = None,
) -> Prompt:
    ...
```

不推荐：

```python
@prompt
def plan_task(
    task,
    repository_context,
    constraints,
):
    ...
```

类型注解能够明确：

```text
需要传入哪些数据
每个数据是什么类型
哪些参数可以为空
哪些参数具有默认值
```

---

## 2.3 参数名称必须表达真实含义

推荐：

```python
def review_code(
    requested_change: str,
    changed_code: str,
    repository_context: str,
) -> Prompt:
    ...
```

不推荐：

```python
def review_code(
    data1: str,
    data2: str,
    context: str,
) -> Prompt:
    ...
```

Prompt Builder 的函数签名本身就应该能够表达它依赖的数据。

---

## 2.4 不要把整个状态对象无脑传入

不推荐：

```python
@prompt
def plan_task(
    state: AgentState,
) -> Prompt:
    user = f"""
    {state}
    """
```

这样无法判断当前提示词真正使用了哪些字段，也容易把大量无关状态传给模型。

更推荐：

```python
@prompt
def plan_task(
    task: str,
    repository_context: str,
    constraints: list[str],
) -> Prompt:
    ...
```

由调用方选择当前提示词真正需要的数据：

```python
prompt = plan_task(
    task=state.task,
    repository_context=state.repository_context,
    constraints=state.constraints,
)
```

Prompt Builder 只接收自己实际需要的参数。

---

## 2.5 简单字符串直接注入

对于短文本，可以直接使用 f-string：

```python
user = f"""
# Task

{task}
"""
```

对于多个动态参数：

```python
user = f"""
# Repository context

{repository_context}

# Constraints

{constraints}

# Requested change

{task}
"""
```

---

## 2.6 复杂数据先转成稳定文本

当参数是列表、字典或其他结构时，应先转换成清晰文本。

例如：

```python
import json


constraints_text = json.dumps(
    constraints,
    ensure_ascii=False,
    indent=2,
)
```

然后注入：

```python
user = f"""
# Constraints

{constraints_text}
"""
```

也可以提供一个简单工具函数：

```python
import json
from typing import Any


def data_block(
    name: str,
    value: Any,
) -> str:
    if isinstance(value, str):
        content = value
    else:
        content = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )

    return (
        f"<{name}>\n"
        f"{content}\n"
        f"</{name}>"
    )
```

使用：

```python
user = f"""
# Repository context

{data_block(
    "repository_context",
    repository_context,
)}

# Constraints

{data_block(
    "constraints",
    constraints,
)}

# Requested change

{data_block(
    "task",
    task,
)}
"""
```

标签的作用只是区分不同数据区域，不需要把它设计成复杂协议。

---

## 2.7 动态参数只注入必要内容

不要因为某段信息可能有用，就把所有信息都塞入提示词。

例如 Planner 只需要：

```text
任务
相关仓库上下文
实现约束
```

就不要额外传入：

```text
完整聊天记录
所有历史任务
无关文件
其他 Agent 的全部内部状态
```

Prompt Builder 的参数越明确，最终提示词越容易阅读和维护。

---

# 3. 消息必须分层

## 3.1 基础消息类型

本地 Agent App 至少区分：

```text
Developer Message
User Message
Assistant Message
```

定义示例：

```python
from dataclasses import dataclass
from typing import Literal


PromptRole = Literal[
    "developer",
    "user",
    "assistant",
]


@dataclass(frozen=True, slots=True)
class Message:
    role: PromptRole
    content: str


@dataclass(frozen=True, slots=True)
class Prompt:
    messages: tuple[Message, ...]
```

一般 Prompt Builder 最常使用：

```text
Developer Message
+
User Message
```

---

## 3.2 Developer Message 放稳定规则

Developer Message 用于放相对稳定的提示词内容：

```text
Agent 的职责
本次组件的任务
固定行为规则
工具使用原则
完成要求
输出要求
稳定示例
```

例如：

```python
developer = """
# Role

You are the planning component of a coding agent.

# Task

Produce an implementation plan for the requested change.

# Rules

- Base the plan on the supplied repository context.
- Identify affected files.
- Produce ordered implementation steps.
- Do not modify code.
"""
```

Developer Message 不应该随着每次调用大幅变化。

---

## 3.3 User Message 放动态任务和数据

User Message 用于放当前调用产生的动态内容：

```text
用户本次任务
当前代码
仓库上下文
文档内容
检索结果
当前错误
动态约束
上一步结果
```

例如：

```python
user = f"""
# Repository context

{repository_context}

# Constraints

{constraints}

# Requested change

{task}
"""
```

每次调用 Prompt Builder 时，User Message 可以根据参数重新生成。

---

## 3.4 Assistant Message 只用于必要的对话前缀

大多数单次 Agent Prompt 不需要预先构造 Assistant Message。

只有确实需要提供历史回答、Few-shot 对话或继续生成前缀时才使用：

```python
Message(
    role="assistant",
    content="...",
)
```

不要为了形式完整，固定给每个 Prompt 添加空的 Assistant Message。

---

## 3.5 固定规则与动态数据不要混在一起

不推荐：

```python
developer = f"""
You are a coding agent.

Current task:

{task}

Repository content:

{repository_context}
"""
```

这里把固定规则和动态数据全部混进了同一个消息。

推荐：

```python
developer = """
You are a coding agent.

Produce an implementation plan from the supplied task
and repository context.
"""

user = f"""
# Repository context

{repository_context}

# Requested task

{task}
"""
```

这样能够直接区分：

```text
哪些内容是提示词规则
哪些内容是本次输入
```

---

## 3.6 消息顺序

推荐顺序：

```text
Developer Message
    ↓
必要的 Few-shot Messages
    ↓
User Message
```

例如：

```python
return Prompt(
    messages=(
        Message(
            role="developer",
            content=developer,
        ),
        Message(
            role="user",
            content=user,
        ),
    )
)
```

对于具有 Few-shot 示例的提示词：

```python
return Prompt(
    messages=(
        Message(
            role="developer",
            content=developer,
        ),
        Message(
            role="user",
            content=example_input,
        ),
        Message(
            role="assistant",
            content=example_output,
        ),
        Message(
            role="user",
            content=current_input,
        ),
    )
)
```

只有在示例确实需要表现对话关系时，才使用多条 User 和 Assistant Message。

---

# 4. 提示词应该怎么写

## 4.1 默认结构

一个普通 Agent Prompt 默认使用以下结构：

```text
Role
Task
Rules
Output
```

根据实际需要，可以增加：

```text
Tool use
Completion criteria
Examples
```

不要求每个提示词机械地包含所有章节。

最小模板：

```python
developer = """
# Role

说明当前 Agent 或组件负责什么。

# Task

说明模型本次必须完成什么任务。

# Rules

说明真正影响结果的行为规则。

# Output

说明最终需要返回什么内容。
"""
```

---

## 4.2 Role：说明组件职责

Role 用于告诉模型当前组件是什么、负责什么。

推荐：

```text
You are the planning component of a coding agent.
```

```text
You review code changes against the requested task.
```

```text
You extract repository information required by another agent.
```

不推荐：

```text
You are the world's greatest programmer.
```

```text
You are a genius AI with unlimited intelligence.
```

Role 的目标不是给模型编写复杂人设，而是明确职责范围。

一个好的 Role 应该回答：

```text
这个组件是谁？
它在整个应用中负责哪一部分？
```

---

## 4.3 Task：说明唯一主要任务

Task 应该清楚描述当前 Prompt 需要产生什么结果。

推荐：

```text
Produce a concrete implementation plan for the requested code change.
```

```text
Review the supplied implementation and identify functional problems.
```

```text
Summarize the supplied document while preserving its main conclusions.
```

不推荐：

```text
Help the user.
```

```text
Handle this request.
```

```text
Analyze the information.
```

这些描述无法明确模型最终需要做什么。

一个 Prompt 最好只有一个主要任务。

例如：

```text
生成实现计划
```

而不是同时要求：

```text
分析需求
搜索仓库
设计架构
修改代码
运行命令
修复错误
审查代码
生成总结
```

如果职责明显不同，应拆成不同 Prompt Builder。

---

## 4.4 Rules：只写真正影响行为的规则

Rules 用于补充模型完成任务时必须遵守的要求。

推荐：

```text
- Base the plan on the supplied repository context.
- Identify the files that require changes.
- Produce the steps in execution order.
- Preserve the existing public API.
```

这些规则描述了可观察的行为。

不推荐：

```text
- Think carefully.
- Be smart.
- Be professional.
- Use best practices.
- Give a high-quality answer.
```

这些要求过于抽象，模型无法从中判断具体应该怎样改变结果。

规则应该尽量满足：

```text
具体
可执行
与当前任务直接相关
不会和其他规则冲突
```

---

## 4.5 使用正向指令

优先告诉模型应该做什么：

```text
Return only the final implementation.
```

比大量使用否定表达更直接：

```text
Do not explain.
Do not summarize.
Do not add notes.
Do not include reasoning.
```

需要禁止某种明确错误时，可以使用否定规则：

```text
Do not invent file names that are absent from the supplied context.
```

但不要让整个 Prompt 变成几十条“不要做什么”。

---

## 4.6 避免重复和强调堆叠

不推荐：

```text
You must return only the result.

Do not return anything except the result.

It is extremely important that you return only the result.

Again, only return the result.
```

推荐：

```text
Return only the final result.
```

同一规则通常写一次即可。

反复使用：

```text
必须
务必
绝对
再次强调
非常重要
```

不会自动提升提示词效果，只会增加冗余。

---

## 4.7 Tool use：只说明何时使用工具

只有当前 Prompt 确实拥有工具时，才增加 Tool use。

例如：

```text
# Tool use

- Inspect repository files when the supplied context is insufficient.
- Use targeted searches before reading large files.
- Run shell commands only when execution evidence is required.
```

这里说明的是工具使用策略。

不要在提示词中重新描述工具定义：

```text
read_file 接受 path:string 参数。
grep 接受 pattern:string 和 directory:string 参数。
```

工具自身的信息应由工具定义提供。

---

## 4.8 Completion criteria：复杂 Agent 可写完成条件

对于需要自主执行多步任务的 Agent，可以明确什么时候算完成。

例如：

```text
# Completion criteria

The task is complete when:

- the requested change has been implemented;
- all affected files have been updated;
- the final response summarizes the completed changes.
```

对于简单任务，不需要机械添加 Completion criteria。

例如摘要 Prompt：

```text
Summarize the supplied article in three paragraphs.
```

已经足够明确，就不需要再写一整段完成条件。

---

## 4.9 Output：说明返回内容，不设计数据结构

Output 部分只说明模型最后应该返回什么。

文本结果：

```text
# Output

Return a concise Markdown summary.
```

代码结果：

```text
# Output

Return only the final Python code.
```

审查结果：

```text
# Output

List each identified problem with its location, reason,
and recommended correction.
```

计划结果：

```text
# Output

Return an ordered implementation plan.
```

输出的数据结构如何定义、如何校验，不属于本提示词规范。

Prompt 只需要说明：

```text
结果包含什么
结果给谁使用
结果使用什么基本表达形式
```

---

## 4.10 Examples：只有必要时才添加

Few-shot 示例适合解决：

```text
分类边界不清楚
任务规则难以用一句话解释
输出风格非常固定
模型经常误解某种特殊情况
```

例如：

```text
# Example

Input:
Rename a private helper function.

Expected behavior:
Update the function definition and all internal references,
but do not modify the public API.
```

不要为了让 Prompt 看起来专业，给所有提示词都添加大量示例。

优先顺序应该是：

```text
先写清楚 Role、Task 和 Rules
    ↓
实际使用
    ↓
发现稳定误解
    ↓
再针对误解补充示例
```

---

## 4.11 长上下文的写法

当 User Message 中包含大量代码或文档时，推荐顺序：

```text
上下文
    ↓
约束
    ↓
最终任务
```

例如：

```python
user = f"""
# Repository context

{repository_context}

# Constraints

{constraints}

# Requested change

{task}

Based on the context above, produce the implementation plan.
"""
```

将最终任务放在长上下文后面，可以再次提醒模型当前要解决的问题。

不同内容之间使用明确标题：

```text
# Repository context
# Current implementation
# Previous error
# Constraints
# Requested change
```

不要把所有内容直接连续拼接成一大段无结构文本。

---

## 4.12 提示词使用 Markdown 分层

推荐使用 Markdown 标题表达结构：

```text
# Role
# Task
# Rules
# Tool use
# Output
```

列表使用：

```text
- ...
- ...
- ...
```

顺序步骤使用：

```text
1. ...
2. ...
3. ...
```

不要依赖大量特殊符号、重复分隔线或复杂自定义语法。

目标是让开发者直接阅读最终 Prompt 时，也能快速理解其结构。

---

## 4.13 Prompt 不负责程序控制流

不要在提示词中编写复杂状态机：

```text
如果第一次失败，则重新尝试。
如果第二次失败，则调用另一个 Agent。
如果第三次失败，则切换模型。
如果达到五次，则终止。
```

确定性的流程应该写在普通代码中。

Prompt 只负责模型需要进行语义判断的部分，例如：

```text
当前实现是否满足需求
应该修改哪些代码
当前错误最可能由什么导致
现有上下文是否足以做出判断
```

原则：

> 能由普通代码稳定表达的流程，不要只写在提示词里。

---

## 4.14 Prompt 应该保持最小化

先写能够完成任务的最小 Prompt：

```text
Role
Task
必要 Rules
Output
```

只有发现实际问题时，再增加：

```text
更具体的规则
工具策略
完成条件
示例
```

不要在项目开始时就写一个几千 Token 的通用超级 Prompt。

每增加一段内容，都应该能够回答：

```text
它解决了什么具体问题？
删除它之后会发生什么明确错误？
```

如果无法回答，就可能不需要这段内容。

---

# 5. 标准示例

```python
from dataclasses import dataclass
from textwrap import dedent
from typing import Literal


PromptRole = Literal[
    "developer",
    "user",
    "assistant",
]


@dataclass(frozen=True, slots=True)
class Message:
    role: PromptRole
    content: str


@dataclass(frozen=True, slots=True)
class Prompt:
    messages: tuple[Message, ...]


def prompt(fn):
    return fn


@prompt
def plan_code_change(
    task: str,
    repository_context: str,
    constraints: list[str],
) -> Prompt:
    developer = dedent(
        """
        # Role

        You are the planning component of a coding agent.

        # Task

        Produce a concrete implementation plan for the
        requested code change.

        # Rules

        - Base the plan on the supplied repository context.
        - Identify the files or modules that require changes.
        - Produce the implementation steps in execution order.
        - Consider the supplied constraints.
        - Do not modify code.

        # Output

        Return an ordered implementation plan.
        """
    ).strip()

    constraints_text = "\n".join(
        f"- {constraint}"
        for constraint in constraints
    )

    user = dedent(
        f"""
        # Repository context

        {repository_context}

        # Constraints

        {constraints_text}

        # Requested change

        {task}

        Based on the context and constraints above,
        produce the implementation plan.
        """
    ).strip()

    return Prompt(
        messages=(
            Message(
                role="developer",
                content=developer,
            ),
            Message(
                role="user",
                content=user,
            ),
        )
    )
```

调用：

```python
built_prompt = plan_code_change(
    task="为文件写入增加原子替换能力",
    repository_context=repository_context,
    constraints=[
        "不能修改公共 API",
        "需要兼容 Windows",
    ],
)
```

模型调用层直接使用：

```python
built_prompt.messages
```

---

# 6. 最终规范

本地 Agent App 的提示词统一遵守以下规则：

```text
1. 一个逻辑提示词对应一个 Prompt Builder 函数。

2. 提示词的完整内容必须能够从一个函数中找到。

3. 提示词通过调用函数生成，不通过读取全局字符串生成。

4. 动态数据只能通过函数参数显式传入。

5. 所有动态参数必须具有明确的类型注解。

6. Prompt Builder 只接收当前提示词真正需要的数据。

7. 固定职责和规则放入 Developer Message。

8. 当前任务和动态上下文放入 User Message。

9. Assistant Message 只在 Few-shot 或对话前缀确实需要时使用。

10. Prompt 默认采用 Role、Task、Rules、Output 结构。

11. Tool use、Completion criteria 和 Examples 按需添加。

12. Role 只说明组件职责，不编写无意义人设。

13. Task 必须描述模型需要产生的明确结果。

14. Rules 必须具体、可执行并与当前任务直接相关。

15. 避免模糊规则、重复强调和无意义修饰。

16. Output 只说明需要返回什么内容。

17. 长上下文使用明确标题分区，最终任务放在上下文后面。

18. 使用 Markdown 标题和列表保持提示词可读。

19. 确定性的流程和状态机写在代码中。

20. Prompt 从最小版本开始，只为真实问题增加规则或示例。
```

最终标准形式：

```python
@prompt
def prompt_name(
    dynamic_input: InputType,
    context: ContextType,
) -> Prompt:
    developer = """
    # Role

    明确当前组件职责。

    # Task

    明确本次需要完成的任务。

    # Rules

    - 只写真正必要的规则。
    - 规则必须具体、直接、可执行。

    # Output

    明确最终返回什么内容。
    """

    user = f"""
    # Context

    {context}

    # Input

    {dynamic_input}

    Based on the information above, complete the task.
    """

    return Prompt(
        messages=(
            Message(
                role="developer",
                content=developer,
            ),
            Message(
                role="user",
                content=user,
            ),
        )
    )
```

整个提示词规范只解决四件事：

```text
提示词存在哪里
提示词如何调用
动态参数如何注入
提示词消息和内容如何编写
```

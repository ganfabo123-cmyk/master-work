# Agent 应用标准工具层设计

## N 个工具 = N 个函数

## 1. 设计目标

Agent 工具层必须遵守一个不可破坏的原则：

> 每个工具只能定义一次，并且只能定义为一个 Python 函数。

假设系统有 20 个工具，那么业务层只能存在 20 个工具函数：

```text
20 个工具 = 20 个 @tool 函数
```

不允许为每个工具额外编写：

```text
JSON Schema
参数 Pydantic Model
工具名称配置
工具描述配置
注册语句
调用映射
参数解析函数
调用包装函数
返回值校验函数
```

下面这些信息必须全部从唯一的工具函数派生：

| 信息          | 唯一来源                |
| ----------- | ------------------- |
| 工具名称        | 函数名                 |
| 工具描述        | 函数 docstring        |
| 参数名称        | 函数参数名               |
| 参数类型        | 参数类型注解              |
| 参数说明        | `Annotated + Field` |
| 参数约束        | `Field`             |
| 是否必填        | 是否存在默认值             |
| JSON Schema | 自动生成                |
| 输入类型校验      | 自动生成                |
| 实际工具执行      | 函数体                 |
| 输出类型        | 返回值注解               |
| 输出校验        | 自动生成                |
| 工具注册        | `@tool` 自动完成        |
| 工具调用分发      | Registry 自动完成       |

最终，一个工具的完整定义只能长这样：

```python
@tool
def read_file(
    path: Annotated[
        str,
        Field(description="需要读取的文件路径"),
    ],
) -> str:
    """读取指定文本文件的完整内容。"""

    return Path(path).read_text(encoding="utf-8")
```

除此之外，不允许出现任何与 `read_file` 对应的重复定义。

---

# 2. 整体目录结构

```text
app/
├── tool_runtime.py    # 通用工具基础设施，只写一次
├── tools.py           # 所有工具，每个工具只有一个函数
└── agent_loop.py      # Agent 循环
```

依赖：

```bash
pip install "pydantic>=2.11,<3"
```

技术基础是：

* `inspect.signature()` 可以读取函数参数、默认值和返回值注解。
* `get_type_hints(..., include_extras=True)` 可以保留 `Annotated` 中的额外元数据。
* Pydantic 的 `create_model()` 可以根据运行时信息动态创建参数模型。
* Pydantic 可以从同一个模型生成 JSON Schema。
* `TypeAdapter` 可以直接校验 `str`、`list[str]`、`dict[str, int]` 等任意受支持类型，不要求额外定义 `BaseModel`。
* Strict Mode 可以阻止 `"123"` 被静默转换成整数 `123`。

---

# 3. 通用工具运行时

下面整个文件在所有 Agent 项目中直接复用。

## `tool_runtime.py`

```python
from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints

from pydantic import (
    BaseModel,
    ConfigDict,
    TypeAdapter,
    ValidationError,
    create_model,
)


class ToolInputError(Exception):
    """LLM 生成的工具参数不符合函数签名。"""

    def __init__(
        self,
        tool_name: str,
        error: ValidationError,
    ) -> None:
        self.tool_name = tool_name
        self.error = error

        super().__init__(
            f"{tool_name}: invalid tool arguments"
        )


class ToolOutputError(Exception):
    """工具函数返回值不符合返回值注解。"""

    def __init__(
        self,
        tool_name: str,
        error: ValidationError,
    ) -> None:
        self.tool_name = tool_name
        self.error = error

        super().__init__(
            f"{tool_name}: invalid tool result"
        )


@dataclass(frozen=True, slots=True)
class CompiledTool:
    """
    工具函数经过编译后的运行时对象。

    它不是工具的第二份定义，只是工具函数的运行时投影。
    """

    name: str
    description: str

    # 唯一的实际执行函数。
    fn: Callable[..., Any]

    signature: inspect.Signature

    # 根据函数参数动态生成。
    args_model: type[BaseModel]

    # 根据返回值注解动态生成。
    result_adapter: TypeAdapter[Any]

    # 发送给 LLM 的工具 Schema。
    llm_schema: dict[str, Any]

    # 内部使用的返回值 Schema。
    result_schema: dict[str, Any]

    async def invoke(
        self,
        raw_arguments: str | dict[str, Any],
    ) -> Any:
        """
        完整工具调用链：

        JSON 解析
            -> 输入类型校验
            -> 调用原函数
            -> 输出类型校验
        """

        try:
            if isinstance(raw_arguments, str):
                validated_arguments = (
                    self.args_model.model_validate_json(
                        raw_arguments,
                        strict=True,
                    )
                )
            else:
                validated_arguments = (
                    self.args_model.model_validate(
                        raw_arguments,
                        strict=True,
                    )
                )
        except ValidationError as exc:
            raise ToolInputError(
                self.name,
                exc,
            ) from exc

        # 从动态参数模型中读取已经校验过的真实 Python 对象。
        kwargs = {
            name: getattr(validated_arguments, name)
            for name in self.signature.parameters
        }

        # 直接调用唯一的原始工具函数。
        result = self.fn(**kwargs)

        # 同时兼容同步函数和异步函数。
        if inspect.isawaitable(result):
            result = await result

        try:
            return self.result_adapter.validate_python(
                result,
                strict=True,
            )
        except ValidationError as exc:
            raise ToolOutputError(
                self.name,
                exc,
            ) from exc

    def serialize_result(
        self,
        result: Any,
    ) -> str:
        """
        将经过校验的返回值统一序列化为 JSON。

        所有工具返回给 LLM 的内容都使用合法 JSON。
        """

        return self.result_adapter.dump_json(
            result,
        ).decode("utf-8")


class ToolRegistry:
    """
    全局工具注册表。

    工具通过 @tool 自动注册，不允许手动维护映射。
    """

    def __init__(self) -> None:
        self._tools: dict[str, CompiledTool] = {}

    def register(
        self,
        compiled_tool: CompiledTool,
    ) -> None:
        if compiled_tool.name in self._tools:
            raise RuntimeError(
                "Duplicate tool name: "
                f"{compiled_tool.name}"
            )

        self._tools[compiled_tool.name] = compiled_tool

    def schemas(self) -> list[dict[str, Any]]:
        """
        返回可以直接传给模型的工具列表。
        """

        return [
            compiled_tool.llm_schema
            for compiled_tool in self._tools.values()
        ]

    def get(
        self,
        name: str,
    ) -> CompiledTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(
                f"Unknown tool: {name}"
            ) from exc

    async def execute(
        self,
        name: str,
        raw_arguments: str | dict[str, Any],
    ) -> dict[str, Any]:
        """
        Agent Runtime 唯一的工具执行入口。
        """

        try:
            compiled_tool = self.get(name)
        except KeyError:
            return {
                "ok": False,
                "content": json.dumps(
                    {
                        "error": "unknown_tool",
                        "tool": name,
                    },
                    ensure_ascii=False,
                ),
            }

        try:
            result = await compiled_tool.invoke(
                raw_arguments,
            )

        except ToolInputError as exc:
            return {
                "ok": False,
                "content": json.dumps(
                    {
                        "error": "input_validation_error",
                        "tool": name,
                        "details": exc.error.errors(
                            include_url=False,
                        ),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            }

        except ToolOutputError as exc:
            return {
                "ok": False,
                "content": json.dumps(
                    {
                        "error": "output_validation_error",
                        "tool": name,
                        "details": exc.error.errors(
                            include_url=False,
                        ),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            }

        except Exception as exc:
            return {
                "ok": False,
                "content": json.dumps(
                    {
                        "error": "tool_execution_error",
                        "tool": name,
                        "message": str(exc),
                    },
                    ensure_ascii=False,
                ),
            }

        return {
            "ok": True,
            "content": compiled_tool.serialize_result(
                result,
            ),
        }


TOOL_REGISTRY = ToolRegistry()


def _compile_tool(
    fn: Callable[..., Any],
) -> CompiledTool:
    """
    将一个普通 Python 函数编译成完整工具。

    所有信息只能从 fn 获取。
    """

    signature = inspect.signature(fn)
    description = inspect.getdoc(fn) or ""

    # include_extras=True 用于保留 Annotated 中的 Field。
    type_hints = get_type_hints(
        fn,
        include_extras=True,
    )

    if not description:
        raise TypeError(
            f"{fn.__name__}: tool docstring is required"
        )

    if "return" not in type_hints:
        raise TypeError(
            f"{fn.__name__}: "
            "return annotation is required"
        )

    fields: dict[str, tuple[Any, Any]] = {}

    for name, parameter in signature.parameters.items():
        if parameter.kind in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            raise TypeError(
                f"{fn.__name__}.{name}: "
                "positional-only parameters, "
                "*args and **kwargs are not supported"
            )

        if name not in type_hints:
            raise TypeError(
                f"{fn.__name__}.{name}: "
                "type annotation is required"
            )

        default = (
            ...
            if parameter.default
            is inspect.Parameter.empty
            else parameter.default
        )

        fields[name] = (
            type_hints[name],
            default,
        )

    # 根据函数签名动态创建输入模型。
    args_model = create_model(
        f"{fn.__name__}Arguments",
        __config__=ConfigDict(
            extra="forbid",
        ),
        **fields,
    )

    parameters_schema = args_model.model_json_schema(
        mode="validation",
    )

    # 强制要求每个参数都具有说明。
    for name in signature.parameters:
        property_schema = (
            parameters_schema["properties"][name]
        )

        if not property_schema.get("description"):
            raise TypeError(
                f"{fn.__name__}.{name}: "
                "parameter description is required; "
                "use Annotated[..., "
                "Field(description='...')]"
            )

    # 返回值模型也只从返回值注解生成。
    result_adapter = TypeAdapter(
        type_hints["return"],
    )

    return CompiledTool(
        name=fn.__name__,
        description=description,
        fn=fn,
        signature=signature,
        args_model=args_model,
        result_adapter=result_adapter,
        llm_schema={
            "type": "function",
            "function": {
                "name": fn.__name__,
                "description": description,
                "parameters": parameters_schema,
            },
        },
        result_schema=result_adapter.json_schema(
            mode="validation",
        ),
    )


def tool(
    fn: Callable[..., Any],
) -> Callable[..., Any]:
    """
    工具装饰器。

    只负责编译和自动注册，最终仍返回原始函数。
    """

    compiled_tool = _compile_tool(fn)

    TOOL_REGISTRY.register(
        compiled_tool,
    )

    # 不返回包装器，保持原函数的类型、签名和直接调用能力。
    return fn
```

---

# 4. 定义工具

## `tools.py`

这里是整个项目唯一允许出现工具业务定义的地方。

```python
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from app.tool_runtime import tool


@tool
def read_file(
    path: Annotated[
        str,
        Field(
            min_length=1,
            description="需要读取的文件路径",
        ),
    ],
) -> str:
    """读取指定 UTF-8 文本文件的完整内容。"""

    return Path(path).read_text(
        encoding="utf-8",
    )


@tool
def write_file(
    path: Annotated[
        str,
        Field(
            min_length=1,
            description="需要写入的文件路径",
        ),
    ],
    content: Annotated[
        str,
        Field(
            description="需要写入文件的完整文本内容",
        ),
    ],
    overwrite: Annotated[
        bool,
        Field(
            description="文件存在时是否允许覆盖",
        ),
    ] = False,
) -> dict[str, str | int]:
    """向指定文件写入 UTF-8 文本内容。"""

    target = Path(path)

    if target.exists() and not overwrite:
        raise FileExistsError(
            f"File already exists: {path}"
        )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_text(
        content,
        encoding="utf-8",
    )

    return {
        "path": str(target),
        "characters_written": len(content),
    }


@tool
async def search_code(
    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="需要搜索的代码关键词",
        ),
    ],
    file_type: Annotated[
        Literal[
            "python",
            "javascript",
            "typescript",
            "all",
        ],
        Field(
            description="需要搜索的代码文件类型",
        ),
    ] = "all",
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=100,
            description="最多返回多少条搜索结果",
        ),
    ] = 20,
) -> list[str]:
    """在当前代码仓库中搜索匹配的代码片段。"""

    # 实际异步搜索逻辑。
    return [
        f"{file_type}:{query}:{index}"
        for index in range(limit)
    ]
```

此时整个项目有三个工具，也只有三个工具函数。

不存在：

```python
READ_FILE_SCHEMA = ...
WRITE_FILE_SCHEMA = ...
SEARCH_CODE_SCHEMA = ...
```

不存在：

```python
TOOL_REGISTRY.register(read_file)
TOOL_REGISTRY.register(write_file)
TOOL_REGISTRY.register(search_code)
```

不存在：

```python
TOOL_MAPPING = {
    "read_file": read_file,
    "write_file": write_file,
    "search_code": search_code,
}
```

也不存在：

```python
class ReadFileArguments(BaseModel):
    ...

class WriteFileArguments(BaseModel):
    ...

class SearchCodeArguments(BaseModel):
    ...
```

---

# 5. 自动生成 Schema

只要 `tools.py` 被导入：

```python
import app.tools

from app.tool_runtime import TOOL_REGISTRY


schemas = TOOL_REGISTRY.schemas()
```

`read_file` 会自动生成类似下面的 Schema：

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "读取指定 UTF-8 文本文件的完整内容。",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "minLength": 1,
          "description": "需要读取的文件路径"
        }
      },
      "required": [
        "path"
      ],
      "additionalProperties": false
    }
  }
}
```

这个 Schema 没有任何字段是手写的：

```text
read_file
    ← 函数名

读取指定 UTF-8 文本文件的完整内容
    ← docstring

path
    ← 参数名

string
    ← str 类型注解

minLength: 1
    ← Field(min_length=1)

需要读取的文件路径
    ← Field(description=...)

required
    ← path 没有默认值

additionalProperties: false
    ← ConfigDict(extra="forbid")
```

---

# 6. Agent Loop 接入

## `agent_loop.py`

```python
import app.tools

from app.tool_runtime import TOOL_REGISTRY


async def run_agent(
    model_client,
    messages: list[dict],
) -> str:
    while True:
        response = await model_client.chat(
            messages=messages,
            tools=TOOL_REGISTRY.schemas(),
        )

        if not response.tool_calls:
            return response.content

        messages.append(
            response.assistant_message,
        )

        for tool_call in response.tool_calls:
            execution = await TOOL_REGISTRY.execute(
                name=tool_call.name,
                raw_arguments=tool_call.arguments,
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": execution["content"],
                }
            )
```

Agent Loop 完全不知道具体存在哪些工具。

它只认识两个统一接口：

```python
TOOL_REGISTRY.schemas()
```

和：

```python
await TOOL_REGISTRY.execute(
    name,
    arguments,
)
```

以后增加工具，只需要增加一个函数：

```python
@tool
def delete_file(
    path: Annotated[
        str,
        Field(
            description="需要删除的文件路径",
        ),
    ],
) -> bool:
    """删除指定文件。"""

    Path(path).unlink()

    return True
```

Agent Loop、Registry、Schema、调用映射全部不需要修改。

---

# 7. 完整执行链

模型调用：

```json
{
  "name": "write_file",
  "arguments": {
    "path": "src/main.py",
    "content": "print('hello')",
    "overwrite": true
  }
}
```

运行时执行：

```text
模型返回工具名和 JSON 参数
            ↓
Registry 根据工具名找到 CompiledTool
            ↓
Pydantic 解析 JSON
            ↓
根据函数参数注解进行严格类型校验
            ↓
根据 Field 检查长度、范围和枚举
            ↓
拒绝不存在的额外参数
            ↓
调用原始 write_file 函数
            ↓
根据返回值注解校验返回结果
            ↓
统一序列化为 JSON
            ↓
作为 tool message 返回模型
```

整个过程中，业务语义只存在于唯一函数中。

---

# 8. 输入校验示例

模型生成：

```json
{
  "path": "src/main.py",
  "content": "hello",
  "overwrite": "yes"
}
```

由于使用：

```python
strict=True
```

字符串 `"yes"` 不会被自动转换成布尔值。

返回：

```json
{
  "error": "input_validation_error",
  "tool": "write_file",
  "details": [
    {
      "type": "bool_type",
      "loc": [
        "overwrite"
      ],
      "msg": "Input should be a valid boolean",
      "input": "yes"
    }
  ]
}
```

这个错误可以直接作为工具消息返回模型，让模型自己重新生成参数。

---

# 9. 输出校验示例

假设工具声明：

```python
@tool
def count_files(
    directory: Annotated[
        str,
        Field(
            description="需要统计的目录",
        ),
    ],
) -> int:
    """统计目录中的文件数量。"""

    return "10"
```

函数声明返回 `int`，实际返回 `"10"`。

工具运行时会产生：

```json
{
  "error": "output_validation_error",
  "tool": "count_files",
  "details": [
    {
      "type": "int_type",
      "loc": [],
      "msg": "Input should be a valid integer",
      "input": "10"
    }
  ]
}
```

这意味着工具函数自身违反了契约。

输入错误通常是模型的问题，输出错误通常是工具实现的问题。

---

# 10. 工具函数编写规范

每个工具必须满足下面的形式：

```python
@tool
def tool_name(
    parameter: Annotated[
        ParameterType,
        Field(
            description="参数的准确语义",
        ),
    ],
) -> ReturnType:
    """告诉模型什么时候以及为什么调用这个工具。"""

    ...
```

## 函数名

函数名直接作为模型看到的工具名：

```python
read_file
search_code
run_tests
execute_command
```

禁止使用没有语义的名称：

```python
handle
process
execute
do_work
tool_1
```

## docstring

docstring 负责说明工具整体用途：

```python
"""读取指定 UTF-8 文本文件的完整内容。"""
```

不要只写：

```python
"""读取文件。"""
```

也不要把参数说明重复写进 docstring。

## 参数说明

参数说明必须跟参数绑定：

```python
path: Annotated[
    str,
    Field(
        description="需要读取的文件路径",
    ),
]
```

禁止在其他文件中说明参数。

## 默认值

有默认值意味着参数可选：

```python
limit: Annotated[
    int,
    Field(
        ge=1,
        le=100,
        description="最多返回多少条结果",
    ),
] = 20
```

没有默认值意味着参数必填：

```python
query: Annotated[
    str,
    Field(
        description="需要搜索的内容",
    ),
]
```

## 枚举

有限选项使用 `Literal`：

```python
mode: Annotated[
    Literal[
        "fast",
        "balanced",
        "thorough",
    ],
    Field(
        description="工具的执行模式",
    ),
] = "balanced"
```

不要写成不受约束的：

```python
mode: str
```

## 返回值

所有工具必须声明返回值：

```python
def read_file(...) -> str:
```

```python
def search_code(...) -> list[str]:
```

```python
def write_file(...) -> dict[str, str | int]:
```

禁止：

```python
def read_file(...):
```

禁止返回无法 JSON 序列化的任意业务对象。

---

# 11. 明确禁止的设计

## 禁止手写 Schema

```python
READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": "...",
}
```

因为它会与函数签名产生漂移。

## 禁止单独参数类

```python
class ReadFileArguments(BaseModel):
    path: str
```

因为工具参数会出现第二份定义。

## 禁止手动注册

```python
TOOL_REGISTRY.register(read_file)
```

因为新增工具时容易漏注册。

## 禁止手动调用分发

```python
if name == "read_file":
    return read_file(**arguments)

if name == "write_file":
    return write_file(**arguments)
```

也禁止：

```python
TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
}
```

Registry 必须由 `@tool` 自动维护。

## 禁止工具包装函数

```python
def call_read_file(arguments):
    validated = ...
    return read_file(...)
```

所有工具必须走统一的：

```python
TOOL_REGISTRY.execute(...)
```

## 禁止参数静默纠正

不要把：

```json
{
  "limit": "20"
}
```

自动转换为：

```json
{
  "limit": 20
}
```

工具参数错误应该明确返回给模型，由模型重新调用。

---

# 12. 该设计的本质

这不是“函数加一个装饰器”这么简单。

它实际上是在把 Python 函数当成一种工具定义语言：

```text
Python 函数
    ↓ 编译
Tool Intermediate Representation
    ├── 工具名称
    ├── 工具描述
    ├── 输入 JSON Schema
    ├── 输入校验器
    ├── 原始执行函数
    ├── 输出校验器
    └── 输出 JSON Schema
```

但这个 Intermediate Representation 只是运行时生成的投影，不是新的事实源。

真正的事实源永远只有：

```python
@tool
def some_tool(...) -> ...:
    ...
```

因此工具发生修改时，只修改这一处：

```text
修改函数参数
    → Schema 自动变化
    → 输入校验自动变化

修改 Field 约束
    → Schema 自动变化
    → 参数校验自动变化

修改返回值注解
    → 输出校验自动变化

修改 docstring
    → 工具描述自动变化

修改函数体
    → 实际执行逻辑变化
```

不会存在 Schema、参数模型、调用函数和实际实现互相漂移的问题。

---

# 13. 最终项目规范

以后所有 Agent 项目统一执行以下规则：

```text
1. 工具只能通过 @tool 函数定义。

2. 一个工具只能对应一个函数。

3. 工具名只能来自函数名。

4. 工具描述只能来自 docstring。

5. 参数类型只能来自类型注解。

6. 参数说明和约束只能来自 Annotated + Field。

7. 输入 Schema 必须自动生成。

8. 输入校验必须自动执行。

9. 工具调用必须直接调用原函数。

10. 返回值类型只能来自返回值注解。

11. 返回值必须经过运行时校验。

12. 工具必须通过装饰器自动注册。

13. Agent Loop 不允许知道具体工具。

14. 禁止手写任何逐工具 Schema、Model、Registry 或 Dispatch。

15. N 个工具必须严格等于 N 个工具函数。
```

最终标准形态只有这一种：

```python
@tool
def tool_name(
    argument: Annotated[
        ArgumentType,
        Field(
            description="参数说明",
        ),
    ],
) -> ReturnType:
    """工具用途说明。"""

    # 唯一的实际实现。
    ...
```

# Harness Skill 规范

## 1. Skill 定义

Skill 是一份按需加载的任务操作说明，用于告诉 Agent：

* 这类任务什么时候使用该 Skill；
* 应该按照什么流程执行；
* 需要时读取哪些资料、运行哪些脚本或使用哪些素材；
* 怎样验证任务已经完成。

Skill 不负责：

* 定义 Agent；
* 保存运行状态；
* 保存动态记忆；
* 调度其他 Agent；
* 定义或实现工具；
* 重复定义 Tool Schema；
* 绕过统一 Tool Runtime 或 MCP Client。

---

## 2. 目录结构

最小 Skill：

```text
skill-name/
└── SKILL.md
```

包含完整资源的 Skill：

```text
skill-name/
├── SKILL.md
├── scripts/
├── references/
└── assets/
```

除 `SKILL.md` 外，其他目录全部可选。

### `SKILL.md`

Agent 执行该类任务时需要遵循的核心流程。

### `scripts/`

确定性的辅助程序，例如：

```text
解析测试日志
扫描项目结构
校验配置文件
转换固定格式
生成报告
```

脚本不是工具，不会自动发送给模型。

### `references/`

Agent 按需读取的详细资料，例如：

```text
框架使用规范
项目约定
数据库 Schema
常见错误说明
领域知识
```

### `assets/`

生成最终产物时使用的素材，例如：

```text
报告模板
配置模板
项目骨架
示例文件
图片和静态资源
```

Skill 本身不包含 `tools.py`。

如果一个扩展既需要提供 Skill，又需要增加模型可调用工具，应在 Skill 目录之外提供 MCP Server。

---

## 3. SKILL.md 格式

```markdown
---
name: fix-python-test
description: Diagnose and fix Python test failures. Use when pytest or unittest reports a failure.
---

# Workflow

1. 运行失败测试并保留完整错误输出。
2. 读取失败测试和相关实现。
3. 定位根本原因。
4. 实施最小范围修改。
5. 重新运行原始失败测试。

需要处理 fixture 问题时，读取：

`references/pytest-fixtures.md`

需要解析大量测试日志时，运行：

`python scripts/parse-pytest-output.py <log-path>`

输出修复报告时，使用：

`assets/fix-report-template.md`

如果当前 Harness 已连接 `project-tools` MCP Server，可以调用：

`project-tools.parse_pytest_log`

# Validation

只有原始失败测试通过后，才能声明任务完成。
```

## 必需内容

Frontmatter 只要求：

```yaml
name: fix-python-test
description: Diagnose and fix Python test failures. Use when pytest or unittest reports a failure.
```

正文只要求：

```text
Workflow
Validation
```

要求：

* `name` 与 Skill 目录名一致；
* `description` 同时说明“做什么”和“什么时候使用”；
* `Workflow` 按执行顺序描述主要步骤；
* `Validation` 给出可观察的完成条件。

其他章节按实际需要增加，不作强制要求。

---

## 4. scripts、references、assets 的使用规则

### scripts

适合放：

```text
输入明确
输出明确
需要重复执行
需要确定性结果
由模型临时编写容易出错
```

例如：

```text
scripts/
└── parse-pytest-output.py
```

Skill 中必须说明什么时候运行：

```markdown
当测试输出超过当前上下文可直接分析的范围时，运行：

python scripts/parse-pytest-output.py pytest.log
```

脚本可以通过现有的 `run_command` 工具执行。

不要因为存在一个脚本，就额外为它创建 Tool Schema。

脚本只有在确实需要作为模型可独立选择和调用的结构化能力时，才应由扩展包中的 MCP Tool 进行封装。

### references

适合放 Agent 需要阅读但不必每次加载的知识：

```text
references/
├── pytest-fixtures.md
├── async-testing.md
└── project-testing-rules.md
```

Skill 中必须写明加载条件：

```markdown
遇到 fixture scope、参数化或依赖关系错误时，读取：

references/pytest-fixtures.md
```

禁止激活 Skill 后默认读取整个 `references/`。

### assets

适合放会进入最终产物的模板或素材：

```text
assets/
├── fix-report-template.md
├── pyproject-template.toml
└── project-template/
```

Asset 默认不需要进入模型上下文。

Agent 可以复制、填充或修改 Asset，例如：

```markdown
生成最终报告时，以：

assets/fix-report-template.md

作为输出模板。
```

---

## 5. Skill 与 MCP 工具

Skill 本身不定义工具。

独立 Skill 只能使用 Harness 已经提供或已经连接的工具。

如果某个扩展既需要提供 Skill，又需要增加模型可调用能力，应由扩展包同时提供：

```text
Skill
+
MCP Server
```

推荐目录：

```text
extension-name/
├── skills/
│   └── skill-name/
│       ├── SKILL.md
│       ├── scripts/
│       ├── references/
│       └── assets/
│
└── mcp/
    └── server.py
```

其中：

* `SKILL.md`：描述任务流程和验证条件；
* `scripts/`：确定性辅助程序；
* `references/`：按需读取的参考知识；
* `assets/`：最终产物使用的模板和素材；
* `mcp/server.py`：向 Harness 暴露该扩展提供的工具。

Skill 和 MCP Server 属于同一个扩展包，但二者职责独立：

```text
Skill
说明这类任务应该怎么做。

MCP Server
提供模型能够调用的实际能力。
```

### Skill 如何使用 MCP 工具

Skill 可以在 Workflow 中引用已经连接的 MCP 工具：

```markdown
# Workflow

1. 获取失败测试的完整日志。
2. 调用 `project-tools.parse_pytest_log` 解析测试失败。
3. 根据结构化结果读取相关代码。
4. 修改代码并重新运行测试。
```

这里的工具名称只是使用说明，不是工具定义。

Skill 禁止：

* 手写 MCP Tool Schema；
* 重复声明工具参数；
* 实现工具输入或输出校验；
* 维护工具注册表；
* 维护工具调用映射；
* 在 `SKILL.md` 中嵌入工具实现；
* 绕过 MCP Client 直接调用 MCP Server 内部函数。

---

## 6. MCP Server 与统一工具规范

一个 MCP Server 可以暴露零个或多个工具：

```text
project-tools MCP Server
├── parse_pytest_log
├── inspect_python_project
└── validate_test_result
```

MCP Server 不是工具。

MCP Server 负责：

* 对外声明可用工具；
* 接收工具调用；
* 将调用转发给对应工具；
* 返回工具执行结果；
* 处理 MCP 协议和传输。

在本 Harness 中，每个 MCP Tool 必须继续遵守统一工具规范：

```text
一个 MCP Tool = 一个唯一的 @tool 函数
```

工具的以下信息只能从该函数派生：

```text
工具名称        ← 函数名
工具描述        ← docstring
参数名称        ← 函数参数名
参数类型        ← 类型注解
参数说明和约束  ← Annotated + Field
输入 Schema     ← 自动生成
输入校验        ← 自动生成
实际执行        ← 函数体
返回类型        ← 返回值注解
输出校验        ← 自动生成
工具注册        ← @tool 自动完成
```

这与现有的“N 个工具严格等于 N 个唯一工具函数”规范保持一致。

MCP Server 只负责把已经编译和注册的工具通过 MCP 协议暴露出去，不得维护第二份工具定义。

推荐结构：

```text
N 个 @tool 函数
    ↓
ToolRegistry 自动编译和注册
    ↓
通用 MCP Adapter 读取 ToolRegistry
    ├── tools/list
    └── tools/call
    ↓
MCP Client
    ↓
Agent
```

因此禁止为了接入 MCP 再重复定义工具：

```python
@tool
def read_file(...):
    ...
```

```python
@mcp.tool()
def duplicate_read_file(...):
    ...
```

也禁止重复维护：

```python
MCP_TOOL_SCHEMAS = {...}
MCP_TOOL_MAPPING = {...}
```

正确方式是：

```text
唯一 @tool 函数
    ↓
ToolRegistry
    ↓
通用 MCP Adapter
```

MCP Adapter 只是协议适配层，不是新的工具事实源。

---

## 7. scripts 与 MCP Tool 的区别

### 使用 `scripts/`

适用于：

* 操作属于固定 Workflow 步骤；
* 可以通过已有命令工具执行；
* 不需要模型独立决定复杂参数；
* 不需要作为通用能力公开；
* 输入和输出主要面向命令行或文件。

例如：

```text
scripts/parse-pytest-output.py
```

Agent 可以通过已有工具执行：

```text
run_command(
    "python scripts/parse-pytest-output.py pytest.log"
)
```

### 使用 MCP Tool

适用于：

* 模型需要主动决定何时调用；
* 需要结构化参数；
* 需要严格输入和输出校验；
* 该能力需要被多个 Skill 或 Agent 复用；
* 不希望模型临时拼接命令行参数。

### MCP Tool 可以调用脚本

脚本可以作为 MCP Tool 函数的内部实现：

```text
唯一 @tool 函数
    ↓
调用 scripts/ 中的确定性程序
```

例如：

```python
@tool
def parse_pytest_log(
    log_path: Annotated[
        str,
        Field(
            description="需要解析的 pytest 日志路径",
        ),
    ],
) -> list[dict[str, str]]:
    """解析 pytest 日志并返回结构化的失败信息。"""

    return run_parser_script(log_path)
```

此时：

* `parse_pytest_log` 是模型可调用的 MCP Tool；
* 内部解析脚本只是实现细节；
* 脚本本身不会自动成为工具；
* 工具的唯一事实源仍然是外层 `@tool` 函数。

---

## 8. 最终规则

```text
1. 一个 Skill 至少包含一个 SKILL.md。

2. SKILL.md 只强制 name、description、Workflow 和 Validation。

3. scripts、references 和 assets 全部可选。

4. scripts 是确定性程序，不自动成为工具。

5. references 是按需读取的知识，不默认全部加载。

6. assets 是最终产物使用的素材，不默认进入上下文。

7. Skill 本身不定义工具，也不包含 tools.py。

8. Skill 只能引用 Harness 已有或已经通过 MCP Server 连接的工具。

9. 需要同时提供 Skill 和新工具时，使用扩展包组合 Skill 与 MCP Server。

10. MCP Server 不是工具，一个 MCP Server 可以暴露多个工具。

11. 在本 Harness 中，一个 MCP Tool 必须对应一个唯一的 @tool 函数。

12. MCP Server 只通过通用 MCP Adapter 暴露 ToolRegistry 中的工具。

13. 禁止为 MCP 重复编写 Schema、参数模型、注册列表、调用映射或第二个工具函数。

14. MCP Server 在扩展加载或配置连接时提供工具，不依赖 Skill 激活后临时注册。

15. Skill 只负责说明何时以及如何使用这些工具。
```

最终一个只包含任务流程和资源的 Skill：

```text
fix-python-test/
├── SKILL.md
├── scripts/
│   └── parse-pytest-output.py
├── references/
│   └── pytest-fixtures.md
└── assets/
    └── fix-report-template.md
```

一个同时提供 Skill 和 MCP 工具的扩展：

```text
python-testing-extension/
├── skills/
│   └── fix-python-test/
│       ├── SKILL.md
│       ├── scripts/
│       │   └── parse-pytest-output.py
│       ├── references/
│       │   └── pytest-fixtures.md
│       └── assets/
│           └── fix-report-template.md
│
└── mcp/
    ├── server.py
    └── tools.py
```

其中：

```text
skills/fix-python-test/
```

只负责说明任务怎么完成。

```text
mcp/tools.py
```

只包含该扩展提供的唯一 `@tool` 工具函数。

```text
mcp/server.py
```

只负责通过通用 MCP Adapter 将 ToolRegistry 暴露为 MCP Server。

Skill 不需要额外配置文件、生命周期系统、版本系统或专用运行状态。

# DSH 插件自动开发插件需求文档

## 1. 项目概述

本插件用于帮助 DeepSeek Harness 自动完成自定义 DSH 插件的需求分析、设计、开发、验证与真实用户验收。

用户只需要描述希望实现的插件能力，例如：

> 我想做一个让 DeepSeek 可以操作本地部署五子棋游戏的插件。

系统负责将这一自然语言需求逐步转化为明确的插件需求文档，并调度多个 Agent 完成插件设计、依赖调查、代码实现、文档编写、构建验证以及真实 DSH 环境中的最终验收。

本插件的目标不是单纯让模型“写出插件代码”，而是建立一套完整的 **DSH Plugin Development Harness**，使插件最终是否可用由真实运行结果和用户实际输入共同验证，而不是仅依赖代码生成 Agent 自己编写的测试。

---

# 2. 核心目标

整体流程：

```text
用户提出需求
    ↓
Phase 1：需求拆解
    ↓
用户确认
    ↓
Phase 2：输入输出与交互设计
    ↓
用户确认
    ↓
Phase 3：生成正式需求文档
    ↓
用户确认
    ↓
创建插件开发任务
    ↓
多 Agent 协作开发
    ↓
工程验证
    ↓
启动真实 DSH 子进程
    ↓
Agent 黑盒验收
    ↓
用户真实输入验收
    ↓
交付插件
```

核心原则：

```text
需求必须经过用户确认
        ↓
实现必须依据确认后的需求
        ↓
代码必须真实 build
        ↓
插件必须在真实 DSH 环境加载
        ↓
必须从真实用户入口测试
        ↓
至少部分最终测试输入由用户本人提供
```

---

# 3. 系统角色

系统至少包含以下角色。

## 3.1 主 Agent

主 Agent 负责：

```text
理解用户需求
→ 与用户确认
→ 形成正式需求
→ 创建开发任务
→ 调度后续开发流程
→ 汇总开发状态
→ 发起最终用户验收
```

主 Agent 原则上不直接承担所有代码开发工作。

它主要负责：

* 需求澄清
* 系统规划
* 用户交互
* 工作流推进
* Agent 调度
* 最终验收协调

---

## 3.2 开发 Agent

开发 Agent 根据任务动态创建。

不同 Agent 应承担相对独立的职责，例如：

```text
Architecture Agent
→ 设计插件整体架构

Dependency Agent
→ 检查 DSH / Cordis 已有能力和可复用依赖

Implementation Agent
→ 实现 src 核心代码

Manifest Agent
→ 处理 package.json / cordis.patch.yml / 配置等

Documentation Agent
→ 根据最终实现编写 README

Validation Agent
→ build、检查配置、运行针对性测试

Acceptance Agent
→ 在真实 DSH 环境中执行最终验收
```

具体 Agent 数量和职责不固定，应根据插件复杂度决定。

---

# 4. Phase 1：需求拆解

## 4.1 目标

将用户较模糊的自然语言需求转化为明确的功能范围。

例如：

```text
用户：

我要让 DeepSeek 可以玩本地部署的五子棋游戏。
```

主 Agent需要进一步拆解：

```text
DeepSeek
→ 获取当前棋盘状态
→ 判断当前轮次
→ 决定落子位置
→ 调用本地游戏接口
→ 游戏执行落子
→ 获取新的棋盘状态
→ 判断游戏是否结束
```

## 4.2 输出内容

Phase 1 至少需要确定：

* 用户最终希望获得什么能力
* 插件主要使用场景
* 插件需要操作的外部系统
* DeepSeek 与外部系统之间的基本交互流程
* 明显的功能边界
* 明显不属于当前插件范围的能力

## 4.3 用户确认

Phase 1 完成后必须向用户确认。

不得直接进入 Phase 2。

用户可以：

```text
确认
修改
补充
删除部分需求
```

只有用户确认后才能进入下一阶段。

---

# 5. Phase 2：输入、输出与交互设计

## 5.1 目标

确定插件在 Harness 中具体如何被调用，以及插件与外部系统如何交换信息。

需要回答：

```text
Agent 给插件什么？
插件返回什么？
插件如何操作外部系统？
一次交互完成到什么程度？
状态如何继续？
异常如何暴露？
```

## 5.2 设计内容

至少考虑：

### Tool 设计

例如：

```text
get_board_state()

place_piece(x, y)

restart_game()

get_game_status()
```

但不得默认一定需要多个 Tool。

应根据需求决定：

```text
一个高层 Tool
或
多个原子 Tool
```

### 输入设计

包括：

* 必填参数
* 可选参数
* 参数类型
* 参数约束

### 输出设计

包括：

* 返回给模型的信息
* 外部状态变化
* 错误信息
* 是否需要结构化数据

### 状态设计

需要明确：

* 是否有会话状态
* 是否依赖外部程序状态
* 插件自身是否持有状态
* 是否能够重新读取真实状态

## 5.3 用户确认

Phase 2 完成后再次向用户确认。

只有用户认可交互方式后才能进入 Phase 3。

---

# 6. Phase 3：生成正式需求文档

最终需求文档必须同时服务于两类消费者：

```text
Human
+
Agent
```

两者信息需求不同。

---

# 7. 双层需求文档设计

## 7.1 Human Overview

面向用户。

目标是：

> 使用尽可能少的信息量，让用户快速建立对整个插件设计的整体认知。

不应该要求用户阅读大量长文本。

推荐形式：

```text
用户请求
→ 获取游戏状态
→ DeepSeek 决策
→ 调用插件 Tool
→ 本地游戏执行
→ 返回新状态
```

或者：

```text
需求
├─ 操作对象：本地五子棋
├─ Agent 能力：读取棋盘 + 落子
├─ 外部交互：本地游戏接口
└─ 验收：真实 DSH 会话可以完成一局交互
```

Human Overview 应重点展示：

* 系统目标
* 核心流程
* 关键组件
* 主要输入输出
* 验收方式

原则：

```text
少文字
高信息密度
可快速扫描
能形成完整 mental model
```

---

## 7.2 Agent Detailed Spec

面向开发 Agent。

详细文档允许较大文字量，需要完整记录已经确认的需求。

至少应包含：

```text
Background

Goals

Non-Goals

User Scenarios

Functional Requirements

Interaction Flow

Tool Requirements

Inputs

Outputs

External Dependencies

State Requirements

Error Handling

Constraints

Edge Cases

Acceptance Criteria

Delivery Requirements
```

该文档是后续开发 Agent 的主要事实来源。

开发 Agent 不应重新自行推测已经确定的用户需求。

---

# 8. 用户对正式需求文档的最终确认

正式需求文档生成后，再次提供给用户检查。

用户可以：

```text
确认
修改部分需求
补充需求
删除需求
重新设计部分输入输出
```

只有需求文档明确确认后，才允许进入开发阶段。

---

# 9. 创建插件开发任务

需求确认后，主 Agent 调用 Cordis / Plugin Create Tool 创建插件开发任务。

输入至少包括：

```text
Detailed Requirement Spec
```

可以同时传递：

```text
Human Overview
项目名称
目标目录
用户确认记录
```

开发阶段必须以正式 Spec 为准，而不能继续依赖最初的模糊自然语言描述。

---

# 10. 多 Agent 开发

开发阶段由多个 Agent 根据职责完成。

支持：

```text
串行
并行
串并行混合
```

---

# 11. Agent 任务划分原则

任务划分优先按照职责和依赖关系，而不是简单按照文件数量划分。

例如：

```text
需求文档
    ↓
Architecture Agent
    ├───────────────┐
    ↓               ↓
Dependency Agent   Implementation Agent
    │               │
    └───────┬───────┘
            ↓
      Integration Agent
            ↓
    Documentation Agent
            ↓
      Validation Agent
```

---

# 12. Architecture Agent

负责：

* DSH 插件整体结构
* Tool / Service 划分
* Config 需求
* inject dependency
* 外部程序交互方式
* 模块职责
* 文件规划

Architecture Agent 不需要承担全部实现。

---

# 13. Dependency Agent

负责检查：

* DSH 已有 Service
* Cordis API
* 官方现有插件
* 可以直接复用的包
* 外部依赖
* 是否已有类似实现

核心原则：

> 能复用已有基础设施时，不重复实现。

---

# 14. Implementation Agent

负责核心插件代码。

包括但不限于：

```text
src/
Tool
Service
Config
外部进程交互
状态解析
错误处理
```

实现必须遵循已经确定的 Architecture 与 Requirement Spec。

---

# 15. Documentation Agent

README 等文档应基于：

```text
最终代码
+
需求文档
+
实际运行方式
```

而不是仅根据最初设计提前生成。

README 至少应说明：

* 插件作用
* 安装方式
* 配置方式
* 使用方式
* Tool 能力
* 示例
* 外部依赖
* 已知限制

---

# 16. Engineering Verification

开发完成后进行第一层验证。

目标：

> 检查插件代码本身是否具备进入真实运行测试的条件。

可以包括：

```text
TypeScript typecheck
build
lint
package validation
cordis.patch.yml validation
dependency validation
tool schema validation
必要的 unit test
必要的 integration test
```

这一层测试不能作为最终完成依据。

---

# 17. 测试原则

禁止使用：

```text
测试通过
=
插件完成
```

因为测试代码本身可能由同一开发 Agent 设计。

存在：

```text
Agent 写实现
↓
Agent 推测实现应该如何工作
↓
Agent 根据同样的假设写测试
↓
测试通过
```

但用户实际使用仍然失败的风险。

因此：

> 自动测试是工程验证工具，而不是真实可用性的最终证明。

---

# 18. Real-Host Acceptance Test

这是整个开发流程的最终技术闸门。

测试必须运行在真正的 DeepSeek Harness 环境。

---

# 19. Clean DSH Process

Acceptance Agent 必须启动新的 DSH 进程。

尽可能避免复用开发环境中已经存在的运行状态。

验收环境应尽量接近真实用户：

```text
build plugin
↓
配置插件
↓
启动真实 dsh
↓
创建真实 session
↓
输入自然语言
↓
模型决定是否调用插件
↓
插件实际执行
↓
外部系统实际变化
↓
模型获取结果
```

---

# 20. Agent Acceptance

首先由独立 Acceptance Agent 进行黑盒测试。

Acceptance Agent 应主要拥有：

```text
用户需求
+
最终插件
+
插件正常安装/启动所需的信息
```

原则上不应依赖开发 Agent 的详细推理过程。

Acceptance Agent 需要模拟正常用户：

```text
输入自然语言
→ 观察模型
→ 观察 Tool Call
→ 观察插件行为
→ 观察外部系统状态
→ 观察最终模型响应
```

例如五子棋插件：

```text
“看一下现在棋盘，然后帮我下一步。”
```

系统需要真实完成：

```text
DSH
→ 模型
→ 插件 Tool
→ 本地游戏
→ 棋盘变化
→ 新状态
→ 模型回复
```

只有完整链路成功，才算通过。

---

# 21. Human Acceptance Test

Agent 自动验收通过后，必须邀请用户参与最终测试。

这是整个系统的重要能力。

---

# 22. 用户输入转发

主 Agent询问用户：

> 当前插件已经通过自动真实环境测试。你可以输入一条自己实际会对 DeepSeek 说的话，我会将它发送到测试 DSH 会话。

用户输入应尽可能：

```text
原样
```

发送到 DSH 子进程。

主 Agent 不应该擅自：

* 修改用户表达
* 补充隐藏提示
* 添加 Tool 使用提示
* 将模糊输入改写成方便插件成功的输入

否则会破坏真实用户测试意义。

流程：

```text
User Input
    ↓
Relay
    ↓
DSH Child Session
    ↓
Model
    ↓
Plugin
    ↓
External System
    ↓
Model Response
    ↓
User
```

---

# 23. Interactive Acceptance Session

Human Acceptance 不应限制为单轮。

用户可以连续测试：

```text
User:
现在帮我下一步。

DSH:
...

User:
尝试落在已经有棋子的地方。

DSH:
...

User:
重新开始游戏。

DSH:
...
```

这些消息需要发送到同一个测试 DSH session，以验证：

* 连续会话能力
* 状态保持
* 异常输入
* 边界情况
* 用户真实表达方式

---

# 24. Acceptance Session Tool

插件内部可以提供类似能力：

```text
acceptance_session_start

acceptance_session_send

acceptance_session_status

acceptance_session_stop
```

其中：

### acceptance_session_start

负责：

* 启动 DSH 子进程
* 创建测试 session
* 确认插件加载成功

### acceptance_session_send

负责：

```text
用户 / Agent 输入
→ DSH 子 session
→ 获取完整响应
```

### acceptance_session_status

负责：

* 查看进程状态
* session 状态
* 最近响应
* 是否发生异常

### acceptance_session_stop

负责结束测试环境。

---

# 25. 测试失败后的处理

真实运行失败后，不应该立即大量编写测试脚本。

优先：

```text
观察真实错误
↓
查看日志 / trace / stderr
↓
定位可能原因
```

如果仍然无法确定问题，再针对具体故障编写诊断测试。

即：

```text
整体运行测试失败
        ↓
能直接定位？
   ├─ Yes → 修复
   │
   └─ No
        ↓
   编写针对性诊断测试
        ↓
      定位
        ↓
      修复
```

测试脚本主要承担：

> 故障诊断和回归验证。

而不是替代真实运行验收。

---

# 26. 修复闭环

任何最终测试发现的问题都必须进入修复循环：

```text
Failure
↓
Problem Diagnosis
↓
选择负责 Agent
↓
修改
↓
Engineering Verification
↓
重新启动 Clean DSH
↓
重新 Acceptance
```

不得因为：

```text
“理论上已经修复”
```

直接宣布任务完成。

---

# 27. Definition of Done

插件只有满足以下条件才能被标记完成：

1. 用户完成 Phase 1 需求确认。
2. 用户完成 Phase 2 输入输出设计确认。
3. 用户确认正式需求文档。
4. 插件源码实现完成。
5. Build 成功。
6. 必要的工程检查通过。
7. 插件能够在新的 DSH 进程中正常加载。
8. Acceptance Agent 可以从真实用户入口完成核心需求。
9. 至少允许用户本人提供真实输入进行测试。
10. 用户输入必须经过真实 DSH session，而不是模拟 Tool 调用。
11. 用户测试过程中发现的问题已经进入修复闭环。
12. 最终插件、README 与真实实现保持一致。

---

# 28. 核心系统原则

## 原则一：需求先确认，再开发

```text
Guess
×
Confirm
✓
```

Agent 不能在需求尚未明确时直接开始实现。

---

## 原则二：用户和 Agent 使用不同信息密度

```text
Human
→ Overview

Agent
→ Detailed Spec
```

不要求用户阅读为了 Agent 准备的大量上下文。

---

## 原则三：可标准化的部分尽可能确定化

DSH 插件中大量内容具有固定结构，例如：

```text
package.json
cordis.patch.yml
index.ts
Tool registration
Config
inject
build
目录结构
```

能够通过规则生成和验证的内容，不应完全依赖模型自由生成。

---

## 原则四：Agent 按职责协作

多个 Agent 的目的不是简单提高并行度。

主要价值是：

```text
关注点隔离
上下文隔离
责任隔离
验证隔离
```

---

## 原则五：测试不能完全由作者定义

开发 Agent 可以写测试，但这些测试不能作为插件最终可用性的唯一证据。

---

## 原则六：真实 Harness 行为高于局部测试

最终判断依据：

```text
真实 DSH
+
真实 Plugin
+
真实 Session
+
真实 Tool Call
+
真实外部系统
```

---

## 原则七：用户行为是最终事实来源之一

至少部分 Acceptance Input 来自真正用户。

系统不能提前知道所有测试输入。

这样可以降低：

```text
自己出题
+
自己写答案
+
自己判分
```

造成的虚假成功。

---

# 29. 系统最终形态

```text
                    USER
                      │
                      ▼
          ┌──────────────────────┐
          │ Requirement Agent    │
          │                      │
          │ Phase 1 Requirement  │
          │ Phase 2 I/O Design   │
          │ Phase 3 Spec         │
          └──────────┬───────────┘
                     │
                User Confirm
                     │
                     ▼
        ┌────────────────────────┐
        │ Detailed Requirement   │
        │ Spec                   │
        └───────────┬────────────┘
                    │
                    ▼
        ┌────────────────────────┐
        │ Development Harness    │
        │                        │
        │ Architecture Agent     │
        │ Dependency Agent       │
        │ Implementation Agent   │
        │ Documentation Agent    │
        │ Validation Agent       │
        └───────────┬────────────┘
                    │
                    ▼
              Plugin Artifact
                    │
                    ▼
        ┌────────────────────────┐
        │ Engineering Gate       │
        │                        │
        │ build                  │
        │ typecheck              │
        │ targeted tests         │
        └───────────┬────────────┘
                    │
                    ▼
        ┌────────────────────────┐
        │ Clean DSH Process      │
        └───────────┬────────────┘
                    │
                    ▼
        ┌────────────────────────┐
        │ Agent Acceptance       │
        │                        │
        │ Real Session           │
        │ Real Prompt            │
        │ Real Tool Call         │
        └───────────┬────────────┘
                    │
                 PASS
                    │
                    ▼
        ┌────────────────────────┐
        │ Human Acceptance       │
        │                        │
 USER ──┤ Raw User Input         │
        │        ↓               │
        │ Real DSH Session       │
        │        ↓               │
        │ Real Plugin Behavior   │
        └───────────┬────────────┘
                    │
                    ▼
                 DELIVERY
```

---

# 30. 一句话定义

**本插件是一个面向 DeepSeek Harness 的插件开发 Harness：它通过用户确认驱动的需求建模、多 Agent 职责协作、确定性工程约束、真实 DSH 环境测试以及用户参与的最终验收，将自然语言插件需求转化为经过真实运行验证的可交付 DSH 插件。**

# DeepSeek Harness Experience Memory 开源发布任务文档

## 0. 任务目标

现有 Experience Memory 插件代码已经完成。

本轮**不要继续扩展 Memory 功能或重新设计架构**，目标是把现有代码整理成一个：

* 可独立发布；
* 可被其他 DeepSeek Harness 用户安装；
* 可在真实 Harness Profile 中加载；
* 有完整 README、安装方式和演示；
* 可在 DeepSeek Harness 官方社区公开展示；

的 **DeepSeek Harness 第三方开源插件**。

最终目标不是向 `deepseek-ai/deepseek-harness` 主仓库提交 PR。

当前官方贡献指南明确说明：DeepSeek Harness 暂时不接受外部 Pull Request，同时明确鼓励开发者创建独立插件、给仓库添加 `dsh-plugin` topic 并分享到社区。

因此本项目的贡献路径是：

```text
现有 Memory Plugin
        ↓
独立可发布插件
        ↓
GitHub Public Repository
        ↓
真实 DSH Profile 安装验证
        ↓
README + Demo
        ↓
dsh-plugin topic
        ↓
DeepSeek Harness
Show Your Plugins! Discussion
```

---

# 1. 本轮禁止修改 Memory V1 核心设计

现有插件已经实现 Keyword Experience Memory。

本轮不得因为开源发布重新增加：

```text
Tree
Graph
Temporary Memory
BM25
Vector Retrieval
Hybrid Retrieval
Workspace Scope
Memory Merge
Memory Delete
Automatic Session Mining
Automatic Deduplication
```

当前 V1 保持：

```text
Task
↓
memory_search
↓
候选 Experience
↓
memory_get
↓
完整历史 Experience
↓
当前任务继续执行
↓
产生新的可复用经验
↓
memory_record
↓
用户确认
↓
memory.md
```

三个 model-facing tools 保持：

```text
memory_search
memory_get
memory_record
```

本轮工作的核心是：

> Packaging / Distribution / Verification / Documentation / Community Release

而不是 Feature Development。

---

# 2. 第一阶段：整理为独立插件

检查当前 Memory 插件是否仍然依赖 DeepSeek Harness monorepo 内部目录结构。

目标是把插件整理成一个可以独立存在的项目。

建议仓库名称：

```text
dsh-experience-memory
```

或者：

```text
deepseek-harness-experience-memory
```

优先推荐：

```text
dsh-experience-memory
```

最终目录至少应该类似：

```text
dsh-experience-memory/
├── src/
│   ├── index.ts
│   ├── memory.ts
│   ├── service.ts
│   ├── model.ts
│   ├── config.ts
│   ├── store/
│   └── retrieval/
│
├── tests/
│
├── package.json
├── cordis.patch.yml
├── tsconfig.json
├── README.md
├── README.zh.md
├── LICENSE
└── .gitignore
```

如果现有实现已经满足独立 package 要求，则不要为了目录美观进行无意义重构。

优先保证：

```text
能安装
能 build
能测试
能被 DSH Loader 加载
```

---

# 3. 必须包装成 DeepSeek Harness Bundle

DeepSeek Harness 官方发布文档规定，可安装插件应该作为 Bundle 分发。

Bundle 的 `package.json` 需要声明：

```json
{
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    }
  }
}
```

否则：

```text
dsh plugin add
```

虽然可能安装 package，但 Harness 不会把它作为 bundle layer 激活。

因此检查并完善：

```text
package.json
cordis.patch.yml
```

---

# 4. package.json

根据现有 TypeScript 构建结构调整，不要机械复制示例。

大致结构：

```json
{
  "name": "dsh-experience-memory",
  "version": "0.1.0",
  "type": "module",
  "main": "lib/index.js",
  "files": [
    "lib",
    "cordis.patch.yml"
  ],
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    }
  }
}
```

需要保证：

```text
main
files
build output
cordis.patch.yml
```

实际一致。

DeepSeek Harness 官方 Bundle 文档：

https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/publish.md

官方中文版本：

https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/publish.zh.md

---

# 5. cordis.patch.yml

创建或检查：

```text
cordis.patch.yml
```

它应该通过 package name 注册插件，而不是引用 monorepo 中的相对源码路径。

例如：

```yaml
- insert:
    - id: experience-memory
      name: dsh-experience-memory
```

具体 ID 和当前插件导出方式以实际代码为准。

不要为了套示例修改现有 Plugin Service 架构。

官方 Bundle 机制要求 Bundle 的 patch file 负责把插件插入 Profile composition。

---

# 6. 从独立环境验证安装

不能只证明：

```text
ctx.plugin(...)
```

或者 monorepo 测试可以运行。

必须证明：

> 一个普通 DeepSeek Harness 用户能够把该插件安装进 Profile。

DeepSeek Harness 官方支持：

```bash
dsh plugin --profile demo add ./dsh-experience-memory
```

安装完成后运行：

```bash
dsh --profile demo --dump-config
```

确认生成的配置中出现：

```text
dsh-experience-memory
```

然后实际启动：

```bash
dsh --profile demo
```

官方文档明确推荐使用 `--dump-config` 检查 Bundle layer 是否实际进入最终配置。

---

# 7. 做一次 Fresh Install 验证

本地 monorepo 环境可能隐藏依赖问题。

因此增加一次真正的 Fresh Install 验证。

推荐流程：

```text
创建干净临时目录
↓
安装/使用 DeepSeek Harness
↓
安装 dsh-experience-memory
↓
dump-config
↓
启动 Profile
↓
确认三个 tools 注册
```

至少确认模型侧实际可见：

```text
memory_search
memory_get
memory_record
```

以及新的 Memory System Prompt section。

如果可以自动化，把这部分加入 integration test。

---

# 8. GitHub 安装方式

DeepSeek Harness 官方支持从 GitHub repository 直接安装插件，例如：

```bash
dsh plugin --profile demo add github:<owner>/dsh-experience-memory
```

但是当前项目是 TypeScript，因此必须检查 GitHub 安装后的 build 行为。

官方文档指出：

> Git install 获取的是源码，不会自动得到普通 `build` 命令生成的产物，因此 TypeScript 插件需要正确处理 `prepare` / build artifact。

同时 pnpm 10 对 Git dependency 的 build scripts 有额外限制。

因此 Codex 必须检查：

```text
从 GitHub checkout 安装以后
lib/index.js 是否真实存在
```

如果不存在，则按照官方 publish guide 增加适合独立仓库环境的：

```json
"prepare": "..."
```

不要让 `prepare` 依赖 DeepSeek Harness monorepo 中不存在的 sibling package 或 project reference。

---

# 9. npm 发布不是第一阶段硬要求

当前开源贡献完成标准不要求立刻发布 npm。

优先完成：

```text
GitHub repository
+
GitHub install
+
real DSH profile verification
```

后续如果需要实现：

```bash
dsh plugin --profile web add dsh-experience-memory
```

这种最简单的一行安装体验，再发布 npm。

DeepSeek Harness 官方明确说明 registry publication 不是 Bundle 的必要条件，可以直接从 Git host 安装。

---

# 10. GitHub Repository 必须完善 README

README 第一屏必须立即说明这个插件解决什么问题。

不要从：

```text
class
interface
MemoryStore
Retriever
```

开始。

建议第一句话：

> Keyword-based experience memory for DeepSeek Harness. It turns reusable successes and failures from coding tasks into persistent few-shot experiences that agents can search and recall across sessions.

然后解释核心问题：

```text
Session stores what happened.

Experience Memory stores what is worth reusing.
```

---

# 11. README 推荐结构

README 至少包括：

```text
# dsh-experience-memory

## Why

## Features

## How It Works

## Installation

## Quick Start

## Tools

### memory_search
### memory_get
### memory_record

## Example

## Memory Format

## Architecture

## Retrieval Layer

## Limitations

## Roadmap

## License
```

---

# 12. README 必须突出差异化

当前 DeepSeek Harness 社区已经存在其他 Long-term Memory Plugin，例如 `dsh-memoria`，其方案包括自动 recall、Python memory engine 和多种记忆类型。

参考：

https://github.com/deepseek-ai/deepseek-harness/discussions/2151

因此 README 不能只描述：

> Long-term memory for DeepSeek Harness.

必须突出本项目自身设计：

```text
Experience Memory
Success + Failure Few-shot
Explicit Agent Recall
Keyword-based Retrieval
Progressive Disclosure
Append-only Markdown Store
Pluggable Retriever
No Vector Database Required
No opaque retrieval score exposed to the model
```

尤其强调：

```text
Session
→ raw execution history

Experience Memory
→ distilled reusable experience
```

这是项目的核心定位。

---

# 13. README 必须有真实 Example

使用真实 Coding Harness 场景。

例如：

```text
Task:
修改包含中文的 DeepSeek Harness 文件

Problem:
写入后出现乱码

Historical Experience:

Keywords:
deepseek-harness
typescript
encoding
windows
filesystem

memory_search(...)
↓
memory-17

memory_get(memory-17)
↓
过去成功/失败经验

Agent:
避免再次使用已经验证失败的方法
```

最好展示一次：

```text
Failure Memory
+
Success Memory
```

让读者明显看出：

> Memory 不是普通 Notes，而是过去任务形成的 Few-shot Experience。

---

# 14. README 必须解释 Retrieval Layer

V1：

```text
Keyword Exact Match
```

但是架构保持：

```text
memory_search
       │
       ▼
MemoryRetriever
       │
       ▼
KeywordRetriever
```

未来允许：

```text
Keyword
   ↓
BM25
   ↓
Vector
   ↓
Hybrid
```

Model-facing API 不需要变化。

README 明确说明：

> V1 intentionally uses deterministic keyword matching. More advanced retrievers can be added behind the retrieval interface without changing memory_record, memory_search, or memory_get.

---

# 15. 不宣传 Ranking Score

继续保持现在的设计原则。

Retriever 内部：

```text
rankingScore
```

可以用于：

```text
candidate filtering
Top-K selection
```

但是 model-facing `memory_search` 不暴露该 score。

模型只看到：

```text
ID
Title
Keywords
Matched Keywords
Outcome
```

README 可解释：

> Retrieval ranking is only a candidate-selection signal. Search order and internal scores are not memory confidence and do not guarantee relevance or correctness.

---

# 16. 添加 GitHub Topics

GitHub Repository 至少增加：

```text
dsh-plugin
deepseek-harness
agent-memory
llm-memory
ai-agent
```

其中：

```text
dsh-plugin
```

是 DeepSeek Harness 官方明确推荐的生态发现方式。

官方 README 也再次建议第三方插件添加 `dsh-plugin` topic。

---

# 17. LICENSE

检查现有代码来源。

如果大量代码直接来自：

```text
deepseek-ai/deepseek-harness
```

原始 Memory Plugin 或其他官方 package，则必须检查和保留相应 MIT License / copyright attribution。

DeepSeek Harness 当前使用 MIT License。

官方 License：

https://github.com/deepseek-ai/deepseek-harness/blob/master/LICENSE

不要因为拆成独立仓库丢失原始许可信息。

---

# 18. 添加 Demo

至少准备一种：

```text
Screenshot
GIF
Demo Video
```

最好是 GIF。

推荐演示：

```text
用户遇到问题

↓

Agent 调用 memory_search

↓

出现候选 Experience

↓

Agent 调用 memory_get

↓

读取过去解决同类问题的 Experience

↓

根据过去经验调整当前行为
```

第二段可以展示：

```text
任务完成
↓
memory_record
↓
用户确认
↓
memory.md
```

这样一个 GIF 就能展示完整闭环。

---

# 19. 发布到 DeepSeek Harness Show Your Plugins!

插件准备完成以后，到：

https://github.com/deepseek-ai/deepseek-harness/discussions

选择：

```text
Show Your Plugins!
```

当前官方专门提供该 Discussion category 分享第三方插件。

---

# 20. 必须遵守 Plugin Category Guidelines

官方当前固定规则：

1. 一个 Discussion 只能介绍一个项目；
2. 项目必须真实集成 DeepSeek Harness；
3. 标题格式必须为：

```text
DSH | Project Name | One-line description
```

4. 正文必须包括：

   * 项目 URL；
   * 简介；
   * Screenshot / GIF / Demo；
   * 如何与 DSH 集成；
5. 必须显著注明：

   * 这是非官方社区项目。

这些要求来自官方置顶的 Plugin Category Guidelines。

官方规则：

https://github.com/deepseek-ai/deepseek-harness/discussions/2004

---

# 21. 推荐 Discussion 标题

建议：

```text
DSH | dsh-experience-memory | Reusable success and failure memory for coding agents
```

或者：

```text
DSH | Experience Memory | Keyword-based reusable task memory for DeepSeek Harness
```

优先推荐第二个：

```text
DSH | Experience Memory | Keyword-based reusable task memory for DeepSeek Harness
```

---

# 22. 推荐 Discussion 开头

开头必须显著标记：

```text
> Unofficial project, independently developed and maintained by a community member.
```

这是官方 Plugin Category Guidelines 要求的格式方向。

然后：

```text
Project URL:
<GitHub URL>

Experience Memory is a lightweight long-term memory plugin for DeepSeek Harness.

Instead of searching raw session histories, it stores distilled successes and failures from previous tasks as reusable experiences.

Agents retrieve candidate experiences through keyword search and load only relevant memories as few-shot context.
```

---

# 23. Discussion 中重点展示四件事

不要写成长篇论文。

重点展示：

### 1. Problem

```text
Raw session history contains too much noisy execution detail.
```

### 2. Core Idea

```text
Task history
→ distilled Experience
→ keywords
→ future recall
```

### 3. Three Tools

```text
memory_search
memory_get
memory_record
```

### 4. Demo

```text
过去解决过一个 Harness encoding 问题

↓

新任务遇到相似问题

↓

keyword recall

↓

读取过去 Experience

↓

作为 few-shot 使用
```

---

# 24. 明确说明与 DSH 的集成方式

Discussion 不要只写功能。

需要明确：

```text
How it integrates with DSH
```

例如根据实际代码说明：

```text
- mounts as a Cordis plugin;
- registers memory_search / memory_get / memory_record through the DSH tool registry;
- registers a fixed memory guidance section in the DSH system prompt;
- stores persistent Experience Memory outside transient model context;
- does not modify agent-loop;
- installs as a DSH bundle through cordis.patch.yml.
```

DeepSeek Harness 官方架构强调，DSH 的 model adapter、tool registry、session log、agent loop 等能力本身均通过 Plugin / Cordis 机制组合，第三方能力应通过插件挂载而非修改 privileged core。

官方架构：

https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md

---

# 25. 发布前验证清单

发布前必须全部满足：

```text
[ ] 独立 package 可以 build

[ ] 单元测试通过

[ ] TypeScript check 通过

[ ] memory_search 正常注册

[ ] memory_get 正常注册

[ ] memory_record 正常注册

[ ] System Prompt section 正常注册

[ ] dsh.bundle.patch 存在

[ ] cordis.patch.yml 存在

[ ] dsh plugin --profile demo add ./... 成功

[ ] dsh --profile demo --dump-config 能看到插件

[ ] Profile 可以实际启动

[ ] 插件卸载后 Tool/System Prompt 不残留

[ ] Fresh install 成功

[ ] UTF-8 中文 Memory 正常读写

[ ] README.md 完成

[ ] README.zh.md 完成

[ ] LICENSE 完成

[ ] GitHub repository public

[ ] 添加 dsh-plugin topic

[ ] 至少一份 screenshot/GIF/demo

[ ] Show Your Plugins! Discussion 准备完成
```

---

# 26. GitHub Release

建议发布：

```text
v0.1.0
```

Release Note 简单说明：

```text
Initial release of Experience Memory for DeepSeek Harness.

Features:
- persistent Experience Memory;
- reusable success/failure memories;
- keyword-based candidate retrieval;
- progressive memory disclosure;
- human-confirmed memory recording;
- pluggable retrieval architecture.
```

V1 不要假装已经有：

```text
BM25
Vector
Hybrid
```

只写 Roadmap。

---

# 27. 最终用户安装体验

第一阶段至少达到：

```bash
dsh plugin --profile web add github:<owner>/dsh-experience-memory
```

随后：

```bash
dsh --profile web --dump-config
dsh --profile web
```

如果后续发布 npm，则目标升级成：

```bash
dsh plugin --profile web add dsh-experience-memory
```

---

# 28. Codex 最终交付物

完成本任务后，需要汇报：

```text
1. 独立插件目录 / package 结构

2. package.json Bundle 配置

3. cordis.patch.yml

4. GitHub install 是否成功

5. Fresh Profile 验证结果

6. dump-config 中插件是否存在

7. 三个 Tools 是否真实注册

8. 所有测试和类型检查结果

9. README 改动

10. LICENSE / attribution 状态

11. Demo 生成方式

12. 尚需人工完成的 GitHub 操作
```

如果 Codex 没有 GitHub 凭据，不要伪造：

```text
Repository created
Release published
Discussion posted
```

只需要把本地仓库整理到可直接发布状态，并给出人工执行命令。

---

# 29. 完成标准

最终不以：

```text
代码能跑
```

作为完成标准。

真正完成标准是：

```text
Someone who did not develop this plugin
        ↓
finds the GitHub repository
        ↓
understands what it does
        ↓
installs it into a clean DSH profile
        ↓
boots DSH successfully
        ↓
sees memory_search / memory_get / memory_record
        ↓
can reproduce the Experience Memory workflow
```

达到这个状态后，再发布：

```text
DeepSeek Harness
→ Discussions
→ Show Your Plugins!
```

此时项目才算完成从：

```text
local implementation
```

到：

```text
public DeepSeek Harness ecosystem contribution
```

的转换。

---

# 30. 官方参考来源

## DeepSeek Harness 主仓库

https://github.com/deepseek-ai/deepseek-harness

用途：

* 官方项目入口；
* 当前项目状态；
* `dsh-plugin` topic；
* License；
* 官方开发文档入口。

---

## 官方 Contributing Guide

https://github.com/deepseek-ai/deepseek-harness/blob/master/CONTRIBUTING.md

用途：

* 当前暂不接受 external PR；
* 官方鼓励独立插件贡献；
* 官方建议插件仓库使用 `dsh-plugin` topic。

---

## 官方 Plugin Packaging / Publishing Guide

https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/publish.md

中文：

https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/publish.zh.md

用途：

* `dsh.bundle`;
* `cordis.patch.yml`;
* `dsh plugin add`;
* profile；
* `--dump-config`;
* GitHub install；
* TypeScript `prepare`；
* pnpm build permission。

---

## 官方 Architecture

https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md

用途：

* Cordis Plugin 架构；
* Profile / Bundle；
* Tool registry；
* System Prompt；
* Session；
* Agent Loop；
* Extension points。

---

## 官方 Plugin Category Guidelines

https://github.com/deepseek-ai/deepseek-harness/discussions/2004

用途：

* Show Your Plugins 发帖规范；
* 标题格式；
* 非官方声明；
* 项目 URL；
* Screenshot / GIF；
* DSH Integration 描述。

---

## 官方 Discussions

https://github.com/deepseek-ai/deepseek-harness/discussions

用途：

* Show Your Plugins；
* 社区发布；
* 项目反馈。

---

# 31. 社区参考项目

以下仅作为发布形式和竞品定位参考，不代表官方推荐。

## dsh-memoria

Discussion：

https://github.com/deepseek-ai/deepseek-harness/discussions/2151

特点：

```text
Long-term memory
Auto recall
Python memory engine
Multiple memory types
```

本项目必须与它区分：

```text
Experience-oriented
Success + Failure Few-shot
Explicit progressive recall
Keyword retrieval
Markdown persistence
Pluggable retriever
No automatic recall injection in V1
```

---

## vision-read 插件发布示例

https://github.com/deepseek-ai/deepseek-harness/discussions/2159

可以参考其 Discussion 展示方式：

```text
Unofficial 声明
Project URL
Introduction
How it integrates with DSH
Real demo
Screenshot
```

不要复制内容，只参考社区插件发布结构。

---

# 32. 最后原则

本轮发布工作的优先级：

```text
可安装
>
可验证
>
可理解
>
可展示
>
功能继续扩展
```

不要为了“让项目显得更复杂”继续加入 Memory 功能。

V1 已经有完整闭环：

```text
record
search
get
```

当前真正需要完成的是：

> **把一个已经能工作的 Memory Plugin，变成别人真的能够安装、理解、验证和使用的开源 DeepSeek Harness Plugin。**

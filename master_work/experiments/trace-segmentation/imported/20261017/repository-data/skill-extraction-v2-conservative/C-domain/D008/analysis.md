# C — D008 领域独立保守 Skill 提取

## 口径

你是一个 Skill 提取器。请只根据当前提供的轨迹内容，提取少量但真正可用的 Skill。目标不是覆盖尽可能多的内容，而是只保留能够指导其他类似任务的具体经验。一个 Skill 只有同时满足：轨迹有明确问题/触发条件/约束；有具体判断/决策/解决动作；不是简单读取/修改/运行/测试流水线；有可核对结果/验证方式/完成条件；去掉项目名、文件名和技术栈专有名词后仍可迁移。

本轮不跨组去重，不调用 embedding；仅保留同时满足触发问题、具体动作、可核对结果和迁移边界的条目。

## 读取与计数

- actual_read_scope: 仅读取 domains.json 的 D008 members 指定的 24 个成员切片；领域之间不共享上下文、不跨领域去重；重复成员在不同领域按各自输入独立读取。
- declared_count: 24
- actual_read_count: 24
- read_session_count: 12
- read_slice_count: 24
- missing_file_count: 0
- skills: 5
- discarded: 24

## Skills

### D008-001 准备对话训练/测试集时，不要把混合 corpus.txt 当成唯一数据源；先检查生成脚本实际组合了哪些来源，再以保留 user/gpt 等角色字段的 JSONL 为主，并显式编码纯文本来源，确保训练和测试语义一致。
- trigger: 多来源、混合格式训练或评估管线。
- actions: 准备对话训练/测试集时，不要把混合 corpus.txt 当成唯一数据源；先检查生成脚本实际组合了哪些来源，再以保留 user/gpt 等角色字段的 JSONL 为主，并显式编码纯文本来源，确保训练和测试语义一致。
- verification: 它针对数据血缘和角色语义保真，并验证了文件存在不等于训练脚本实际使用。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 多来源、混合格式训练或评估管线。
- source: segments__claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-02 event_index=195 — Looking at the pipeline: - `encode_corpus.py` — only encodes the **erotica JSON** (`fastchat-erotica-16k-test.json`) into `train_encoded.jsonl` / `test_encoded.jsonl` - `corpus.txt` — contains erotica + TinyStories + OpenWebText (3 sourc...

### D008-002 显存不足但上下文长度是硬约束时，先用实际 GPU 架构排除不支持的精度格式，再优先把 micro-batch 降到 1、用 gradient accumulation 保持有效 batch，保留目标 context size。
- trigger: 显存受限且上下文长度不可牺牲的训练任务。
- actions: 显存不足但上下文长度是硬约束时，先用实际 GPU 架构排除不支持的精度格式，再优先把 micro-batch 降到 1、用 gradient accumulation 保持有效 batch，保留目标 context size。
- verification: 给出了硬件事实、参数优先级和具体逃生路径，而非泛泛建议减小 batch。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 显存受限且上下文长度不可牺牲的训练任务。
- source: segments__claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-02 event_index=195 — Looking at the pipeline: - `encode_corpus.py` — only encodes the **erotica JSON** (`fastchat-erotica-16k-test.json`) into `train_encoded.jsonl` / `test_encoded.jsonl` - `corpus.txt` — contains erotica + TinyStories + OpenWebText (3 sourc...

### D008-003 在 C/C++ 工程中固定 include 只放头文件、src 只放实现文件，并让 Make/脚本目标反映目录约定；构建失败时检查实际编译命令、脚本语法和测试入口，而不是只修 IDE 报红。
- trigger: 有公开头文件和多平台构建脚本的 C/C++ 项目。
- actions: 在 C/C++ 工程中固定 include 只放头文件、src 只放实现文件，并让 Make/脚本目标反映目录约定；构建失败时检查实际编译命令、脚本语法和测试入口，而不是只修 IDE 报红。
- verification: 它把目录约定、构建入口和测试命令变成可审计的工程边界。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 有公开头文件和多平台构建脚本的 C/C++ 项目。
- source: segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-02 event_index=407 — D:\Yggdrasil>make test "=== Running test fixtures ===" 'pass' is not recognized as an internal or external command, operable program or batch file. make: *** [test] Error 1

### D008-004 把会话轨迹发送到外部服务前，先核对项目公开性和许可证，定位单个会话，做本地自动脱敏，再人工复查姓名、路径、内部 URL 和部署信息；遇到 trust-boundary 拒绝就停止，不绕过。
- trigger: 把代码或会话数据提交给外部数据集、审查服务或公共平台。
- actions: 把会话轨迹发送到外部服务前，先核对项目公开性和许可证，定位单个会话，做本地自动脱敏，再人工复查姓名、路径、内部 URL 和部署信息；遇到 trust-boundary 拒绝就停止，不绕过。
- verification: 证据同时覆盖公开性、许可、脱敏和拒绝后的停机边界。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 把代码或会话数据提交给外部数据集、审查服务或公共平台。
- source: segments__claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01 event_index=193 — There are unrelated changes in the tree (the `utils/ranking/*` files, PNGs, docs, Svelte components). Those are not mine and won't go in this PR. But first I need to understand why `generated-models.json` shows 1833 insertions when I onl...

### D008-005 动态路由或 API 文件生成异常时，检查生成清单中的真实 route key/import path，再对照源码目录和运行时 HTTP 状态；自动生成文件被 formatter 改写时，先修生成器/忽略策略，不把手工修补当长期架构。
- trigger: 有自动生成 routes manifest、格式化钩子和动态路径的前端框架。
- actions: 动态路由或 API 文件生成异常时，检查生成清单中的真实 route key/import path，再对照源码目录和运行时 HTTP 状态；自动生成文件被 formatter 改写时，先修生成器/忽略策略，不把手工修补当长期架构。
- verification: 证据把 route manifest、formatter 和开发服务器行为联系起来，能避免反复手改生成文件。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 有自动生成 routes manifest、格式化钩子和动态路径的前端框架。
- source: segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01 event_index=13 — Base directory for this skill: C:\Users\USER\.claude\skills\material-3 # Material Design 3 This skill guides implementation of Google's Material Design 3 (MD3) — a personal, adaptive, expressive design system. MD3 uses dynamic color, ton...

## Discarded

- D008-004: 用户指出本地字体后先检查资产和编译路径 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D008-005: 构建后恢复派生文件并保持 PR 只含意图变更 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D008-007: 对第三方移动应用采用构建门槛、静态扫描、真机行为和清理闭环 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D008-008: 审查 APK 前先验证发布物身份与包类型 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D008-009: 把持续集成失败拆成 schema 门槛和构建工具链分别修复 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D008-010: 遵循仓库既有元数据约定，避免为单个条目过度引入新 schema — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D008-011: 修改本地化源文件时保持格式并只重新生成派生消息 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-03: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-05: segments__claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01: segments__claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-05: segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-06: segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-06 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-07: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-07 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02: segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-01: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-02: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-03: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-04: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-06: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-06 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-08: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-08 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。

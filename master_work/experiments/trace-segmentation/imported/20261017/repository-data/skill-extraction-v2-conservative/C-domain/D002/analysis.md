# C — D002 领域独立保守 Skill 提取

## 口径

你是一个 Skill 提取器。请只根据当前提供的轨迹内容，提取少量但真正可用的 Skill。目标不是覆盖尽可能多的内容，而是只保留能够指导其他类似任务的具体经验。一个 Skill 只有同时满足：轨迹有明确问题/触发条件/约束；有具体判断/决策/解决动作；不是简单读取/修改/运行/测试流水线；有可核对结果/验证方式/完成条件；去掉项目名、文件名和技术栈专有名词后仍可迁移。

本轮不跨组去重，不调用 embedding；仅保留同时满足触发问题、具体动作、可核对结果和迁移边界的条目。

## 读取与计数

- actual_read_scope: 仅读取 domains.json 的 D002 members 指定的 43 个成员切片；领域之间不共享上下文、不跨领域去重；重复成员在不同领域按各自输入独立读取。
- declared_count: 43
- actual_read_count: 43
- read_session_count: 20
- read_slice_count: 43
- missing_file_count: 0
- skills: 5
- discarded: 47

## Skills

### D002-001 显存不足但上下文长度是硬约束时，先用实际 GPU 架构排除不支持的精度格式，再优先把 micro-batch 降到 1、用 gradient accumulation 保持有效 batch，保留目标 context size。
- trigger: 显存受限且上下文长度不可牺牲的训练任务。
- actions: 显存不足但上下文长度是硬约束时，先用实际 GPU 架构排除不支持的精度格式，再优先把 micro-batch 降到 1、用 gradient accumulation 保持有效 batch，保留目标 context size。
- verification: 给出了硬件事实、参数优先级和具体逃生路径，而非泛泛建议减小 batch。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 显存受限且上下文长度不可牺牲的训练任务。
- source: segments__claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-02 event_index=195 — Looking at the pipeline: - `encode_corpus.py` — only encodes the **erotica JSON** (`fastchat-erotica-16k-test.json`) into `train_encoded.jsonl` / `test_encoded.jsonl` - `corpus.txt` — contains erotica + TinyStories + OpenWebText (3 sourc...

### D002-002 面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在所有可用解释器版本上运行同一套测试，不凭当前版本通过宣称兼容。
- trigger: 需要支持多个语言或运行时版本，且能列出实际版本。
- actions: 面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在所有可用解释器版本上运行同一套测试，不凭当前版本通过宣称兼容。
- verification: 证据覆盖需求、阻塞点、修复和 3.7/3.12/3.14 矩阵验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 需要支持多个语言或运行时版本，且能列出实际版本。
- source: segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01 event_index=19 — Today, our target is to reach till milestone 3, also note, for the github version of this project the cryptoscam will just be random hashing functions and encryption running in the background since github hates exploitative code, however...

### D002-003 测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。
- trigger: C/C++ 启动崩溃、有限栈空间或大型状态对象。
- actions: 测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。
- verification: 轨迹从固定退出码定位到 1MB AtomTable 按值复制，并以 17 个测试通过完成因果验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: C/C++ 启动崩溃、有限栈空间或大型状态对象。
- source: segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03 event_index=123 — Now implement the C FFI layer. This is a clean `extern "C"` wrapper over the engine — opaque handles, no C++ headers exposed:

### D002-004 跨 MB1/MB2、UEFI/GOP 等低级协议迁移时，保留旧入口与新入口的显式分支，打印并核对真实 boot tag/framebuffer mode，再依据地址映射和显示模式修复构建模块与应用抽象，最后重新生成镜像验证。
- trigger: 内核、bootloader、固件或 framebuffer 协议迁移。
- actions: 跨 MB1/MB2、UEFI/GOP 等低级协议迁移时，保留旧入口与新入口的显式分支，打印并核对真实 boot tag/framebuffer mode，再依据地址映射和显示模式修复构建模块与应用抽象，最后重新生成镜像验证。
- verification: 证据强调运行时 tag/mode，而不是凭启动配置文件猜测协议是否兼容。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 内核、bootloader、固件或 framebuffer 协议迁移。
- source: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-02 event_index=80 — 
- source: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-04 event_index=500 — 

### D002-005 低级交互程序退出时出现固定地址崩溃，先和同系统中能正常退出的程序比较输入/清理模式，逐步去掉非必要的清屏、光标恢复或忙轮询；用阻塞输入或自然返回建立最小安全路径，未证实的根因保持为假设。
- trigger: 内核/用户态边界上的交互程序退出崩溃。
- actions: 低级交互程序退出时出现固定地址崩溃，先和同系统中能正常退出的程序比较输入/清理模式，逐步去掉非必要的清屏、光标恢复或忙轮询；用阻塞输入或自然返回建立最小安全路径，未证实的根因保持为假设。
- verification: 轨迹用 quill 这一已知工作实现做对照，并明确区分已证实路径与仍待验证的假设。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 内核/用户态边界上的交互程序退出崩溃。
- source: segments__claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d__segment-02 event_index=175 — Found it. The GPF at `rip=0x1052804` on exit is caused by `showCursor()` calling `vga_cursor_enable(14, 15)` which does `outb` to VGA I/O ports — **those ports are not accessible from Ring-1 userland** (CPL=1 vs IOPL=0). Snake avoids thi...

## Discarded

- D002-001: 把多阶段需求转成明确的本轮范围与排除项 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-002: 在训练数据切分前保留对话角色和来源元数据 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-005: 把可嵌入库与 CLI 分离并提供窄的纯 C ABI — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-006: 让头文件、实现文件和构建目标的边界可检查 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-008: 用户指出本地字体后先检查资产和编译路径 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-009: 用新数组引用触发响应式系统更新 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-010: 让窗口打开和进程清理具备幂等生命周期 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-013: 从参考源解析资源并用结构性计数验证结果 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-014: 清理工程时只删除可证明的派生物并同步构建入口 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-015: 构建后恢复派生文件并保持 PR 只含意图变更 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-016: 外发轨迹前做公开性核验、脱敏复查和信任边界停机 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-017: 状态型解释器先建立状态再按要求顺序执行 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-018: 按阶段建立提取边界并以不变量约束低级运行时 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-019: 用索引调试过程中的数据结构不变量和旧二进制隔离 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-020: 先解除测试前置阻塞再判断功能级失败 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-021: 把跨写入和查询的类型转换集中到单一绑定点 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-022: 跨 C 后端与 JS 用户态时先复用现有能力再新增绑定 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-023: 用权限边界和已知程序定位用户态退出故障 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-024: 审查 APK 前先验证发布物身份与包类型 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-025: 把持续集成失败拆成 schema 门槛和构建工具链分别修复 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-026: 遵循仓库既有元数据约定，避免为单个条目过度引入新 schema — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-027: 修改本地化源文件时保持格式并只重新生成派生消息 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-028: 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D002-029: 解释内核最小系统时先分清 kernel、PID 1 和 userspace 责任 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-02: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-01: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-03: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-05: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-03: segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-04: segments__claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-05: segments__claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01: segments__claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-01: segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-02: segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-03: segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-04: segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-05: segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-06: segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-06 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02: segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-01: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-02: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-04: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-06: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-06 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__cursor__debaa898-grafana-loki-monitoring__segment-01: segments__cursor__debaa898-grafana-loki-monitoring__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__opencode__ses_129b55f7effeSKRtimLg9wxpXa__segment-01: segments__opencode__ses_129b55f7effeSKRtimLg9wxpXa__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。

# C — D005 领域独立保守 Skill 提取

## 口径

你是一个 Skill 提取器。请只根据当前提供的轨迹内容，提取少量但真正可用的 Skill。目标不是覆盖尽可能多的内容，而是只保留能够指导其他类似任务的具体经验。一个 Skill 只有同时满足：轨迹有明确问题/触发条件/约束；有具体判断/决策/解决动作；不是简单读取/修改/运行/测试流水线；有可核对结果/验证方式/完成条件；去掉项目名、文件名和技术栈专有名词后仍可迁移。

本轮不跨组去重，不调用 embedding；仅保留同时满足触发问题、具体动作、可核对结果和迁移边界的条目。

## 读取与计数

- actual_read_scope: 仅读取 domains.json 的 D005 members 指定的 45 个成员切片；领域之间不共享上下文、不跨领域去重；重复成员在不同领域按各自输入独立读取。
- declared_count: 45
- actual_read_count: 45
- read_session_count: 16
- read_slice_count: 45
- missing_file_count: 0
- skills: 6
- discarded: 47

## Skills

### D005-001 实现阶段性能力时，先让阶段专属测试和既有回归都通过，再把 README/计划表标记为完成；若失败来自旧进程、锁文件或工具链噪声，先隔离环境问题再判断代码结果。
- trigger: 有独立阶段测试入口的编译器、运行时、游戏或应用工程。
- actions: 实现阶段性能力时，先让阶段专属测试和既有回归都通过，再把 README/计划表标记为完成；若失败来自旧进程、锁文件或工具链噪声，先隔离环境问题再判断代码结果。
- verification: 轨迹把测试证据、环境噪声隔离和交付文档绑定成完整闭环。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 有独立阶段测试入口的编译器、运行时、游戏或应用工程。
- source: segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04 event_index=1433 — 48/48 + 17/17. Now update the README and add the LICENSE:
- source: segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02 event_index=270 — continue complete M1, create a README.MD

### D005-002 面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在所有可用解释器版本上运行同一套测试，不凭当前版本通过宣称兼容。
- trigger: 需要支持多个语言或运行时版本，且能列出实际版本。
- actions: 面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在所有可用解释器版本上运行同一套测试，不凭当前版本通过宣称兼容。
- verification: 证据覆盖需求、阻塞点、修复和 3.7/3.12/3.14 矩阵验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 需要支持多个语言或运行时版本，且能列出实际版本。
- source: segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01 event_index=19 — Today, our target is to reach till milestone 3, also note, for the github version of this project the cryptoscam will just be random hashing functions and encryption running in the background since github hates exploitative code, however...

### D005-003 需要被另一语言或运行时嵌入时，把核心 lexer/parser/codegen 和批处理逻辑放进库，让 CLI 只处理参数、文件和输出；跨 C/C++ 边界只暴露纯 C 结构、句柄和错误结果。
- trigger: 编译器、解释器或数据工具需要被其他语言嵌入。
- actions: 需要被另一语言或运行时嵌入时，把核心 lexer/parser/codegen 和批处理逻辑放进库，让 CLI 只处理参数、文件和输出；跨 C/C++ 边界只暴露纯 C 结构、句柄和错误结果。
- verification: 轨迹明确拆分库/CLI，并采用 opaque handle、extern C 和不暴露 C++ 类型的 ABI 边界。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 编译器、解释器或数据工具需要被其他语言嵌入。
- source: segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03 event_index=123 — Now implement the C FFI layer. This is a clean `extern "C"` wrapper over the engine — opaque handles, no C++ headers exposed:

### D005-004 测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。
- trigger: C/C++ 启动崩溃、有限栈空间或大型状态对象。
- actions: 测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。
- verification: 轨迹从固定退出码定位到 1MB AtomTable 按值复制，并以 17 个测试通过完成因果验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: C/C++ 启动崩溃、有限栈空间或大型状态对象。
- source: segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03 event_index=123 — Now implement the C FFI layer. This is a clean `extern "C"` wrapper over the engine — opaque handles, no C++ headers exposed:

### D005-005 排查文件路由 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让 loader 使用相对路径，再用真实 HTTP 200 验证。
- trigger: 文件路由、SSR loader 和后端 API 代理组合。
- actions: 排查文件路由 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让 loader 使用相对路径，再用真实 HTTP 200 验证。
- verification: 同一诊断链把环境变量作用域、实际参数名和代理后的 200 结果分开验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 文件路由、SSR loader 和后端 API 代理组合。
- source: segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02 event_index=307 — Server is up. API route 404 means Manic isn't picking up nested API directories. Per AGENTS.md: `app/api/hello/index.ts → /api/hello` — but we have `app/api/reddit/user/index.ts` which would mount at `/api/reddit/user`. Let me check if d...
- source: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-04 event_index=464 — Still 404 — the env var still isn't loading. The docs confirm the issue: `$env/dynamic/private` values are only available inside the request lifecycle. But the real problem here is simpler — the `.env` file may just not be getting picked...
- source: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-05 event_index=493 — The real fix here is to eliminate the env variable problem entirely. The right SvelteKit pattern is to create a **`+server.ts` proxy route** inside the frontend that forwards `/db/*` requests to the backend. Then all server loaders use r...

### D005-006 跨 MB1/MB2、UEFI/GOP 等低级协议迁移时，保留旧入口与新入口的显式分支，打印并核对真实 boot tag/framebuffer mode，再依据地址映射和显示模式修复构建模块与应用抽象，最后重新生成镜像验证。
- trigger: 内核、bootloader、固件或 framebuffer 协议迁移。
- actions: 跨 MB1/MB2、UEFI/GOP 等低级协议迁移时，保留旧入口与新入口的显式分支，打印并核对真实 boot tag/framebuffer mode，再依据地址映射和显示模式修复构建模块与应用抽象，最后重新生成镜像验证。
- verification: 证据强调运行时 tag/mode，而不是凭启动配置文件猜测协议是否兼容。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 内核、bootloader、固件或 framebuffer 协议迁移。
- source: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-02 event_index=80 — 
- source: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-04 event_index=500 — 

## Discarded

- D005-001: 把多阶段需求转成明确的本轮范围与排除项 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-005: 让头文件、实现文件和构建目标的边界可检查 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-008: 用户指出本地字体后先检查资产和编译路径 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-009: 用新数组引用触发响应式系统更新 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-010: 让窗口打开和进程清理具备幂等生命周期 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-011: 用同源代理消除前端运行时后端地址分歧 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-012: 把多分辨率界面布局变成运行时几何而非编译期常量 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-014: 从参考源解析资源并用结构性计数验证结果 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-015: 构建后恢复派生文件并保持 PR 只含意图变更 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-016: 外发轨迹前做公开性核验、脱敏复查和信任边界停机 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-017: 状态型解释器先建立状态再按要求顺序执行 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-018: 用索引调试过程中的数据结构不变量和旧二进制隔离 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-019: Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-020: 先读取外部 API 的真实 payload 再建模和渲染 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-021: 用游标和 IntersectionObserver 实现可恢复的分页加载 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-022: 遵循仓库既有元数据约定，避免为单个条目过度引入新 schema — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-023: 修改本地化源文件时保持格式并只重新生成派生消息 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-024: 固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-025: 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-026: 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D005-027: 把数据驱动的内容分组放在服务端 load，保持组件只负责呈现 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-03: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-01: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-03: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-05: segments__claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01: segments__claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-03: segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-04: segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-03: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-04: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-05: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-06: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-06 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-07: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-07 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02: segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-04: segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-01: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-02: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-01: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-02: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-03: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-04: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-04: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-06: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-06 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。

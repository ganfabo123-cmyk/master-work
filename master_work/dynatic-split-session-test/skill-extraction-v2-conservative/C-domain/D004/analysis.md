# C — D004 领域独立保守 Skill 提取

## 口径

你是一个 Skill 提取器。请只根据当前提供的轨迹内容，提取少量但真正可用的 Skill。目标不是覆盖尽可能多的内容，而是只保留能够指导其他类似任务的具体经验。一个 Skill 只有同时满足：轨迹有明确问题/触发条件/约束；有具体判断/决策/解决动作；不是简单读取/修改/运行/测试流水线；有可核对结果/验证方式/完成条件；去掉项目名、文件名和技术栈专有名词后仍可迁移。

本轮不跨组去重，不调用 embedding；仅保留同时满足触发问题、具体动作、可核对结果和迁移边界的条目。

## 读取与计数

- actual_read_scope: 仅读取 domains.json 的 D004 members 指定的 29 个成员切片；领域之间不共享上下文、不跨领域去重；重复成员在不同领域按各自输入独立读取。
- declared_count: 29
- actual_read_count: 29
- read_session_count: 11
- read_slice_count: 29
- missing_file_count: 0
- skills: 5
- discarded: 29

## Skills

### D004-001 排查文件路由 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让 loader 使用相对路径，再用真实 HTTP 200 验证。
- trigger: 文件路由、SSR loader 和后端 API 代理组合。
- actions: 排查文件路由 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让 loader 使用相对路径，再用真实 HTTP 200 验证。
- verification: 同一诊断链把环境变量作用域、实际参数名和代理后的 200 结果分开验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 文件路由、SSR loader 和后端 API 代理组合。
- source: segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02 event_index=307 — Server is up. API route 404 means Manic isn't picking up nested API directories. Per AGENTS.md: `app/api/hello/index.ts → /api/hello` — but we have `app/api/reddit/user/index.ts` which would mount at `/api/reddit/user`. Let me check if d...
- source: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-04 event_index=464 — Still 404 — the env var still isn't loading. The docs confirm the issue: `$env/dynamic/private` values are only available inside the request lifecycle. But the real problem here is simpler — the `.env` file may just not be getting picked...
- source: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-05 event_index=493 — The real fix here is to eliminate the env variable problem entirely. The right SvelteKit pattern is to create a **`+server.ts` proxy route** inside the frontend that forwards `/db/*` requests to the backend. Then all server loaders use r...

### D004-002 用户说明字体已在仓库中时，先读取字体目录和现有 SCSS token，用 @font-face 与正确相对产物路径接入本地字体；只有本地资产不存在时才考虑远程字体，并检查编译 CSS 的加载路径。
- trigger: 前端字体迁移和设计系统接入。
- actions: 用户说明字体已在仓库中时，先读取字体目录和现有 SCSS token，用 @font-face 与正确相对产物路径接入本地字体；只有本地资产不存在时才考虑远程字体，并检查编译 CSS 的加载路径。
- verification: 它以资产事实纠正了远程字体初始方案，并保留了编译路径检查。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 前端字体迁移和设计系统接入。
- source: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-01 event_index=51 — brother I have fonts in the fonts directory, use your eyes
- source: segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01 event_index=13 — Base directory for this skill: C:\Users\USER\.claude\skills\material-3 # Material Design 3 This skill guides implementation of Google's Material Design 3 (MD3) — a personal, adaptive, expressive design system. MD3 uses dynamic color, ton...

### D004-003 数据源内容已变化但 UI 不刷新时，检查响应式系统是否只比较引用；刷新时复制成新数组对象再赋值 store，并用实际界面刷新确认。
- trigger: Alpine、React store 或其他按引用检测变化的 UI。
- actions: 数据源内容已变化但 UI 不刷新时，检查响应式系统是否只比较引用；刷新时复制成新数组对象再赋值 store，并用实际界面刷新确认。
- verification: 证据把同一引用不触发更新的机制与 spread 复制修复直接关联。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: Alpine、React store 或其他按引用检测变化的 UI。
- source: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05 event_index=557 — 

### D004-004 当前端 loader 对后端地址的读取时机不一致时，把请求收敛到同源 server proxy，由 proxy 负责转发；页面只依赖相对 URL，并用开发服务器实际返回码和构建结果验证。
- trigger: SSR 与浏览器请求路径不同、存在端口或环境差异的前端。
- actions: 当前端 loader 对后端地址的读取时机不一致时，把请求收敛到同源 server proxy，由 proxy 负责转发；页面只依赖相对 URL，并用开发服务器实际返回码和构建结果验证。
- verification: 它解决的是请求生命周期和部署地址分歧，而非简单改一个 URL。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: SSR 与浏览器请求路径不同、存在端口或环境差异的前端。
- source: segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02 event_index=307 — Server is up. API route 404 means Manic isn't picking up nested API directories. Per AGENTS.md: `app/api/hello/index.ts → /api/hello` — but we have `app/api/reddit/user/index.ts` which would mount at `/api/reddit/user`. Let me check if d...
- source: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-05 event_index=493 — The real fix here is to eliminate the env variable problem entirely. The right SvelteKit pattern is to create a **`+server.ts` proxy route** inside the frontend that forwards `/db/*` requests to the backend. Then all server loaders use r...

### D004-005 会消耗硬件、启动外部进程或产生不可逆成本的功能，默认由 dangerous/feature flag 阻断；解锁后再要求 CLI 精确确认字符串，确认前展示影响范围；非确认输入必须 no-op 且可测试 abort path。
- trigger: 线程风暴、矿机、删除、发布等高影响操作。
- actions: 会消耗硬件、启动外部进程或产生不可逆成本的功能，默认由 dangerous/feature flag 阻断；解锁后再要求 CLI 精确确认字符串，确认前展示影响范围；非确认输入必须 no-op 且可测试 abort path。
- verification: 同时具备默认阻断、二次确认、公开警告和 no-op 验证，安全边界具体可审计。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 线程风暴、矿机、删除、发布等高影响操作。
- source: segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02 event_index=537 — now time for milestone 7

## Discarded

- D004-004: 让窗口打开和进程清理具备幂等生命周期 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D004-007: 把不同部署/政策要求隔离为独立实现并保留切换边界 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D004-008: 清理工程时只删除可证明的派生物并同步构建入口 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D004-009: Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D004-010: 先读取外部 API 的真实 payload 再建模和渲染 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D004-011: 用游标和 IntersectionObserver 实现可恢复的分页加载 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D004-012: 静态部署项目先核对构建输出目录和托管根目录 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D004-013: 固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D004-014: 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D004-015: 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D004-016: 把数据驱动的内容分组放在服务端 load，保持组件只负责呈现 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-02: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-03: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-04: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01: segments__claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-01: segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02: segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-01: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-02: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-01: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-02: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-03: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-04: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-04: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-08: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-08 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。

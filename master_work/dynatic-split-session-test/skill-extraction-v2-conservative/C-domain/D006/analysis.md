# C — D006 领域独立保守 Skill 提取

## 口径

你是一个 Skill 提取器。请只根据当前提供的轨迹内容，提取少量但真正可用的 Skill。目标不是覆盖尽可能多的内容，而是只保留能够指导其他类似任务的具体经验。一个 Skill 只有同时满足：轨迹有明确问题/触发条件/约束；有具体判断/决策/解决动作；不是简单读取/修改/运行/测试流水线；有可核对结果/验证方式/完成条件；去掉项目名、文件名和技术栈专有名词后仍可迁移。

本轮不跨组去重，不调用 embedding；仅保留同时满足触发问题、具体动作、可核对结果和迁移边界的条目。

## 读取与计数

- actual_read_scope: 仅读取 domains.json 的 D006 members 指定的 36 个成员切片；领域之间不共享上下文、不跨领域去重；重复成员在不同领域按各自输入独立读取。
- declared_count: 36
- actual_read_count: 36
- read_session_count: 16
- read_slice_count: 36
- missing_file_count: 0
- skills: 6
- discarded: 40

## Skills

### D006-001 测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。
- trigger: C/C++ 启动崩溃、有限栈空间或大型状态对象。
- actions: 测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。
- verification: 轨迹从固定退出码定位到 1MB AtomTable 按值复制，并以 17 个测试通过完成因果验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: C/C++ 启动崩溃、有限栈空间或大型状态对象。
- source: segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03 event_index=123 — Now implement the C FFI layer. This is a clean `extern "C"` wrapper over the engine — opaque handles, no C++ headers exposed:

### D006-002 排查文件路由 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让 loader 使用相对路径，再用真实 HTTP 200 验证。
- trigger: 文件路由、SSR loader 和后端 API 代理组合。
- actions: 排查文件路由 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让 loader 使用相对路径，再用真实 HTTP 200 验证。
- verification: 同一诊断链把环境变量作用域、实际参数名和代理后的 200 结果分开验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 文件路由、SSR loader 和后端 API 代理组合。
- source: segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02 event_index=307 — Server is up. API route 404 means Manic isn't picking up nested API directories. Per AGENTS.md: `app/api/hello/index.ts → /api/hello` — but we have `app/api/reddit/user/index.ts` which would mount at `/api/reddit/user`. Let me check if d...

### D006-003 数据源内容已变化但 UI 不刷新时，检查响应式系统是否只比较引用；刷新时复制成新数组对象再赋值 store，并用实际界面刷新确认。
- trigger: Alpine、React store 或其他按引用检测变化的 UI。
- actions: 数据源内容已变化但 UI 不刷新时，检查响应式系统是否只比较引用；刷新时复制成新数组对象再赋值 store，并用实际界面刷新确认。
- verification: 证据把同一引用不触发更新的机制与 spread 复制修复直接关联。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: Alpine、React store 或其他按引用检测变化的 UI。
- source: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05 event_index=557 — 

### D006-004 把 open、close、createProcess 和 terminateProcess 视为一个生命周期：重复打开已存在窗口时直接返回且不创建新进程，关闭窗口必须通过 onClose 清理，最后检查重复点击和关闭后的进程表。
- trigger: 桌面式 Web UI、窗口管理器和有资源副作用的 open/close。
- actions: 把 open、close、createProcess 和 terminateProcess 视为一个生命周期：重复打开已存在窗口时直接返回且不创建新进程，关闭窗口必须通过 onClose 清理，最后检查重复点击和关闭后的进程表。
- verification: 同时覆盖幂等入口、资源创建、释放和可观察的泄漏检查。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 桌面式 Web UI、窗口管理器和有资源副作用的 open/close。
- source: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05 event_index=557 — 

### D006-005 当前端 loader 对后端地址的读取时机不一致时，把请求收敛到同源 server proxy，由 proxy 负责转发；页面只依赖相对 URL，并用开发服务器实际返回码和构建结果验证。
- trigger: SSR 与浏览器请求路径不同、存在端口或环境差异的前端。
- actions: 当前端 loader 对后端地址的读取时机不一致时，把请求收敛到同源 server proxy，由 proxy 负责转发；页面只依赖相对 URL，并用开发服务器实际返回码和构建结果验证。
- verification: 它解决的是请求生命周期和部署地址分歧，而非简单改一个 URL。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: SSR 与浏览器请求路径不同、存在端口或环境差异的前端。
- source: segments__claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02 event_index=307 — Server is up. API route 404 means Manic isn't picking up nested API directories. Per AGENTS.md: `app/api/hello/index.ts → /api/hello` — but we have `app/api/reddit/user/index.ts` which would mount at `/api/reddit/user`. Let me check if d...

### D006-006 支持多种屏幕尺寸时，定义允许的分辨率选项和运行时 ScreenConfig，用当前宽高派生网格、侧栏和 cell size；渲染容量可保留最大值，但布局按 viewport 合成，并为每种尺寸运行构建或烟测。
- trigger: 游戏或桌面 UI 需要支持多个固定分辨率。
- actions: 支持多种屏幕尺寸时，定义允许的分辨率选项和运行时 ScreenConfig，用当前宽高派生网格、侧栏和 cell size；渲染容量可保留最大值，但布局按 viewport 合成，并为每种尺寸运行构建或烟测。
- verification: 轨迹把屏幕选项、几何派生、比例和构建验证连成具体实现策略。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 游戏或桌面 UI 需要支持多个固定分辨率。
- source: segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02 event_index=270 — continue complete M1, create a README.MD

## Discarded

- D006-001: 把多阶段需求转成明确的本轮范围与排除项 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-002: 用阶段专属测试套件证明阶段完成后再更新文档 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-003: 把可嵌入库与 CLI 分离并提供窄的纯 C ABI — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-006: 用户指出本地字体后先检查资产和编译路径 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-011: 对高影响操作实施分层开关、精确确认和公开警告 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-012: 把不同部署/政策要求隔离为独立实现并保留切换边界 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-013: 清理工程时只删除可证明的派生物并同步构建入口 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-014: 按阶段建立提取边界并以不变量约束低级运行时 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-015: 用索引调试过程中的数据结构不变量和旧二进制隔离 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-016: Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-017: 先读取外部 API 的真实 payload 再建模和渲染 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-018: 用游标和 IntersectionObserver 实现可恢复的分页加载 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-019: 静态部署项目先核对构建输出目录和托管根目录 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-020: 固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-021: 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-022: 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D006-023: 把固定资源约束写成可检查的不变量并将大型工作区移出栈 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-02: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-03: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-04: segments__claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01: segments__claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-03: segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-04: segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-01: segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-02: segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-03: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-06: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-06 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-07: segments__claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-07 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02: segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-01: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-02: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-01: segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-01: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-02: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-03: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-04: segments__claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。

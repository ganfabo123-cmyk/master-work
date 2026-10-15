# A — 完整 Session 保守 Skill 提取

## 口径

你是一个 Skill 提取器。请只根据当前提供的轨迹内容，提取少量但真正可用的 Skill。目标不是覆盖尽可能多的内容，而是只保留能够指导其他类似任务的具体经验。一个 Skill 只有同时满足：轨迹有明确问题/触发条件/约束；有具体判断/决策/解决动作；不是简单读取/修改/运行/测试流水线；有可核对结果/验证方式/完成条件；去掉项目名、文件名和技术栈专有名词后仍可迁移。

本轮不跨组去重，不调用 embedding；仅保留同时满足触发问题、具体动作、可核对结果和迁移边界的条目。

## 读取与计数

- actual_read_scope: 读取 manifest 中全部 30 个 Session，并逐个读取其 context-expanded-sessions 下全部 118 个 JSON 文件（117 个 segment-*.json 与 1 个 index/元数据文件）；未读取其他实验组输入。
- declared_count: 30
- actual_read_count: 30
- read_session_count: 30
- missing_file_count: 0
- skills: 12
- discarded: 21

## Skills

### A-001 准备对话模型训练/测试集时，不要直接把混合 corpus.txt 当成唯一数据源；先检查数据生成脚本实际组合了哪些来源，再以保留 user/gpt 等角色字段的 JSONL 为主，并把纯文本来源显式编码成约定角色，确保训练集和测试集与真实语料构成一致。
- trigger: 适用于由多种来源、不同格式组成的训练/评估管线；前提是角色或来源语义会影响模型学习或评估。
- actions: 准备对话模型训练/测试集时，不要直接把混合 corpus.txt 当成唯一数据源；先检查数据生成脚本实际组合了哪些来源，再以保留 user/gpt 等角色字段的 JSONL 为主，并把纯文本来源显式编码成约定角色，确保训练集和测试集与真实语料构成一致。
- verification: 这是可复用的数据血缘和语义保真规则，直接指出了一个常见但隐蔽的失败模式：文件存在不等于训练管线使用了它。单轨迹也足以形成清晰、可验证的 Skill。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于由多种来源、不同格式组成的训练/评估管线；前提是角色或来源语义会影响模型学习或评估。
- source: ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a event_index=37 — using raw_corpus for training isnt good ... metadata of 'user', 'gpt' etc isnt lost
- source: ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a event_index=195 — encode_corpus.py ... only encodes the erotica JSON ... corpus.txt ... is never used by the trainer

### A-002 当显存不足但上下文长度是硬约束时，先用实际 GPU 架构排除不支持的精度格式，再优先把 micro-batch 降到 1、用 gradient accumulation 保持有效 batch，保留目标 context size；不要用不受硬件支持的 FP8 作为默认逃生路径。
- trigger: 适用于显存受限的训练任务，尤其是 context length 有明确验收要求时；前提是能读取 GPU/运行时能力。
- actions: 当显存不足但上下文长度是硬约束时，先用实际 GPU 架构排除不支持的精度格式，再优先把 micro-batch 降到 1、用 gradient accumulation 保持有效 batch，保留目标 context size；不要用不受硬件支持的 FP8 作为默认逃生路径。
- verification: 它给出约束优先级和可操作的调参顺序，兼顾硬件事实、上下文质量和有效 batch，远比泛泛的“减少 batch size”更可迁移。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于显存受限的训练任务，尤其是 context length 有明确验收要求时；前提是能读取 GPU/运行时能力。
- source: ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a event_index=185 — FP8 ... requires Ada/Hopper ... the A500 is Ampere
- source: ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a event_index=190 — batch_size 1 ... grad_accum 32 ... 1024 ctx — untouched

### A-003 面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在可用的多个解释器版本上运行同一套测试，而不是仅凭当前版本通过就宣称兼容。
- trigger: 适用于需要支持多个语言/运行时版本的项目；前提是能列出实际可用的版本并执行同一回归集。
- actions: 面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在可用的多个解释器版本上运行同一套测试，而不是仅凭当前版本通过就宣称兼容。
- verification: 轨迹展示了从需求、阻塞点定位、兼容实现到跨版本验证的完整闭环，而不是只提供一个版本号清单。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于需要支持多个语言/运行时版本的项目；前提是能列出实际可用的版本并执行同一回归集。
- source: 07b57159-218e-4330-a64e-0ec4b4355056 event_index=425 — Support both 3.7 and 4.8+
- source: 07b57159-218e-4330-a64e-0ec4b4355056 event_index=430 — kw_only=True ... 3.10+ only; int | float union
- source: 07b57159-218e-4330-a64e-0ec4b4355056 event_index=482 — All three testable versions (3.7, 3.12, 3.14) pass identically

### A-004 当一个工具需要被另一语言或运行时嵌入时，把核心 lexer/parser/codegen 与批处理逻辑放进库，让 CLI 只处理参数、文件和输出；跨 C/C++ 边界只暴露纯 C 结构和错误结果，避免 STL、异常或 C++ 类穿过 ABI。
- trigger: 适用于把编译器、解释器或数据处理工具嵌入其他语言/宿主运行时；前提是宿主边界需要稳定 ABI。
- actions: 当一个工具需要被另一语言或运行时嵌入时，把核心 lexer/parser/codegen 与批处理逻辑放进库，让 CLI 只处理参数、文件和输出；跨 C/C++ 边界只暴露纯 C 结构和错误结果，避免 STL、异常或 C++ 类穿过 ABI。
- verification: 它明确了职责边界、内存/异常边界和公开接口的形状，可直接指导架构切分，超出某个具体编译器实现细节。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于把编译器、解释器或数据处理工具嵌入其他语言/宿主运行时；前提是宿主边界需要稳定 ABI。
- source: 92833a43-c30d-4b44-8447-c32ee17d6e6e event_index=2 — The CLI becomes a user of the library, not the owner of the logic
- source: 92833a43-c30d-4b44-8447-c32ee17d6e6e event_index=193 — Public C API — the only header GlacioJS needs

### A-005 遇到测试程序启动即崩溃、且测试主体还未执行时，先检查大型结构体是否被按值声明或返回；把隐式拷贝改为引用/指针后再重跑最小测试和全套测试，确认崩溃与修复的因果关系。
- trigger: 适用于 C/C++ 启动即崩溃、栈空间有限或大型状态对象的测试/运行时；前提是能看到类型大小和初始化路径。
- actions: 遇到测试程序启动即崩溃、且测试主体还未执行时，先检查大型结构体是否被按值声明或返回；把隐式拷贝改为引用/指针后再重跑最小测试和全套测试，确认崩溃与修复的因果关系。
- verification: 同一诊断规则在两个不同工程中出现并且能导出具体修复动作：从按值复制改为引用，之后以小测试和全量测试验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于 C/C++ 启动即崩溃、栈空间有限或大型状态对象的测试/运行时；前提是能看到类型大小和初始化路径。
- source: 479c5e9f-a299-457f-8459-5948adf8aa8e event_index=324 — AtomTable t = make_table(); — this copies the 1MB AtomTable by value onto the LOCAL stack
- source: 479c5e9f-a299-457f-8459-5948adf8aa8e event_index=334 — All 17 atom tests pass
- source: c99032e9-377b-4ae9-a9a9-ec7752b059cd event_index=1203 — AtomTable t = make_table() copies the ~1MB AtomTable onto the local stack
- source: c99032e9-377b-4ae9-a9a9-ec7752b059cd event_index=1219 — Now rebuild and run everything

### A-006 排查 SvelteKit 等文件路由的 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让页面 loader 使用相对路径，再用真实 HTTP 200 验证。
- trigger: 适用于文件系统路由、服务端 loader 和后端 API 代理组合；前提是能读取实际目录名、框架文档和网络响应。
- actions: 排查 SvelteKit 等文件路由的 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让页面 loader 使用相对路径，再用真实 HTTP 200 验证。
- verification: 它把 404 分解成两个可证伪的层次：路由参数事实和运行时配置作用域，并给出同源代理这个稳定的边界修复。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于文件系统路由、服务端 loader 和后端 API 代理组合；前提是能读取实际目录名、框架文档和网络响应。
- source: c84c0ad3-c368-40df-87b1-5ef9effe237a event_index=464 — env var still isn't loading
- source: c84c0ad3-c368-40df-87b1-5ef9effe237a event_index=493 — create a +server.ts proxy route ... forwards /db/* requests
- source: c84c0ad3-c368-40df-87b1-5ef9effe237a event_index=504 — directories are literally named [slug] ... params.name won't exist

### A-007 把应用的 open、close、createProcess 和 terminateProcess 看成一个生命周期：重复打开已存在窗口时直接返回且不创建新进程，关闭窗口必须通过 onClose 调用应用清理，最后检查重复点击和关闭后的进程表。
- trigger: 适用于桌面式 Web UI、窗口管理器、任务/进程面板和任何有 open/close 副作用的交互系统。
- actions: 把应用的 open、close、createProcess 和 terminateProcess 看成一个生命周期：重复打开已存在窗口时直接返回且不创建新进程，关闭窗口必须通过 onClose 调用应用清理，最后检查重复点击和关闭后的进程表。
- verification: 它明确了幂等入口、资源创建和资源释放三者必须同时设计，直接针对重复点击造成的泄漏和关闭不清理问题。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于桌面式 Web UI、窗口管理器、任务/进程面板和任何有 open/close 副作用的交互系统。
- source: 09d9abe9-0a02-4bd1-8129-3b864695079d event_index=577 — createProcess()d every time open() is called, leaking processes
- source: 09d9abe9-0a02-4bd1-8129-3b864695079d event_index=596 — guard ... with windows.isOpen() ... onClose ... terminateProcess()

### A-008 需要支持多种屏幕尺寸时，先定义允许的分辨率选项和运行时 ScreenConfig，再用 active width/height 派生网格、侧栏和 cell size；让渲染纹理保留最大容量但按当前 viewport 合成，并用明确比例（如 80/20）和每个分辨率的构建结果验证。
- trigger: 适用于游戏 HUD、仪表盘和响应式界面；前提是布局规则能表达为运行时几何或比例。
- actions: 需要支持多种屏幕尺寸时，先定义允许的分辨率选项和运行时 ScreenConfig，再用 active width/height 派生网格、侧栏和 cell size；让渲染纹理保留最大容量但按当前 viewport 合成，并用明确比例（如 80/20）和每个分辨率的构建结果验证。
- verification: 它把溢出、响应式、可选分辨率和网格缩放统一到运行时几何模型，避免为每种尺寸复制一套界面代码。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于游戏 HUD、仪表盘和响应式界面；前提是布局规则能表达为运行时几何或比例。
- source: 4222016d-1932-4abb-94b3-463203bd8876 event_index=887 — screen size should either be 640x320, 1920 x 720, 1920 x 1080 ... option to choose
- source: 4222016d-1932-4abb-94b3-463203bd8876 event_index=1166 — Grid = 80% of screen width ... Sidebar = 20%
- source: d4c4d47d-642c-4c26-a866-51ab85587896 event_index=49 — its overflowing the screen ... fix that
- source: d4c4d47d-642c-4c26-a866-51ab85587896 event_index=414 — show only 2 one below another and then pagination

### A-009 跨 MB1/MB2、UEFI/GOP 或类似低级协议迁移时，保留旧入口与新入口的显式分支，先打印并核对实际 boot tag/framebuffer mode，再依据真实地址映射和显示模式修复构建模块与应用显示抽象，最后重新生成镜像验证。
- trigger: 适用于操作系统、引导程序、驱动和硬件协议兼容迁移；前提是运行时能暴露启动参数或硬件模式。
- actions: 跨 MB1/MB2、UEFI/GOP 或类似低级协议迁移时，保留旧入口与新入口的显式分支，先打印并核对实际 boot tag/framebuffer mode，再依据真实地址映射和显示模式修复构建模块与应用显示抽象，最后重新生成镜像验证。
- verification: 这是具体的证据驱动迁移方法，避免把某个启动协议的假设偷偷带入另一个入口；低级系统中单条轨迹已经给出足够强的可迁移规则。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于操作系统、引导程序、驱动和硬件协议兼容迁移；前提是运行时能暴露启动参数或硬件模式。
- source: 17c2cf98-e64a-43c6-932e-fa7efcade358 event_index=259 — MB1 ... MB2 ... no actual text is rendered just plain black screen
- source: 17c2cf98-e64a-43c6-932e-fa7efcade358 event_index=279 — [BOOT] MB2 boot
- source: 17c2cf98-e64a-43c6-932e-fa7efcade358 event_index=310 — fix the snake game to properly support both MB2 and MB1

### A-010 排查低级交互程序退出时的固定地址崩溃时，先和同一系统中已知能正常退出的程序比较输入/清理模式，再逐步去掉非必要的清屏、光标恢复或忙轮询，使用阻塞输入或自然返回建立最小安全路径，并把尚未证实的根因保持为假设。
- trigger: 适用于内核态/嵌入式交互程序、终端 UI 和退出清理崩溃；前提是有同一代码库中的稳定对照实现。
- actions: 排查低级交互程序退出时的固定地址崩溃时，先和同一系统中已知能正常退出的程序比较输入/清理模式，再逐步去掉非必要的清屏、光标恢复或忙轮询，使用阻塞输入或自然返回建立最小安全路径，并把尚未证实的根因保持为假设。
- verification: 它强调对照、最小化和证据分级，特别适合固定 RIP 但初始根因不确定的低级故障。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于内核态/嵌入式交互程序、终端 UI 和退出清理崩溃；前提是有同一代码库中的稳定对照实现。
- source: f93127ef-dec9-4d58-964b-ee660964ec4d event_index=168 — General Protection Fault ... on quit/exit of htop
- source: f93127ef-dec9-4d58-964b-ee660964ec4d event_index=187 — look at what quill does on exit
- source: f93127ef-dec9-4d58-964b-ee660964ec4d event_index=213 — Using getChar() ... matches exactly the pattern quill uses

### A-011 对于会消耗硬件、启动外部进程或产生不可逆成本的功能，先用显式 dangerous/feature flag 阻断默认路径，再要求 CLI 中的精确确认字符串，确认前展示影响范围；非确认输入必须 no-op 并可测试 abort path。
- trigger: 适用于资源密集、破坏性、付费或外部副作用操作；前提是 CLI/入口可以提供独立开关和确认交互。
- actions: 对于会消耗硬件、启动外部进程或产生不可逆成本的功能，先用显式 dangerous/feature flag 阻断默认路径，再要求 CLI 中的精确确认字符串，确认前展示影响范围；非确认输入必须 no-op 并可测试 abort path。
- verification: 这是可迁移的安全交互协议，证据明确覆盖默认阻断、影响披露、精确确认和取消验证；不需要把具体高风险功能本身迁移出去。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于资源密集、破坏性、付费或外部副作用操作；前提是 CLI/入口可以提供独立开关和确认交互。
- source: 07b57159-218e-4330-a64e-0ec4b4355056 event_index=537 — now time for milestone 7
- source: 07b57159-218e-4330-a64e-0ec4b4355056 event_index=658 — first ask the user confirmation in the cli with a warning
- source: 07b57159-218e-4330-a64e-0ec4b4355056 event_index=675 — anything other than YES ... Aborted

### A-012 需要保存敏感地址或配置时，不把真实值直接写入代码仓库；使用运行时盐/随机 UUID 等输入加密后存储，并把盐/存储位置与代码分开，提供显式 setup/show/clear 入口和加密-解密 round-trip 测试，同时支持安全的非交互初始化参数。
- trigger: 适用于钱包地址、API token、部署密钥等敏感配置；前提是密钥管理策略允许本地加密存储，并能明确区分交互与自动化初始化。
- actions: 需要保存敏感地址或配置时，不把真实值直接写入代码仓库；使用运行时盐/随机 UUID 等输入加密后存储，并把盐/存储位置与代码分开，提供显式 setup/show/clear 入口和加密-解密 round-trip 测试，同时支持安全的非交互初始化参数。
- verification: 轨迹包含存储分离、用户输入安全、自动化接口和 round-trip 验证四个必要部分；Skill 描述的是安全边界与验证方法，不复述具体加密实现细节。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 适用于钱包地址、API token、部署密钥等敏感配置；前提是密钥管理策略允许本地加密存储，并能明确区分交互与自动化初始化。
- source: 07b57159-218e-4330-a64e-0ec4b4355056 event_index=585 — value is encrypted using current_time, current_date, random UUID as salt + value ... salt itself is stored in another ... directory
- source: 07b57159-218e-4330-a64e-0ec4b4355056 event_index=632 — getpass reads directly from the TTY ... add a --address flag for non-interactive use
- source: 07b57159-218e-4330-a64e-0ec4b4355056 event_index=642 — Encrypt → decrypt round-trip perfect

## Discarded

- S01: 把多阶段需求转成明确的本轮范围与排除项 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S04: 用阶段专属测试套件证明阶段完成后再更新文档 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S07: 让头文件、实现文件和构建目标的边界可检查 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S10: 用户指出本地字体后先检查资产和编译路径 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S11: 用新数组引用触发 Alpine 等响应式系统更新 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S13: 用同源代理消除前端运行时后端地址分歧 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S17: 从参考源解析资源并用结构性计数验证结果 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S19: 把不同部署/政策要求隔离为独立实现并保留切换边界 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S21: 清理工程时只删除可证明的派生物并同步构建入口 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S22: 构建后恢复派生文件并保持 PR 只含意图变更 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S23: 外发轨迹前做公开性核验、脱敏复查和信任边界停机 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S24: 从配置和迁移代码追溯字段语义再解释数据 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- S25: 状态型解释器先建立状态再按要求的顺序执行 — 未达到宁少勿滥口径：缺少足够明确的迁移边界、可核对结果，或本轮优先保留更具体的经验。
- W01: 泛化为‘先 Read/Edit，再 Compile/Test’ — 这是几乎所有开发轨迹都有的工具顺序，没有具体诊断不变量或可迁移决策。
- W02: 把所有 UI ‘更像 Apple/更好看’请求合并成一个设计 Skill — 轨迹显示的是不同项目和个人审美偏好；除局部字体、响应式几何等已拆出的具体规则外，整体目标不足以形成可验证 Skill。
- W03: 把 Vercel 部署、插件安装和一次性部署配置当作通用 Skill — 证据是单次项目配置和外部平台行为，缺少稳定的跨平台不变量；不能只因出现了 buildCommand 就泛化。
- W04: 把所有 donate-trace 对话抽成‘任何数据都可以上传’ — 高质量部分是公开性、脱敏和信任边界停机；‘上传数据’本身不是 Skill，且轨迹明确显示外部上传可能被阻断。
- W05: 把具体的加密货币挖矿实现步骤提取成 Skill — 轨迹支持的是危险操作的分层确认与敏感配置保护，不足以或不应把具体挖矿实现传播为通用 Skill；功能本身也是项目域特例。
- W06: 把 30 条中的未含正文的工具调用轨迹当作行为 Skill — 该轨迹有 tool call 计数但 context-expanded 分段没有可用 text 事件，无法从正文证明具体意图或质量。
- W07: 把固定项目事实（某角色名、某书名、某个人 URL）当作 Skill — 这些是内容资产或个人偏好，不能脱离项目迁移；已保留的 Skill 只描述内容校验或 URL 清理方法。
- W08: 把‘更新 README/CHANGELOG’单独提取成高质量 Skill — 仅有文档更新动作时过于泛化；只有与测试门槛、派生物清理或 ABI 交付边界结合时，才形成上面保留的具体 Skill。

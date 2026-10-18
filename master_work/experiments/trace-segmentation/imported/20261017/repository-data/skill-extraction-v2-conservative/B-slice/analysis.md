# B — 97 个切片保守 Skill 提取

## 口径

你是一个 Skill 提取器。请只根据当前提供的轨迹内容，提取少量但真正可用的 Skill。目标不是覆盖尽可能多的内容，而是只保留能够指导其他类似任务的具体经验。一个 Skill 只有同时满足：轨迹有明确问题/触发条件/约束；有具体判断/决策/解决动作；不是简单读取/修改/运行/测试流水线；有可核对结果/验证方式/完成条件；去掉项目名、文件名和技术栈专有名词后仍可迁移。

本轮不跨组去重，不调用 embedding；仅保留同时满足触发问题、具体动作、可核对结果和迁移边界的条目。

## 读取与计数

- actual_read_scope: 递归逐个读取 97 个 segment-*.json（声明 97）；所属 Session 目录 30 个；不读取完整 Session 或领域输入。
- declared_count: 97
- actual_read_count: 97
- read_session_count: 30
- read_slice_count: 97
- missing_file_count: 0
- skills: 16
- discarded: 34

## Skills

### B-001 准备对话训练/测试集时，不要把混合 corpus.txt 当成唯一数据源；先检查生成脚本实际组合了哪些来源，再以保留 user/gpt 等角色字段的 JSONL 为主，并显式编码纯文本来源，确保训练和测试语义一致。
- trigger: 多来源、混合格式训练或评估管线。
- actions: 准备对话训练/测试集时，不要把混合 corpus.txt 当成唯一数据源；先检查生成脚本实际组合了哪些来源，再以保留 user/gpt 等角色字段的 JSONL 为主，并显式编码纯文本来源，确保训练和测试语义一致。
- verification: 它针对数据血缘和角色语义保真，并验证了文件存在不等于训练脚本实际使用。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 多来源、混合格式训练或评估管线。
- source: claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-01.json event_index=37 — actually using raw_corpus for training isnt good, inspect the entire main.py to identify what the actual corpus is composed of then make a test-train seta from that dataset so the metadata of "user", "gpt" etc isnt lost
- source: claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-02.json event_index=195 — Looking at the pipeline: - `encode_corpus.py` — only encodes the **erotica JSON** (`fastchat-erotica-16k-test.json`) into `train_encoded.jsonl` / `test_encoded.jsonl` - `corpus.txt` — contains erotica + TinyStories + OpenWebText (3 sourc...

### B-002 显存不足但上下文长度是硬约束时，先用实际 GPU 架构排除不支持的精度格式，再优先把 micro-batch 降到 1、用 gradient accumulation 保持有效 batch，保留目标 context size。
- trigger: 显存受限且上下文长度不可牺牲的训练任务。
- actions: 显存不足但上下文长度是硬约束时，先用实际 GPU 架构排除不支持的精度格式，再优先把 micro-batch 降到 1、用 gradient accumulation 保持有效 batch，保留目标 context size。
- verification: 给出了硬件事实、参数优先级和具体逃生路径，而非泛泛建议减小 batch。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 显存受限且上下文长度不可牺牲的训练任务。
- source: claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-02.json event_index=185 — FP8 needs PyTorch 2.1+ with Hopper (H100) or Ada (RTX 40xx) GPUs — the A500 is Ampere and doesn't have FP8 hardware. Your real options: | Precision | A500 Support | Notes | |---|---|---| | `fp32` | Yes | Slowest, most VRAM | | `fp16` | Y...
- source: claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-02.json event_index=190 — With 4GB VRAM, 350M model in bf16, and 1024 ctx — the only lever is batch size. Let's find the minimum that fits: ```powershell python train.py --chunk_size 1024 --batch_size 1 --grad_accum 32 --dtype bf16 ``` - **batch_size 1** — absolu...

### B-003 实现阶段性能力时，先让阶段专属测试和既有回归都通过，再把 README/计划表标记为完成；若失败来自旧进程、锁文件或工具链噪声，先隔离环境问题再判断代码结果。
- trigger: 有独立阶段测试入口的编译器、运行时、游戏或应用工程。
- actions: 实现阶段性能力时，先让阶段专属测试和既有回归都通过，再把 README/计划表标记为完成；若失败来自旧进程、锁文件或工具链噪声，先隔离环境问题再判断代码结果。
- verification: 轨迹把测试证据、环境噪声隔离和交付文档绑定成完整闭环。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 有独立阶段测试入口的编译器、运行时、游戏或应用工程。
- source: claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6/segment-04.json event_index=1433 — 48/48 + 17/17. Now update the README and add the LICENSE:
- source: claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833/segment-03.json event_index=581 — All three suites pass green: - **Stage 1 smoke**: all passed, allocs=1246 / frees=1246 (zero leak) - **Stage 2 subsystems**: 135/135 passed - **Stage 3 bytecode**: 101/101 passed The library built cleanly -- no warnings on the new files....
- source: claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-02.json event_index=621 — do M4-M6

### B-004 面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在所有可用解释器版本上运行同一套测试，不凭当前版本通过宣称兼容。
- trigger: 需要支持多个语言或运行时版本，且能列出实际版本。
- actions: 面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在所有可用解释器版本上运行同一套测试，不凭当前版本通过宣称兼容。
- verification: 证据覆盖需求、阻塞点、修复和 3.7/3.12/3.14 矩阵验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 需要支持多个语言或运行时版本，且能列出实际版本。
- source: claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json event_index=425 — Support both 3.7 and 4.8+
- source: claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json event_index=482 — All three testable versions (3.7, 3.12, 3.14) pass identically. The freethreaded 3.14t launcher tag doesn't work with `py -V:3.14t` on your setup but that's a launcher quirk, not a code issue — it's the same interpreter as 3.14.

### B-005 需要被另一语言或运行时嵌入时，把核心 lexer/parser/codegen 和批处理逻辑放进库，让 CLI 只处理参数、文件和输出；跨 C/C++ 边界只暴露纯 C 结构、句柄和错误结果。
- trigger: 编译器、解释器或数据工具需要被其他语言嵌入。
- actions: 需要被另一语言或运行时嵌入时，把核心 lexer/parser/codegen 和批处理逻辑放进库，让 CLI 只处理参数、文件和输出；跨 C/C++ 边界只暴露纯 C 结构、句柄和错误结果。
- verification: 轨迹明确拆分库/CLI，并采用 opaque handle、extern C 和不暴露 C++ 类型的 ABI 边界。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 编译器、解释器或数据工具需要被其他语言嵌入。
- source: claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e/segment-01.json event_index=71 — The CLI still needs the full C++ headers (watcher, batch, signal handling) since it drives those directly. The split is: `libyggdrasil` contains all logic files except `main.cpp`; `main.cpp` links against `libyggdrasil` and uses both the...
- source: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json event_index=123 — Now implement the C FFI layer. This is a clean `extern "C"` wrapper over the engine — opaque handles, no C++ headers exposed:

### B-006 测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。
- trigger: C/C++ 启动崩溃、有限栈空间或大型状态对象。
- actions: 测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。
- verification: 轨迹从固定退出码定位到 1MB AtomTable 按值复制，并以 17 个测试通过完成因果验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: C/C++ 启动崩溃、有限栈空间或大型状态对象。
- source: claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json event_index=324 — Line 108: `AtomTable t = make_table();` — this copies the 1MB `AtomTable` by value onto the LOCAL stack! That's an immediate stack overflow. This was pre-existing before my changes. This is a simple fix — change the copy to a reference:

### B-007 排查文件路由 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让 loader 使用相对路径，再用真实 HTTP 200 验证。
- trigger: 文件路由、SSR loader 和后端 API 代理组合。
- actions: 排查文件路由 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让 loader 使用相对路径，再用真实 HTTP 200 验证。
- verification: 同一诊断链把环境变量作用域、实际参数名和代理后的 200 结果分开验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 文件路由、SSR loader 和后端 API 代理组合。
- source: claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-04.json event_index=464 — Still 404 — the env var still isn't loading. The docs confirm the issue: `$env/dynamic/private` values are only available inside the request lifecycle. But the real problem here is simpler — the `.env` file may just not be getting picked...
- source: claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-05.json event_index=493 — The real fix here is to eliminate the env variable problem entirely. The right SvelteKit pattern is to create a **`+server.ts` proxy route** inside the frontend that forwards `/db/*` requests to the backend. Then all server loaders use r...
- source: claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json event_index=307 — Server is up. API route 404 means Manic isn't picking up nested API directories. Per AGENTS.md: `app/api/hello/index.ts → /api/hello` — but we have `app/api/reddit/user/index.ts` which would mount at `/api/reddit/user`. Let me check if d...

### B-008 把 open、close、createProcess 和 terminateProcess 视为一个生命周期：重复打开已存在窗口时直接返回且不创建新进程，关闭窗口必须通过 onClose 清理，最后检查重复点击和关闭后的进程表。
- trigger: 桌面式 Web UI、窗口管理器和有资源副作用的 open/close。
- actions: 把 open、close、createProcess 和 terminateProcess 视为一个生命周期：重复打开已存在窗口时直接返回且不创建新进程，关闭窗口必须通过 onClose 清理，最后检查重复点击和关闭后的进程表。
- verification: 同时覆盖幂等入口、资源创建、释放和可观察的泄漏检查。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 桌面式 Web UI、窗口管理器和有资源副作用的 open/close。
- source: claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-05.json event_index=577 — I can see several problems: 1. **Each `ClockApp` instance has `private process` but a new instance is created in `core.ts` for `desktopIcon()`, then a different one would be used for `open()` — but actually the same instance is used here...
- source: claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-05.json event_index=596 — Here's what was actually broken and what's fixed: **Process lifecycle bugs:** - Apps were calling `createProcess()` unconditionally on every `open()` click, even when the window was already open — leaking processes every click. Now each ...

### B-009 支持多种屏幕尺寸时，定义允许的分辨率选项和运行时 ScreenConfig，用当前宽高派生网格、侧栏和 cell size；渲染容量可保留最大值，但布局按 viewport 合成，并为每种尺寸运行构建或烟测。
- trigger: 游戏或桌面 UI 需要支持多个固定分辨率。
- actions: 支持多种屏幕尺寸时，定义允许的分辨率选项和运行时 ScreenConfig，用当前宽高派生网格、侧栏和 cell size；渲染容量可保留最大值，但布局按 viewport 合成，并为每种尺寸运行构建或烟测。
- verification: 轨迹把屏幕选项、几何派生、比例和构建验证连成具体实现策略。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 游戏或桌面 UI 需要支持多个固定分辨率。
- source: claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-02.json event_index=621 — do M4-M6
- source: claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-05.json event_index=1100 — 

### B-010 跨 MB1/MB2、UEFI/GOP 等低级协议迁移时，保留旧入口与新入口的显式分支，打印并核对真实 boot tag/framebuffer mode，再依据地址映射和显示模式修复构建模块与应用抽象，最后重新生成镜像验证。
- trigger: 内核、bootloader、固件或 framebuffer 协议迁移。
- actions: 跨 MB1/MB2、UEFI/GOP 等低级协议迁移时，保留旧入口与新入口的显式分支，打印并核对真实 boot tag/framebuffer mode，再依据地址映射和显示模式修复构建模块与应用抽象，最后重新生成镜像验证。
- verification: 证据强调运行时 tag/mode，而不是凭启动配置文件猜测协议是否兼容。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 内核、bootloader、固件或 framebuffer 协议迁移。
- source: claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358/segment-02.json event_index=80 — 
- source: claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358/segment-04.json event_index=500 — 

### B-011 低级交互程序退出时出现固定地址崩溃，先和同系统中能正常退出的程序比较输入/清理模式，逐步去掉非必要的清屏、光标恢复或忙轮询；用阻塞输入或自然返回建立最小安全路径，未证实的根因保持为假设。
- trigger: 内核/用户态边界上的交互程序退出崩溃。
- actions: 低级交互程序退出时出现固定地址崩溃，先和同系统中能正常退出的程序比较输入/清理模式，逐步去掉非必要的清屏、光标恢复或忙轮询；用阻塞输入或自然返回建立最小安全路径，未证实的根因保持为假设。
- verification: 轨迹用 quill 这一已知工作实现做对照，并明确区分已证实路径与仍待验证的假设。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 内核/用户态边界上的交互程序退出崩溃。
- source: claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json event_index=175 — Found it. The GPF at `rip=0x1052804` on exit is caused by `showCursor()` calling `vga_cursor_enable(14, 15)` which does `outb` to VGA I/O ports — **those ports are not accessible from Ring-1 userland** (CPL=1 vs IOPL=0). Snake avoids thi...
- source: claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json event_index=213 — Using `getChar()` (blocking) matches exactly the pattern quill uses and avoids the busy-poll entirely. The downside is no auto-refresh — press any key to refresh, `q` to quit. That's the safe pattern the codebase already validates. If yo...

### B-012 把参考实现中的结构化资源转换成运行时资源时，读取完整参考文件并编写解析器，不手抄内容；接入前验证帧数、宽高和关键字符映射与来源一致。
- trigger: 动画帧、字体表、协议表等有明确结构的外部资源。
- actions: 把参考实现中的结构化资源转换成运行时资源时，读取完整参考文件并编写解析器，不手抄内容；接入前验证帧数、宽高和关键字符映射与来源一致。
- verification: 证据包含参考文件输入、解析接入和终端输出核对，能迁移到其他资源转换。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 动画帧、字体表、协议表等有明确结构的外部资源。
- source: claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json event_index=326 — @nyancat.c @animation.c
- source: claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json event_index=384 — D:\CFML>python main.py run d:\CFML\tests\test_nyancat.cfml Launching Nyan Cat... ~~ NYAN CAT ~~ >>=====-- ,_, >>~~~~~-- (o.o) >>----- > ^ < >>=====-- >>~~~~~-- >>----- Nyan Cat complete. uh allow us a way to override to pygame via the --...

### B-013 会消耗硬件、启动外部进程或产生不可逆成本的功能，默认由 dangerous/feature flag 阻断；解锁后再要求 CLI 精确确认字符串，确认前展示影响范围；非确认输入必须 no-op 且可测试 abort path。
- trigger: 线程风暴、矿机、删除、发布等高影响操作。
- actions: 会消耗硬件、启动外部进程或产生不可逆成本的功能，默认由 dangerous/feature flag 阻断；解锁后再要求 CLI 精确确认字符串，确认前展示影响范围；非确认输入必须 no-op 且可测试 abort path。
- verification: 同时具备默认阻断、二次确认、公开警告和 no-op 验证，安全边界具体可审计。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 线程风暴、矿机、删除、发布等高影响操作。
- source: claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-03.json event_index=656 — also when the @cryptoscam directory is run, first ask the user confirmation in the cli with a warning and then let them proceed with destroying their computer
- source: claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json event_index=537 — now time for milestone 7

### B-014 同一功能在不同部署目标上受不同政策约束时，维护独立实现文件/模块和明确选择点；共享入口只选择实现，不把目标规则揉进模糊分支。
- trigger: 同一产品有多个发布渠道、合规政策或运营环境。
- actions: 同一功能在不同部署目标上受不同政策约束时，维护独立实现文件/模块和明确选择点；共享入口只选择实现，不把目标规则揉进模糊分支。
- verification: GitHub-safe 与 Codeberg 版本被分别实现，切换边界清晰且可审计。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 同一产品有多个发布渠道、合规政策或运营环境。
- source: claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json event_index=582 — Milestone 7 done. Results: **`@nuke`** — 1864 threads, Fibonacci(999) iteratively. All completed in **0.35s** on your 22-core machine. Fibonacci(999) is 209 digits long. **`@cryptoscam`** — two separate files as planned: - [dangerous_git...
- source: claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-03.json event_index=604 — Now update `dangerous_codeberg.py` to load the wallet dynamically and fall back gracefully if not set up, with the ETH address as the current placeholder:

### B-015 把会话轨迹发送到外部服务前，先核对项目公开性和许可证，定位单个会话，做本地自动脱敏，再人工复查姓名、路径、内部 URL 和部署信息；遇到 trust-boundary 拒绝就停止，不绕过。
- trigger: 把代码或会话数据提交给外部数据集、审查服务或公共平台。
- actions: 把会话轨迹发送到外部服务前，先核对项目公开性和许可证，定位单个会话，做本地自动脱敏，再人工复查姓名、路径、内部 URL 和部署信息；遇到 trust-boundary 拒绝就停止，不绕过。
- verification: 证据同时覆盖公开性、许可、脱敏和拒绝后的停机边界。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 把代码或会话数据提交给外部数据集、审查服务或公共平台。
- source: claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json event_index=180 — I'll use the code-review-and-pr skill to do this properly — review the changes, strip any AI tells, and open the PR in your name against develop.
- source: claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json event_index=227 — The diff is clean: no em dashes (I used colons and parentheses), no AI mentions, no stray comments, and it mirrors the sibling MiniMax entries field for field. One thing worth flagging: the `desc` says the model handles text, image and v...

### B-016 用户询问数据集字段含义时不按字段名猜测；先查配置中正负选项定义，再查迁移/写入代码如何把字段绑定到回答两侧和偏好，最后用字段级证据解释。
- trigger: 数据集字段名称含义不透明、存在正负投票或多问题来源。
- actions: 用户询问数据集字段含义时不按字段名猜测；先查配置中正负选项定义，再查迁移/写入代码如何把字段绑定到回答两侧和偏好，最后用字段级证据解释。
- verification: 单个切片已经完成从字段定义到写入路径的证据闭环，单来源不降低质量。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 数据集字段名称含义不透明、存在正负投票或多问题来源。
- source: claude_code__comparia-voting-fields-anon/segment-01.json event_index=29 — I now have everything I need to answer [NAME] accurately. Here's what the code confirms: - **`useful` is a *positive* reason; `superficial` is a *negative* reason.** They come from two different questions in the voting flow — "What did y...

## Discarded

- S01: 把多阶段需求转成明确的本轮范围与排除项 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S07: 让头文件、实现文件和构建目标的边界可检查 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S10: 用户指出本地字体后先检查资产和编译路径 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S11: 用新数组引用触发响应式系统更新 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S13: 用同源代理消除前端运行时后端地址分歧 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S20: 敏感配置采用加密存储、分离盐和可验证初始化 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S21: 清理工程时只删除可证明的派生物并同步构建入口 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S22: 构建后恢复派生文件并保持 PR 只含意图变更 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S25: 状态型解释器先建立状态再按要求顺序执行 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S26: 按阶段建立提取边界并以不变量约束低级运行时 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S27: 用索引调试过程中的数据结构不变量和旧二进制隔离 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S28: 先解除测试前置阻塞再判断功能级失败 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S29: 把跨写入和查询的类型转换集中到单一绑定点 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S30: 跨 C 后端与 JS 用户态时先复用现有能力再新增绑定 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S31: 用权限边界和已知程序定位用户态退出故障 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S32: Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S33: 先读取外部 API 的真实 payload 再建模和渲染 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S34: 用游标和 IntersectionObserver 实现可恢复的分页加载 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S35: 对第三方移动应用采用构建门槛、静态扫描、真机行为和清理闭环 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S36: 审查 APK 前先验证发布物身份与包类型 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S37: 把持续集成失败拆成 schema 门槛和构建工具链分别修复 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S38: 遵循仓库既有元数据约定，避免为单个条目过度引入新 schema — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S39: 修改本地化源文件时保持格式并只重新生成派生消息 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S40: 安装外部 Skill 前先识别其实际形态 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S41: 静态部署项目先核对构建输出目录和托管根目录 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S42: 固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S43: 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S44: 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S45: 把固定资源约束写成可检查的不变量并将大型工作区移出栈 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S46: 解释内核最小系统时先分清 kernel、PID 1 和 userspace 责任 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S47: 对阈值型批处理在下一次抓取前检查终止条件 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- S48: 把数据驱动的内容分组放在服务端 load，保持组件只负责呈现 — 未达到宁少勿滥口径：切片证据不足以同时证明具体决策、结果与迁移边界，或本轮未保留该泛化候选。
- cursor__debaa898-grafana-loki-monitoring/segment-01.json: cursor__debaa898-grafana-loki-monitoring/segment-01.json — 只有 SemanticSearch/Grep/Glob/Read 工具事件，没有 user_text 或 assistant_text，无法从轨迹还原可迁移决策链。
- claude_code__4130c9a7-ee88-443a-91b5-224accd13629/segment-01.json: claude_code__4130c9a7-ee88-443a-91b5-224accd13629/segment-01.json — 任务是宽泛的全栈 job board 构建，切片缺少可定位的诊断、边界或验证细节；仅凭最终概述不提取高质量 Skill。

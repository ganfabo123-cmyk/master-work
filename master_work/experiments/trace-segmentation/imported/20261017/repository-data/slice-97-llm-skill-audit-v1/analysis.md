# 97 切片 LLM Skill audit v1

这是一份不受聚类候选约束的切片级 Skill 提取。每个切片独立判断；没有要求至少两个相似 Session、跨 Session 或多切片共现。单切片可以产生多个 Skill，单来源 Skill 也保留。

## 实际读取范围

- 输入目录：`C:\Users\35153\PycharmProjects\master-work\vibecoding-trace-data-bundle\dynatic-split-session-test\calibrated-confidence-length-banded-v3-slices`
- 实际读取：97 个 `segment-*.json` 切片，来自 30 个 Session 目录；目录中的 `index.json` 数量为 30。
- 读取内容：每个切片中的 text、tool_call、thinking/reasoning（若存在）及 tool_result 元数据；证据仅引用实际事件索引或短引文。
- 缺失文件：0。未修改算法代码。

## 统计

提取高质量 Skill **48** 条；来源切片数量分布为 `{'1': 30, '2': 16, '3': 2}`，来源 Session 数量分布为 `{'1': 41, '2': 6, '3': 1}`。去重后覆盖 **41/97 个切片**、**23/30 个 Session**。

完整字段（skill_id、具体内容、来源切片数量/ID、来源 Session ID、来源绝对路径、事件证据、适用边界和质量理由）见同目录 `analysis.json`。

## 提取出的 Skill

### S01 把多阶段需求转成明确的本轮范围与排除项

收到包含多个 milestone 的需求时，先写清本轮要完成、明确跳过和未来分支，再按范围实现；用户改变阶段时重新读取当前状态，只扩展到新授权阶段。

来源切片（2）：`claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json`、`claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-02.json`
来源 Session（2）：`07b57159-218e-4330-a64e-0ec4b4355056`、`4222016d-1932-4abb-94b3-463203bd8876`
关键证据：
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json` event `19`：Today, our target is to reach till milestone 3, also note, for the github version of this project the cryptoscam will just be random hashing functions and encryption running in the background since github hates exploitative code, however...
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json` event `192`：now organize test files properly into a directory and do milestone 4, skip milestone5, do milestone 6
- `claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-02.json` event `270`：continue complete M1, create a README.MD
适用边界：有路线图或阶段表，且阶段排除项可从用户或项目文档确定。
高质量原因：证据同时包含阶段目标、跳过项和继续扩展，能把自然语言范围变成可验收边界。

### S02 在训练数据切分前保留对话角色和来源元数据

准备对话训练/测试集时，不要把混合 corpus.txt 当成唯一数据源；先检查生成脚本实际组合了哪些来源，再以保留 user/gpt 等角色字段的 JSONL 为主，并显式编码纯文本来源，确保训练和测试语义一致。

来源切片（2）：`claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-01.json`、`claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-02.json`
来源 Session（1）：`ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a`
关键证据：
- `claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-01.json` event `37`：actually using raw_corpus for training isnt good, inspect the entire main.py to identify what the actual corpus is composed of then make a test-train seta from that dataset so the metadata of "user", "gpt" etc isnt lost
- `claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-02.json` event `195`：Looking at the pipeline: - `encode_corpus.py` — only encodes the **erotica JSON** (`fastchat-erotica-16k-test.json`) into `train_encoded.jsonl` / `test_encoded.jsonl` - `corpus.txt` — contains erotica + TinyStories + OpenWebText (3 sourc...
适用边界：多来源、混合格式训练或评估管线。
高质量原因：它针对数据血缘和角色语义保真，并验证了文件存在不等于训练脚本实际使用。

### S03 按硬件能力选择精度并用梯度累积保留上下文长度

显存不足但上下文长度是硬约束时，先用实际 GPU 架构排除不支持的精度格式，再优先把 micro-batch 降到 1、用 gradient accumulation 保持有效 batch，保留目标 context size。

来源切片（1）：`claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-02.json`
来源 Session（1）：`ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a`
关键证据：
- `claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-02.json` event `185`：FP8 needs PyTorch 2.1+ with Hopper (H100) or Ada (RTX 40xx) GPUs — the A500 is Ampere and doesn't have FP8 hardware. Your real options: | Precision | A500 Support | Notes | |---|---|---| | `fp32` | Yes | Slowest, most VRAM | | `fp16` | Y...
- `claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a/segment-02.json` event `190`：With 4GB VRAM, 350M model in bf16, and 1024 ctx — the only lever is batch size. Let's find the minimum that fits: ```powershell python train.py --chunk_size 1024 --batch_size 1 --grad_accum 32 --dtype bf16 ``` - **batch_size 1** — absolu...
适用边界：显存受限且上下文长度不可牺牲的训练任务。
高质量原因：给出了硬件事实、参数优先级和具体逃生路径，而非泛泛建议减小 batch。

### S04 用阶段专属测试套件证明阶段完成后再更新文档

实现阶段性能力时，先让阶段专属测试和既有回归都通过，再把 README/计划表标记为完成；若失败来自旧进程、锁文件或工具链噪声，先隔离环境问题再判断代码结果。

来源切片（3）：`claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6/segment-04.json`、`claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-02.json`、`claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833/segment-03.json`
来源 Session（3）：`39082932-131c-40a9-872d-1d3ac8ed1fd6`、`4222016d-1932-4abb-94b3-463203bd8876`、`6a7964ed-6f92-4eee-ae5e-3f91a6445833`
关键证据：
- `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6/segment-04.json` event `1433`：48/48 + 17/17. Now update the README and add the LICENSE:
- `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833/segment-03.json` event `581`：All three suites pass green: - **Stage 1 smoke**: all passed, allocs=1246 / frees=1246 (zero leak) - **Stage 2 subsystems**: 135/135 passed - **Stage 3 bytecode**: 101/101 passed The library built cleanly -- no warnings on the new files....
- `claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-02.json` event `621`：do M4-M6
适用边界：有独立阶段测试入口的编译器、运行时、游戏或应用工程。
高质量原因：轨迹把测试证据、环境噪声隔离和交付文档绑定成完整闭环。

### S05 用语法审计和多版本矩阵实现兼容性

面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在所有可用解释器版本上运行同一套测试，不凭当前版本通过宣称兼容。

来源切片（1）：`claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json`
来源 Session（1）：`07b57159-218e-4330-a64e-0ec4b4355056`
关键证据：
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json` event `425`：Support both 3.7 and 4.8+
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json` event `482`：All three testable versions (3.7, 3.12, 3.14) pass identically. The freethreaded 3.14t launcher tag doesn't work with `py -V:3.14t` on your setup but that's a launcher quirk, not a code issue — it's the same interpreter as 3.14.
适用边界：需要支持多个语言或运行时版本，且能列出实际版本。
高质量原因：证据覆盖需求、阻塞点、修复和 3.7/3.12/3.14 矩阵验证。

### S06 把可嵌入库与 CLI 分离并提供窄的纯 C ABI

需要被另一语言或运行时嵌入时，把核心 lexer/parser/codegen 和批处理逻辑放进库，让 CLI 只处理参数、文件和输出；跨 C/C++ 边界只暴露纯 C 结构、句柄和错误结果。

来源切片（2）：`claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json`、`claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e/segment-01.json`
来源 Session（2）：`479c5e9f-a299-457f-8459-5948adf8aa8e`、`92833a43-c30d-4b44-8447-c32ee17d6e6e`
关键证据：
- `claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e/segment-01.json` event `71`：The CLI still needs the full C++ headers (watcher, batch, signal handling) since it drives those directly. The split is: `libyggdrasil` contains all logic files except `main.cpp`; `main.cpp` links against `libyggdrasil` and uses both the...
- `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json` event `123`：Now implement the C FFI layer. This is a clean `extern "C"` wrapper over the engine — opaque handles, no C++ headers exposed:
适用边界：编译器、解释器或数据工具需要被其他语言嵌入。
高质量原因：轨迹明确拆分库/CLI，并采用 opaque handle、extern C 和不暴露 C++ 类型的 ABI 边界。

### S07 让头文件、实现文件和构建目标的边界可检查

在 C/C++ 工程中固定 include 只放头文件、src 只放实现文件，并让 Make/脚本目标反映目录约定；构建失败时检查实际编译命令、脚本语法和测试入口，而不是只修 IDE 报红。

来源切片（2）：`claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6/segment-01.json`、`claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6/segment-02.json`
来源 Session（1）：`39082932-131c-40a9-872d-1d3ac8ed1fd6`
关键证据：
- `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6/segment-01.json` event `39`：include should have all header files and src should only contains cpp files
- `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6/segment-02.json` event `407`：D:\Yggdrasil>make test "=== Running test fixtures ===" 'pass' is not recognized as an internal or external command, operable program or batch file. make: *** [test] Error 1
适用边界：有公开头文件和多平台构建脚本的 C/C++ 项目。
高质量原因：它把目录约定、构建入口和测试命令变成可审计的工程边界。

### S08 用对象大小和拷贝路径定位启动期栈溢出

测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。

来源切片（1）：`claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json`
来源 Session（1）：`479c5e9f-a299-457f-8459-5948adf8aa8e`
关键证据：
- `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json` event `324`：Line 108: `AtomTable t = make_table();` — this copies the 1MB `AtomTable` by value onto the LOCAL stack! That's an immediate stack overflow. This was pre-existing before my changes. This is a simple fix — change the copy to a reference:
适用边界：C/C++ 启动崩溃、有限栈空间或大型状态对象。
高质量原因：轨迹从固定退出码定位到 1MB AtomTable 按值复制，并以 17 个测试通过完成因果验证。

### S09 用路由事实和请求生命周期排查前端 404

排查文件路由 404 时，先核对实际目录参数名和请求生命周期中的环境变量可见性；如果后端地址只在服务端请求期可用，增加同源 proxy route，让 loader 使用相对路径，再用真实 HTTP 200 验证。

来源切片（3）：`claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json`、`claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-04.json`、`claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-05.json`
来源 Session（2）：`7563bddf-c1a0-4c3e-86ee-062bf288e6d3`、`c84c0ad3-c368-40df-87b1-5ef9effe237a`
关键证据：
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-04.json` event `464`：Still 404 — the env var still isn't loading. The docs confirm the issue: `$env/dynamic/private` values are only available inside the request lifecycle. But the real problem here is simpler — the `.env` file may just not be getting picked...
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-05.json` event `493`：The real fix here is to eliminate the env variable problem entirely. The right SvelteKit pattern is to create a **`+server.ts` proxy route** inside the frontend that forwards `/db/*` requests to the backend. Then all server loaders use r...
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json` event `307`：Server is up. API route 404 means Manic isn't picking up nested API directories. Per AGENTS.md: `app/api/hello/index.ts → /api/hello` — but we have `app/api/reddit/user/index.ts` which would mount at `/api/reddit/user`. Let me check if d...
适用边界：文件路由、SSR loader 和后端 API 代理组合。
高质量原因：同一诊断链把环境变量作用域、实际参数名和代理后的 200 结果分开验证。

### S10 用户指出本地字体后先检查资产和编译路径

用户说明字体已在仓库中时，先读取字体目录和现有 SCSS token，用 @font-face 与正确相对产物路径接入本地字体；只有本地资产不存在时才考虑远程字体，并检查编译 CSS 的加载路径。

来源切片（2）：`claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-01.json`、`claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-01.json`
来源 Session（2）：`09d9abe9-0a02-4bd1-8129-3b864695079d`、`7563bddf-c1a0-4c3e-86ee-062bf288e6d3`
关键证据：
- `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-01.json` event `51`：brother I have fonts in the fonts directory, use your eyes
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-01.json` event `13`：Base directory for this skill: C:\Users\USER\.claude\skills\material-3 # Material Design 3 This skill guides implementation of Google's Material Design 3 (MD3) — a personal, adaptive, expressive design system. MD3 uses dynamic color, ton...
适用边界：前端字体迁移和设计系统接入。
高质量原因：它以资产事实纠正了远程字体初始方案，并保留了编译路径检查。

### S11 用新数组引用触发响应式系统更新

数据源内容已变化但 UI 不刷新时，检查响应式系统是否只比较引用；刷新时复制成新数组对象再赋值 store，并用实际界面刷新确认。

来源切片（1）：`claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-05.json`
来源 Session（1）：`09d9abe9-0a02-4bd1-8129-3b864695079d`
关键证据：
- `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-05.json` event `557`：（非文本事件；见事件索引）
- `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-05.json` event `568`：I think the apps are not properly returning data or process lifecycle
适用边界：Alpine、React store 或其他按引用检测变化的 UI。
高质量原因：证据把同一引用不触发更新的机制与 spread 复制修复直接关联。

### S12 让窗口打开和进程清理具备幂等生命周期

把 open、close、createProcess 和 terminateProcess 视为一个生命周期：重复打开已存在窗口时直接返回且不创建新进程，关闭窗口必须通过 onClose 清理，最后检查重复点击和关闭后的进程表。

来源切片（1）：`claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-05.json`
来源 Session（1）：`09d9abe9-0a02-4bd1-8129-3b864695079d`
关键证据：
- `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-05.json` event `577`：I can see several problems: 1. **Each `ClockApp` instance has `private process` but a new instance is created in `core.ts` for `desktopIcon()`, then a different one would be used for `open()` — but actually the same instance is used here...
- `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d/segment-05.json` event `596`：Here's what was actually broken and what's fixed: **Process lifecycle bugs:** - Apps were calling `createProcess()` unconditionally on every `open()` click, even when the window was already open — leaking processes every click. Now each ...
适用边界：桌面式 Web UI、窗口管理器和有资源副作用的 open/close。
高质量原因：同时覆盖幂等入口、资源创建、释放和可观察的泄漏检查。

### S13 用同源代理消除前端运行时后端地址分歧

当前端 loader 对后端地址的读取时机不一致时，把请求收敛到同源 server proxy，由 proxy 负责转发；页面只依赖相对 URL，并用开发服务器实际返回码和构建结果验证。

来源切片（2）：`claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json`、`claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-05.json`
来源 Session（2）：`7563bddf-c1a0-4c3e-86ee-062bf288e6d3`、`c84c0ad3-c368-40df-87b1-5ef9effe237a`
关键证据：
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-05.json` event `493`：The real fix here is to eliminate the env variable problem entirely. The right SvelteKit pattern is to create a **`+server.ts` proxy route** inside the frontend that forwards `/db/*` requests to the backend. Then all server loaders use r...
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json` event `325`：Key insight from line 377: **`mode: "frontend"` skips the API loader entirely**. Only `mode: "fullstack"` loads `app/api/`. The manic.config.ts currently has `mode: "fullstack"` (the formatter changed it from `"frontend"`). That's actual...
适用边界：SSR 与浏览器请求路径不同、存在端口或环境差异的前端。
高质量原因：它解决的是请求生命周期和部署地址分歧，而非简单改一个 URL。

### S14 把多分辨率界面布局变成运行时几何而非编译期常量

支持多种屏幕尺寸时，定义允许的分辨率选项和运行时 ScreenConfig，用当前宽高派生网格、侧栏和 cell size；渲染容量可保留最大值，但布局按 viewport 合成，并为每种尺寸运行构建或烟测。

来源切片（2）：`claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-02.json`、`claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-05.json`
来源 Session（1）：`4222016d-1932-4abb-94b3-463203bd8876`
关键证据：
- `claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-02.json` event `621`：do M4-M6
- `claude_code__4222016d-1932-4abb-94b3-463203bd8876/segment-05.json` event `1100`：（非文本事件；见事件索引）
适用边界：游戏或桌面 UI 需要支持多个固定分辨率。
高质量原因：轨迹把屏幕选项、几何派生、比例和构建验证连成具体实现策略。

### S15 迁移低级启动/显示路径时以运行时事实校验协议兼容性

跨 MB1/MB2、UEFI/GOP 等低级协议迁移时，保留旧入口与新入口的显式分支，打印并核对真实 boot tag/framebuffer mode，再依据地址映射和显示模式修复构建模块与应用抽象，最后重新生成镜像验证。

来源切片（2）：`claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358/segment-02.json`、`claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358/segment-04.json`
来源 Session（1）：`17c2cf98-e64a-43c6-932e-fa7efcade358`
关键证据：
- `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358/segment-02.json` event `80`：（非文本事件；见事件索引）
- `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358/segment-04.json` event `500`：（非文本事件；见事件索引）
适用边界：内核、bootloader、固件或 framebuffer 协议迁移。
高质量原因：证据强调运行时 tag/mode，而不是凭启动配置文件猜测协议是否兼容。

### S16 用已知工作实现对照并缩小退出崩溃的最小路径

低级交互程序退出时出现固定地址崩溃，先和同系统中能正常退出的程序比较输入/清理模式，逐步去掉非必要的清屏、光标恢复或忙轮询；用阻塞输入或自然返回建立最小安全路径，未证实的根因保持为假设。

来源切片（1）：`claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json`
来源 Session（1）：`f93127ef-dec9-4d58-964b-ee660964ec4d`
关键证据：
- `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json` event `175`：Found it. The GPF at `rip=0x1052804` on exit is caused by `showCursor()` calling `vga_cursor_enable(14, 15)` which does `outb` to VGA I/O ports — **those ports are not accessible from Ring-1 userland** (CPL=1 vs IOPL=0). Snake avoids thi...
- `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json` event `213`：Using `getChar()` (blocking) matches exactly the pattern quill uses and avoids the busy-poll entirely. The downside is no auto-refresh — press any key to refresh, `q` to quit. That's the safe pattern the codebase already validates. If yo...
适用边界：内核/用户态边界上的交互程序退出崩溃。
高质量原因：轨迹用 quill 这一已知工作实现做对照，并明确区分已证实路径与仍待验证的假设。

### S17 从参考源解析资源并用结构性计数验证结果

把参考实现中的结构化资源转换成运行时资源时，读取完整参考文件并编写解析器，不手抄内容；接入前验证帧数、宽高和关键字符映射与来源一致。

来源切片（1）：`claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json`
来源 Session（1）：`07b57159-218e-4330-a64e-0ec4b4355056`
关键证据：
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json` event `326`：@nyancat.c @animation.c
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json` event `384`：D:\CFML>python main.py run d:\CFML\tests\test_nyancat.cfml Launching Nyan Cat... ~~ NYAN CAT ~~ >>=====-- ,_, >>~~~~~-- (o.o) >>----- > ^ < >>=====-- >>~~~~~-- >>----- Nyan Cat complete. uh allow us a way to override to pygame via the --...
适用边界：动画帧、字体表、协议表等有明确结构的外部资源。
高质量原因：证据包含参考文件输入、解析接入和终端输出核对，能迁移到其他资源转换。

### S18 对高影响操作实施分层开关、精确确认和公开警告

会消耗硬件、启动外部进程或产生不可逆成本的功能，默认由 dangerous/feature flag 阻断；解锁后再要求 CLI 精确确认字符串，确认前展示影响范围；非确认输入必须 no-op 且可测试 abort path。

来源切片（2）：`claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json`、`claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-03.json`
来源 Session（1）：`07b57159-218e-4330-a64e-0ec4b4355056`
关键证据：
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-03.json` event `656`：also when the @cryptoscam directory is run, first ask the user confirmation in the cli with a warning and then let them proceed with destroying their computer
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json` event `537`：now time for milestone 7
适用边界：线程风暴、矿机、删除、发布等高影响操作。
高质量原因：同时具备默认阻断、二次确认、公开警告和 no-op 验证，安全边界具体可审计。

### S19 把不同部署/政策要求隔离为独立实现并保留切换边界

同一功能在不同部署目标上受不同政策约束时，维护独立实现文件/模块和明确选择点；共享入口只选择实现，不把目标规则揉进模糊分支。

来源切片（2）：`claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json`、`claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-03.json`
来源 Session（1）：`07b57159-218e-4330-a64e-0ec4b4355056`
关键证据：
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json` event `582`：Milestone 7 done. Results: **`@nuke`** — 1864 threads, Fibonacci(999) iteratively. All completed in **0.35s** on your 22-core machine. Fibonacci(999) is 209 digits long. **`@cryptoscam`** — two separate files as planned: - [dangerous_git...
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-03.json` event `604`：Now update `dangerous_codeberg.py` to load the wallet dynamically and fall back gracefully if not set up, with the ETH address as the current placeholder:
适用边界：同一产品有多个发布渠道、合规政策或运营环境。
高质量原因：GitHub-safe 与 Codeberg 版本被分别实现，切换边界清晰且可审计。

### S20 敏感配置采用加密存储、分离盐和可验证初始化

保存敏感地址或配置时不把真实值写入代码仓库；使用运行时日期/时间/随机 UUID 等输入形成盐后加密，盐和存储位置与代码分开，提供 setup/show/clear 或安全非交互初始化，并测试加密-解密 round-trip。

来源切片（1）：`claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-03.json`
来源 Session（1）：`07b57159-218e-4330-a64e-0ec4b4355056`
关键证据：
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-03.json` event `589`：Smart — obfuscation so the wallet address in the repo isn't the live one. I'll build the whole system: encrypted address store, salt in a separate location, and wire it into the Codeberg cryptoscam. ETH placeholder for now, Monero added ...
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-03.json` event `632`：The `echo` piped into `getpass` doesn't work — `getpass` reads directly from the TTY. That's actually correct security behaviour. Let me add a `--address` flag for non-interactive use:
适用边界：钱包地址、token、密钥等需要落盘但不应入库的配置。
高质量原因：证据覆盖存储设计、TTY 行为和非交互参数修复，边界比泛泛的加密建议更具体。

### S21 清理工程时只删除可证明的派生物并同步构建入口

整理目录前列出候选文件的来源和是否仍被构建入口引用，只删除旧输出、重复源码和测试产物；删除后检查树、构建脚本和资源路径，并更新 README/.gitignore 防止下一次构建重新污染仓库。

来源切片（2）：`claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json`、`claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e/segment-02.json`
来源 Session（2）：`07b57159-218e-4330-a64e-0ec4b4355056`、`92833a43-c30d-4b44-8447-c32ee17d6e6e`
关键证据：
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-02.json` event `491`：`animation.c` and `nyancat.c` should move into a `reference/` folder (they're source material, not CFML code). Everything else is clean. I'll do it all in parallel.
- `claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e/segment-02.json` event `224`：Good — no git repo yet, so the `bin/`/`build/`/`lib/` directories are just local and the `.gitignore` will exclude them correctly when the repo is initialized. No stale tracked files to worry about. Let me do a final sanity check — verif...
适用边界：有源码、生成物、参考资料和构建缓存混在一起的工程。
高质量原因：轨迹展示了先列清单、移动参考资源、修复加载路径、再写忽略规则的顺序。

### S22 构建后恢复派生文件并保持 PR 只含意图变更

允许构建生成临时派生文件时，提交前逐项核对 diff，恢复未要求的生成物，只 stage 与需求直接相关的源文件，并确认分支、提交和 PR 描述与最小改动一致。

来源切片（1）：`claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json`
来源 Session（1）：`2965219c-42ad-45af-889c-4581ecbe0103`
关键证据：
- `claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json` event `193`：There are unrelated changes in the tree (the `utils/ranking/*` files, PNGs, docs, Svelte components). Those are not mine and won't go in this PR. But first I need to understand why `generated-models.json` shows 1833 insertions when I onl...
- `claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json` event `235`：Build validates clean. The build regenerated the derived files again, so I'll restore those and stage only `models.json`, then commit, push, and open the PR.
适用边界：有自动生成目录、模型目录或代码生成器的 PR。
高质量原因：实际构建放大了 diff，轨迹据此区分源文件与派生噪声并恢复后再提交。

### S23 外发轨迹前做公开性核验、脱敏复查和信任边界停机

把会话轨迹发送到外部服务前，先核对项目公开性和许可证，定位单个会话，做本地自动脱敏，再人工复查姓名、路径、内部 URL 和部署信息；遇到 trust-boundary 拒绝就停止，不绕过。

来源切片（1）：`claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json`
来源 Session（1）：`2965219c-42ad-45af-889c-4581ecbe0103`
关键证据：
- `claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json` event `180`：I'll use the code-review-and-pr skill to do this properly — review the changes, strip any AI tells, and open the PR in your name against develop.
- `claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json` event `227`：The diff is clean: no em dashes (I used colons and parentheses), no AI mentions, no stray comments, and it mirrors the sibling MiniMax entries field for field. One thing worth flagging: the `desc` says the model handles text, image and v...
适用边界：把代码或会话数据提交给外部数据集、审查服务或公共平台。
高质量原因：证据同时覆盖公开性、许可、脱敏和拒绝后的停机边界。

### S24 从配置和迁移代码追溯字段语义再解释数据

用户询问数据集字段含义时不按字段名猜测；先查配置中正负选项定义，再查迁移/写入代码如何把字段绑定到回答两侧和偏好，最后用字段级证据解释。

来源切片（1）：`claude_code__comparia-voting-fields-anon/segment-01.json`
来源 Session（1）：`comparia-voting-fields-anon`
关键证据：
- `claude_code__comparia-voting-fields-anon/segment-01.json` event `29`：I now have everything I need to answer [NAME] accurately. Here's what the code confirms: - **`useful` is a *positive* reason; `superficial` is a *negative* reason.** They come from two different questions in the voting flow — "What did y...
适用边界：数据集字段名称含义不透明、存在正负投票或多问题来源。
高质量原因：单个切片已经完成从字段定义到写入路径的证据闭环，单来源不降低质量。

### S25 状态型解释器先建立状态再按要求顺序执行

若语言要求值按正向求值、语句按反向执行，把求值状态预计算与副作用执行分开：先正向建立赋值结果，再反向执行语句，并为读取先前赋值写回归测试。

来源切片（1）：`claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json`
来源 Session（1）：`07b57159-218e-4330-a64e-0ec4b4355056`
关键证据：
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json` event `82`：Now the `@reverse` logic needs a proper implementation — let me fix the `run` method to handle it correctly (pre-scan vs mid-program):
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056/segment-01.json` event `90`：Also fix the `directive_reverse` handler in core.py since `reverse_mode` was renamed:
适用边界：具有反向执行、延迟副作用或状态预计算语义的解释器。
高质量原因：轨迹明确修复了 pre-scan 与 mid-program reverse 的职责分离，而不是用标志位掩盖执行顺序。

### S26 按阶段建立提取边界并以不变量约束低级运行时

对大型 C 运行时做模块提取时，先把每个阶段的边界、不变量和允许的资源策略写入计划；例如禁止初始化后动态分配、固定循环上限、无递归，再以阶段测试和构建结果确认边界。

来源切片（2）：`claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833/segment-01.json`、`claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833/segment-03.json`
来源 Session（1）：`6a7964ed-6f92-4eee-ae5e-3f91a6445833`
关键证据：
- `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833/segment-01.json` event `8`：Let me start by reading the memory index and any existing project context before planning.
- `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833/segment-03.json` event `581`：All three suites pass green: - **Stage 1 smoke**: all passed, allocs=1246 / frees=1246 (zero leak) - **Stage 2 subsystems**: 135/135 passed - **Stage 3 bytecode**: 101/101 passed The library built cleanly -- no warnings on the new files....
适用边界：解释器/运行时拆分、内核模块化或安全关键 C 子系统提取。
高质量原因：证据把阶段拆分与 JPL 风格的可静态审计不变量绑定，具有明确工程前提。

### S27 用索引调试过程中的数据结构不变量和旧二进制隔离

新增索引或缓存后，先打印桶数量、起始偏移和候选位置等不变量；若测试无输出或退出码异常，先排除旧二进制/文件锁，再定位布局错误，修复后重建全部测试。

来源切片（1）：`claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json`
来源 Session（1）：`479c5e9f-a299-457f-8459-5948adf8aa8e`
关键证据：
- `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json` event `184`：Exit code `-1073741571` = `0xC00000FD` = stack overflow. The `ChoicePoint` struct is now massive — `CP_MAX_CANDIDATES = 320` `uint32_t`s = 1280 bytes per entry, and `CHOICE_STACK_CAPACITY = 256` entries, giving `256 * sizeof(ChoicePoint)...
- `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json` event `236`：Found the index bug. Look at bucket 0: - `slot[0]=pos0 head=path(a,b)` ← correct - `slot[1]=pos1 head=path(b,c)` ← WRONG — this should be `path(a,c)` at pos2 And bucket 1 (`b`): - `slot[0]=pos1 head=path(b,c)` ← correct, but start=1 inst...
- `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e/segment-03.json` event `280`：All 13 indexing tests pass. Now let me do a final complete run of all the suites:
适用边界：手写索引、缓存、choice table 或二进制测试产物的 C/C++ 项目。
高质量原因：轨迹从栈溢出、旧 binary 干扰到桶布局错位逐层缩小问题，最后用完整套件验证。

### S28 先解除测试前置阻塞再判断功能级失败

新测试全部在 setup 阶段失败时，先确认 fixture 使用的类型/序列化能力是否被底层支持；修复一个真实前置阻塞后，观察失败是否移动到预期功能层，再继续实现深层特性。

来源切片（1）：`claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8/segment-01.json`
来源 Session（1）：`3be5ba0c-62b2-4645-8589-9216be0c10d8`
关键证据：
- `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8/segment-01.json` event `77`：All 13 fail at line 96 — that's inside `stockedShop()`, the setup, before any query even runs. Let me get the actual exception message.
- `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8/segment-01.json` event `97`：`LocalDateTime` is definitively unsupported as a value field — so `Product` can't be tabled at all, which is why every test dies in `stockedShop()`. Before I reshape the spec, I need to know the *deeper* question: does querying *through ...
- `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8/segment-01.json` event `182`：（非文本事件；见事件索引）
适用边界：TDD 规格测试、ORM、编译器 fixture 或多层协议测试。
高质量原因：轨迹用 LocalDateTime 支持修复证明了失败从建表阶段移动到 zoom 查询阶段，因果链可复现。

### S29 把跨写入和查询的类型转换集中到单一绑定点

当一个值类型同时出现在写入、查询参数和读回路径时，在底层 prepared-statement/读回 coercion 等明确 chokepoint 实现统一转换，并为默认值和 round-trip 补测试，避免各调用方各自编码。

来源切片（1）：`claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8/segment-01.json`
来源 Session（1）：`3be5ba0c-62b2-4645-8589-9216be0c10d8`
关键证据：
- `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8/segment-01.json` event `151`：Confirmed — `_newPreparedStatement` is the single binding chokepoint for both writes and query params. Now I'll make the edits. First, `BasicSQLiteDataBase`: convert `LocalDateTime` ↔ ISO text at binding, and register it as a basic type.
- `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8/segment-01.json` event `185`：No regressions — the existing date-free specs still pass. ## Done: `LocalDateTime` support added to Topsoil Four small, surgical changes, all hanging off a single binding chokepoint so writes and query parameters stay consistent: 1. **`B...
适用边界：数据库 ORM 或需要保持序列化一致性的类型系统。
高质量原因：证据明确指出单一绑定点同时覆盖写入和查询，减少结果/参数不一致。

### S30 跨 C 后端与 JS 用户态时先复用现有能力再新增绑定

为用户态监控程序提供系统指标时，先盘点现有 JS builtin/syscall 和已知工作程序的渲染路径，只为缺失指标增加最小 C→JS binding，再让 JS 前端复用 VGA/GOP 双路径和现有 Makefile 生成规则。

来源切片（2）：`claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-01.json`、`claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json`
来源 Session（1）：`f93127ef-dec9-4d58-964b-ee660964ec4d`
关键证据：
- `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-01.json` event `41`：Now I have everything I need. The architecture is clear: - **C backend** (`kernel/htop.c`) — a new `SYS_HTOP_INFO` syscall that returns CPU usage (tick-based), memory stats (PMM), uptime, and a process snapshot - **JS frontend** (`userla...
- `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json` event `139`：Now the Makefile — add the `.js.h` target and hook it into `JS_HEADERS`, `kernel/seed.o`, `userland/apps.o`:
适用边界：内核/运行时向脚本用户态暴露系统指标或图形能力。
高质量原因：轨迹先识别已有 getProcessList/getTicks，再补 getMemInfo/fbInfo 等最小缺口，保持后端和 UI 职责分离。

### S31 用权限边界和已知程序定位用户态退出故障

固定地址退出崩溃时，检查调用链最终是否触及只有特权级可访问的 I/O 或清理路径；拿正常程序比较并逐步移除退出期操作，确认是权限/生命周期边界而非 UI 逻辑后再修。

来源切片（1）：`claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json`
来源 Session（1）：`f93127ef-dec9-4d58-964b-ee660964ec4d`
关键证据：
- `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json` event `175`：Found it. The GPF at `rip=0x1052804` on exit is caused by `showCursor()` calling `vga_cursor_enable(14, 15)` which does `outb` to VGA I/O ports — **those ports are not accessible from Ring-1 userland** (CPL=1 vs IOPL=0). Snake avoids thi...
- `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d/segment-02.json` event `187`：The JS itself looks clean at exit. The GPF at a fixed `rip=0x1052804` points to a specific instruction in the kernel — likely inside `js_freestate` or `js_dostring`'s unwinding. Let me check if snake's JS counterparts have the same issue...
适用边界：Ring-1/Ring-0、驱动、裸机或受限沙箱中的交互程序。
高质量原因：证据把 GPF 追到 VGA I/O 与特权级，并结合 quill 的自然返回模式给出最小修复方向。

### S32 Windows 文件路由异常时用最小扁平入口规避并验证真实挂载路径

在 Windows 上发现框架把反斜杠和 index 文件名错误拼进 API 路由时，先从生成的 OpenAPI/实际 HTTP 路径确认转换结果，再把嵌套路由收敛到一个扁平入口，重启服务并直接请求验证。

来源切片（1）：`claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json`
来源 Session（1）：`7563bddf-c1a0-4c3e-86ee-062bf288e6d3`
关键证据：
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json` event `332`：The paths are being built with Windows backslashes (`\`) instead of forward slashes, and the `index` isn't being stripped. The API loader uses `file` from `glob.scan()` which on Windows returns paths with backslashes. The route path tran...
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json` event `369`：Good — now `app/api/reddit/` is an empty directory. Let me remove it and create `app/api/reddit.ts` directly:
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json` event `389`：500 error — the route is being hit but failing. Let me check what error is thrown. Looking at the API loader source again (line 61-64): when the default export is a Hono instance (has `.fetch`), it does `app.route(routePath, h)`. The `ro...
适用边界：跨平台文件扫描生成路由、插件或资源路径。
高质量原因：证据从反斜杠转换事实到扁平 `app/api/reddit.ts` workaround，并以 500/路由行为继续验证。

### S33 先读取外部 API 的真实 payload 再建模和渲染

接入第三方 API 的图片、缩略图和 Markdown 内容时，先打印/检查真实 JSON 结构，再建立最小接口和共享解析器；处理 HTML 编码 URL、分辨率回退和不同文本字段后才改组件。

来源切片（1）：`claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-03.json`
来源 Session（1）：`7563bddf-c1a0-4c3e-86ee-062bf288e6d3`
关键证据：
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-03.json` event `597`：Now I have everything I need. The structure is clear: - `preview.images[0].source.url` — full res (HTML-encoded `&amp;`) - `preview.images[0].resolutions` — pick the largest (last entry) - `body` / `selftext` — markdown text for comments...
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-03.json` event `717`：All clean — no unused `timeAgo` anywhere, `formatNum` is used in both files for subscriber/karma counts. Everything is wired up: - **`app/components/RedditPost.tsx`** — shared `MD3PostCard` and `CarbonPostRow` components with `markdown-i...
适用边界：第三方 JSON 结构不稳定或文档不足的前端集成。
高质量原因：轨迹具体识别了 preview.images.source/resolutions、selftext/body 和 HTML 编码，并把解析逻辑共享化。

### S34 用游标和 IntersectionObserver 实现可恢复的分页加载

外部 feed 有 `after` 游标时，把游标、items、loading 状态封装到共享 hook；在列表底部放 sentinel，用 IntersectionObserver 的 rootMargin 提前触发请求，追加下一页并对 user/subreddit 两条路由复用。

来源切片（1）：`claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-03.json`
来源 Session（1）：`7563bddf-c1a0-4c3e-86ee-062bf288e6d3`
关键证据：
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-03.json` event `734`：Reddit uses cursor-based pagination via the `after` token returned in each response. The plan: build a `useRedditFeed` hook that holds `after`, appends pages, and attaches an IntersectionObserver to a sentinel div at the bottom of the fe...
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-03.json` event `821`：All four component functions receive `sentinelRef` and `loadingMore`, both page components pass them through. The infinite scroll is fully wired: - `useRedditFeed(url)` manages `items`, `after` cursor, and `loadingMore` state - It attach...
适用边界：有 cursor/after 分页的长列表或 feed。
高质量原因：轨迹同时给出状态字段、sentinel、200px rootMargin 和两个消费者的完整接线。

### S35 对第三方移动应用采用构建门槛、静态扫描、真机行为和清理闭环

审查待提交移动应用时，先选有可构建 pipeline 和真实 APK 的候选；再做权限/trackers/版本静态扫描，安装后运行关键流程并看 logcat，报告只写事实；每次审查结束卸载应用，遇到可疑应用仅静态分析。

来源切片（1）：`claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-09.json`
来源 Session（1）：`da5d32d6-547f-45ae-a5b5-4747ed06542f`
关键证据：
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-09.json` event `2044`：Both are the same device (the Pixel = your Haven host), and I'm cleared to post factual reports directly. Good — I'll keep reports strictly objective (tested-on-device facts + build observations, no approve/reject calls) and run anything...
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-09.json` event `2061`：Statically it's clean and notably privacy-respecting: **no INTERNET permission at all** (fully offline), **zero trackers**, MIT, version matches the recipe (2.0/20001). One minor note: the launcher label is "ExpenseTrack" while AutoName ...
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-09.json` event `2127`：✅ First review posted (note `3466823631` on MR !30678), app uninstalled. That's one full on-device review end to end. Next: **ScenePeek** (`com.divinelink.scenepeek`, MR !34924) — a TMDB movie browser. More to scrutinize: it's a network ...
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-09.json` event `2160`：Two solid reviews posted (both apps uninstalled). Let me do a third with a different angle — scrutinizing one of the templated-looking "*Tech*" submissions (same author, three generic apps same day, all failed pipelines). I'll **static-a...
适用边界：F-Droid 或类似第三方移动应用供应链审查。
高质量原因：它把构建资格、静态证据、运行时证据、客观报告和设备清理串成安全的重复流程。

### S36 审查 APK 前先验证发布物身份与包类型

当 release 文件名、包名或应用名不一致时，先从 manifest/组件确认 APK 的真实 package 和服务类型，再决定是否能代表目标应用；若拿到的是插件或错误 ABI，应停止把它当成主应用报告。

来源切片（1）：`claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-10.json`
来源 Session（1）：`da5d32d6-547f-45ae-a5b5-4747ed06542f`
关键证据：
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-10.json` event `2358`：GloomChat has no release APK (skip — can't get it without building). Let me scrutiny-scan the keyboard (Xime — though its release APK is oddly named `kaomoji-2.0.0`, so I'll verify the package) and RPClient:
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-10.json` event `2363`：Two notable results: - **Xime**: the downloaded APK is actually `com.kingzcheung.xime.plugin.**kaomoji**` — a **plugin**, not the keyboard itself. So I can't scrutinize the actual IME from it. Let me check if the real IME APK is in the r...
适用边界：APK release、插件、ABI split 或同仓库多应用场景。
高质量原因：Xime 的插件误认被实际识别并纠正，避免基于错误工件作安全结论。

### S37 把持续集成失败拆成 schema 门槛和构建工具链分别修复

CI 失败时先读取具体 job 输出，区分元数据 schema 错误和构建工具链错误；先修复最小 schema 约束并等待门禁确认，再单独修 Node/依赖问题，最后观察完整 build job，而不把整条 pipeline 当作一个黑盒失败。

来源切片（2）：`claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-10.json`、`claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-11.json`
来源 Session（1）：`da5d32d6-547f-45ae-a5b5-4747ed06542f`
关键证据：
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-10.json` event `2405`：Found why our MR's pipeline failed — two issues. One is a quick fix: **1. Schema validation:** `AutoUpdateMode: 'Version v%v' does not match '^(None|Version( \+.+)?)$'` — F-Droid's current schema wants just `Version` (the tag pattern is ...
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f/segment-11.json` event `2451`：**Fix #1 confirmed on F-Droid CI — `schema validation` now passes** (it was the job that rejected `AutoUpdateMode: Version v%v`). The other metadata jobs (lint, rewritemeta, source/tools checks) are running and passed before, so they'll ...
适用边界：有多个并行门禁、schema/lint/build 分阶段的 CI。
高质量原因：证据明确区分两个失败原因，并以 schema job 通过和 build watcher 作为不同验证点。

### S38 遵循仓库既有元数据约定，避免为单个条目过度引入新 schema

新增模型或目录元数据时，先比较同类条目和维护者最近提交；若仓库把许可证细节放在现有 license + fyi，就复用既有条目模式，不因为新信息单独新增许可证类型；构建后只保留 source-of-truth 变更。

来源切片（1）：`claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json`
来源 Session（1）：`2965219c-42ad-45af-889c-4581ecbe0103`
关键证据：
- `claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json` event `159`：Got it. The convention on develop is that the sibling MiniMax models (M2.7, M2.5) reuse the existing `"Modified MIT"` license and describe the licensing nuances in the `fyi` text, rather than introducing a brand-new license entry. I over...
- `claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json` event `174`：Build passes and `licenses.json` is back to clean (no diff). The M3 entry now follows the develop convention exactly: it reuses the existing `"Modified MIT"` license like its siblings M2.7/M2.5, with the licensing nuances described in th...
- `claude_code__2965219c-42ad-45af-889c-4581ecbe0103/segment-01.json` event `214`：This is the key finding. The real maintainer practice on develop is to edit **only `models.json`** when adding a model (the Gemini/Grok commit touched nothing else; IBM Granite added only manual locale translations). They do **not** comm...
适用边界：有维护者惯例、schema 文件和生成输出的目录/模型目录。
高质量原因：轨迹展示了从过度设计新 license 回退到 sibling convention，并验证最终 diff 只含一条源数据。

### S39 修改本地化源文件时保持格式并只重新生成派生消息

合并 i18n 条目时，先修改源 JSON，再检查 diff 是否发生无关重排；恢复错误缩进后只重新生成被 gitignore 的编译消息，最后把预存在的 typecheck 错误与本次页面改动分开报告。

来源切片（2）：`claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b/segment-01.json`、`claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b/segment-02.json`
来源 Session（1）：`89cf9e13-a4bd-4cf9-9486-7c89737bec1b`
关键证据：
- `claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b/segment-01.json` event `80`：The original uses 4-space indentation; my 2-space write reformatted everything. Let me revert and redo correctly.
- `claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b/segment-02.json` event `120`：The 18 errors are all pre-existing in `SensitiveDataModal.svelte` (an untracked WIP file referencing `sante.confirm.*` keys) — unrelated to my change. The datasets page is clean. Let me do a final visual sanity check of the page diff.
适用边界：多语言源 JSON、生成消息和大型前端类型检查。
高质量原因：证据把格式噪声、派生文件和预存在错误分别处理，保持小 diff 可审计。

### S40 安装外部 Skill 前先识别其实际形态

用户要求安装外部扩展时，先检查仓库结构和入口文件，区分 marketplace/plugin 与单独 SKILL.md；确认是 skill 后放入约定的 skills/<name>/ 目录，完成后验证其出现在可用清单。

来源切片（1）：`claude_code__da6566ff-0116-4424-bb59-660623f9eb31/segment-01.json`
来源 Session（1）：`da6566ff-0116-4424-bb59-660623f9eb31`
关键证据：
- `claude_code__da6566ff-0116-4424-bb59-660623f9eb31/segment-01.json` event `35`：The workflow is: add the GitHub repo as a marketplace, then install from it. Let me first check what's in the humanizer repo to understand its structure.
- `claude_code__da6566ff-0116-4424-bb59-660623f9eb31/segment-01.json` event `46`：It has a `SKILL.md` file — this is a skill, not a marketplace plugin. Skills go in `~/.claude/skills/<name>/`. Let me install it there.
- `claude_code__da6566ff-0116-4424-bb59-660623f9eb31/segment-01.json` event `56`：The `humanizer` skill is now installed and active — you can see it already appears in the available skills list. Use it with `/humanizer` in any Claude Code session. It removes AI writing patterns like em dash overuse, "rule of three" ph...
适用边界：外部技能、插件或 marketplace 安装任务。
高质量原因：轨迹先排除错误安装路径，再依据 SKILL.md 形态完成用户级安装并验证激活。

### S41 静态部署项目先核对构建输出目录和托管根目录

部署无 bundling 依赖的静态项目时，先检查 package build 实际写入的目录和 index/assets 所在位置；若平台自动探测会把 root site 当成 dist，显式设置空 buildCommand 和正确 outputDirectory，再部署后检查真实页面。

来源切片（1）：`claude_code__11ef2190-67e2-4707-8212-ab12ebffdbc2/segment-01.json`
来源 Session（1）：`11ef2190-67e2-4707-8212-ab12ebffdbc2`
关键证据：
- `claude_code__11ef2190-67e2-4707-8212-ab12ebffdbc2/segment-01.json` event `53`：`main.js` has no imports — esbuild bundling is unnecessary. The real issue is `vercel.json` has no `buildCommand` or `outputDirectory`, so Vercel auto-detects the `package.json` build script (which outputs to `dist/main.js`) while `index...
- `claude_code__11ef2190-67e2-4707-8212-ab12ebffdbc2/segment-01.json` event `65`：Deployed successfully. Here's the summary: **Fix applied:** Added `"buildCommand": ""` and `"outputDirectory": "."` to `vercel.json`. The build script was outputting to `dist/` while all assets (`index.html`, `main.js`, CSS, fonts) live ...
适用边界：Vercel 等根据 package.json 自动探测构建的静态站点。
高质量原因：证据明确找到了 root/dist 不一致这一实际原因，并在部署结果中验证修复。

### S42 固定高度内容面板打开时暂时隐藏装饰区以释放滚动空间

对带固定对话区、sprite/装饰区和内容面板的窄屏 UI，内容页打开时让装饰区隐藏、内容面板占满可滚动高度；关闭时恢复装饰，避免 ABOUT 等长内容被裁切。

来源切片（1）：`claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f/segment-01.json`
来源 Session（1）：`0ca72c0c-ac42-400a-8ca6-cc31a787225f`
关键证据：
- `claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f/segment-01.json` event `79`：Now also hide the sprite area when any section opens (and restore on close), so the content panel gets the full battle box height:
- `claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f/segment-01.json` event `92`：Three changes made: 1. **ABOUT now uses `showContent`** — renders inside the scrollable content panel instead of the fixed dialogue area, so it can scroll if needed 2. **Sprite hides when any section opens** — the full battle box height ...
适用边界：复古对话框、游戏 UI 或固定 viewport 的内容型面板。
高质量原因：证据展示了问题、状态切换和恢复动作，策略具体到可直接复用的布局状态。

### S43 用真实 HTTP 状态和 Cookie 事实区分浏览器请求与服务端请求

第三方接口在服务端返回 403、浏览器返回 200 时，不继续猜 header spoofing；用 curl/DevTools 对比状态、Origin/Referer 和 cookie，确认 bot/会话边界，再选择官方 OAuth、带授权 cookie 的受控 proxy 或浏览器端请求，并记录 cookie 过期处理。

来源切片（1）：`claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json`
来源 Session（1）：`7563bddf-c1a0-4c3e-86ee-062bf288e6d3`
关键证据：
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json` event `441`：Reddit is blocking our server-side fetch with 403 — it's rate-limiting or blocking non-browser requests. The exact URLs from the user work in a browser because the browser sends cookies and has a different fingerprint. The fix: fetch dir...
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json` event `489`：Reddit returns **403 Blocked** for server-side requests regardless of UA. The `.json` URL only works from a real browser with cookies. The original approach — **fetch directly from the browser** — is the only one that works. No proxy nee...
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json` event `539`：It's Cloudflare/Reddit's bot detection — it sets a `csv` cookie on first visit and blocks requests without it. The browser passes because it has accumulated cookies from previous Reddit visits. No amount of header spoofing will bypass th...
适用边界：受 bot detection、cookie、Origin 或登录态影响的第三方 API。
高质量原因：轨迹用 403/200 对照排除了单纯 User-Agent 伪装，并明确了可行方案与会话过期边界。

### S44 用生成清单和实际 HTTP 状态校验文件路由，不把自动生成文件当黑盒

动态路由或 API 文件生成异常时，检查生成清单中的真实 route key/import path，再对照源码目录和运行时 HTTP 状态；自动生成文件被 formatter 改写时，先修生成器/忽略策略，不把手工修补当长期架构。

来源切片（2）：`claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-01.json`、`claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json`
来源 Session（1）：`7563bddf-c1a0-4c3e-86ee-062bf288e6d3`
关键证据：
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-01.json` event `105`：The routes aren't being picked up yet — Manic needs the dev server to regenerate the route manifest. Let me check the generated routes file first.
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3/segment-02.json` event `242`：Lint passes now. But the routes manifest is corrupted again by the formatter, and then the bundler fails because the import paths are broken. The formatter keeps running every time I save the file. The root cause: `oxfmt` escapes `[` and...
适用边界：有自动生成 routes manifest、格式化钩子和动态路径的前端框架。
高质量原因：证据把 route manifest、formatter 和开发服务器行为联系起来，能避免反复手改生成文件。

### S45 把固定资源约束写成可检查的不变量并将大型工作区移出栈

在遵循 NASA/JPL 风格的 C/C++ 代码中，用固定上限、无递归、初始化后无 malloc 等不变量限制实现；若这些固定数组让测试栈溢出，把非重入的工作区移到静态/显式存储，并以全套测试确认。

来源切片（1）：`claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd/segment-02.json`
来源 Session（1）：`c99032e9-377b-4ae9-a9a9-ec7752b059cd`
关键证据：
- `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd/segment-02.json` event `71`：（非文本事件；见事件索引）
- `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd/segment-02.json` event `334`：Now update `solver_env_init` and `rename_term` to use `clause_arena` for reading clause terms:
适用边界：安全关键、实时或需要静态资源上界的 C/C++ 子系统。
高质量原因：轨迹把代码规范、数据结构大小、栈溢出诊断和 10/10 套件通过放在同一闭环中。

### S46 解释内核最小系统时先分清 kernel、PID 1 和 userspace 责任

构建最小 Linux 系统时，先确认 kernel 源树不包含 Bash、libc、/etc 或 /bin；再明确 init_post 的 PID 1 交接和 userspace process manager 责任，最后按 syscall/静态链接边界组织 minit 文件。

来源切片（1）：`claude_code__47d9fc04-420c-47bb-8ac0-85780af22632/segment-01.json`
来源 Session（1）：`47d9fc04-420c-47bb-8ac0-85780af22632`
关键证据：
- `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632/segment-01.json` event `52`：Correct. This is the raw Linux 3.0.1 kernel source — **just the kernel itself**. It contains zero userspace: - No systemd - No Bash - No libc - No coreutils (`ls`, `cp`, etc.) - No `/etc`, `/bin`, `/usr` — nothing The kernel's job is to ...
- `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632/segment-01.json` event `64`：That's a clean design — essentially a **shepherd init**. The logic maps directly to kernel syscalls. Here's exactly what you need: --- ## Core Syscalls You'll Use | What | Syscall | Purpose | |---|---|---| | Launch program | `fork()` + `...
- `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632/segment-01.json` event `71`：Simple and clean. For **minit** as PID 1, here's every file you need to write and where it lives: --- ## Files You Write ### 1. The init itself ``` minit/ ├── minit.c ← PID 1 — the entire process manager ├── minit.h ← structs, constants,...
适用边界：定制内核、initramfs、PID 1 或极简 Linux 用户空间。
高质量原因：它先纠正 kernel/userspace 概念混淆，再给出 syscall 和目录职责，能迁移到任何最小系统构建。

### S47 对阈值型批处理在下一次抓取前检查终止条件

按目标字符数或字节数抓取外部资料时，把终止检查放在下一次 fetch 之前；允许最后一本完整纳入，即使它使总量超过阈值，只跳过下一本，避免半截资源和多余网络请求。

来源切片（1）：`claude_code__674e0f5c-c481-4830-b2ef-3e1e069a2b7f/segment-01.json`
来源 Session（1）：`674e0f5c-c481-4830-b2ef-3e1e069a2b7f`
关键证据：
- `claude_code__674e0f5c-c481-4830-b2ef-3e1e069a2b7f/segment-01.json` event `38`：Good catch. The current script already does that correctly — `if total_chars >= target_bytes: break` is checked **before** fetching the next book, so any book that pushes over the target is fully included and only the *next* book is skip...
- `claude_code__674e0f5c-c481-4830-b2ef-3e1e069a2b7f/segment-01.json` event `45`：The logic is correct — the `break` fires at the top of the loop before fetching, so a book that crosses the threshold is always fully included. Running it now.
适用边界：下载书籍、日志、分片或语料等按累计大小停止的批处理。
高质量原因：证据清楚解释了 break 的位置与完整资源边界，属于可复用的循环不变量。

### S48 把数据驱动的内容分组放在服务端 load，保持组件只负责呈现

当数据库列表需要按章节、字母或特殊项分组时，先读取真实数据并在 server load 中完成分类和计数，再将已分组结构交给 UI 组件；组件只处理选中态、列表和 master-detail 呈现。

来源切片（1）：`claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-03.json`
来源 Session（1）：`c84c0ad3-c368-40df-87b1-5ef9effe237a`
关键证据：
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-03.json` event `370`：Now I have a clear picture. The data has four natural groups: - **Chapters** (255) — `Chapter N` - **Episodes** (53) — `Episode N` - **Characters/Lore** (~155) — everything else alphabetically - **Special** (2) — `<…>` titles The right t...
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-03.json` event `376`：The grouping logic belongs in the server load — keeps the component clean. I'll classify each page there, then replace PageList with a new `CollectionBrowser` component.
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a/segment-03.json` event `404`：Clean. The layout now works like this: **Desktop (`≥768px`)** — true Finder-style split: - Left column (240px): folder list with active row highlighted in solid `$color-primary` red, chevron on the right, item count badge - Red vertical ...
适用边界：数据库浏览器、目录页或 master-detail UI。
高质量原因：轨迹先按真实标题分出四组，再让 server load 分类，最终形成稳定的 Finder-style 两栏组件。

## rejected_or_weak

以下切片没有混入高质量 Skill 清单：
- `cursor__debaa898-grafana-loki-monitoring/segment-01.json`：只有 SemanticSearch/Grep/Glob/Read 工具事件，没有 user_text 或 assistant_text，无法从轨迹还原可迁移决策链。
- `claude_code__4130c9a7-ee88-443a-91b5-224accd13629/segment-01.json`：任务是宽泛的全栈 job board 构建，切片缺少可定位的诊断、边界或验证细节；仅凭最终概述不提取高质量 Skill。

## 可比性备注

本报告的切片级来源统计与此前 30 条原始 Session 的 Skill 审计口径不同：同一个 Session 的多个切片可以分别贡献 Skill，因此 Skill 数量和覆盖切片数量不能直接当作 Session 数量比较；应使用 `source_session_ids` 去重后的覆盖数进行对照。

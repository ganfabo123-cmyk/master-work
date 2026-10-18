# C — D007 领域独立保守 Skill 提取

## 口径

你是一个 Skill 提取器。请只根据当前提供的轨迹内容，提取少量但真正可用的 Skill。目标不是覆盖尽可能多的内容，而是只保留能够指导其他类似任务的具体经验。一个 Skill 只有同时满足：轨迹有明确问题/触发条件/约束；有具体判断/决策/解决动作；不是简单读取/修改/运行/测试流水线；有可核对结果/验证方式/完成条件；去掉项目名、文件名和技术栈专有名词后仍可迁移。

本轮不跨组去重，不调用 embedding；仅保留同时满足触发问题、具体动作、可核对结果和迁移边界的条目。

## 读取与计数

- actual_read_scope: 仅读取 domains.json 的 D007 members 指定的 27 个成员切片；领域之间不共享上下文、不跨领域去重；重复成员在不同领域按各自输入独立读取。
- declared_count: 27
- actual_read_count: 27
- read_session_count: 11
- read_slice_count: 27
- missing_file_count: 0
- skills: 6
- discarded: 23

## Skills

### D007-001 实现阶段性能力时，先让阶段专属测试和既有回归都通过，再把 README/计划表标记为完成；若失败来自旧进程、锁文件或工具链噪声，先隔离环境问题再判断代码结果。
- trigger: 有独立阶段测试入口的编译器、运行时、游戏或应用工程。
- actions: 实现阶段性能力时，先让阶段专属测试和既有回归都通过，再把 README/计划表标记为完成；若失败来自旧进程、锁文件或工具链噪声，先隔离环境问题再判断代码结果。
- verification: 轨迹把测试证据、环境噪声隔离和交付文档绑定成完整闭环。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 有独立阶段测试入口的编译器、运行时、游戏或应用工程。
- source: segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04 event_index=1433 — 48/48 + 17/17. Now update the README and add the LICENSE:
- source: segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02 event_index=270 — continue complete M1, create a README.MD
- source: segments__claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03 event_index=581 — All three suites pass green: - **Stage 1 smoke**: all passed, allocs=1246 / frees=1246 (zero leak) - **Stage 2 subsystems**: 135/135 passed - **Stage 3 bytecode**: 101/101 passed The library built cleanly -- no warnings on the new files....

### D007-002 面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在所有可用解释器版本上运行同一套测试，不凭当前版本通过宣称兼容。
- trigger: 需要支持多个语言或运行时版本，且能列出实际版本。
- actions: 面对旧版本运行时兼容需求时，先审计语法/API 中明确的版本阻塞点，再用兼容写法替换；随后在所有可用解释器版本上运行同一套测试，不凭当前版本通过宣称兼容。
- verification: 证据覆盖需求、阻塞点、修复和 3.7/3.12/3.14 矩阵验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 需要支持多个语言或运行时版本，且能列出实际版本。
- source: segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01 event_index=19 — Today, our target is to reach till milestone 3, also note, for the github version of this project the cryptoscam will just be random hashing functions and encryption running in the background since github hates exploitative code, however...

### D007-003 需要被另一语言或运行时嵌入时，把核心 lexer/parser/codegen 和批处理逻辑放进库，让 CLI 只处理参数、文件和输出；跨 C/C++ 边界只暴露纯 C 结构、句柄和错误结果。
- trigger: 编译器、解释器或数据工具需要被其他语言嵌入。
- actions: 需要被另一语言或运行时嵌入时，把核心 lexer/parser/codegen 和批处理逻辑放进库，让 CLI 只处理参数、文件和输出；跨 C/C++ 边界只暴露纯 C 结构、句柄和错误结果。
- verification: 轨迹明确拆分库/CLI，并采用 opaque handle、extern C 和不暴露 C++ 类型的 ABI 边界。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 编译器、解释器或数据工具需要被其他语言嵌入。
- source: segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03 event_index=123 — Now implement the C FFI layer. This is a clean `extern "C"` wrapper over the engine — opaque handles, no C++ headers exposed:
- source: segments__claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e__segment-01 event_index=71 — The CLI still needs the full C++ headers (watcher, batch, signal handling) since it drives those directly. The split is: `libyggdrasil` contains all logic files except `main.cpp`; `main.cpp` links against `libyggdrasil` and uses both the...

### D007-004 在 C/C++ 工程中固定 include 只放头文件、src 只放实现文件，并让 Make/脚本目标反映目录约定；构建失败时检查实际编译命令、脚本语法和测试入口，而不是只修 IDE 报红。
- trigger: 有公开头文件和多平台构建脚本的 C/C++ 项目。
- actions: 在 C/C++ 工程中固定 include 只放头文件、src 只放实现文件，并让 Make/脚本目标反映目录约定；构建失败时检查实际编译命令、脚本语法和测试入口，而不是只修 IDE 报红。
- verification: 它把目录约定、构建入口和测试命令变成可审计的工程边界。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 有公开头文件和多平台构建脚本的 C/C++ 项目。
- source: segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-01 event_index=39 — include should have all header files and src should only contains cpp files
- source: segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-02 event_index=407 — D:\Yggdrasil>make test "=== Running test fixtures ===" 'pass' is not recognized as an internal or external command, operable program or batch file. make: *** [test] Error 1

### D007-005 测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。
- trigger: C/C++ 启动崩溃、有限栈空间或大型状态对象。
- actions: 测试程序启动即崩溃且主体尚未执行时，先检查大型结构体是否按值声明或被隐式复制；改为引用/指针后先跑最小测试，再跑全套测试确认因果。
- verification: 轨迹从固定退出码定位到 1MB AtomTable 按值复制，并以 17 个测试通过完成因果验证。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: C/C++ 启动崩溃、有限栈空间或大型状态对象。
- source: segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03 event_index=123 — Now implement the C FFI layer. This is a clean `extern "C"` wrapper over the engine — opaque handles, no C++ headers exposed:

### D007-006 把参考实现中的结构化资源转换成运行时资源时，读取完整参考文件并编写解析器，不手抄内容；接入前验证帧数、宽高和关键字符映射与来源一致。
- trigger: 动画帧、字体表、协议表等有明确结构的外部资源。
- actions: 把参考实现中的结构化资源转换成运行时资源时，读取完整参考文件并编写解析器，不手抄内容；接入前验证帧数、宽高和关键字符映射与来源一致。
- verification: 证据包含参考文件输入、解析接入和终端输出核对，能迁移到其他资源转换。；以 sources 中的事件证据核对动作和结果，轨迹未展示的结果不作推断。
- scope_limit: 动画帧、字体表、协议表等有明确结构的外部资源。
- source: segments__claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01 event_index=19 — Today, our target is to reach till milestone 3, also note, for the github version of this project the cryptoscam will just be random hashing functions and encryption running in the background since github hates exploitative code, however...

## Discarded

- D007-001: 把多阶段需求转成明确的本轮范围与排除项 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D007-007: 把多分辨率界面布局变成运行时几何而非编译期常量 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D007-009: 清理工程时只删除可证明的派生物并同步构建入口 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D007-010: 状态型解释器先建立状态再按要求顺序执行 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D007-011: 按阶段建立提取边界并以不变量约束低级运行时 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D007-012: 用索引调试过程中的数据结构不变量和旧二进制隔离 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- D007-013: 把固定资源约束写成可检查的不变量并将大型工作区移出栈 — 未达到宁少勿滥口径：领域内轨迹没有同时给出足够具体的触发、动作、结果和可迁移边界，或本轮保留更少的强证据候选。
- segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-03: segments__claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-01: segments__claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-01: segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-02: segments__claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-06: segments__claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-06 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-02: segments__claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02: segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-03: segments__claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-02: segments__claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-02 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-01: segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-01 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-03: segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-03 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-04: segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-04 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-05: segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-05 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06: segments__claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。
- segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-08: segments__claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-08 — 存在操作或项目描述，但在本领域独立审阅中未形成足够具体的决策链、边界条件或验证闭环；保留为弱结果。

---
name: fix-lnk1107-odin-dll-import-lib
description: Use when MSVC link.exe fails with LNK1107 "invalid or corrupt file" naming a .dll that an Odin foreign import (or similar) references directly. Helps the agent confirm the DLL is a valid PE, generate an import .lib via llvm-dlltool plus a .def (or clang++ -Wl,/DEF:), repoint the foreign import, and verify by rebuilding and running the binary. Requires Windows, clang++, llvm-dlltool, the DLL export list, and a runnable smoke test. Do not use when LNK1107 names a genuinely truncated file, or when the build/run problem is a different link error code.
triggers:
  - "LNK1107"
  - "invalid or corrupt file"
  - "llvm-dlltool"
---
# Fix MSVC LNK1107 by Linking an Import Library Instead of the DLL

## Goal
当 MSVC 链接器对被 `foreign import` 直接引用的 `.dll` 报 `LNK1107: invalid or corrupt file` 时，生成可用的导入库 `<name>.lib`，把 foreign import 从 `.dll` 改指 `.lib`，使 `odin build` 无 LNK1107、退出码为 0，且构建出的二进制运行冒烟测试通过。

## Scope
### In scope
- Windows 环境、Odin 调用 MSVC `link.exe` 时，`LNK1107` 报错对象是 `foreign import` 直接指向的 `.dll` 的场景。
- 用 `llvm-dlltool -m i386:x86-64 -d <name>.def -l <name>.lib` 从手写 `.def` 生成导入库。
- 改写 Odin `foreign import` 的 Windows 分支，使其指向 `.lib`。
- 用 `clang++ -target x86_64-pc-windows-msvc -shared -Wl,/DEF:<name>.def` 在编译 DLL 时同步产出导入库，并把该参数固化进构建脚本。
- 构建验证与运行验证（冒烟测试）。

### Out of scope
- 非 MSVC 链接器或非 Windows 平台的链接问题。
- ELF/Mach-O 共享库（`.so`、`.dylib`）的加载与链接。
- DLL 文件本身真正损坏（截断、编译中断）时的重建修复（轨迹未提供该分支的处理）。
- `LNK2019` 缺符号、`LNK1121` 等其它链接错误码的处理（轨迹未提供）。
- 运行期 `Exit code 123` 的根因定位（轨迹未确认原因，仅作为修复后的注意项保留）。

## Inputs
1. **LNK1107 错误输出** — 类型：工具结果文本（`odin build` / `link.exe` stderr）；来源：失败的构建命令；必需：是；约束：报错文件名应为 `.dll`，且与 `foreign import` 指向的路径一致；默认值：无。
2. **引用 DLL 的 foreign import 源文件** — 类型：Odin 源文件（如 `src/bridge.odin`）；来源：项目仓库；必需：是；约束：Windows 分支当前写成 `foreign import epilog_lib "../engine/epilog/epilog.dll"`；默认值：无。
3. **DLL 导出函数清单** — 类型：C FFI 头文件 / 接口声明（如 `engine/epilog/include/epilog_ffi.h`）；来源：项目 `include/` 目录；必需：是；约束：清单名必须与 `extern "C"` 实际导出名一致，不臆造；默认值：无。
4. **待链接的 DLL 文件** — 类型：PE 文件；来源：构建产物目录（如 `engine/epilog/epilog.dll`）；必需：是；约束：`file` 显示为 `PE32+ executable ... (DLL), x86-64`；默认值：无。
5. **工具链** — 类型：可执行程序 `clang++`、`llvm-dlltool`、`odin`（诊断时另有 `file`、`xxd`、`llvm-nm`）；来源：环境 PATH；必需：是；约束：目标为 Windows x86-64（`llvm-dlltool -m i386:x86-64` 与 DLL 架构一致）；默认值：无。
6. **运行期验证入口** — 类型：可执行产物及其冒烟测试输出；来源：构建输出目录（如 `build\dmls.exe`）；必需：是（仅验证步骤需要）；约束：运行输出含可判定的通过行与退出码；默认值：无。

## Outputs
### Artifacts
- `<dll 目录>/<name>.def` — 模块定义文件：首行 `LIBRARY <name>`，`EXPORTS` 后逐行列出导出符号（格式：文本）。
- `<dll 目录>/<name>.lib` — MSVC 导入库（本轨迹实例为 4458 字节的 `epilog.lib`）。
- 修改后的 foreign import 源文件 — Windows 分支改为 `foreign import epilog_lib "../engine/epilog/epilog.lib"`，并附注释说明 DLL 运行期需在 exe 同目录或 PATH。
- 重建的可执行产物（本轨迹实例：`build\dmls.exe`，随后续迭代为 622592 → 698368 字节）。
- （可选）更新后的构建脚本 — DLL 编译命令加入 `-target x86_64-pc-windows-msvc` 与 `-Wl,/DEF:<路径>\<name>.def`。

### Success criteria
- `odin build` 输出不再出现 `fatal error LNK1107`，且打印 `Build exit: 0` 或 `Exit: 0`。
- DLL 编译输出出现 `Creating library <name>.lib and object <name>.exp`。
- 运行可执行产物打印 `=== Bridge smoke test: PASS ===` 并以 `Exit: 0` 结束。
- 固化后整套脚本运行输出含 `[engine] Built ...\<name>.dll + <name>.lib` 与 `[odin] Built build\dmls.exe`。

### Failure criteria
- 同一 `.dll` 仍触发 `LNK1107`。
- `.lib` 未生成，或生成后出现其它链接错误（轨迹未提供后续错误文本）。
- 构建成功但运行退出码非 0（如 `Exit code 123`）——此时不得宣称问题已解决。

## Preconditions
- 目标平台为 Windows，Odin 构建走 MSVC `link.exe`；否则 LNK 错误码不适用。
- `clang++`、`llvm-dlltool`、`odin` 均在 PATH 中，且 `llvm-dlltool -m i386:x86-64` 可用（用于生成与 x86-64 DLL 匹配的导入库）。
- 已有 DLL 导出符号的权威来源（FFI 头文件中的 `extern "C"` 声明）；若只能靠 `llvm-nm`/`dumpbin` 枚举，注意本轨迹中 `llvm-nm epilog.dll` 返回 `epilog.dll: no symbols`、`dumpbin: command not found`。
- DLL 文件存在，且经 `file` / MZ 头检查为有效 PE（本轨迹：`PE32+ executable for MS Windows 6.00 (DLL), x86-64, 6 sections`）。
- 拥有可执行的运行验证方式（冒烟测试或等价的最小运行入口）。
- 具备修改 foreign import 源文件与构建脚本的权限。
- 任一条件不满足：停止执行并向报告缺失项，不进入修复流程。

## Procedure
### Step 1: 确认 LNK1107 的对象是 foreign import 指向的 DLL，并排除文件损坏
- actions: 读取构建错误，确认报错路径与 `foreign import` 声明指向的是同一个 `.dll`；用 `file <dll>` 与 `head -c 4 <dll> | xxd` 检查文件头。
- inputs: LNK1107 错误文本、DLL 路径。
- outputs: 判定记录——DLL 本身是有效 PE（本轨迹：`epilog.dll: PE32+ executable for MS Windows 6.00 (DLL), x86-64, 6 sections`，文件头 `4d5a 9000`），因此问题在“把 PE 映像当库读”而非文件损坏。
- cautions: `file` 显示正常不等于 `link.exe` 能读它作库；不要因它“看起来没问题”就继续复制 DLL 到 build 目录、反复重建 DLL 或追加 `/LIBPATH` —— 轨迹中这三种做法之后 LNK1107 均原样复现。
- preserve: 不修改、不截断 DLL 本身。
- next: 判定为有效 PE → 进入 Step 2；若文件确实损坏/截断 → 停止并另行修复（轨迹未提供该分支）。

### Step 2: 从 FFI 头文件生成 .def 导出清单
- actions: 在 DLL 所在目录创建 `<name>.def`，首行 `LIBRARY <name>`，`EXPORTS` 下逐行列出 `extern "C"` 导出函数名（与头文件一一对应）。
- inputs: FFI 头文件、DLL 所在目录。
- outputs: `<name>.def`（本轨迹 `epilog.def` 含 `epilog_create`、`epilog_query` 等 15 个导出名）。
- cautions: 符号名以接口定义为准；不要依赖符号表枚举——本轨迹中 `llvm-nm epilog.dll` 输出 `epilog.dll: no symbols`、`dumpbin: command not found`，最终按头文件手写清单。
- preserve: 不删除已存在的同名 `.def`，只在缺失时新建或按需补齐。
- next: `.def` 内容与头文件核对一致 → 进入 Step 3。

### Step 3: 用 llvm-dlltool 生成导入库
- actions: 执行 `llvm-dlltool -m i386:x86-64 -d <name>.def -l <name>.lib`，随后 `ls -la <name>.lib` 确认生成。
- inputs: Step 2 的 `.def`。
- outputs: `<name>.lib`（本轨迹实例 `-rw-r--r-- ... 4458 ... epilog.lib`）。
- cautions: `-m i386:x86-64` 必须与 DLL 架构一致（本例 x86-64）；`ls` 输出缺失即视为失败，不要继续。
- preserve: 不改写 DLL、不改写源码。
- next: `.lib` 存在且非空 → 进入 Step 4。

### Step 4: 把 foreign import 改指导入库
- actions: 编辑 Odin 源的 Windows 分支，将 `foreign import epilog_lib "../engine/epilog/epilog.dll"` 改为 `foreign import epilog_lib "../engine/epilog/epilog.lib"`，并注明 DLL 需在运行期位于 exe 同目录或 PATH。
- inputs: Step 1 确认的 foreign import 源文件。
- outputs: 更新后的源文件（编辑工具回执确认已更新）。
- cautions: 只改 Windows 分支；非 Windows 分支的 `foreign import` 保持原样。
- preserve: 其余 `foreign epilog_lib { ... }` 过程绑定、类型定义与无关文件全部不动。
- next: 保存成功 → 进入 Step 5。

### Step 5: 重建并运行验证
- actions: 执行 `odin build src -out:build\<name>.exe`；把 `<name>.dll` 复制到 exe 同目录；运行该 exe。
- inputs: 修改后的项目、生成的 `.lib`、DLL。
- outputs: 构建无 LNK1107 且退出码 0（本轨迹 `Build exit: 0`）；运行输出 `=== Bridge smoke test: PASS ===` 与 `Exit: 0`。
- cautions: 链接通过不代表可运行——本轨迹链接修复后首次运行返回 `Exit code 123`；运行验证不可省略，失败时按 Common Failures 处理，不宣称已修复。
- preserve: 保留 DLL 与 exe 同目录的布局（`build/` 中同时有 `dmls.exe` 与 `epilog.dll`）。
- next: 构建与运行均通过 → 进入 Step 6；运行失败 → 处理运行问题后重跑本步骤。

### Step 6: 把导入库生成固化进构建脚本
- actions: 在构建 DLL 的 `clang++` 命令中加入 `-target x86_64-pc-windows-msvc` 与 `-Wl,/DEF:<路径>\<name>.def`，使编译 DLL 时同时产出 `<name>.lib`；随后完整跑一次脚本（含 build 与 run）。
- inputs: 现有构建脚本、Step 2 的 `.def`。
- outputs: `Creating library <...>.lib and object <...>.exp`、`[engine] Built ...\<name>.dll + <name>.lib`、`[odin] Built build\dmls.exe`、运行冒烟通过。
- cautions: 只新增编译参数，不改脚本其余逻辑；`-target` 与 `/DEF` 两项在本轨迹中是同时加入的，效果按整体验证结论使用。
- preserve: 脚本原有的 debug/engine/run/clean 分支保持不变。
- next: 全链路（编译 DLL → 链接 Odin → 运行）通过 → 结束并汇报。

## Decision Rules
### When LNK1107 报错文件是被 foreign import 直接引用的 .dll，且 `file`/MZ 头显示它是有效 PE
→ 走 Step 2–4：写 `.def`、`llvm-dlltool` 生成 `.lib`、把 foreign import 改指 `.lib`；停止继续复制 DLL 到 build 目录、重复重建 DLL、追加 `/LIBPATH` 这三类尝试（轨迹中它们之后错误原文不变）。

### When 需要把修复固化、且 DLL 由 clang++ 编译
→ 在编译命令加 `-target x86_64-pc-windows-msvc` 与 `-Wl,/DEF:<路径>\<name>.def`，一次编译同时产出 DLL 与导入库（轨迹中输出 `Creating library epilog.lib and object epilog.exp`、`Exit: 0`，随后整套脚本端到端通过）。

### When 构建已通过但运行退出码非 0
→ 以运行结果为准：确认 `<name>.dll` 与 exe 同目录后，用 `-target x86_64-pc-windows-msvc -Wl,/DEF:<name>.def` 重建 DLL 并重跑；在原因未被工具输出确认前，只报告“已定位的改动与验证结果”，不宣称根因已确认。

### When `llvm-nm` 报 `no symbols` 或 `dumpbin` 不可用
→ 不在枚举导出上继续尝试，直接依据 FFI 头文件手写 `.def`（轨迹采用并通过验证的路径）。

### When LNK1107 指向的文件不是 foreign import 引用的 DLL
→ 停止套用本流程并向报告（该分支轨迹未提供处理与验证）。

## Invariants
- 只改 foreign import 的 Windows 分支与构建脚本中 DLL 编译参数；不改无关源文件、不动其它 foreign 绑定。
- 不删除、不覆盖已有的 DLL、`.def`、`.lib` 及其它既有构建产物（新建或按需补齐除外）。
- 不修改未经授权的构建配置项（如 debug/engine/run/clean 分支逻辑）。
- 不跳过运行验证：构建退出码 0 只证明链接成功，不能代替 exe 运行结果。
- 不把 `file`/MZ 头检查当作链接成功或运行成功的证据。
- 不把推测当作已确认的原因（尤其 `Exit code 123` 的成因，轨迹未定论）。
- 不报告未经工具输出验证的成功；汇报必须引用实际构建/运行输出。
- 非 Windows 分支的 foreign import 与源码其余部分保持原样。

## Common Failures
### Failure: 反复复制 DLL、重建 DLL、追加 /LIBPATH 后 LNK1107 原样复现
- symptoms: 连续多次构建返回 `Exit code 83` 与 `d:\dmls\engine\epilog\epilog.dll : fatal error LNK1107: invalid or corrupt file: cannot read at 0x2F8`，报错文件始终是同一个 `.dll`。
- causes: 链接器收到的输入仍是 `.dll` 本身——复制到 build 目录、重新编译 DLL 都不改变输入文件类型；加 `/LIBPATH:engine\\epilog` 后同一错误复现（轨迹可观察事实）。把 PE 映像当库读这一点是与“改指 .lib 后即通过”相互印证的解释。
- recovery: 转入 Step 2–4：生成 `.def` + `.lib` 并把 foreign import 改指 `.lib`。

### Failure: 链接通过后运行返回非 0 退出码（Exit code 123）
- symptoms: `odin build` 已无 LNK 错误，但运行 exe 返回 `Exit code 123`；`Get-ChildItem build` 显示 `dmls.exe` 与 `epilog.dll` 同时存在。
- causes: 轨迹未提供确认原因；助手曾判断为运行时找不到 DLL，但目录列表显示 DLL 在位。之后用 `-target x86_64-pc-windows-msvc -Wl,/DEF:epilog.def` 重建 DLL、重建 exe 后运行通过——该改动与结果相关，但未做单变量验证，因果未定论。
- recovery: 确认 DLL 与 exe 同目录、以 msvc target + `/DEF` 重建 DLL 后重跑；若仍失败，报告实际输出，不宣称已修复。

### Failure: 无法从 DLL 枚举导出符号
- symptoms: `llvm-nm epilog.dll` → `epilog.dll: no symbols`；`dumpbin /exports` → `dumpbin: command not found`；`hexdump` 也不可用。
- causes: 该环境下工具缺失或 DLL 不带可枚举符号表（未进一步确认）。
- recovery: 直接依据 FFI 头文件手写 `.def` 的 `EXPORTS` 清单（轨迹采用并通过验证的路径），必要时用 `xxd`/`strings` 只做存在性检查。

## Verification
1. 构建输出中不存在 `fatal error LNK1107`，且出现 `Build exit: 0`（或等价的 0 退出码行）。
2. `ls -la <name>.lib` 显示导入库存在且非空（本轨迹实测 4458 字节）。
3. DLL 编译输出出现 `Creating library <name>.lib and object <name>.exp`（固化 `/DEF` 后）。
4. foreign import 源文件的 Windows 分支读回后为 `foreign import epilog_lib "../engine/epilog/epilog.lib"`。
5. 运行构建出的 exe，输出含 `=== Bridge smoke test: PASS ===`，且进程退出码为 0（`Exit: 0`）。
6. 运行目录中 exe 与 DLL 并存（本轨迹 `build` 目录列出 `dmls.exe`、`epilog.dll`）。
7. 固化后整套构建脚本输出 `[engine] Built engine\epilog\epilog.dll + epilog.lib`、`[odin] Built build\dmls.exe`，随后自动运行同样打印冒烟通过行。
8. 汇报中的每条“成功”都能对应上述某条可观察输出原文；任何一条未观察到即不宣称完成。

## Examples
### Example 1: Odin foreign import 直接指向 DLL 导致 LNK1107
- input: 构建输出 `d:\dmls\engine\epilog\epilog.dll : fatal error LNK1107: invalid or corrupt file: cannot read at 0x2F8`；`src/bridge.odin` 的 Windows 分支为 `foreign import epilog_lib "../engine/epilog/epilog.dll"`；FFI 头文件给出全部 `epilog_*` 导出名；环境有 `clang++`、`llvm-dlltool`、`odin`。
- procedure: Step 1（`file` 确认 `PE32+ executable ... x86-64`，判定非损坏）→ Step 2（按头文件写 `epilog.def`）→ Step 3（`llvm-dlltool -m i386:x86-64 -d epilog.def -l epilog.lib`）→ Step 4（foreign import 改指 `../engine/epilog/epilog.lib`）→ Step 5（`odin build` 后复制 DLL 并运行）。
- expected result: `epilog.lib` 生成；`odin build` 输出 `Build exit: 0` 且无 LNK1107；exe 运行打印 `=== Bridge smoke test: PASS ===` 与 `Exit: 0`。
- parameterized values: `<project>=DMLS`、`<dll>=epilog.dll`、`<def>=epilog.def`、`<lib>=epilog.lib`、`<exe>=build\dmls.exe`、架构 `x86-64`、`-m i386:x86-64`、导出名列表取自对应项目 FFI 头文件。

### Example 2: 把导入库生成固化进构建脚本
- input: 构建脚本中 DLL 编译行为 `clang++ <CXXFLAGS> -shared <srcs> -o "<dll>"`，`CXXFLAGS` 含 `-std=c++23 -O2 -DNDEBUG -I<dir>\include`（无 `-target`、无 `/DEF`），需要每次构建都产出导入库。
- procedure: Step 6（在该命令追加 `-target x86_64-pc-windows-msvc` 与 `-Wl,/DEF:<dir>\epilog.def`，随后完整执行脚本的 build + run）。
- expected result: 脚本输出 `Creating library engine\epilog\epilog.lib and object engine\epilog\epilog.exp`、`[engine] Built engine\epilog\epilog.dll + epilog.lib`、`[odin] Built build\dmls.exe`，自动运行打印冒烟通过行。
- parameterized values: `<dir>=engine\epilog`、`<dll>=epilog.dll`、`-target x86_64-pc-windows-msvc`、`-Wl,/DEF:!EPILOG_DIR!\epilog.def`、输出 `<exe>=build\dmls.exe`。

## Evidence
1. file_id: `claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02`，source_index: 225，source_part_index: 0，quote: `d:\dmls\engine\epilog\epilog.dll : fatal error LNK1107: invalid or corrupt file: cannot read at 0x2F8`，supports: problem——`odin build` 时链接器对 foreign import 指向的 `.dll` 报 LNK1107（problem）。
2. 同上，source_index: 204，source_part_index: 0，quote: `foreign import epilog_lib "../engine/epilog/epilog.dll"`，supports: problem 的配置来源——最初写入的 bridge.odin 在 Windows 分支直接引用 `.dll`。
3. 同上，source_index: 230，source_part_index: 0，quote: `epilog.dll: PE32+ executable for MS Windows 6.00 (DLL), x86-64, 6 sections`，supports: 判定依据——DLL 本身是有效 PE，排除“文件真损坏”。
4. 同上，source_index: 252，source_part_index: 0，quote: `00000000: 4d5a 9000`，supports: 判定依据——MZ 文件头完好。
5. 同上，source_index: 235，source_part_index: 0，quote: `d:\dmls\engine\epilog\epilog.dll : fatal error LNK1107: invalid or corrupt file: cannot read at 0x2F8`，supports: 失败尝试——追加 `/LIBPATH:engine\\epilog` 后同一错误复现，该方向不解决问题。
6. 同上，source_index: 237，source_part_index: 0，quote: `epilog.dll: no symbols`，supports: 分支——无法用 `llvm-nm` 枚举导出，转为按头文件手写 `.def`。
7. 同上，source_index: 254，source_part_index: 0，quote: `llvm-dlltool -m i386:x86-64 -d epilog.def -l epilog.lib 2>&1`，supports: action——用 llvm-dlltool 从 `.def` 生成导入库。
8. 同上，source_index: 257，source_part_index: 0，quote: `-rw-r--r-- 1 [NAME] 197121 4458 Jun  7 15:30 epilog.lib`，supports: verification——`epilog.lib` 实际生成。
9. 同上，source_index: 262，source_part_index: 0，quote: `foreign import epilog_lib "../engine/epilog/epilog.lib"`，supports: action——foreign import 从 `.dll` 改指导入库（263 为编辑成功回执）。
10. 同上，source_index: 282，source_part_index: 0，quote: `Creating library epilog.lib and object epilog.exp`，supports: verification——`clang++ -Wl,/DEF:epilog.def` 编译 DLL 时同步产出导入库。
11. 同上，source_index: 282，source_part_index: 0，quote: `Exit: 0`，supports: verification——带 `/DEF` 的 DLL 编译退出码为 0。
12. 同上，source_index: 285，source_part_index: 0，quote: `Build exit: 0`，supports: verification——改指 `.lib` 后 `odin build src -out:build\dmls.exe` 退出码为 0 且无 LNK1107 文本。
13. 同上，source_index: 288，source_part_index: 0，quote: `=== Bridge smoke test: PASS ===`，supports: verification——修复后的 exe 实际运行冒烟测试通过（运行级验证，而非仅构建通过）。
14. 同上，source_index: 317，source_part_index: 0，quote: `[engine] Built engine\epilog\epilog.dll + epilog.lib`，supports: verification——固化进构建脚本后 DLL 与导入库随脚本一起产出。
15. 同上，source_index: 317，source_part_index: 0，quote: `[odin] Built build\dmls.exe`，supports: verification——整套脚本端到端链接成功。
16. 同上，source_index: 276，source_part_index: 0，quote: `Exit code 123`，supports: common failure——链接修复后仍可能出现的运行失败，故必须保留运行验证。
17. 同上，source_index: 297，source_part_index: 0，quote: `-Wl,/DEF generates epilog.lib (import library) alongside the DLL`，supports: action——在构建脚本中固化“编译 DLL 同时生成导入库”的做法。

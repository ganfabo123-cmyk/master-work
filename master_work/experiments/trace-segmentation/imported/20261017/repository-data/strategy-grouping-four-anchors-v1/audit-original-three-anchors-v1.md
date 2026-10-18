# 原始 Session 三类锚点组人工审查

日期：2026-10-13。范围仅为 `sessions-30` 下的 `stack-site`、`config-change`、`dependency-change`；共 68 个原始分组。未审查测试组或切片组，未修改分组算法，未重新运行实验。

## 判定口径与结果

逐组读取原始 JSONL 中的锚点及相关诊断、操作、实际输出。计入“可提取”的条件：能围绕该锚点形成具体、可迁移的处理经验，有相应实施和相关验证证据。允许单 Session 支持；不要求两个 Session。只出现依赖声明、伴随配置变化、笼统安装操作、未经验证的诊断，或靠关闭检查消除报错，均不计入本次分子。

这不是已生成 Skill 的验收结果，而是人工判断的可提取组比例。相关阶段验证通过可以支持限定范围的经验；不能据此声称整个工程修复成功。

| 策略 | 可提取组 | 总组 | 占比 |
| --- | ---: | ---: | ---: |
| 调用栈 | 12 | 19 | 63.2% |
| 配置修改 | 3 | 26 | 11.5% |
| 依赖变化 | 9 | 23 | 39.1% |
| 合计 | 24 | 68 | 35.3% |

**68 组全部只有一个原始 Session。** 因此这里无法评估跨 Session 共性，也不能把单成员组的表面纯度当成聚类成功。同一经验可以对应多个组，24 是组数，不能称为 24 个不同 Skill。例如 Solid 初始化、JDK 升级配套各支持多个配置或依赖组。

## 可回溯记录

以下索引为原始 JSONL 的 **零基行索引**，不是模型回合号；查看文件时对应第 `索引 + 1` 行。原始目录：`C:/Users/35153/PycharmProjects/master-work/sessions/claude_code/`。分组 ID、键和来源的完整机器记录仍在同目录实验的 `sessions-30/<策略>/groups.json`。

来源缩写：

| 缩写 | 原始文件名 |
| --- | --- |
| COMP | `89cf9e13-a4bd-4cf9-9486-7c89737bec1b.jsonl` |
| DSP | `da5d32d6-547f-45ae-a5b5-4747ed06542f.jsonl` |
| ICE | `860618e1-0cf6-43c6-81cf-fe67123082ba.jsonl` |
| RED | `7563bddf-c1a0-4c3e-86ee-062bf288e6d3.jsonl` |
| CFML | `07b57159-218e-4330-a64e-0ec4b4355056.jsonl` |
| NEON | `ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a.jsonl` |
| DB | `c84c0ad3-c368-40df-87b1-5ef9effe237a.jsonl` |
| JAVA | `3be5ba0c-62b2-4645-8589-9216be0c10d8.jsonl` |
| OS | `09d9abe9-0a02-4bd1-8129-3b864695079d.jsonl` |
| API | `4130c9a7-ee88-443a-91b5-224accd13629.jsonl` |
| BENTO | `d4c4d47d-642c-4c26-a866-51ab85587896.jsonl` |

### 调用栈：12 / 19

| 组 ID（统一前缀 stack-site-） | 可提取 | 判断及原始证据 |
| --- | --- | --- |
| bbfe0cb4e870 | 否 | COMP 171：数据库 URL 缺失被识别，但数据库配置没有完成修复。前端预览绕过不能验证这一根因修复。 |
| 64e0a95a5915 | 是 | DSP 686、688–690：WebView CDP 连接时机导致 socket hang up；等待端点就绪再连接，实际输出 connected=true。经验是初始化顺序与就绪检测，不是通用网络重试。 |
| d7acef79a781 | 否 | ICE 108：目录/缓存权限故障；后续换框架重建项目，未验证该权限问题的针对性修复。 |
| 5dc1e5f04830 | 否 | RED 227、239–240、256–257：lint 与生成文件有处理，但 bundler 仍失败；不能抽象为该构建栈的已解决经验。 |
| fbd833c947fd | 是 | ICE 947–949、957：cp1252 输出文本失败；stdout 显式 UTF-8 后实际输出原先无法编码的内容。仅支持文本输出编码经验。分组异常名被包装为 Exception，不是精确根异常。 |
| 56e927c67309 | 是 | DSP 1477、1483–1490：pipx 环境引用已不存在的解释器；删除损坏环境后重建，安装与 CLI --version 验证成功。 |
| d21771301187 | 否 | DSP 1508：系统 Python 不能导入 pipx 环境中的包；后续读取源码绕过，缺少正确解释器 import 验证。 |
| f1b04b3c9b81 | 否 | CFML 314、319–320：pygame 缺失后安装成功，但仅是通用缺包安装，没有足够具体的可复用决策。 |
| 0f2e53fb10cd | 否 | ICE 929、931–932：pypdf 不可用后改用已安装的 pymupdf，确实读出 PDF；替换包的单次操作信息较薄，不计入本次可用经验分子。 |
| 1dc7cd9e2b87 | 是 | NEON 169、173、176、178–179：虚拟环境缺 torch，不应直接重装大依赖；核对实际解释器，系统 Python 已能正确识别 torch/CUDA/GPU。仅限环境定位。 |
| 481646130e03 | 是 | DB 240、243、247、258–260、275：Svelte SCSS 缺预处理；添加 vitePreprocess 后重新构建通过。栈键含畸形 file URI 和 bundler 包装位置，实际根因来自上下文。 |
| 8ee3eb1d9bb5 | 是 | DSP 1513、1517–1518、1528：获取源码时间前尚未 checkout，SOURCE_DATE_EPOCH 为 None 导致环境编码 TypeError；提前 clone/checkout 后运行进入 npm/Vite 构建。只证明该前置阶段推进，F-Droid 完整构建仍有后续问题。 |
| 1d2e5fd67cdc | 是 | CFML 126–131：dataclass 继承默认字段与必填字段顺序冲突；kw_only=True 后类可实例化并运行到 lexer。 |
| d90b744c0b0a | 是 | CFML 169–174、176、178、181：采用 keyword-only 字段后旧位置参数调用失效；修改构造调用为命名参数。后续还修了前向求值环境，最终输出 3、2、1；不能把最终通过全归因于一个改动。 |
| c869f65cb347 | 是 | COMP 151、153、195、197–199：共享 layout 的后端依赖阻断前端预览；临时使用形状兼容的 fallback，目标路由 HTTP 200 且包含目标内容。只适用于本地预览隔离，原记录要求提交前撤销，不能推广成生产故障掩盖。 |
| 0f0e23d3b265 | 是 | CFML 283–288、299、302、306、310–311：终端 UnicodeEncodeError 采用 ASCII fallback；重新运行实际打印完成信息，原编码异常消失。但仍有 Tkinter 线程清理 exit=3，不声称完整动画程序通过。 |
| 6869e8d04203 | 是 | JAVA 364、368、372、378、385、388：JDK 25 class major 69 超出实际解析到的 Groovy/ASM 支持；核对依赖树并强制兼容 Groovy 后 compileTestGroovy 通过，补 launcher 后测试任务通过。经验需要检查实际解析版本，不能只改声明。 |
| e4dcde7310e0 | 是 | JAVA 1153、1155、1160、1164、1167、1171：PropertyLens 初始化读取空模型；先 seed empty state 再建立 zoom/lens。目标测试 31 项零失败，后续全套 455 项零失败。 |
| 278d9ea7bd07 | 否 | JAVA 79、82、89、97：NullObject.invokeMethod 是清理/关闭阶段异常，另有不支持 LocalDateTime 的主问题；没有针对该栈的修复与验证链。 |

### 配置修改：3 / 26

ICE 的前 14 组来自项目重建时整份 tsconfig 替换。旧 React Router 配置曾被删除；算法保留的历史快照不能直接当成新配置的即时前态。不能把 14 个 diff 字段视为 14 项独立修复。

| 组 ID（统一前缀 config-change-） | 键 | 可提取 | 判断及原始证据 |
| --- | --- | --- | --- |
| ca678c07273b | esModuleInterop | 否 | ICE 213：随重建消失，没有针对性理由或验证。 |
| 5271e65bacc8 | isolatedModules | 否 | ICE 213：模板字段，没有对应问题与验证。 |
| 37d34aa00871 | jsx | 是 | ICE 207–213、237–238：手工建立 Solid/Vite 配套，保留 JSX 供 Solid 插件处理，实际 Vite 编译通过。与下组共同支持一项初始化配套经验；未独立做 tsc 验证或逐键消融。 |
| 7ead800acf1a | jsxImportSource | 是 | ICE 207–213、237–238：Solid JSX 配置与 vite-plugin-solid 配套，完整脚手架编译通过；只支持配套方案，不证明该键单独修复了某个错误。 |
| 2eb237f15a12 | lib | 否 | ICE 213：重建中的伴随删除。 |
| a50a3c22f9be | module | 否 | ICE 213：模板整体替换，未有针对性修复证据。 |
| 5ecf7ea08ee9 | paths/~/* | 否 | ICE 213：旧项目路径映射删除，不是通用修复。 |
| 83d1fe268303 | resolveJsonModule | 否 | ICE 213：重建中的伴随删除。 |
| c191b12e6e69 | rootDirs | 否 | ICE 213：旧 React Router 目录配置移除，无独立经验。 |
| b86066c0895e | skipLibCheck | 否 | ICE 213：伴随删除；没有类型检查验证。 |
| 35ec872b6f27 | target | 否 | ICE 213：模板设置，没有相应兼容性验证。 |
| 3a304066193d | types | 否 | ICE 213：伴随删除，没有类型检查验证。 |
| 0e5ccad271ae | verbatimModuleSyntax | 否 | ICE 213：伴随删除，没有对应诊断。 |
| 6dfdb7164573 | include | 否 | ICE 213：项目目录变更，未运行 tsc 验证 include 覆盖。 |
| 16a4fde66940 | categories/perf | 否 | RED 183：删除规则类别消除 lint 问题，无法证明代码问题解决或检查等价。 |
| c1a887309e6d | ignorePatterns | 是 | RED 227、231–232、239–240：lint 先于 manifest 重新生成，生成器所有的文件受到不适当格式化/检查；定向排除该生成文件后 lint 阶段通过。仍有 bundler 失败，经验仅限 lint 与生成文件职责边界。 |
| 2d66c632bc34 | jsPlugins | 否 | RED 167、172、179：TS 插件加载失败后移除插件；恢复基础 lint，但也取消框架检查，缺少保留原校验能力的方案。 |
| 677c11cfa22e | manic/image-needs-dimensions | 否 | RED 172：伴随插件移除，未证明该规则应删除。 |
| 8208d3f3b25c | manic/no-raw-anchor-element | 否 | RED 172：伴随插件移除，未证明该规则应删除。 |
| 2a185c909775 | manic/no-raw-img-element | 否 | RED 172：伴随插件移除，未证明该规则应删除。 |
| d5ee23f3480e | manic/no-sibling-route-import | 否 | RED 172：伴随插件移除，未证明该规则应删除。 |
| b5b6a1481197 | manic/routes-require-default-export | 否 | RED 172：伴随插件移除，未证明该规则应删除。 |
| 226ce87ec1d2 | max-lines | 否 | RED 234：关闭检查，不视为可靠处理经验。 |
| 36a1348e51fd | require-unicode-regexp | 否 | RED 234：关闭检查，不视为可靠处理经验。 |
| 1fcfd45b8ca2 | module | 否 | OS 170–171、482–483：有 ESM/打包器对齐的解释和改动，但只有 esbuild 构建成功，没有 tsc/原类型报错消失的实际验证；保留为候选，未计入。 |
| 6eca441a5692 | moduleResolution | 否 | OS 170–171、482–483：与上组同一处理；esbuild 成功不能代替 TypeScript 模块解析验证。 |

### 依赖变化：9 / 23

18 组只是 `declaration_old_unknown`，即观察到声明、旧状态未知，不能叫作已确认升级。其中有具体使用和验证的声明组仍可支持初始化经验；其余不能仅凭 npm install 成功计入。

| 组 ID（统一前缀 dependency-change-） | 依赖 | 可提取 | 判断及原始证据 |
| --- | --- | --- | --- |
| afe4b5c51555 | com.android.application | 否 | DSP 105：初始化声明，未展示该版本选择或兼容问题的解决依据。 |
| 356cba7c7f6b | net.ltgt.errorprone | 是 | JAVA 325、329、331、338–339、352–353：迁移 JDK 25 时检查 launcher/toolchain 区别并配套更新分析插件，真实 compile 成功。与下面两个依赖同一经验，不是三个独立版本最佳实践。 |
| 2355dec6d17d | org.jetbrains.kotlin.android | 否 | DSP 105：初始化声明，缺少具体版本选择经验。 |
| 77094466cc84 | androidx.core:core-ktx | 是 | DSP 780–785、789–796：target SDK 35 系统栏覆盖，采用 WindowInsetsCompat/ViewCompat 调整 padding，构建与安装通过，有截图产物。未在本轮看截图，不能声称视觉正确性已验收。 |
| 8b30018d5bcf | androidx.webkit:webkit | 是 | DSP 111、131、144、686、689–690：将 web dist 同步到 assets，以 WebViewAssetLoader 虚拟 HTTPS 主机加载本地资源；实际 APK 构建/安装和 WebView 页面脚本连接成功。支持离线 WebView 资源装配经验，非某个版本升级结论。 |
| 69526b6f05bf | error_prone_core | 是 | JAVA 325、331、352–353：JDK 25 配套静态分析器更新并真实编译验证。共享升级方案，未做各依赖独立因果验证。 |
| 746e00683b3c | nullaway | 是 | JAVA 325、331、352–353：同一 JDK/分析工具兼容方案与 compile 验证。 |
| 95ae17da4d24 | junit-platform-launcher | 是 | JAVA 378、380–382、385、387–388：compileTestGroovy 已通过但运行器缺 launcher；核对解析到的平台版本并补齐 test runtime launcher，测试任务成功。 |
| d3fa2e2727ed | bcryptjs | 否 | API 45、199–203：后端初始化声明/安装；没有相应密码认证流程的运行验证。 |
| 826a323aeb6b | cors | 否 | API 45、199–203：后端声明/安装，未验证跨域行为。 |
| fea47791b879 | dotenv | 否 | API 45、199–203：后端声明/环境文件创建，未验证加载行为。 |
| f7afe0bfafd5 | esbuild | 否 | BENTO 38、455、478、487、520：有脚本和部署资源排障讨论，缺少实际构建/部署资源访问验证；不能把写出脚本当作修复成功。 |
| 8137471b72aa | express | 否 | API 45、199–203：后端框架声明，未有 API 服务运行验证。 |
| 1f15ab5ccbe7 | express-rate-limit | 否 | API 45、199–203：声明，未验证限流机制。 |
| 88b149615c22 | express-validator | 否 | API 45、199–203：声明，未验证输入拒绝流程。 |
| cdfaf23fb979 | helmet | 否 | API 45、199–203：声明，未验证响应头机制。 |
| 42ebdf051a40 | jsonwebtoken | 否 | API 45、199–203：声明，未验证 token 签发/校验流程。 |
| 53eddb5d3360 | mongoose | 否 | API 45、199–203：声明，未验证数据库连通/持久化。 |
| d89eab3ec755 | multer | 否 | API 45、199–203：声明，未验证文件上传。 |
| b4256094e977 | nodemailer | 否 | API 45、199–203：声明，未验证邮件发送。 |
| 36a1960409ff | solid-js | 是 | ICE 196–204、207–213、235–238：交互式脚手架阻塞后手工装配 Solid/Vite 工程，真实安装与编译成功。与下面两个依赖及两个配置组同一初始化经验。 |
| f0f127260d81 | vite | 是 | ICE 207–213、235–238：同一非交互式初始化配套与构建验证，不是独立 Vite 版本升级经验。 |
| abd138308415 | vite-plugin-solid | 是 | ICE 207–213、235–238：同一 Solid 插件/JSX 配套与构建验证。 |

## 结论边界

调用栈组在本次样本中最有用，通常同时提供失败位置、触发条件和修复后是否推进的可核对证据，但包装栈/清理栈不一定是根因。配置组多数是整份重写的伴随变化；依赖组多数是初始声明。只有找回原始上下文才能区分可复用处理经验与这些弱证据。

可提取不代表内容能不经审查直接投入使用。最终 Skill 应保留上面记录的适用范围、相关验证与未解决事项。此次没有实际生成 Skill 正文，没有估计 Skill 损失率，没有统计不同 Skill 数量。

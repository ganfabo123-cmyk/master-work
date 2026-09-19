## 经验一:机制调研先派 explorer,拿到路径再读文件

在 2026-08-23,我做了"开发生成插件 `@deepseek-ai/dsh-markdown-to-csv` 时的仓库机制调研:当时在不知道先例路径的情况下,用 grep/read 自己逐个文件翻仓库,去找三个问题的答案(Web GUI 如何提供可点击下载链接、插件内部如何编程式调用 subagent、生成插件的 package.json/tsconfig 规范形态)"。
反馈为 失败(根据用户反馈:他事后提醒"我提供了 explorer agent,你为什么不问他",说明本可用而没用,走了远路;且我在踩坑后才通过 git log 发现 HEAD 里早就躺着 say-hello 完整先例)。

当时我的做法是:
- 全程自己 manual 探索:读仓库地图、cookbook、dsh-tools/subagent/llm/host-webserver 源码、client 的 markdown 渲染器与 URL 白名单、attachment/session-export、plugin-reference、tsconfig/pnpm 配置……大量重复阅读后才拼出结论。
- 对"下载链接机制""subagent 接口""插件规格"这类问题,明知道目标位置未知、需要跨包对比语义,却没有调用 explorer,也没有先查 git history 里的已提交生成插件先例。

我需要深刻思考一下这次失败的背后原因:
为什么我会失败,我认为原因是:
- 我自己拥有完整的 read/grep 能力,下意识认为"文件已知、自己读最直接",于是把"找路径"和"读文件"混为一谈,全程自己扫仓库;而 explorer 正是为"目标位置未知、跨包语义对比、只要结论+证据路径"设计的。
- 工具链脚手架是 TODO 占位,没有指向已完成先例(say-hello 就在 git HEAD),导致我先反向拼规格、后才发现模板。
可迁移原则:凡是"不知道去哪找"或"要跨多个包对比语义"的机制性问题,必须先派 explorer 拿答案与证据路径,再只读关键文件;涉及"生成插件该长什么样"时,先查 git history 中的已提交生成插件,再动手。

---

## 经验二:需求阶段先确认"谁处理输入"的角色边界

在 2026-08-23,我做了"需求阶段把'用插件的模型处理输入'理解成插件内部调用 subagent 来规范化表格,并按此实现了整套 subagent 委托(提示词模块、JSON 合同解析、相关测试与文档)"。
反馈为 失败(根据用户反馈:他看到实现后明确纠正"不需要 subagent,处理用户信息的是调用方 agent,插件只负责转换生成链接",第一版实现被全部推翻重写)。

当时我的做法是:
- 需求澄清时问了三个问题(转换流程/下载链接/模型来源),第三问给出了 subagent 等选项,用户选择"直接用 subagent",我便默认了"插件内部调用模型"这一读法,没有进一步确认"谁处理用户输入"这个架构边界。
- 直接进入实现,把 subagent 委托当成正确方向写完整套代码后才暴露问题。

我需要深刻思考一下这次失败的背后原因:
为什么我会失败,我认为原因是:
- "调用插件的模型对用户输入进行处理"存在两个可互换的角色读法:插件自身调用模型,或调用方 agent 处理输入、插件只做转换;我把表述当成了确定方向,而不是当歧义去澄清。
- 需求澄清问题本身也偏向了方案("用 subagent?还是配置模型?"),没有先问最基础的"输入处理发生在哪一侧"。
可迁移原则:任何涉及"谁/哪一侧负责处理输入、规范化数据"的表述,在提交元数据前必须用 ask user 直接确认角色边界,绝不默认一种读法;需求模板里应显式包含"调用方 agent 处理(推荐) vs 插件自身处理"这一问。

---

## 经验三:插件 patch 用 insert + file:// 直载,不要用包名

在 2026-08-23,我做了"把加载插件的 patch 文件写成按包名引用(`name: '@deepseek-ai/dsh-markdown-to-csv'`),导致 dsh web 与验收子进程都加载不到插件"。
反馈为 失败,后经纠正成功(根据用户反馈:他多次问 agent 都得到'没有 markdown_to_csv 工具';他指出自己加载 cordis-sub-agent 用的就是 `temp-cordis-sub-agent.yml` 的 `insert:` + `file://` 写法;我照此改写后他本地 `--patch` 一次通过)。

当时我的做法是:
- 起初误以为按包名引用是正确方式,排查了很久:先怀疑 subagents 注册表缺失,又怀疑 bundle 依赖声明,甚至动用 codex 确认"包名解析不到"这一根因。
- 最终参考用户的 `temp-cordis-sub-agent.yml`,把 patch 改为 `insert:` + `file://` 绝对路径直载构建产物 `lib/index.js`:
  ```yaml
  - insert:
      - id: markdown-to-csv
        name: 'file:///D:/<repo>/packages/generated/dsh-markdown-to-csv/lib/index.js'
  ```

我需要深刻思考一下这次失败并成功纠正的背后原因:
为什么我会失败,我认为原因是:
- 包名解析锚点($DSH_HOME/profiles/node_modules 镜像 apps/cli 与各 bundle 的依赖闭包;验收子进程的 jsonrpc-demo 依赖表面)里都没有生成插件,且解析失败是**静默**的——工具不注册、零报错,只能靠"问模型有没有工具"才能发现。
- 我一开始不知道(也没先查)仓库里已有的 patch 写法先例(temp-cordis-sub-agent.yml 与 git HEAD 中的 say-hello/cordis.yml 都是 `insert:` + `file://`)。
可迁移原则:加载生成插件的 patch 必须用 `insert:` + `file://` 直载 lib/index.js,不要用包名;`insert:` 只属于 overlay patch(--patch 传入的文件),不能进主配置;验收组合 agent-spine 没有 webServer,验收 overlay 需额外以 file:// 带上 host-webserver(config host: 127.0.0.1, port: 0),且该 overlay 不能用于 dsh web(会与已有 webServer 服务重复导致组合失败);遇到"插件加载不上"先自查 patch 引用方式与解析锚点,而非怀疑业务代码。

---
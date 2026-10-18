# skills_b — B组实验语料（35 个机器抽取 skill）

## 出处

- 来源运行：`skills-result/20261014-210632`（原始运行目录 `skill-runs/20261014-210632`，模型 `mimo-v2.6-flash`）
- 分组：每个运行目录含三组 skill（`A-original` / `B-selected` / `C-context-collapsed`），本语料只取 **`B-selected`（B组）**
- 提取命令：`python extract_skills_b.py`（幂等；字节级复制 + 出处校验）
- 逐条出处元数据：`index.jsonl`（name / group_id / error_key / 来源 session / sha256）

## 规模与分布

35 个 skill，落在 14 个 error_key 簇：

| error_key | 数量 | | error_key | 数量 |
| --- | --- | --- | --- | --- |
| exit-status:0x00000460 | 4 | | ms-linker:LNK1105 | 2 |
| exit-status:0xC00000FD | 5 | | ms-linker:LNK1107 | 1 |
| exit-status:0xC0000135 | 3 | | ms-linker:LNK1120 | 4 |
| exit-status:0x00000451 | 1 | | ms-linker:LNK2019 | 5 |
| symbolic-code:ECONNRESET | 1 | | symbolic-code:ENOTEMPTY | 2 |
| symbolic-code:EPERM | 3 | | typescript:TS1484 | 2 |
| typescript:TS2554 | 1 | | typescript:TS6133 | 1 |

## 格式

标准 SKILL.md：frontmatter `name` + `description` + `triggers`（单行 description，"Use when …
Do not use when …"句式，372–636 字符，中位数 535；正文为 Goal / Scope / Inputs / Outputs /
Preconditions / Procedure / Decision Rules / Invariants / Common Failures / Verification /
Examples / Evidence 的完整结构，Evidence 节带来源 session 的逐条引用）。

`triggers:` 为 2026-10-15 补写的结构化触发签名（`add_triggers_skills_b.py`，策划映射表即
该脚本内的 TRIGGERS 字典），共 96 条，只收机器模板文本（错误码 / NTSTATUS 十六进制与
十进制双形态 / errno / 编译器与词法器诊断原句 / 脚手架提示语），每条都经脚本校验在
正文或证据引文中有出处。近重复族共享族签名是有意行为（同问题多变体共同命中，由
description 相似度排序决定注入谁）；已验证族分离成立：LNK1107 输入不会触发 LNK1105
三件套，TS2554 输入不会触发 TS1484 专属 skill。

与 `retrieval_program.py` 解析器已验证兼容：35/35 通过 `_parse_skill_description`；
`full_content` 保留 frontmatter 原文，命中时由 `_skill_body()` 剥离（v1 既有设计）。

## 有意保留的近重复（对比组，不去重）

不同 error_key 簇之间存在同主题近重复，正是检索实验需要的测试素材
（同族区分、语义路由 vs 字面签名的分歧点）：

- **锁定的输出 exe**：`fix-windows-lnk1105-locked-output-exe`、`resolve-lnk1105-locked-output-on-windows`、`handle-locked-or-stale-test-binaries`
- **大 fixture 栈溢出**：`fix-test-stack-overflow-large-fixtures`、`fix-stack-overflow-large-test-fixtures`、`fix-windows-0xc00000fd-stack-overflow`、`fix-windows-stack-overflow-in-large-local-fixtures`、`keep-large-test-fixtures-off-windows-stack`、`avoid-odin-large-struct-stack-frames`
- **测试宏 token 粘贴/计数器**：`fix-test-macro-token-paste-counter`、`fix-test-macro-token-pasting-ids`、`fix-test-macro-unique-name-pasting`、`capture-counter-once-for-test-macros`
- **lexer 点号**：`fix-lexer-dot-followed-by-nonspace`、`fix-lexer-dot-after-concatenated-literals`
- **LNK2019 头文件全局**：`fix-lnk2019-header-inline-global`、`fix-lnk2019-header-global-with-inline-variable`
- **SolidJS 脚手架**：`scaffold-solidjs-vite-noninteractive`、`scaffold-solidjs-vite-non-interactive`
- **react-router typegen 目录锁**：`clear-locked-react-router-typegen-dirs`、`unblock-react-router-typegen-enotempty`
- **useRef TS2554**：`fix-react19-useref-ts2554-no-default`、`fix-ts2554-useref-tsc-batch`

## 与 skills_tests 的关系

- `skills_tests/`（10 个，手工从卡死 trace 提炼）= 策略 v1 的当前语料，保持不动；
- `skills_b/`（本目录，35 个，机器批量抽取）= 扩展实验语料；
- 切换语料只需改 `retrieval_program.py` 的 `SKILLS_TESTS_ROOT` 指向（或改为可配置），本目录未接入。

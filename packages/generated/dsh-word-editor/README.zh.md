[English](README.md) | 中文

# @deepseek-ai/dsh-word-editor

一个个人 Word（`.docx`）快速编辑与生成插件。它暴露模型工具 `word_open`、`word_read`、`word_find`、`word_str_replace`、`word_add_to`、`word_delete`、`word_formula_scan`、`word_formula_convert`、`word_generate`、`word_superscript` 和 `word_save`，让调用方 agent 打开源文档（或模板副本），并通过会话内的目标 id 对其进行编辑：带样式白名单的纯 OOXML 结构读取与编辑、表格行克隆、原子保存，以及通过 Windows Word COM 自动化进行的原生 Word OMath 转换（并为有歧义的 LaTeX 配备公式清理子代理）。一次性的 `word_generate` 会把 Markdown 稿件与模板转换为正文格式与模板样式、页面布局一致的新文档；`word_superscript` 会把既有文档中的方括号引用转换为真正的上标 run。它从不覆盖源文件；输出是源文件旁的一个新文件，以可点击的本地链接返回并附带变更（或结构）摘要。

## 插件形态

注册这十一个工具的功能插件，通过 `cordis.yml` 组合。需要 `tools`、`subprocess` 和 `subagents` 服务。dsh web 基础 profile 提供全部三个服务；验收 overlay 通过直接文件 URL 添加 thin-profile 依赖。

## 工具

### word_open

`word_open({ source_path? , from_template? })` 将源 `.docx` 打开为一份工作副本，或从已配置的模板新建一份工作副本（`from_template: true`）。此后的一切操作都作用于副本 —— `word_save` 写入的是新文件，从不写源文件。

### word_read

`word_read()` 按顺序返回整个工作文档的块结构 —— 段落、标题、表格（行与单元格）、内容控件、OMath 和节属性 —— 每个元素附带其目标 id、类型和样式。正文段落只显示首句预览和结构标志；其余所有元素以及所有表格单元格段落显示全文。首先调用它来收集目标 id。

### word_find

`word_find({ id?, content? })` 按 `target_id` 读取某段落的全文，或查找全文包含某子串的所有段落。两者同时给出时，只检查指定段落，且该段落必须包含该子串。无参数是参数错误；非段落 id 是类型错误。匹配结果复用 `word_read()` 的目标 id。

### word_str_replace

`word_str_replace({ target_id, old_content, content, style = 'keep' })` 替换段落中的一段精确子串（或整段文本），并审计替换前后的文本与样式。`old_content` 必须精确匹配，否则拒绝本次编辑。多行 `content` 会拆分为多个段落；普通替换拒绝跨越公式、图形或域 —— 请改用公式工具。

### word_add_to

`word_add_to({ target_id, content, style, position, is_new_para })` 在段落、单元格、表格行或整个文档处添加内容。新段落应用逻辑样式；行内追加则保持原段落。添加表格行会克隆目标行（保留列宽、边框、底纹、合并与行高），并用提供的逐列文本填充每个单元格。

### word_delete

`word_delete({ target_id, content?, style? })` 删除一段精确子串；省略 `content` 时删除整个段落 / 表格行 / 表格。`style` 作为删除前的断言；不存在隐式的全部删除。

### word_formula_scan

`word_formula_scan({ target_id? })` 扫描文档（或单个目标）中尚未成为 Word OMath 的 LaTeX，返回候选公式及其源文本区间、显示类型和置信度。已存在的 OMath 受保护，绝不重复扫描。有歧义的候选会交给清理子代理，后者通过 `submit_formula_candidates` 结构化结果对其进行规范化（去除 Markdown 代码围栏、零宽字符和拆分 run 噪声）。

### word_formula_convert

`word_formula_convert({ candidate_ids, minimum_confidence? })` 在本机通过 Windows Word COM（`OMaths.Add` + `BuildUp`）把已确认的候选转换为原生 Word OMath。低于置信度下限的候选会被跳过并附带警告。Word 不可用时返回运行时环境错误且不存储任何内容 —— LaTeX 从不会被保存为虚假的转换结果。

### word_generate

`word_generate({ markdown_path, template_path? })` 一次性从 Markdown 稿件和模板生成一份全新 `.docx`。插件自行解析 Markdown（1–3 级标题、以空行分隔的正文段落、有序/无序列表、管道表格、图片、参考文献，以及行内 `\(...\)` / `$...$` 数学公式与块级 `$$...$$` 数学公式），并将模板副本重塑为使用模板具体样式和页面布局（保留其样式、页眉页脚和节属性）的正文。封面与目录刻意不在其职责范围内 —— 由调用方负责。识别出的每条公式会以裸 LaTeX 文本写入正文（`\(...\)` / `$...$` / `$$...$$` 包裹符会被剥除），调用方可在后续用 `word_formula_scan` + `word_formula_convert` 将其转换为原生 OMath。返回输出文档的可点击链接以及一份结构化概览（标题、段落/表格/参考文献/图片数量），便于模型在不必通读整篇文档的情况下确认结构。

### word_superscript

`word_superscript({ source_path })` 打开一份既有 `.docx`，把其正文与表格单元格中所有类似 `[1]`、`[1-4]`、`[1,2,5]`、`[1、2]` 的方括号引用转换为真正的上标 run，并保留其余所有行内格式（粗体、斜体、字号）。它会在源文件旁另存一份 `-superscripted-<timestamp>.docx`（从不覆盖源文件），并返回输出链接与转换的引用数量。参考文献列表（`参考文献` 样式的段落）保持原样，因此其行首 `[1]` 标记仍作为列表编号，而非上标。

### word_save

`word_save()` 将工作副本原子写入源文件旁的 `{base}-edited-{timestamp}.docx`，并返回其真实路径、可点击的本地链接、变更摘要，以及 Word 无法刷新目录域时的警告。保存前会先将源文件与其打开时的字节进行比对；源文件已变更则拒绝保存。

## 配置

```yaml
plugins:
  word-editor:
    template: 'D:\Users\Lenovo\Desktop\文件\开题报告-初稿.docx'
    proposalTableTemplate: 'D:\Users\Lenovo\Desktop\文件\开题报告-初稿-专属表格样式.docx'
    allowlist: ['reference', 'table_content']
    subagentProvider: 'spawn'
    updateToc: true
```

- `template`：稿件生成所用的默认模板。
- `proposalTableTemplate`：带有专属表格样式的首次适配模板。
- `allowlist`：在固定的正文/标题/目录/参考文献/表格内容样式集合之外，写工具可显式设置的附加逻辑样式名。
- `subagentProvider`：公式清理子代理运行所在的 `ctx.subagents` 提供方（默认 `spawn`）。
- `updateToc`：保存时通过 Word 刷新文档的目录域（默认 `true`）。

## 前置条件

- Microsoft Word（Windows）及较新的 PowerShell，用于 `formula_convert` 和可选的目录刷新。没有 Word 时，编辑工具与 `formula_scan` 仍可使用；`formula_convert` 返回环境错误。
- 一份使用白名单样式名的源 `.docx`，或一个已配置的模板。首次适配的模板即开题报告模板，其样式为：正文 `Normal (Web)`、三级标题 `heading 2/3/4`、`toc 1/2/3`、表格单元格 `表格内容`、参考文献 `参考文献`，以及专属的 `开题报告表格` 表格样式 —— 全部按名称动态解析，从不使用硬编码的样式 id。

## 模型体验

### 插件交互

#### 模型看到的内容

模型看到这十一个工具的 schema。工具描述告诉它先 `word_read()` 获取目标 id、用 `word_find()` 定位具体段落、通过写工具进行编辑（写工具返回审计记录）、用 `word_generate` 从 Markdown 生成全新文档、用 `word_superscript` 把方括号引用转为上标、用公式工具扫描和转换公式，并告知输出是新的可点击本地文档链接而非粘贴内容。

#### Token 影响

主要开销来自 `read()` 的结构转储（受硬性元素上限约束）和 `find()` 返回的段落全文。写工具返回紧凑的审计记录。

#### KV 缓存影响

无固定前缀：该插件不向系统提示词追加任何按请求变化的文本。

## 已知限制与待办事项

- `formula_convert` 需要装有 Microsoft Word 的 Windows 主机；在其他环境中它返回运行时环境错误，且绝不把 LaTeX 存为已转换的公式。
- `word_generate` 解析行内 `\(...\)` / `$...$` 与块级 `$$...$$`（含跨行公式体），并将其以裸 LaTeX 文本写入正文（剥除包裹符）；它不构建 OMath —— 公式转换由 `word_formula_convert`（或调用方自有的流程）负责。封面与目录不在其职责范围内 —— 由调用方负责。
- `word_superscript` 只匹配方括号内的数字列表引用；含数学公式、图形、域或换行的段落保持原样、不做转换。
- 多段替换内容会按换行拆分为多个独立段落；单个段落无法承载内嵌换行。
- 表格行克隆保留目标行的格式与结构，但跨合并区间的单元格会保留该合并，而不是将其拆开。
- 批量删除必须逐一列出每个 `target_id`；不存在隐式的全部删除。
- 目录域刷新依赖保存时的 Word；没有 Word 时，目录域留待 Word 打开文档时更新。

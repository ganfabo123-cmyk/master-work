# 公式转换状态说明（2026-09）

本文档描述 `dsh-word-editor` 在公式处理上的当前状态、`word_generate` 与
公式转换的关系，以及已知问题和后续方向。它只陈述现状，不承诺某个交付目标。

## 背景

插件最初想实现：「`word_generate` 生成 Markdown 稿件的同时，把正文里的
行内公式 `\(...\)` / `$...$` 与块级公式 `$$...$$` 就地转成 Word 原生 OMath，
一步到位，免去你逐个手动转换」。

为此新增/修改了：
- `markdown.ts`：识别 `\(...\)`（行内）、`$...$`（行内）、`$$...$$`（块级，
  含跨行），并把公式解析为数学 run / 数学块。
- `generate.ts`：生成阶段把每条公式写入唯一的占位符（`%%DSH_MATH_<n>%%`），
  同时收集 `latex` 与 `display` 信息。
- `wordcom.ts`：新增生成专用脚本（按占位符就地替换成 OMath）。
- `coordinator.ts`：`generateFromMarkdown` 在保存前调用 Word COM 做转换。

## 当前状态（结论）

**「`word_generate` 自动转 OMath」功能已从产品中移除。** 公式转换不再由
`word_generate` 承担，统一由你后续自行转换（例如用 `word_formula_scan` +
`word_formula_convert`，或你自己的流程）。

现在的行为：
- `word_generate` 仍解析 `\(...\)`、`$...$`、`$$...$$`，但只把公式的
  **裸 LaTeX 文本**（去掉 `\(`/`\)`/`$`/`$$` 包裹符）写入正文。不做任何 OMath。
- `word_formula_scan` / `word_formula_convert` 这两个手动转换工具**保留**，
  你可以在生成后用它们把 LaTeX 转成原生 Word OMath。
- 生成专用脚本 `buildGenerateWordScript` 与占位符机制已删除。

## 移除原因（已知问题）

用真实 Microsoft Word COM 验证时发现：`OMaths.Add` + `BuildUp` 依赖 Word 的
线性公式导入能力，对**复杂 LaTeX 指令转换不完整**。实测残留了这些字面文本：

- `\text{...}`（多次出现，如 `\{\text{Support},\text{Reject},\text{Refine},...\}`）
- `\langle` / `\rangle`
- `\rho`、`\alpha`、`\rightarrow`

也就是说，部分公式即使被建立了「公式对象」，内容仍显示为 LaTeX 反斜杠，
没有排成专业数学公式，达不到「显示成公式、不再是一堆反斜杠」的预期。
因此不适合把「自动转换」做为 `word_generate` 的默认行为，故移除。

## 已验证可行的转换链路（供你后续自行转换时参考）

如果之后想在 Word COM 里把一段 LaTeX 就地转成 OMath，下面这条链是经过真实
Word 验证可用的（关键在于 `OMaths.Add` 返回的是 `Range`，不是 `OMaths` 集合）：

```powershell
$rng = $doc.Content.Duplicate()
$found = $rng.Find
$found.Text = "<占位符或定位文本>"
$found.Forward = $true
$found.Wrap = $false
if ($found.Execute()) {
  $rng.Text = "<linear LaTeX>"
  $mathRange = $doc.OMaths.Add($rng)   # 返回 Range，不是集合
  $omath = $mathRange.OMaths.Item(1)   # 经 Range.OMaths.Item(1) 取 OMath
  $omath.BuildUp()                     # 转专业二维公式（对复杂指令可能不净）
  $omath.Type = 0                      # wdMathInline；1 为 wdMathDisplay
}
```

注意：

- 必须用可写模式打开文档：`Documents.Open(path, $false, $false)`（第三参若为
  `$true` 是只读，后续 `Save()` 会失败）。
- `OMaths.Add(...)` 返回 `Range`；对它调 `.Item(1)`/`.Count` 会报
  "does not contain a method named 'Item'"，这是已知的 PowerShell COM 绑定
  现象，不是写得不对。
- 脚本应包 `try/finally` 确保 Word 退出，否则失败会残留后台 WINWORD 进程
  并锁住文档。
- 用执行 `Find` 的那个 `Range` 对象本身做替换，而不是 `$found.Parent.Range`。

## 后续可选方向（未实施）

1. 把 LaTeX 里 Word 不支持/转换不完整的指令（`\text`、`\langle` 等）在交给
   Word 前做**预处理映射**，再调 `BuildUp`。
2. 或在 OOXML 层面直接构造 OMML（需要自有 LaTeX 解析器），完全不依赖 Word 的
   非线性公式导入器。工作量更大、风险更高。
3. 若只需要「公式显示成形、接受少量残留」，可把 BuildUp 失败的反馈提升为非
   静默，让调用端能看出哪些公式没转净，而不是悄悄留下反斜杠。

## 相关文件

- `src/services/markdown.ts`：公式识别（`\(`、`$`、`$$`）。
- `src/services/formula.ts`：公式候选扫描（`word_formula_scan` 用）。
- `src/services/wordcom.ts`：Word COM 脚本构造 + 执行（`word_formula_convert`
  用，含 TOC 刷新）。生成专用脚本已删。
- `src/coordinator.ts`：`generateFromMarkdown`（不再做自动转换）。
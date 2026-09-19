English | [中文](README.zh.md)

# @deepseek-ai/dsh-word-editor

A personal Word (`.docx`) quick-editing and generation plugin. It exposes the
model tools `word_open`, `word_read`, `word_find`, `word_str_replace`,
`word_add_to`, `word_delete`, `word_formula_scan`, `word_formula_convert`,
`word_generate`, `word_superscript`, and `word_save`, so the caller agent opens
a source document (or a template copy), edits it through in-session target
ids: pure-OOXML structure reading and editing with a style whitelist,
table-row cloning, and atomic save, plus native Word OMath conversion via
Windows Word COM automation (with a formula-cleanup subagent for ambiguous
LaTeX). A one-shot `word_generate` converts a Markdown manuscript and a
template into a fresh document whose body matches the template's styles and
page layout, and `word_superscript` turns bracket citations in an existing
document into genuine superscript runs. It never overwrites the source; output
is a new file next to it, returned as a clickable local link with a change (or
structure) summary. Tools are `word_`-prefixed so they never collide with the
built-in filesystem `read` / search tools on the calling agent.

## Plugin form

Function plugin registering the eleven `word_`-prefixed tools, composed
through `cordis.yml`. Requires the `tools`, `subprocess`, and `subagents`
services. The dsh web base profile provides all three; the acceptance overlay
adds the thin-profile dependencies by direct file URL.

## Tools

### word_open

`word_open({ source_path? , from_template? })` opens a source `.docx` into a
working copy, or creates a fresh working copy from the configured template
(`from_template: true`). Everything after it is a copy — `word_save` writes a
new file, never the source.

### word_read

`word_read()` returns the whole working document's block structure —
paragraphs, headings, tables (rows and cells), content controls, OMath, and
section properties — in order, each with its target id, kind, and style. Body
paragraphs show only their first sentence preview plus structure flags; every
other element and every table-cell paragraph shows full text. Call it first to
collect target ids.

### word_find

`word_find({ id? , content? })` reads a paragraph in full by its `target_id`,
or finds every paragraph whose full text contains a substring. With both, only
the named paragraph is checked and must contain the substring. No argument is
a parameter error; a non-paragraph id is a type error. Matches reuse the
`word_read()` target ids.

### word_str_replace

`word_str_replace({ target_id, old_content, content, style = 'keep' })`
replaces an exact substring (or whole text) of a paragraph and audits
before/after and styles. `old_content` must match exactly or the edit is
refused. Multi-line `content` splits into separate paragraphs; plain
replacement refuses to cross a formula, drawing, or field — use the formula
tools instead.

### word_add_to

`word_add_to({ target_id, content, style, position, is_new_para })` adds
content at a paragraph, cell, table row, or the whole document. A new
paragraph applies the logical style; inline append keeps the paragraph. Adding
a table row clones the target row (preserving widths, borders, shading,
merges, and height) and fills each cell with the provided per-column text.

### word_delete

`word_delete({ target_id, content?, style? })` removes an exact substring, or
a whole paragraph / table row / table when `content` is omitted. `style` acts
as a pre-removal assertion; there is no implicit delete-all.

### word_formula_scan

`word_formula_scan({ target_id? })` scans the document (or one target) for
LaTeX that is not yet a Word OMath, returning candidates with source spans,
display kind, and confidence. Existing OMath is protected and never re-scanned.
Ambiguous candidates are handed to a cleanup subagent that normalizes them
(strips Markdown fences, zero-width chars, and split-run noise) through the
`submit_formula_candidates` structured result.

### word_formula_convert

`word_formula_convert({ candidate_ids, minimum_confidence? })` converts
confirmed candidates to native Word OMath through Windows Word COM
(`OMaths.Add` + `BuildUp`) on this host. Candidates below the confidence floor
are skipped with a warning. When Word is unavailable it returns a
runtime-environment error and stores nothing — LaTeX is never kept as a fake
conversion.

### word_generate

`word_generate({ markdown_path, template_path? })` generates a fresh `.docx`
from a Markdown manuscript and a template in one pass. The plugin parses the
Markdown itself (level 1–3 headings, blank-line-separated body paragraphs,
ordered/unordered lists, pipe tables, images, references, and inline math
`\(...\)` / `$...$` plus block math `$$...$$`) and reshapes a copy of the
template into a body that uses the template's concrete styles and page layout
(keeping its styles, headers, footers, and section properties). Cover and TOC
are intentionally outside its scope — the caller owns those. Every recognized
formula is written as bare LaTeX text (the `\(...\)` / `$...$` / `$$...$$`
delimiters are stripped) so the caller can convert it to native OMath with
`word_formula_scan` + `word_formula_convert` afterward. Returns the output
document's clickable link plus a structured outline (headings,
paragraph/table/reference/image counts) so the model can confirm the structure
without reading the whole document.

### word_superscript

`word_superscript({ source_path })` opens an existing `.docx` and turns every
bracket citation like `[1]`, `[1-4]`, `[1,2,5]`, or `[1、2]` in its body and
table cells into a genuine superscript run, preserving all other inline
formatting (bold, italic, font size). It saves a new
`-superscripted-<timestamp>.docx` next to the source (never overwriting it)
and returns the output link plus the number of citations converted.
Reference-list paragraphs (styled `参考文献`) are left untouched so their
leading `[1]` markers stay as list numbering, not superscripts.

### word_save

`word_save()` atomically writes the working copy to
`{base}-edited-{timestamp}.docx` next to the source and returns its real path,
a clickable local link, the change summary, and a warning when Word could not
refresh the TOC field. The source is checked against its open-time bytes
first; a changed source refuses the save.

## Configuration

```yaml
plugins:
  word-editor:
    template: 'D:\Users\Lenovo\Desktop\文件\开题报告-初稿.docx'
    proposalTableTemplate: 'D:\Users\Lenovo\Desktop\文件\开题报告-初稿-专属表格样式.docx'
    allowlist: ['reference', 'table_content']
    subagentProvider: 'spawn'
    updateToc: true
```

- `template`: default template for manuscript generation.
- `proposalTableTemplate`: the first-adapted template with the dedicated table
  style.
- `allowlist`: extra logical style names a write tool may set explicitly, on
  top of the fixed body/heading/toc/reference/table-content set.
- `subagentProvider`: the `ctx.subagents` provider the formula-cleanup
  subagent runs on (default `spawn`).
- `updateToc`: refresh the document's table-of-contents fields through Word on
  save (default `true`).

## Prerequisites

- Microsoft Word (Windows) with a recent PowerShell, for `formula_convert` and
  the optional TOC refresh. Without Word, editing tools and `formula_scan`
  still work; `formula_convert` returns an environment error.
- A source `.docx`, or a configured template, using the whitelisted style
  names. The first-adapted template is the proposal (开题报告) template whose
  styles are `Normal (Web)` for body, `heading 2/3/4` for the three heading
  levels, `toc 1/2/3`, `表格内容` for table cells, `参考文献` for references,
  and the exclusive `开题报告表格` table style — resolved dynamically by name,
  never by a hard-coded style id.

## Model Experience

### Plugin interaction

#### What the model sees

The model sees the eleven `word_`-prefixed tool schemas. The tool descriptions
tell it to `word_read()` first to obtain target ids, use `word_find()` for a
specific paragraph,
edit through the write tools (which return audit records), use `word_generate`
to produce a fresh document from Markdown, use `word_superscript` to convert
bracket citations to superscript runs, scan and convert formulas with the
formula tools, and that the output is a new clickable local
document link rather than pasted content.

#### Token effect

The main cost is the `word_read()` structure dump (bounded by a hard element
cap) and full paragraph text from `word_find()`. Write tools return compact
audit
records.

#### KV Cache effect

No fixed prefix: the plugin appends no per-request text to the system prompt.

## Known Limitations and Deferred Work

- `formula_convert` requires a Windows host with Microsoft Word installed; in
  other environments it returns a runtime-environment error and never stores
  LaTeX as a converted formula.
- `word_generate` parses inline `\(...\)` / `$...$` and block `$$...$$`
  (including multi-line bodies) and writes them as bare LaTeX text (delimiters
  stripped); it does not build OMath — converting formulas is left to
  `word_formula_convert` (or a caller-managed flow). Cover and TOC are outside
  its scope — the caller owns those.
- `word_superscript` matches bracket digit-list citations only; a paragraph
  containing math, a drawing, a field, or a line break is left untouched.
- Multi-paragraph replacement splits on newline into separate paragraphs; a
  single paragraph cannot carry an embedded line break.
- Table-row cloning preserves the target row's formatting and structure, but a
  cell spanning a merged range keeps that merge rather than splitting it.
- Batch deletes must list each `target_id`; there is no implicit delete-all.
- TOC-field refresh relies on Word at save time; without Word the TOC field is
  left for Word to update on open.
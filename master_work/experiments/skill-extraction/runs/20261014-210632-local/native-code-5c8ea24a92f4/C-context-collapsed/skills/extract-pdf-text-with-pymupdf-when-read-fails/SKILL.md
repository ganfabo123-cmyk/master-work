---
name: extract-pdf-text-with-pymupdf-when-read-fails
description: Use when the built-in Read tool fails on a PDF (reporting it as password-protected) even though the file opens fine in a viewer, typically because the PDF carries a permissions/print lock rather than an open password. Helps the agent convert the PDF to plain text with a Python library (pymupdf/pdfminer) and then mine the text for the sections relevant to the task. Do not use for scanned/image-only PDFs that need OCR, for genuinely password-protected files, or when Read can open the PDF directly.
---
# Extract PDF Text with Python When the Read Tool Refuses the PDF

## Goal
Obtain the full text of a PDF that the built-in Read tool refuses to open (it reports the file as password-protected even though the user says it is not), by converting it to a plain-text file with a Python PDF library, so the content can be read and mined for task-relevant sections.

## Scope
### In scope
- PDFs with permissions/owner locks (restricted printing/copying) that make the Read tool report a password error across all page-range attempts (`pages: "1-20"`, `pages: "1-5"`).
- Checking which Python PDF libraries are available (`pypdf`, `pdfminer`, `pymupdf`) and converting with the one present — pymupdf preferred when available.
- Reading the resulting `.txt` in chunks and locating relevant sections by scanning for keyword lines, instead of reading a 243-page document linearly.
- Cleaning up the temporary `.txt` after the needed content has been extracted.

### Out of scope
- Scanned/image-only PDFs that yield no text layer (need OCR).
- PDFs with a real user password that even pymupdf cannot open.
- Parsing PDF structure (tables, images, fonts) — plain text extraction only.

## Inputs
- **PDF file path** — type: file path — source: user/project directory — required: yes — constraints: file must exist and have a text layer — default: 无.
- **Read tool failure evidence** — type: tool error — source: Read attempts on the PDF — required: no — constraints: `is_error: true` on at least two different page ranges confirms it is not a range issue — default: 无.
- **Python interpreter** — type: runtime — source: preinstalled — required: yes — constraints: observed available with `pymupdf` and `pdfminer` installed; `pypdf` availability unconfirmed in the trace — default: 无.
- **Output text path** — type: file path — source: agent choice — required: yes — constraints: place next to the PDF for simple cleanup (observed: `<project>/apple-style-guide.txt`) — default: `<pdf-name>.txt` beside the PDF.
- **Topic keywords** — type: string list — source: task at hand — required: no — constraints: used to locate relevant sections in the extracted text — default: 无.

## Outputs
### Artifacts
- A UTF-8 plain-text dump of the PDF (e.g. `apple-style-guide.txt`) containing all pages' text in order.
- A digest of the sections relevant to the task (what was found, where), reported back to the user.
- The temp `.txt` deleted after use (observed: `rm d:/IceBerg/apple-style-guide.txt`).

### Success criteria
- The conversion command exits 0; the produced `.txt` can be read with the Read tool in chunks; page count / total chars are known; task-relevant passages are located and summarized.

### Failure criteria
- No Python PDF library is importable, the extracted text is empty (scanned PDF), or the library raises an encryption error — report the blocker instead of pretending the content was read.

## Preconditions
- The Read tool has already failed on the PDF for at least two page ranges (e.g. `1-20` and `1-5`), so the failure is with the file, not the request.
- The user has confirmed the PDF is not protected by an open password (in the trace the user insisted `its not password protect`), which makes a permissions lock the likely cause.
- Python 3 is available on PATH as `python`, and network/pip access exists if a library must be installed (the trace found `pdfminer` and `pymupdf` already importable).
- Sufficient disk space next to the PDF for the text dump.

## Procedure
### Step 1: Confirm the Read failure is systematic
Actions: attempt Read on the PDF with at least two different page ranges (observed: `pages: "1-20"` twice, then `pages: "1-5"`); all return `is_error: true`. Ask the user to confirm there is no open password before assuming a permissions lock.
Inputs: PDF path. Outputs: confirmation that the failure is file-level. Cautions: do not conclude "password-protected" as fact — report it as the tool's claim (in the trace the user corrected the agent: the file was not password protected). Next: Step 2.

### Step 2: Check which Python PDF libraries are available
Actions: run import probes in one command, e.g. `python -c "import pypdf; print('pypdf ok')"`; same for `pdfminer` and `pymupdf`.
Inputs: python on PATH. Outputs: list of usable libraries. Cautions: prefer `pymupdf` when present — it handles permissions-locked PDFs well and is fast. Next: Step 3.

### Step 3: Convert the PDF to a text file
Actions: run a short script: open the PDF with pymupdf, concatenate `page.get_text()` for every page, write the result to a UTF-8 `.txt` next to the PDF, and print page count + total chars. Add `sys.stdout.reconfigure(encoding='utf-8')` in later commands if the console garbles non-ASCII output.
Inputs: PDF path, output path. Outputs: `.txt` file + page/char counts. Cautions: use raw strings for Windows paths; the conversion succeeding does not prove the text is meaningful — check it in Step 4. Next: Step 4.

### Step 4: Read and mine the text dump
Actions: Read the `.txt` in chunks (e.g. first 100 lines to identify the document shape); for a long A–Z style document, scan line-by-line with a small Python one-liner for the keyword lines that mark relevant sections, then print those sections by line ranges.
Inputs: `.txt` + topic keywords. Outputs: located passages. Cautions: for a 243-page reference, most content is irrelevant product terminology — filter to sections that change the actual work (UI writing rules, typography, capitalization) rather than summarizing everything. Next: Step 5.

### Step 5: Report findings and clean up
Actions: present the actionable findings (e.g. button labels use title-style caps; `typeface` → `font`; curly quotes; `…` ellipsis), noting which ones go beyond any existing project guide; then delete the temp `.txt` so the directory stays clean.
Inputs: findings. Outputs: report + clean directory. Cautions: keep the source PDF — only the generated dump is disposable. Next: done.

## Decision Rules
### When Read fails on every page range but the user says the file is not password-protected
Treat it as a permissions/print lock that blocks the tool: switch to Python text extraction rather than asking the user to re-export or send a different file.

### When the extraction library choice is open
Use `pymupdf` if importable; fall back to `pdfminer`; only reach for `pypdf` if the others are absent (its availability was not confirmed in the trace).

### When console output shows mojibake for non-ASCII text
Re-run the Python snippets with `sys.stdout.reconfigure(encoding='utf-8')`; do not switch libraries for an encoding artifact.

### When the extracted text is empty or near-empty
The PDF is likely scanned images — stop and report that OCR is required; further text extraction attempts will not help.

### When the document is large and mostly irrelevant
Locate relevant sections by keyword-scanning line numbers and printing only those ranges; report only findings that change the work at hand.

## Invariants
- Never claim the PDF's content was read on the strength of the Read tool's failure message; content claims require the successful `.txt` dump.
- Do not tell the user their file is password-protected as established fact when only the tool reported so — surface it as a tool limitation until proven.
- Delete only the temp `.txt` you created; never delete the source PDF.
- Do not paste huge extracted text into the conversation; summarize with locations (line ranges/section names).
- Report the extraction honestly: if the command failed or text was empty, say so instead of describing what the document "probably" contains.

## Common Failures
### Failure: Agent insists the PDF is password-protected
Symptoms: after Read fails, the agent tells the user to re-export or unlock the file; the user pushes back (`its not password protect`). Cause: conflating the tool's error message with the file's actual state. Recovery: reframe as a tool-level limitation (permissions lock), confirm with the user, and proceed to Python extraction.

### Failure: Repeating Read with smaller page ranges
Symptoms: multiple Read attempts (`1-20`, then `1-5`) all return the same error. Cause: the failure is file-level, not range-level. Recovery: stop after two attempts; move to extraction.

### Failure: Garbled non-ASCII output from Python one-liners
Symptoms: mojibake or exceptions printing extracted characters on a Windows console. Cause: console encoding. Recovery: add `sys.stdout.reconfigure(encoding='utf-8')` and read the written `.txt` file (UTF-8) rather than relying on console echo.

### Failure: No usable text after conversion
Symptoms: `.txt` is empty or whitespace-only. Cause: scanned PDF without a text layer. Recovery: report that OCR is needed; do not fabricate content.

## Verification
1. The conversion command exits 0 (`"is_error": false` on the Bash result) and prints page count and total character count — in the trace the dump reported 243 pages.
2. The Read tool can open the produced `.txt` and return content (the first chunk identified the document as an A–Z style dictionary).
3. Follow-up Python section-extraction commands on the `.txt` all exit 0 and return the targeted passages (observed: repeated keyword/line-range extractions without errors).
4. The findings taken from the dump are concrete and specific (e.g. sentence-style vs title-style capitalization rules, `typeface` → `font`, curly-quote and ellipsis rules) — proof the text was genuinely read, not paraphrased from expectations.
5. The temp `.txt` is deleted afterwards (the `rm` of the generated file exits 0) while the source PDF remains.

## Examples
### Example 1: Read a permissions-locked style-guide PDF
Input: `d:\IceBerg\apple-style-guide.pdf`; Read with `pages: "1-20"` and `pages: "1-5"` both return `is_error: true`; user states the file is not password protected.
Procedure: probe libraries (`python -c "import pypdf ... pdfminer ... pymupdf"`), then run the pymupdf dump script (open doc, `page.get_text()` per page, write UTF-8 `.txt` beside the PDF, print counts); Read the `.txt` in chunks; scan for keyword lines (`capitalization`, `em dash`, `quotation marks`, `ellipsis`, `button`, `links`) and print those sections by line range; report actionable rules; `rm` the `.txt`.
Expected result: a 243-page text dump; relevant typography/UI-writing rules extracted (title-style button labels, curly quotes, `…` ellipsis, `font` not `typeface`); directory left without the temp file. Parameterized values: PDF name `apple-style-guide.pdf`, output `apple-style-guide.txt`, library `pymupdf`.

## Evidence
All quotes from `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-07` (tool-call arguments, `is_error` flags, and assistant/user texts are visible in this slice; tool-result bodies are collapsed).

- **problem** — source_index 908 (tool_call:Read, `pages: "1-20"`) → source_index 909 (tool_result) `"is_error": true`; repeated at source_index 917/918 (`pages: "1-20"`) and 919/920 (`pages: "1-5"`) with `"is_error": true`; assistant_text at source_index 910: `The PDF is password-protected so I can't read it directly.`; user correction at source_index 913: `its not password protect @apple-style-guide.pdf`; assistant_text at 921: `The tool is consistently reporting it as password-protected regardless of the page range — this is a tool-level limitation, not necessarily a real password.`; user at 924: `you can use python to convert it to txt`. supports: the failure is file/tool-level and a permissions lock, not a real password; the extraction approach came from the user's steer and was then executed.
- **action** — source_index 928 (tool_call:Bash): import probes `python -c "import pypdf; print('pypdf ok')"` / `pdfminer` / `pymupdf`, result 929 `"is_error": false`; source_index 931 (tool_call:Bash) conversion script: `import pymupdf`, `doc = pymupdf.open(...)`, `text += page.get_text()`, writing `apple-style-guide.txt`, result 932 `"is_error": false`. supports: the exact conversion recipe and that it ran without error.
- **verification** — source_index 932 (tool_result) `"is_error": false`; assistant_text at 936: `243 pages — it's the full A–Z style dictionary.` (the page count came from the successful dump); subsequent section-extraction Bash results at source_index 947, 949, 955, 957, 959, 964 all show `"is_error": false`, and the resulting findings at 965/972 are concrete rules (`Button labels should use title-style capitalization`, `typeface` → `font`, curly quotes, `…` ellipsis) — proof the text was genuinely read; cleanup at source_index 1014 (`rm d:/IceBerg/apple-style-guide.txt`) with result 1015 `"is_error": false` shows the temp dump was removed while the PDF remained. supports: end-to-end success of extract → mine → clean up, verified through exit status and the specificity of the extracted content (result bodies are collapsed in this slice, so the exit-status flags and the derived content are the available evidence).

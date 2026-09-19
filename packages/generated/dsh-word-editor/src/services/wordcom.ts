/**
 * Windows Word COM bridge of @deepseek-ai/dsh-word-editor. Formula conversion
 * and TOC refresh require Microsoft Word; this module builds the PowerShell
 * script (pure and unit-testable) and runs it through `ctx.subprocess.spawn`
 * against a real `powershell.exe`. Word-unavailable or COM failures surface as
 * a loud runtime-environment error so LaTeX is never stored as converted.
 * @module @deepseek-ai/dsh-word-editor/services/wordcom
 */

import type { Context } from '@deepseek-ai/cordis'
import type { SubprocessHandle } from '@deepseek-ai/dsh-subprocess'

/** A single formula conversion request passed to the Word script. */
export interface OMathConversion {
  /** Current paragraph text the script uses to locate the edit range. */
  paragraphText: string
  /** The exact substring within paragraphText to replace with an OMath. */
  linearMath: string
  /** `inline` keeps the math inside the paragraph; `block` makes a display OMath paragraph. */
  display: 'inline' | 'block'
}

/**
 * Build the PowerShell script that: opens a .docx in background Word, updates
 * every TOC field, converts each linear-math span into a native OMath
 * (`OMaths.Add` + `BuildUp`), saves, and closes — all with `$ErrorActionPreference
 * = 'Stop'`. Pure string construction so tests can assert the wiring without
 * Word.
 * @param docPath - absolute path of the working .docx.
 * @param conversions - the linear-math spans to build up.
 * @param updateToc - whether to refresh the document's tables of contents.
 * @returns the PowerShell source.
 */
export function buildWordScript(docPath: string, conversions: OMathConversion[], updateToc: boolean): string {
  const log = (msg: string): string => `Write-Output '${msg.replace(/'/g, "''")}'`
  const inner: string[] = [
    log('opening word'),
    '$word = New-Object -ComObject Word.Application',
    '$word.Visible = $false',
    'try { $word.DisplayAlerts = 0 } catch {}',
    `$doc = $word.Documents.Open('${docPath.replace(/'/g, "''")}', $false, $false)`,
  ]
  if (updateToc) {
    inner.push(log('updating_toc'), 'foreach ($toc in $doc.TablesOfContents) { $toc.Update() }')
  }
  conversions.forEach((c, i) => {
    const type = c.display === 'block' ? 1 : 0
    inner.push(
      log(`converting_${i}`),
      '$range = $doc.Content.Duplicate()',
      '$found = $range.Find',
      `$found.Text = ${json(c.paragraphText)}`,
      '$found.Forward = $true',
      '$found.Wrap = $false',
      'if ($found.Execute()) {',
      `  $range.Text = ${json(c.linearMath)}`,
      '  $mathRange = $doc.OMaths.Add($range)',
      '  $omath = $mathRange.OMaths.Item(1)',
      '  try { $omath.BuildUp() } catch {}',
      `  $omath.Type = ${type}`,
      `  Write-Output 'converted_ok_${i}'`,
      '} else {',
      `  throw 'formula target not found: ${c.paragraphText.slice(0, 40).replace(/'/g, "''")}'`,
      '}',
    )
  })
  inner.push(
    log('saving'),
    '$doc.Save()',
    log('done'),
  )
  return [
    '$ErrorActionPreference = \'Stop\'',
    '$word = $null',
    '$doc = $null',
    'try {',
    ...inner.map(l => `  ${l}`),
    '} catch {',
    '  Write-Output "error: $($_.Exception.Message)"',
    '  throw',
    '} finally {',
    '  if ($doc) { try { $doc.Close(0) } catch {} }',
    '  if ($word) { $word.Quit() }',
    '  if ($word) { [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null }',
    '}',
  ].join('\n')
}

/** JSON-quote a PowerShell double-quoted string segment. */
function json(s: string): string {
  return `"${s.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\$/g, '`$')}"`
}

/** The collected outcome of a Word bridge run. */
export interface WordRunResult {
  exitCode: number | null
  stdout: string
  stderr: string
}

/**
 * Run a PowerShell script with `powershell.exe -NoProfile -NonInteractive`.
 * @param ctx - the plugin context whose `subprocess` service spawns the process.
 * @param script - the PowerShell source to execute.
 * @param signal - abort signal for the spawned process.
 * @returns the run results.
 * @throws a loud runtime-environment error when powershell or Word is unusable.
 */
export async function runPowerShell(ctx: Context, script: string, signal: AbortSignal): Promise<WordRunResult> {
  let handle: SubprocessHandle
  try {
    handle = ctx.subprocess.spawn({
      argv: ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
      cwd: process.cwd(),
      stdio: {
        stdin: 'ignore',
        stdout: { maxBytes: 64 * 1024 },
        stderr: { maxBytes: 16 * 1024 },
      },
      graceMs: 20_000,
      signal,
    })
  } catch (error: unknown) {
    throw new Error(
      `formula_convert cannot start Word automation (${error instanceof Error ? error.message : String(error)}); `
      + 'Microsoft Word and PowerShell are required on this Windows host',
    )
  }
  const outcome = await handle.done
  const stdout = handle.collected.stdout?.readFrom(0).text ?? ''
  const stderr = handle.collected.stderr?.readFrom(0).text ?? ''
  if (outcome.exitCode !== 0) {
    const detail = `${stderr.trim()}\n${stdout.trim()}`.slice(-1500)
    throw new Error(`formula_convert: Word automation failed (exit ${String(outcome.exitCode)}):\n${detail || 'unknown error'}`)
  }
  return { exitCode: outcome.exitCode, stdout, stderr }
}

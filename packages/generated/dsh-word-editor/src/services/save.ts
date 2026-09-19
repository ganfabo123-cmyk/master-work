/**
 * Atomic save service of @deepseek-ai/dsh-word-editor: serialize the DOCX
 * document back into its entry set, write a temporary file, and rename it into
 * place so a failure never leaves a plausible but corrupted result file. The
 * TOC-field refresh is delegated to Word (when available) because recomputing
 * a TOC requires Word's layout engine.
 * @module @deepseek-ai/dsh-word-editor/services/save
 */

import { readFileSync, renameSync, unlinkSync, writeFileSync } from 'node:fs'
import { dirname, basename, join } from 'node:path'
import { randomBytes } from 'node:crypto'
import { XMLSerializer } from '@xmldom/xmldom'
import { strToU8, zipSync } from 'fflate'
import type { DocxDocument } from './oooxml.js'

/**
 * Serialize the edited DOCX container back to bytes.
 * @param doc - the edited document container.
 * @returns the serialized `.docx` bytes.
 */
export function serializeDocx(doc: DocxDocument): Uint8Array {
  const entries: Record<string, Uint8Array> = {}
  for (const [name, bytes] of doc.entries) {
    if (name === 'word/document.xml') {
      const xml = new XMLSerializer().serializeToString(doc.document)
      entries[name] = strToU8(xml)
    } else {
      entries[name] = bytes
    }
  }
  const out = zipSync(entries, { level: 6 })
  return new Uint8Array(out)
}

/**
 * Atomically persist a new `.docx` next to the source file. Writes to a
 * random-named temp path in the same directory, then renames into the final
 * destination; a failure removes the temp file and leaves no partial result.
 * @param doc - the edited document container.
 * @param sourcePath - the absolute source path (the output lives in its directory).
 * @param outputPrefix - the output file base name prefix.
 * @returns the final absolute output path.
 */
export function saveAtomically(doc: DocxDocument, sourcePath: string, outputPrefix: string): string {
  const bytes = serializeDocx(doc)
  const dir = dirname(sourcePath)
  const stamp = timestamp()
  const finalPath = join(dir, `${outputPrefix}-edited-${stamp}.docx`)
  const tempPath = join(dir, `.${outputPrefix}-edited-${stamp}-${randomBytes(4).toString('hex')}.tmp`)
  try {
    writeFileSync(tempPath, Buffer.from(bytes))
    renameSync(tempPath, finalPath)
  } catch (error: unknown) {
    try {
      unlinkSync(tempPath)
    } catch {
      // the temp may already be gone; a rename failure is the real error
    }
    throw error
  }
  return finalPath
}

/** A compact local timestamp for the output file name, e.g. 20260903-093000. */
export function timestamp(d = new Date()): string {
  const p = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
}

/**
 * Atomically persist a generated `.docx` with a `-generated-` name marker.
 * Writes to a random-named temp path in the target directory, then renames into
 * the final destination; a failure removes the temp file and leaves no partial
 * result.
 * @param doc - the generated document container.
 * @param basePath - the markdown source path (its directory and base name define the output).
 * @returns the final absolute output path.
 */
export function saveGenerated(doc: DocxDocument, basePath: string): string {
  const prefix = outputPrefixFrom(basePath)
  const dir = dirname(basePath)
  const stamp = timestamp()
  const finalPath = join(dir, `${prefix}-generated-${stamp}.docx`)
  const tempPath = join(dir, `.${prefix}-generated-${stamp}-${randomBytes(4).toString('hex')}.tmp`)
  const bytes = serializeDocx(doc)
  try {
    writeFileSync(tempPath, Buffer.from(bytes))
    renameSync(tempPath, finalPath)
  } catch (error: unknown) {
    try {
      unlinkSync(tempPath)
    } catch {
      // the temp may already be gone; a rename failure is the real error
    }
    throw error
  }
  return finalPath
}

/**
 * Atomically persist a superscript-converted `.docx` with a `-superscripted-`
 * name marker next to the source. Writes to a random-named temp path in the
 * source directory, then renames into the final destination; a failure removes
 * the temp file and leaves no partial result.
 * @param doc - the converted document container.
 * @param sourcePath - the source `.docx` path (defines the output directory and base name).
 * @returns the final absolute output path.
 */
export function saveSuperscripted(doc: DocxDocument, sourcePath: string): string {
  const prefix = outputPrefixFrom(sourcePath)
  const dir = dirname(sourcePath)
  const stamp = timestamp()
  const finalPath = join(dir, `${prefix}-superscripted-${stamp}.docx`)
  const tempPath = join(dir, `.${prefix}-superscripted-${stamp}-${randomBytes(4).toString('hex')}.tmp`)
  const bytes = serializeDocx(doc)
  try {
    writeFileSync(tempPath, Buffer.from(bytes))
    renameSync(tempPath, finalPath)
  } catch (error: unknown) {
    try {
      unlinkSync(tempPath)
    } catch {
      // the temp may already be gone; a rename failure is the real error
    }
    throw error
  }
  return finalPath
}

/** Baseline output file-name prefix taken from a source path. */
export function outputPrefixFrom(path: string): string {
  return basename(path, '.docx')
}

/**
 * Check that the source file still matches the bytes the session was opened
 * from; a mismatch means another process changed the document under us.
 * @param path - the source path.
 * @param original - the bytes the session was opened from.
 * @returns true when unchanged.
 */
export function unchangedSince(path: string, original: Uint8Array): boolean {
  try {
    return Buffer.from(readFileSync(path)).equals(Buffer.from(original))
  } catch {
    return false
  }
}

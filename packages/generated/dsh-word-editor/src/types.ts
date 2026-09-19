/**
 * Shared value types of @deepseek-ai/dsh-word-editor. Types only — no runtime
 * code lives here. Runtime behavior lives in the services and tools modules.
 * @module @deepseek-ai/dsh-word-editor/types
 */

/**
 * A logical style name exposed to the model. The templates a plugin handles
 * map each logical style to a concrete paragraph/table style (resolved
 * dynamically by name at open time), never a numeric styleId.
 */
export type LogicalStyle =
  | 'body'
  | 'heading_1'
  | 'heading_2'
  | 'heading_3'
  | 'toc_1'
  | 'toc_2'
  | 'toc_3'
  | 'table_content'
  | 'reference'
  | 'keep'

/**
 * The kind of a block element as surfaced to the model by {@link read} /
 * {@link find}. Paragraphs are classified by logical style so that body,
 * headings, TOC, references, and table content are never confused with one
 * another.
 */
export type ElementKind =
  | 'body'
  | 'heading'
  | 'toc'
  | 'reference'
  | 'table'
  | 'table_content'
  | 'sdt'
  | 'section_properties'
  | 'other'

/** Presence flags collected for one element in a {@link read} preview. */
export interface ElementFlags {
  /** True when the element contains at least one OMath formula. */
  hasMath: boolean
  /** True when the element contains an image, drawing, or picture. */
  hasPicture: boolean
  /** True when the element contains a hyperlink. */
  hasHyperlink: boolean
  /** True when the element contains a field (for example a TOC or PAGE field). */
  hasField: boolean
}

/**
 * One block element shown by {@link read}: the session-generated target id,
 * OOXML element type, kind, logical style, a preview or full content, its
 * parent id and children. `content` holds the full readable text for
 * non-body elements and for table cells; `content_preview` holds only the
 * first sentence for body paragraphs.
 */
export interface ReadElement {
  target_id: string
  ooxml_type: string
  kind: ElementKind
  style: LogicalStyle | string
  content?: string
  content_preview?: string
  content_truncated?: boolean
  contains?: string[]
  native_id?: string
  parent_id?: string
  children?: ReadElement[]
}

/** The structured document overview returned by {@link read}. */
export interface ReadResult {
  document_path: string
  /** True when a hard output cap cut the returned structure short. */
  truncated: boolean
  elements: ReadElement[]
}

/** One paragraph found by {@link find}. */
export interface FindParagraph {
  target_id: string
  content: string
  style: LogicalStyle | string
  parent_id?: string
  parent_kind?: ElementKind
  children?: Array<{ target_id: string; type: string; position: number; content?: string }>
  prev?: { target_id: string; content_preview: string }
  next?: { target_id: string; content_preview: string }
}

/** Audit record returned by every write tool. */
export interface EditAudit {
  location: string
  before: string
  after: string
  before_style: LogicalStyle | string
  after_style: LogicalStyle | string
  affects_table: boolean
  affects_formula: boolean
  warning?: string
}

/** A detected, not-yet-converted LaTeX candidate from {@link formula_scan}. */
export interface FormulaCandidate {
  /** Session-generated id for this candidate (returned to formula_convert). */
  candidate_id: string
  /** target_id of the paragraph or cell holding the candidate. */
  target_id: string
  source_start: number
  source_end: number
  source_text: string
  /** Present when a cleanup subagent already normalized the source. */
  normalized_latex?: string
  display: 'inline' | 'block'
  confidence: number
  reason: string
}

/** The cleanup subagent's structured verdict (see {@link formula_cleanup}). */
export interface FormulaCleanupVerdict {
  candidates: FormulaCandidate[]
}

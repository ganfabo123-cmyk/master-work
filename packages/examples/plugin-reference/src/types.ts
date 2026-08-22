export interface ReferenceNote {
  id: string
  title: string
  content: string
  tags: string[]
  createdAt: string
}

export interface ReferenceNoteInput {
  title: string
  content: string
  tags: string[]
}

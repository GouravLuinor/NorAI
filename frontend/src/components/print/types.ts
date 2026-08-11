import type { Question } from '../../stores/useQuizStore'
import type { ConceptMapResponse } from '../../lib/conceptMapLayout'

/** A raw chapter payload as produced by the backend endpoints: structured JSON
 * ({ title, sections }), a JSON-encoded string, plain markdown, or a guide
 * chapter object ({ markdown }). parseChapterContent() normalizes all of them. */
export type PrintChapterPayload =
  | string
  | { title?: string; markdown?: string; sections?: unknown[] }

export interface PrintDataNotes {
  type: 'notes' | 'revision'
  chapters: PrintChapterPayload[]
}
export interface PrintDataGuide {
  type: 'guide'
  title: string
  chapters: PrintChapterPayload[]
}
export interface PrintDataConcepts {
  type: 'concepts'
  maps: { ch: number; data: ConceptMapResponse }[]
}
export interface PrintDataAssessment {
  type: 'assessment'
  assessmentChapters: { ch: number; questions: Question[] }[]
}
export type PrintData = PrintDataNotes | PrintDataGuide | PrintDataConcepts | PrintDataAssessment

export type PrintType = 'notes' | 'revision' | 'guide' | 'concepts' | 'assessment'

declare global {
  interface Window {
    __PRINT_DATA__?: PrintData
  }
}

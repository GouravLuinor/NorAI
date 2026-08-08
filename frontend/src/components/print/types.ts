import type { Question } from '../../stores/useQuizStore'
import type { ConceptMapResponse } from '../../lib/conceptMapLayout'

export interface PrintDataNotes {
  type: 'notes' | 'revision'
  chapters: any[]
}
export interface PrintDataGuide {
  type: 'guide'
  title: string
  chapters: any[]
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

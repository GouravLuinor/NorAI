import type { Question } from '../../stores/useQuizStore'

export interface PrintDataNotes {
  type: 'notes' | 'revision'
  chapters: any[]
}
export interface PrintDataAssessment {
  type: 'assessment'
  assessmentChapters: { ch: number; questions: Question[] }[]
}
export type PrintData = PrintDataNotes | PrintDataAssessment

declare global {
  interface Window {
    __PRINT_DATA__?: PrintData
  }
}

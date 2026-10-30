import { create } from 'zustand'
import { apiGet } from '../lib/http'

export interface RecentLecture {
  lecture_id: string
  title: string
  category?: string
  chapter_count: number
  duration_seconds: number
  is_demo: boolean
  source_type: string
  last_chapter_id?: number
}

export interface DueFlashcardDeck {
  lecture_id: string
  lecture_title: string
  chapter_id: number
  due_count: number
  total_cards: number
  is_demo?: boolean
}

export interface QuizRetakeItem {
  attempt_id: string
  lecture_id: string
  lecture_title: string
  chapter_id: number | null
  difficulty: string
  score: number
  total: number
  missed_count: number
  finished_at: string
  is_demo?: boolean
}

export interface StudyStats {
  total_user_lectures: number
  total_quizzes_finished: number
  total_cards_rated: number
}

export interface StudyOverview {
  recent_lecture: RecentLecture | null
  flashcards_due: {
    total_due: number
    decks: DueFlashcardDeck[]
  }
  quiz_retakes: QuizRetakeItem[]
  stats: StudyStats
}

interface StudyState {
  overview: StudyOverview | null
  loading: boolean
  error: boolean
  loadOverview: () => Promise<void>
}

export const useStudyStore = create<StudyState>((set) => ({
  overview: null,
  loading: false,
  error: false,

  loadOverview: async () => {
    set({ loading: true, error: false })
    try {
      const data = await apiGet<StudyOverview>('/study/overview')
      set({ overview: data, loading: false })
    } catch {
      set({ error: true, loading: false })
    }
  },
}))

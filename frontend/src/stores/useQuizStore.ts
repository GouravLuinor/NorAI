import { create } from 'zustand'
import { getLectureId } from '../lib/threadStorage'
import { apiGet, apiPost, apiFetchRaw, API_BASE } from '../lib/http'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface QuestionFeedback {
  question_number: number
  remark: string
}

export interface Question {
  id: number
  type: 'MCQ' | 'True/False' | 'ShortAnswer' | 'Short Answer' | 'Conceptual' | 'Scenario' | 'Application' | 'Fill in the Blank' | string
  difficulty?: string
  question: string
  options?: string[]
  answer: string
  explanation: string
}

export interface QuizEvaluation {
  final_score: number | null
  total_questions: number
  per_question_feedback: QuestionFeedback[]
  overall_insights: string
}

export interface Flashcard {
  front: string
  back: string
  explanation?: string
}

/** SM-2 scheduling state for one card (P6.2), persisted server-side per (lecture, chapter, card). */
export interface FlashcardSchedule {
  rating: string
  easiness: number
  reps: number
  interval_days: number
  due_at: string
  due_in_days: number
  last_reviewed_at: string
}

export type FlashcardScheduleMap = Record<string, FlashcardSchedule>

export interface FlashcardRatingsResponse {
  ratings: Record<string, string>
  schedule: FlashcardScheduleMap
}

export type QuizDifficulty = 'Easy' | 'Medium' | 'Hard'

/** Source citation for a quiz question — returned by POST /quiz/explain. */
export interface QuizCitation {
  source: string | null
  heading?: string
  heading_path?: string
  chapter_id?: number | null
  chunk_id?: string | number | null
  text?: string
  screenshot?: string | null
  message?: string
}

export interface QuizAttempt {
  id: string
  lecture_id: string
  chapter_id: number | null
  difficulty: string
  started_at: string
  finished_at: string | null
  score: number
  total: number
}

interface QuizState {
  aiMode: 'tutor' | 'quiz' | 'cards' | 'socratic'
  setMode: (mode: 'tutor' | 'quiz' | 'cards' | 'socratic') => void

  isActive: boolean
  isQuizLoading: boolean
  attemptId: string | null
  questions: Question[]
  currentIndex: number
  answers: string[]
  confidences: string[]
  score: number
  evaluation: QuizEvaluation | null
  quizStartTime: number | null
  quizChapterId: number | null
  quizDifficulty: QuizDifficulty | null

  startQuiz: (questions: Question[], chapterId?: number | null, difficulty?: QuizDifficulty | null) => void
  setQuizLoading: (loading: boolean) => void
  createAttempt: (questions: Question[], chapterId?: number | null, difficulty?: QuizDifficulty | null) => Promise<string | null>
  submitAnswer: (answer: string) => void
  setConfidence: (confidence: string) => void
  nextQuestion: () => void
  endQuiz: (evaluation: QuizEvaluation) => void
  finishAttempt: (evaluation: QuizEvaluation) => Promise<void>
  retakeQuiz: () => Promise<void>

  /** BUG-6: called by useThreadStore on every thread switch — always idempotent */
  reset: () => void
}

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------
const INITIAL_STATE: Omit<
  QuizState,
  | 'setMode' | 'startQuiz' | 'createAttempt' | 'submitAnswer' | 'setConfidence'
  | 'nextQuestion' | 'endQuiz' | 'finishAttempt' | 'retakeQuiz' | 'reset' | 'setQuizLoading'
> = {
  aiMode: 'tutor',
  isActive: false,
  isQuizLoading: false,
  attemptId: null,
  questions: [],
  currentIndex: 0,
  answers: [],
  confidences: [],
  score: 0,
  evaluation: null,
  quizStartTime: null,
  quizChapterId: null,
  quizDifficulty: null,
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useQuizStore = create<QuizState>((set, get) => ({
  ...INITIAL_STATE,

  setMode: (mode) => set({ aiMode: mode }),

  startQuiz: (questions, chapterId = null, difficulty = null) =>
    set({
      aiMode: 'quiz',
      isActive: true,
      isQuizLoading: false,
      questions,
      currentIndex: 0,
      answers: [],
      confidences: new Array(questions.length).fill(''),
      score: 0,
      evaluation: null,
      quizStartTime: Date.now(),
      quizChapterId: chapterId ?? null,
      quizDifficulty: difficulty ?? null,
    }),

  setQuizLoading: (loading) => set({ isQuizLoading: loading }),

  createAttempt: async (questions, chapterId = null, difficulty = null) => {
    const lectureId = getLectureId()
    get().startQuiz(questions, chapterId, difficulty)
    try {
      const data = await apiPost<{ attempt_id: string }>(`${API_BASE}/quiz/attempts`, {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lecture_id: lectureId,
          chapter_id: chapterId ?? null,
          difficulty: difficulty || 'All',
          questions,
        }),
      })
      const attemptId = data.attempt_id
      set({ attemptId })
      return attemptId
    } catch (err) {
      console.warn('[QuizStore] Failed to create attempt record:', err)
    }
    return null
  },

  submitAnswer: (answer) => {
    const { questions, currentIndex, score } = get()
    const q = questions[currentIndex]
    const autoGraded = q.type === 'MCQ' || q.type === 'True/False'
    const correct = autoGraded
      ? answer.trim().toLowerCase() === q.answer.trim().toLowerCase()
      : false
    set({ answers: [...get().answers, answer], score: correct ? score + 1 : score })
  },

  setConfidence: (confidence) => {
    const { currentIndex, confidences } = get()
    const updated = [...confidences]
    updated[currentIndex] = confidence
    set({ confidences: updated })
  },

  nextQuestion: () => {
    const { currentIndex, questions } = get()
    if (currentIndex + 1 < questions.length) set({ currentIndex: currentIndex + 1 })
  },

  endQuiz: (evaluation) => set({ evaluation }),

  finishAttempt: async (evaluation) => {
    set({ evaluation })
    const { attemptId, questions, answers, confidences, score } = get()
    if (!attemptId) return
    const lectureId = getLectureId()
    const answersPayload = questions.map((q, i) => ({
      id: q.id,
      question_id: q.id,
      user_answer: answers[i] || '',
    }))
    try {
      await apiPost<{ success: boolean }>(
        `${API_BASE}/quiz/attempts/${attemptId}/finish?lecture_id=${encodeURIComponent(lectureId)}`,
        {
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            answers: answersPayload,
            confidences,
            evaluation,
            score: evaluation.final_score ?? score,
            total: questions.length,
          }),
        },
      )
    } catch (err) {
      console.warn('[QuizStore] Failed to finish attempt record:', err)
    }
  },

  retakeQuiz: async () => {
    const { quizChapterId, quizDifficulty } = get()
    const lectureId = getLectureId()
    const questions = await fetchQuizQuestions(quizChapterId ?? undefined, lectureId, quizDifficulty ?? undefined)
    if (questions.length > 0) {
      get().createAttempt(questions, quizChapterId, quizDifficulty)
    }
  },

  reset: () => set({ ...INITIAL_STATE }),
}))

// ---------------------------------------------------------------------------
// API helpers — now lecture‑aware
// ---------------------------------------------------------------------------

export async function fetchQuizQuestions(
  chapterId?: number,
  lectureId?: string,
  difficulty?: QuizDifficulty,
): Promise<Question[]> {
  const params = new URLSearchParams()
  if (chapterId !== undefined) params.set('chapter_id', String(chapterId))
  if (lectureId) params.set('lecture_id', lectureId)
  if (difficulty) params.set('difficulty', difficulty)
  const data = await apiGet<Question[] | { questions: Question[]; incomplete?: boolean }>(
    `${API_BASE}/quiz/questions?${params}`,
  )
  const raw = Array.isArray(data) ? data : data?.questions ?? []
  return raw.map((q) => ({
    ...q,
    id: (q as Question & { question_id?: number }).question_id ?? q.id,
  }))
}

/** Whether this chapter's assessment came back partially generated. */
export async function fetchQuizIncomplete(
  chapterId?: number,
  lectureId?: string,
): Promise<boolean> {
  const params = new URLSearchParams()
  if (chapterId !== undefined) params.set('chapter_id', String(chapterId))
  if (lectureId) params.set('lecture_id', lectureId)
  try {
    const data = await apiGet<{ questions?: unknown; incomplete?: boolean }>(
      `${API_BASE}/quiz/questions?${params}`,
    )
    return Boolean(data && typeof data === 'object' && 'incomplete' in data ? data.incomplete : false)
  } catch {
    return false
  }
}

export async function evaluateQuiz(
  questions: Array<Question & { user_answer: string }>,
  startTime: number,
  confidences: string[],
): Promise<QuizEvaluation> {
  const elapsed = Math.round((Date.now() - startTime) / 1000)
  const data = await apiPost<{ evaluation: QuizEvaluation }>(`${API_BASE}/quiz/evaluate`, {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ questions, elapsed_seconds: elapsed, confidences }),
  })
  return data.evaluation as QuizEvaluation
}

/** Cite a question's source in the lecture — metered only on explicit click. */
export async function explainQuizQuestion(
  question: string,
  lectureId: string,
  chapterId?: number | null,
): Promise<QuizCitation> {
  const data = await apiPost<QuizCitation>(`${API_BASE}/quiz/explain`, {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, lecture_id: lectureId, chapter_id: chapterId ?? null }),
  })
  return data
}

export async function fetchGeneratedFlashcards(
  chapterId?: number,
  lectureId?: string,
): Promise<Flashcard[]> {
  const params = new URLSearchParams()
  if (chapterId !== undefined) params.set('chapter_id', String(chapterId))
  if (lectureId) params.set('lecture_id', lectureId)
  const data = await apiGet<Flashcard[] | { flashcards: Flashcard[] }>(
    `${API_BASE}/flashcards?${params}`,
  )
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.flashcards)) return data.flashcards
  return []
}

export async function fetchQuizAttempts(
  lectureId: string,
  chapterId?: number,
): Promise<QuizAttempt[]> {
  const params = new URLSearchParams({ lecture_id: lectureId })
  if (chapterId !== undefined) params.set('chapter_id', String(chapterId))
  try {
    const data = await apiGet<{ attempts?: QuizAttempt[] }>(`${API_BASE}/quiz/attempts?${params}`)
    return data?.attempts || []
  } catch {
    return []
  }
}

export async function fetchQuizMissed(
  attemptId: string,
  lectureId: string,
): Promise<string[]> {
  try {
    const data = await apiGet<{ attempt_id: string; question_ids: string[] | number[] }>(
      `${API_BASE}/quiz/attempts/${attemptId}/missed?lecture_id=${encodeURIComponent(lectureId)}`,
    )
    return (data?.question_ids || []).map(String)
  } catch {
    return []
  }
}

export async function persistFlashcardRatings(
  ratings: Array<{ card_key: string; rating: string }>,
  lectureId: string,
  chapterId?: number,
): Promise<FlashcardScheduleMap | null> {
  try {
    const data = await apiPost<{ schedule?: FlashcardScheduleMap }>(`${API_BASE}/flashcards/ratings`, {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lecture_id: lectureId,
        chapter_id: chapterId ?? null,
        ratings,
      }),
    })
    return data?.schedule || null
  } catch {
    return null
  }
}

export async function fetchFlashcardRatings(
  lectureId: string,
  chapterId?: number,
): Promise<FlashcardRatingsResponse> {
  try {
    const params = new URLSearchParams({ lecture_id: lectureId })
    if (chapterId !== undefined) params.set('chapter_id', String(chapterId))
    const data = await apiGet<FlashcardRatingsResponse>(`${API_BASE}/flashcards/ratings?${params}`)
    return {
      ratings: data?.ratings || {},
      schedule: data?.schedule || {},
    }
  } catch {
    return { ratings: {}, schedule: {} }
  }
}

/** Download the lecture's full deck as an Anki `.apkg` file (P6.2). */
export async function downloadFlashcardsApkg(lectureId: string): Promise<boolean> {
  try {
    const res = await apiFetchRaw(
      `${API_BASE}/flashcards/export?lecture_id=${encodeURIComponent(lectureId)}`,
    )
    if (!res.ok) return false
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `norai-flashcards-${lectureId}.apkg`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    return true
  } catch {
    return false
  }
}
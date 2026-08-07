import { create } from 'zustand'
import { getLectureId } from '../lib/threadStorage'

const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || ''

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

export type QuizDifficulty = 'Easy' | 'Medium' | 'Hard'

/** Source citation for a quiz question — returned by POST /quiz/explain. */
export interface QuizCitation {
  source: string | null
  heading?: string
  heading_path?: string
  chapter_id?: number | null
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
  | 'nextQuestion' | 'endQuiz' | 'finishAttempt' | 'retakeQuiz' | 'reset'
> = {
  aiMode: 'tutor',
  isActive: false,
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

  createAttempt: async (questions, chapterId = null, difficulty = null) => {
    const lectureId = getLectureId()
    get().startQuiz(questions, chapterId, difficulty)
    try {
      const res = await fetch(`${API_BASE}/quiz/attempts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lecture_id: lectureId,
          chapter_id: chapterId ?? null,
          difficulty: difficulty || 'All',
          questions,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        const attemptId = data.attempt_id
        set({ attemptId })
        return attemptId
      }
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
      await fetch(`${API_BASE}/quiz/attempts/${attemptId}/finish?lecture_id=${encodeURIComponent(lectureId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers: answersPayload,
          confidences,
          evaluation,
          score: evaluation.final_score ?? score,
          total: questions.length,
        }),
      })
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
  const res = await fetch(`${API_BASE}/quiz/questions?${params}`)
  if (!res.ok) throw new Error('Failed to load quiz questions')
  const data = await res.json()
  const raw = Array.isArray(data) ? data : data && Array.isArray(data.questions) ? data.questions : []
  return (raw as Array<Record<string, unknown>>).map((q) => ({
    ...q,
    id: (q.id as number) ?? (q.question_id as number),
  })) as Question[]
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
    const res = await fetch(`${API_BASE}/quiz/questions?${params}`)
    if (!res.ok) return false
    const data = await res.json()
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
  const res = await fetch(`${API_BASE}/quiz/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ questions, elapsed_seconds: elapsed, confidences }),
  })
  if (!res.ok) throw new Error('Evaluation failed')
  const data = await res.json()
  return data.evaluation as QuizEvaluation
}

/** Cite a question's source in the lecture — metered only on explicit click. */
export async function explainQuizQuestion(
  question: string,
  lectureId: string,
  chapterId?: number | null,
): Promise<QuizCitation> {
  const res = await fetch(`${API_BASE}/quiz/explain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, lecture_id: lectureId, chapter_id: chapterId ?? null }),
  })
  if (!res.ok) throw new Error('Explain failed')
  return (await res.json()) as QuizCitation
}

export async function fetchGeneratedFlashcards(
  chapterId?: number,
  lectureId?: string,
): Promise<Flashcard[]> {
  const params = new URLSearchParams()
  if (chapterId !== undefined) params.set('chapter_id', String(chapterId))
  if (lectureId) params.set('lecture_id', lectureId)
  const res = await fetch(`${API_BASE}/flashcards?${params}`)
  if (!res.ok) throw new Error('Failed to load flashcards')
  const data = await res.json()
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
  const res = await fetch(`${API_BASE}/quiz/attempts?${params}`)
  if (!res.ok) return []
  const data = await res.json()
  return (data.attempts || []) as QuizAttempt[]
}

export async function fetchQuizMissed(
  attemptId: string,
  lectureId: string,
): Promise<string[]> {
  const res = await fetch(
    `${API_BASE}/quiz/attempts/${attemptId}/missed?lecture_id=${encodeURIComponent(lectureId)}`
  )
  if (!res.ok) return []
  const data = await res.json()
  return (data.question_ids || []).map(String)
}

export async function persistFlashcardRatings(
  ratings: Array<{ card_key: string; rating: string }>,
  lectureId: string,
  chapterId?: number,
): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/flashcards/ratings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lecture_id: lectureId,
        chapter_id: chapterId ?? null,
        ratings,
      }),
    })
    return res.ok
  } catch {
    return false
  }
}

export async function fetchFlashcardRatings(
  lectureId: string,
  chapterId?: number,
): Promise<Record<string, string>> {
  try {
    const params = new URLSearchParams({ lecture_id: lectureId })
    if (chapterId !== undefined) params.set('chapter_id', String(chapterId))
    const res = await fetch(`${API_BASE}/flashcards/ratings?${params}`)
    if (!res.ok) return {}
    const data = await res.json()
    return (data.ratings || {}) as Record<string, string>
  } catch {
    return {}
  }
}
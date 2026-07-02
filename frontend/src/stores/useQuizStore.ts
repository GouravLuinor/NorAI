/**
 * useQuizStore.ts
 *
 * Fix log:
 *  BUG-6  reset() is called by useThreadStore.setThreadId() whenever the user
 *         switches threads. This guarantees aiMode, evaluation, and isActive
 *         never bleed across threads.
 *         The reset() action is idempotent and safe to call from any context.
 *
 *  Also:  evaluateQuiz() and fetchQuizQuestions() use the same API_BASE
 *         resolution as useThreadStore so they share the same proxy path.
 */

import { create } from 'zustand'

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
  type: 'MCQ' | 'True/False' | 'ShortAnswer'
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

interface QuizState {
  aiMode: 'tutor' | 'quiz' | 'cards'
  setMode: (mode: 'tutor' | 'quiz' | 'cards') => void

  isActive: boolean
  questions: Question[]
  currentIndex: number
  answers: string[]
  confidences: string[]
  score: number
  evaluation: QuizEvaluation | null
  quizStartTime: number | null
  quizChapterId: number | null

  startQuiz: (questions: Question[], chapterId?: number | null) => void
  submitAnswer: (answer: string) => void
  setConfidence: (confidence: string) => void
  nextQuestion: () => void
  endQuiz: (evaluation: QuizEvaluation) => void
  retakeQuiz: () => Promise<void>

  /** BUG-6: called by useThreadStore on every thread switch — always idempotent */
  reset: () => void
}

// ---------------------------------------------------------------------------
// Initial state snapshot (defined once so reset() always returns a clean ref)
// ---------------------------------------------------------------------------
const INITIAL_STATE: Omit<
  QuizState,
  | 'setMode' | 'startQuiz' | 'submitAnswer' | 'setConfidence'
  | 'nextQuestion' | 'endQuiz' | 'retakeQuiz' | 'reset'
> = {
  aiMode: 'tutor',
  isActive: false,
  questions: [],
  currentIndex: 0,
  answers: [],
  confidences: [],
  score: 0,
  evaluation: null,
  quizStartTime: null,
  quizChapterId: null,
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useQuizStore = create<QuizState>((set, get) => ({
  ...INITIAL_STATE,

  setMode: (mode) => set({ aiMode: mode }),

  startQuiz: (questions, chapterId = null) =>
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
    }),

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

  retakeQuiz: async () => {
    const { quizChapterId } = get()
    const questions = await fetchQuizQuestions(quizChapterId ?? undefined)
    if (questions.length > 0) {
      set({
        questions,
        currentIndex: 0,
        answers: [],
        confidences: new Array(questions.length).fill(''),
        score: 0,
        evaluation: null,
        quizStartTime: Date.now(),
        isActive: true,
      })
    }
  },

  // BUG-6: full reset — safe to call cross-store from useThreadStore
  reset: () => set({ ...INITIAL_STATE }),
}))

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

export async function fetchQuizQuestions(chapterId?: number): Promise<Question[]> {
  const params = chapterId !== undefined ? `?chapter_id=${chapterId}` : ''
  const res = await fetch(`${API_BASE}/quiz/questions${params}`)
  if (!res.ok) throw new Error('Failed to load quiz questions')
  return res.json()
}

export async function evaluateQuiz(
  questions: any[],
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

export async function fetchGeneratedFlashcards(chapterId?: number): Promise<any[]> {
  const params = new URLSearchParams()
  if (chapterId !== undefined) params.set('chapter_id', String(chapterId))
  const res = await fetch(`${API_BASE}/flashcards?${params}`)
  if (!res.ok) throw new Error('Failed to load flashcards')
  return res.json()
}

export async function fetchSummary(chapterId: number): Promise<string> {
  const res = await fetch(`${API_BASE}/summary?chapter_id=${chapterId}`)
  if (!res.ok) throw new Error('Summary not available')
  return res.text()
}
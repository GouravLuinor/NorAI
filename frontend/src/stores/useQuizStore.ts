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

interface QuizState {
  aiMode: 'tutor' | 'quiz' | 'cards' | 'socratic'
  setMode: (mode: 'tutor' | 'quiz' | 'cards' | 'socratic') => void

  isActive: boolean
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
  submitAnswer: (answer: string) => void
  setConfidence: (confidence: string) => void
  nextQuestion: () => void
  endQuiz: (evaluation: QuizEvaluation) => void
  retakeQuiz: () => Promise<void>

  /** BUG-6: called by useThreadStore on every thread switch — always idempotent */
  reset: () => void
}

// ---------------------------------------------------------------------------
// Initial state
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
    const { quizChapterId, quizDifficulty } = get()
    const lectureId = getLectureId()
    const questions = await fetchQuizQuestions(quizChapterId ?? undefined, lectureId, quizDifficulty ?? undefined)
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
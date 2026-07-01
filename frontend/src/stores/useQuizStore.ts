import { create } from 'zustand'

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

interface QuizState {
  aiMode: 'tutor' | 'quiz' | 'cards'
  setMode: (mode: 'tutor' | 'quiz' | 'cards') => void

  isActive: boolean
  questions: Question[]
  currentIndex: number
  answers: string[]
  confidences: string[]
  score: number
  evaluation: {
    final_score: number | null
    total_questions: number
    per_question_feedback: QuestionFeedback[]
    overall_insights: string
  } | null
  quizStartTime: number | null
  quizChapterId: number | null

  startQuiz: (questions: Question[], chapterId?: number | null) => void
  submitAnswer: (answer: string) => void
  setConfidence: (confidence: string) => void
  nextQuestion: () => void
  endQuiz: (evaluation: QuizState['evaluation']) => void
  retakeQuiz: () => Promise<void>
  reset: () => void
}

export const useQuizStore = create<QuizState>((set, get) => ({
  aiMode: 'tutor',
  setMode: (mode) => set({ aiMode: mode }),

  isActive: false,
  questions: [],
  currentIndex: 0,
  answers: [],
  confidences: [],
  score: 0,
  evaluation: null,
  quizStartTime: null,
  quizChapterId: null,

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
    const isAutoGraded = q.type === 'MCQ' || q.type === 'True/False'
    const isCorrect = isAutoGraded
      ? answer.trim().toLowerCase() === q.answer.trim().toLowerCase()
      : false
    const newScore = isCorrect ? score + 1 : score
    set({
      answers: [...get().answers, answer],
      score: newScore,
    })
  },

  setConfidence: (confidence) => {
    const { currentIndex, confidences } = get()
    const updated = [...confidences]
    updated[currentIndex] = confidence
    set({ confidences: updated })
  },

  nextQuestion: () => {
    const { currentIndex, questions } = get()
    const nextIndex = currentIndex + 1
    if (nextIndex < questions.length) {
      set({ currentIndex: nextIndex })
    }
  },

  endQuiz: (evaluation) => {
    set({ evaluation })
  },

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

  reset: () =>
    set({
      isActive: false,
      questions: [],
      currentIndex: 0,
      answers: [],
      confidences: [],
      score: 0,
      evaluation: null,
      quizStartTime: null,
      aiMode: 'tutor',
    }),
}))

// ── API helpers ──────────────────────────────────────────────────────────────

export async function fetchQuizQuestions(chapterId?: number): Promise<Question[]> {
  const params = chapterId !== undefined ? `?chapter_id=${chapterId}` : ''
  const res = await fetch(`/quiz/questions${params}`)
  if (!res.ok) throw new Error('Failed to load quiz questions')
  return res.json()
}

export async function evaluateQuiz(
  questions: any[],
  startTime: number,
  confidences: string[]
): Promise<QuizState['evaluation']> {
  const elapsed = Math.round((Date.now() - startTime) / 1000)
  const payload = {
    questions,
    elapsed_seconds: elapsed,
    confidences,
  }
  const res = await fetch('/quiz/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error('Evaluation failed')
  const data = await res.json()
  return data.evaluation
}

export async function fetchGeneratedFlashcards(chapterId?: number): Promise<any[]> {
  const params = new URLSearchParams()
  if (chapterId !== undefined) params.set('chapter_id', String(chapterId))
  // No 'n' → server returns all cards
  const res = await fetch(`/flashcards?${params}`)
  if (!res.ok) throw new Error('Failed to load flashcards')
  return res.json()
}

export async function fetchSummary(chapterId: number): Promise<string> {
  const res = await fetch(`/summary?chapter_id=${chapterId}`)
  if (!res.ok) throw new Error('Summary not available')
  return res.text()
}
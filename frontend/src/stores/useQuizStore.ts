import { create } from 'zustand'

export interface Question {
  id: number
  type: 'MCQ' | 'True/False' | 'ShortAnswer'
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
  score: number
  evaluation: string | null

  startQuiz: (questions: Question[]) => void
  submitAnswer: (answer: string) => void
  nextQuestion: () => void
  endQuiz: (evaluation: string) => void
  reset: () => void
}

export const useQuizStore = create<QuizState>((set, get) => ({
  aiMode: 'tutor',
  setMode: (mode) => set({ aiMode: mode }),

  isActive: false,
  questions: [],
  currentIndex: 0,
  answers: [],
  score: 0,
  evaluation: null,

  startQuiz: (questions) =>
    set({
      aiMode: 'quiz',
      isActive: true,
      questions,
      currentIndex: 0,
      answers: [],
      score: 0,
      evaluation: null,
    }),

  // Record answer, update score, DO NOT advance index
  submitAnswer: (answer) => {
    const { questions, currentIndex, answers, score } = get()
    const currentQ = questions[currentIndex]
    const isCorrect = answer.trim().toLowerCase() === currentQ.answer.trim().toLowerCase()
    const newScore = isCorrect ? score + 1 : score
    set({
      answers: [...answers, answer],
      score: newScore,
    })
  },

  // Move to next question or trigger evaluation if last
  nextQuestion: () => {
    const { currentIndex, questions, score, answers, endQuiz } = get()
    const nextIndex = currentIndex + 1
    if (nextIndex >= questions.length) {
      // Last question – trigger evaluation
      const msg = `You scored ${score}/${questions.length}. ${
        score === questions.length
          ? "Perfect! You've mastered these concepts."
          : 'Review the questions you missed to strengthen your understanding.'
      }`
      endQuiz(msg)
    } else {
      set({ currentIndex: nextIndex })
    }
  },

  endQuiz: (evaluation) => set({ evaluation }),

  reset: () =>
    set({
      isActive: false,
      questions: [],
      currentIndex: 0,
      answers: [],
      score: 0,
      evaluation: null,
      aiMode: 'tutor',
    }),
}))
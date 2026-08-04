import { useChapterStore } from '../../stores/useChapterStore'
import { useQuizStore, fetchQuizQuestions } from '../../stores/useQuizStore'
import { ChatArea } from '../chat/ChatArea'
import { QuizPanel } from '../quiz/QuizPanel'
import { FlashcardsPanel } from '../flashcards/FlashcardsPanel'
import { motion, AnimatePresence } from 'framer-motion'
import { useToastStore } from '../../stores/useToastStore'
import { useEffect } from 'react'
import { useLectureStore } from '../../stores/useLectureStore'

export function AIPanel() {
  const { activeChapterId } = useChapterStore()
  const activeLectureId = useLectureStore(s => s.activeLectureId)
  const { aiMode, setMode, startQuiz } = useQuizStore()
  const addToast = useToastStore(s => s.addToast)

useEffect(() => {
  if (aiMode === 'quiz') {
    const lectureId = useLectureStore.getState().activeLectureId || undefined
    fetchQuizQuestions(activeChapterId, lectureId).then((qs) => {
      if (qs.length > 0) {
        useQuizStore.getState().startQuiz(qs, activeChapterId)
      }
    })
  }
}, [activeChapterId])  // intentionally only on chapter change — NOT on aiMode

  let ActivePanel: React.ReactNode
  if (aiMode === 'quiz') {
    ActivePanel = <QuizPanel />
  } else if (aiMode === 'cards') {
    ActivePanel = <FlashcardsPanel />
  } else {
    ActivePanel = <ChatArea />
  }

  return (
    <div className="flex flex-col min-h-0 bg-ns overflow-hidden h-full">
      {/* Header */}
      <div className="px-3.5 py-2.5 border-b border-bdr flex items-center gap-2 shrink-0 bg-ns2/40 fold-marks relative">
        <div className="w-7 h-7 rounded-sm bg-npf flex items-center justify-center text-11 font-medium text-npfg shadow-ev1 relative">
          N
          <span className="absolute bottom-0 right-0 w-1.5 h-1.5 rounded-full bg-ng border-1.5 border-ns" />
        </div>
        <div>
          <div className="font-display text-xs font-medium text-nt">Nora</div>
          <div className="spec-label mt-0.5">
            {String(activeChapterId).padStart(2, '0')} · {aiMode === 'quiz' ? 'Quiz' : aiMode === 'cards' ? 'Cards' : 'Tutor'}
          </div>
        </div>
        <div className="ml-auto flex gap-0.5 bg-ns2 rounded-lg p-0.5">
          {(['tutor', 'quiz', 'cards'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => {
                if (mode === 'quiz') {
                  fetchQuizQuestions(activeChapterId, activeLectureId || undefined)
                    .then((qs) => startQuiz(qs, activeChapterId))
                  addToast('Quiz started', 'success')
                }
                 else if (mode === 'cards') {
                  setMode('cards')
                  addToast('Flashcards mode activated', 'info')
                } else {
                  setMode('tutor')
                }
              }}
              className={`px-2 py-1 rounded-md text-2xs transition ${
                (mode === 'tutor' && aiMode === 'tutor') ||
                (mode === 'quiz' && aiMode === 'quiz') ||
                (mode === 'cards' && aiMode === 'cards')
                  ? 'bg-nt4/20 text-nt shadow-ev1'
                  : 'text-nt3 hover:text-nt2'
              }`}
            >
              {mode === 'tutor' ? 'Tutor' : mode === 'quiz' ? 'Quiz' : 'Cards'}
            </button>
          ))}
        </div>
      </div>

      {/* Panel content with Framer Motion transitions */}
      <div className="flex-1 overflow-hidden relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={aiMode}
            initial={{ opacity: 0, x: 15 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -15 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="h-full w-full"
          >
            {ActivePanel}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
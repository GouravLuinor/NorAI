import { useChapterStore } from '../../stores/useChapterStore'
import { useQuizStore, fetchQuizQuestions } from '../../stores/useQuizStore'
import { ChatArea } from '../chat/ChatArea'
import { QuizPanel } from '../quiz/QuizPanel'
import { FlashcardsPanel } from '../flashcards/FlashcardsPanel'
import { PersonaModal } from '../chat/PersonaModal'
import { motion, AnimatePresence } from 'framer-motion'
import { useToastStore } from '../../stores/useToastStore'
import { useState } from 'react'
import { useLectureStore } from '../../stores/useLectureStore'
import { SegmentedControl } from '../ui/SegmentedControl'
import { SlidersHorizontal } from 'lucide-react'
import { FOCUS_RING } from '../ui/shared'

export function AIPanel() {
  const activeChapterId = useChapterStore((s) => s.activeChapterId)
  const activeLectureId = useLectureStore(s => s.activeLectureId)
  const aiMode = useQuizStore((s) => s.aiMode)
  const setMode = useQuizStore((s) => s.setMode)
  const startQuiz = useQuizStore((s) => s.startQuiz)
  const setQuizLoading = useQuizStore((s) => s.setQuizLoading)
  const addToast = useToastStore(s => s.addToast)
  const [settingsOpen, setSettingsOpen] = useState(false)

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
            {String(activeChapterId).padStart(2, '0')} · {aiMode === 'quiz' ? 'Quiz' : aiMode === 'cards' ? 'Cards' : aiMode === 'socratic' ? 'Study' : 'Tutor'}
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label="Tutor settings (persona & study mode)"
            title="Tutor settings"
            className={`p-1.5 rounded-md text-nt3 hover:text-nt2 hover:bg-ns3 transition ${FOCUS_RING}`}
          >
            <SlidersHorizontal size={14} strokeWidth={1.5} />
          </button>
          <SegmentedControl
            containerClass="flex gap-0.5 bg-ns2 rounded-lg p-0.5"
            itemClass="px-2 py-1 rounded-md text-2xs transition"
            activeClass="bg-nt4/20 text-nt shadow-ev1"
            inactiveClass="text-nt3 hover:text-nt2"
            options={[
              { value: 'tutor', label: 'Tutor' },
              { value: 'socratic', label: 'Study' },
              { value: 'quiz', label: 'Quiz' },
              { value: 'cards', label: 'Cards' },
            ]}
            value={aiMode}
            onChange={(mode) => {
              if (mode === 'quiz') {
                // Switch eagerly so an empty/errored fetch still lands on the
                // quiz panel's "no questions" state instead of silently
                // staying on Tutor; toast only once questions actually load.
                setMode('quiz')
                setQuizLoading(true)
                fetchQuizQuestions(activeChapterId, activeLectureId || undefined)
                  .then((qs) => {
                    if (qs.length > 0) {
                      startQuiz(qs, activeChapterId)
                      addToast('Quiz started', 'success')
                    }
                  })
                  .catch(() => {})
                  .finally(() => setQuizLoading(false))
              } else if (mode === 'cards') {
                setMode('cards')
                addToast('Flashcards mode activated', 'info')
              } else if (mode === 'socratic') {
                setMode('socratic')
                addToast('Study mode activated — I will guide you with questions', 'info')
              } else {
                setMode('tutor')
              }
            }}
          />
        </div>
      </div>

      {/* Panel content with smooth fade transitions */}
      <div className="flex-1 overflow-hidden relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={aiMode}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="h-full w-full"
          >
            {ActivePanel}
          </motion.div>
        </AnimatePresence>
      </div>

      <PersonaModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
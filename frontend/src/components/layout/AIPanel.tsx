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
import { friendlyError } from '../../lib/errorCopy'
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
      <div className="px-3 py-2 border-b border-bdr flex items-center justify-between gap-2 shrink-0 bg-ns2/40 fold-marks relative">
        <div className="flex items-center gap-2 shrink-0">
          <div className="w-6 h-6 rounded-sm bg-npf flex items-center justify-center text-10 font-medium text-npfg shadow-ev1 relative shrink-0">
            N
            <span className="absolute bottom-0 right-0 w-1.5 h-1.5 rounded-full bg-ng border-1.5 border-ns" />
          </div>
          <div className="shrink-0">
            <div className="font-display text-xs font-medium text-nt leading-tight">Nora</div>
            <div className="spec-label text-3xs text-nt3">
              {String(activeChapterId).padStart(2, '0')} · {aiMode === 'quiz' ? 'Quiz' : aiMode === 'cards' ? 'Cards' : aiMode === 'socratic' ? 'Study' : 'Tutor'}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label="Tutor settings (persona & study mode)"
            title="Tutor settings"
            className={`p-1 rounded-md text-nt3 hover:text-nt2 hover:bg-ns3 transition shrink-0 ${FOCUS_RING}`}
          >
            <SlidersHorizontal size={13} strokeWidth={1.5} />
          </button>
          <SegmentedControl
            containerClass="flex gap-0.5 bg-ns2 rounded-lg p-0.5 shrink-0"
            itemClass="px-2 py-0.5 rounded-md text-2xs transition font-medium"
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
                    } else {
                      addToast('No questions found for this chapter yet.', 'info')
                    }
                  })
                  .catch((err) => addToast(friendlyError(err) || 'Could not load quiz questions.', 'error'))
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
import { DEFAULT_TRIAL_QUOTA_MINUTES, DEMO_LECTURE_IDS } from '../../config/features'
import { useChapterStore } from '../../stores/useChapterStore'
import { useQuizStore, fetchQuizQuestions } from '../../stores/useQuizStore'
import { ChatArea } from '../chat/ChatArea'
import { QuizPanel } from '../quiz/QuizPanel'
import { FlashcardsPanel } from '../flashcards/FlashcardsPanel'
import { PersonaModal } from '../chat/PersonaModal'
import { useToastStore } from '../../stores/useToastStore'
import { useState } from 'react'
import { useLectureStore } from '../../stores/useLectureStore'
import { useVideoStore } from '../../stores/useVideoStore'
import { friendlyError } from '../../lib/errorCopy'
import { SegmentedControl } from '../ui/SegmentedControl'
import { SlidersHorizontal } from 'lucide-react'
import { FOCUS_RING } from '../ui/shared'

import { useAuthStore } from '../../stores/useAuthStore'
import { ArrowRight, Check } from 'lucide-react'
import { Button } from '../ui/Button'

export function AIPanel() {
  const user = useAuthStore((s) => s.user)
  const isDocument = useVideoStore((s) => s.sourceKind === 'document')
  const openAuthModal = useAuthStore((s) => s.openAuthModal)
  const activeChapterId = useChapterStore((s) => s.activeChapterId)
  const activeLectureId = useLectureStore(s => s.activeLectureId)
  const aiMode = useQuizStore((s) => s.aiMode)
  const setMode = useQuizStore((s) => s.setMode)
  const startQuiz = useQuizStore((s) => s.startQuiz)
  const setQuizLoading = useQuizStore((s) => s.setQuizLoading)
  const addToast = useToastStore(s => s.addToast)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const isDemoLecture = Boolean(activeLectureId && DEMO_LECTURE_IDS.includes(activeLectureId))

  if (!user && !isDemoLecture) {
    return (
      <div className="flex flex-col min-h-0 bg-ns overflow-hidden h-full">
        <NoraHeader subtitle="Answers from this lecture" />

        <div className="flex-1 flex flex-col justify-center px-6 py-8 overflow-y-auto">
          <h3 className="font-serif font-semibold text-22 text-nt leading-snug mb-2">
            Ask Nora about this lecture
          </h3>
          <p className="text-15 text-nt2 mb-5 leading-relaxed max-w-[34ch]">
            Make a free account to ask questions. Nora answers from what the lecturer said and shows the moment they said it.
          </p>

          <ul className="space-y-2.5 mb-7 text-14 text-nt2">
            {[
              'Answers come only from this lecture',
              'Every source is a timestamp you can play',
              `Free: ${DEFAULT_TRIAL_QUOTA_MINUTES} minutes of your own lectures a month`,
            ].map((t) => (
              <li key={t} className="flex items-start gap-2.5">
                <Check size={16} strokeWidth={2} className="text-np mt-0.5 shrink-0" />
                <span>{t}</span>
              </li>
            ))}
          </ul>

          <div className="space-y-2 max-w-xs">
            <Button
              onClick={() => openAuthModal('signup')}
              className="w-full h-11 px-4 rounded-md text-15 font-bold gap-2"
            >
              Create free account <ArrowRight size={16} strokeWidth={2} />
            </Button>
            <button
              onClick={() => openAuthModal('login')}
              className={`w-full h-10 px-4 rounded-md text-14 font-bold text-nt2 hover:text-nt hover:bg-ns2 transition-colors cursor-pointer ${FOCUS_RING}`}
            >
              I have an account: sign in
            </button>
          </div>
        </div>
      </div>
    )
  }

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
      <div className="px-4 pt-3 pb-2 border-b border-bdr shrink-0">
        <div className="flex items-center gap-2.5">
          <NoraAvatar />
          <div className="min-w-0">
            <div className="text-16 font-bold text-nt leading-tight">Nora</div>
            <div className="text-12 text-nt3 leading-tight">Answers from this {isDocument ? 'document' : 'lecture'}</div>
          </div>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label="Tutor settings (persona and study mode)"
            title="Tutor settings"
            className={`ml-auto p-1.5 rounded-md text-nt3 hover:text-nt hover:bg-ns2 transition shrink-0 ${FOCUS_RING}`}
          >
            <SlidersHorizontal size={16} strokeWidth={1.75} />
          </button>
        </div>
        <div className="mt-3">
          <SegmentedControl
            containerClass="grid grid-cols-4 gap-1 bg-ns2 rounded-md p-1"
            itemClass="h-8 rounded-[4px] text-13 font-bold transition-colors cursor-pointer"
            inactiveClass="text-nt3 hover:text-nt"
            options={[
              { value: 'tutor', label: 'Ask', activeClass: 'bg-ns text-z-notes shadow-ev1' },
              { value: 'socratic', label: 'Coach', activeClass: 'bg-ns text-z-notes shadow-ev1' },
              { value: 'quiz', label: 'Quiz', activeClass: 'bg-ns text-z-quiz shadow-ev1' },
              { value: 'cards', label: 'Cards', activeClass: 'bg-ns text-z-cards shadow-ev1' },
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
                addToast('Coach mode: Nora will guide you with questions', 'info')
              } else {
                setMode('tutor')
              }
            }}
          />
        </div>
      </div>

      {/* Panel content: mode switches are instant (motion is reserved for
          shelf-mark presses and seeks). */}
      <div className="flex-1 overflow-hidden relative">
        <div key={aiMode} className="h-full w-full">
          {ActivePanel}
        </div>
      </div>

      <PersonaModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

function NoraAvatar() {
  return (
    <div
      aria-hidden="true"
      className="w-[30px] h-[30px] rounded-[4px] bg-brass text-[#16181A] flex items-center justify-center text-15 font-bold shrink-0"
    >
      N
    </div>
  )
}

function NoraHeader({ subtitle }: { subtitle: string }) {
  return (
    <div className="px-4 py-3 border-b border-bdr flex items-center gap-2.5 shrink-0">
      <NoraAvatar />
      <div>
        <div className="text-16 font-bold text-nt leading-tight">Nora</div>
        <div className="text-12 text-nt3 leading-tight">{subtitle}</div>
      </div>
    </div>
  )
}

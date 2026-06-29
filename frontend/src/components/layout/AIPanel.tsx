import { useChapterStore } from '../../stores/useChapterStore'
import { useQuizStore } from '../../stores/useQuizStore'
import { ChatArea } from '../chat/ChatArea'
import { QuizPanel } from '../quiz/QuizPanel'
import { FlashcardsPanel } from '../flashcards/FlashcardsPanel'
import { mockQuizQuestions } from '../../mocks/quizData'

export function AIPanel() {
  const { activeChapterId } = useChapterStore()
  const { aiMode, setMode, startQuiz, reset } = useQuizStore()

  let ActivePanel: React.ReactNode
  if (aiMode === 'quiz') {
    ActivePanel = <QuizPanel />
  } else if (aiMode === 'cards') {
    ActivePanel = <FlashcardsPanel />
  } else {
    ActivePanel = <ChatArea />
  }

  return (
    <div className="flex flex-col min-h-0 bg-ns overflow-hidden">
      {/* Header */}
      <div className="px-3.5 py-2.5 border-b border-bdr flex items-center gap-2 shrink-0">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-np to-nbl flex items-center justify-center text-[11px] font-medium text-white shadow-sm relative">
          N
          <span className="absolute bottom-0 right-0 w-1.5 h-1.5 rounded-full bg-ng border-1.5 border-ns" />
        </div>
        <div>
          <div className="text-xs font-medium text-nt">Nora</div>
          <div className="text-[10px] text-nt3">
            Ch {String(activeChapterId).padStart(2, '0')} · {aiMode === 'quiz' ? 'Quiz' : aiMode === 'cards' ? 'Cards' : 'Tutor'}
          </div>
        </div>
        <div className="ml-auto flex gap-0.5 bg-ns2 rounded-lg p-0.5">
          {(['tutor', 'quiz', 'cards'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => {
                if (mode === 'quiz') {
                  startQuiz(mockQuizQuestions)
                } else if (mode === 'cards') {
                  setMode('cards')
                } else {
                  setMode('tutor')
                  reset()
                }
              }}
              className={`px-2 py-1 rounded-md text-[10px] transition ${
                (mode === 'tutor' && aiMode === 'tutor') ||
                (mode === 'quiz' && aiMode === 'quiz') ||
                (mode === 'cards' && aiMode === 'cards')
                  ? 'bg-ns4 text-nt shadow-sm'
                  : 'text-nt3 hover:text-nt2'
              }`}
            >
              {mode === 'tutor' ? 'Tutor' : mode === 'quiz' ? 'Quiz' : 'Cards'}
            </button>
          ))}
        </div>
      </div>

      {/* Panel content */}
      <div className="flex-1 overflow-hidden">{ActivePanel}</div>
    </div>
  )
}
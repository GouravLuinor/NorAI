import { ChevronDown, Lock, LockOpen, Info, Quote, Check, X } from 'lucide-react'
import type { Question } from '../../stores/useQuizStore'
import { FOCUS_RING } from '../ui/shared'

// ── Badge ────────────────────────────────────────────────────────────────────
export function Badge({ type, difficulty }: { type: string; difficulty: string }) {
  const diffColors: Record<string, string> = {
    Easy: 'text-ng bg-ngb border-ngbr',
    Medium: 'text-na bg-nab border-nabr',
    Hard: 'text-nr bg-nrb border-nrbr',
  }
  return (
    <div className="flex items-center gap-2">
      <span className="inline-flex items-center px-2 py-0.5 rounded-sm text-12 font-bold bg-nblb text-nbl">
        {type}
      </span>
      <span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-12 font-bold border ${diffColors[difficulty] || 'bg-ns3 text-nt2'}`}>
        {difficulty}
      </span>
    </div>
  )
}

// ── MCQ Options ──────────────────────────────────────────────────────────────
export function MCQOptions({ options }: { options: string[] }) {
  const letters = ['A', 'B', 'C', 'D', 'E', 'F']
  return (
    <div className="flex flex-col gap-2.5 mt-5">
      {options.map((opt, i) => (
        <div key={i} className="flex items-start gap-3 px-3.5 py-3 rounded-md bg-ns border border-bdr2">
          <span className="w-7 h-7 rounded-[4px] border-[1.5px] border-nt3 flex items-center justify-center font-mono text-13 font-semibold text-nt2 shrink-0">{letters[i]}</span>
          <span className="text-16 text-nt leading-relaxed pt-0.5">{opt}</span>
        </div>
      ))}
    </div>
  )
}

// ── True/False Options ───────────────────────────────────────────────────────
export function TrueFalseOptions() {
  return (
    <div className="flex gap-3 mt-5">
      <div className="flex-1 flex items-center justify-center gap-2 h-12 rounded-md bg-ns border border-bdr2 text-16 font-bold text-nt2">
        <Check size={17} strokeWidth={2} aria-hidden="true" /> True
      </div>
      <div className="flex-1 flex items-center justify-center gap-2 h-12 rounded-md bg-ns border border-bdr2 text-16 font-bold text-nt2">
        <X size={17} strokeWidth={2} aria-hidden="true" /> False
      </div>
    </div>
  )
}

// ── Free‑Response Lines ──────────────────────────────────────────────────────
export function FreeResponseLines({ count = 4 }: { count?: number }) {
  return (
    <div className="mt-5">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={`h-9 ${i === 0 ? 'border-t' : ''} border-b border-ns4 flex items-end pb-1.5`}>
          {i === 0 && <span className="text-15 text-nt4 italic">Write your answer here…</span>}
        </div>
      ))}
      <div className="flex items-start gap-2 mt-4 p-3 rounded-md bg-ns2 text-14 text-nt2">
        <Info size={15} strokeWidth={1.5} className="text-nt3 mt-0.5 shrink-0" />
        <span>Suggested length: 2–4 sentences.</span>
      </div>
    </div>
  )
}

// ── Question Card ────────────────────────────────────────────────────────────
export function QuestionCard({ question, index, onExplain }: {
  question: Question
  index: number
  onExplain?: (question: Question) => void
}) {
  const hasOptions = Array.isArray(question.options) && question.options.length > 0
  return (
    <div className="bg-ns border border-bdr rounded-md p-5 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <span className="font-mono text-14 font-semibold text-z-quiz">Q{index + 1}</span>
        <Badge type={question.type} difficulty={question.difficulty ?? 'Medium'} />
      </div>
      <div className="font-serif text-18 text-nt leading-snug mb-5 max-w-[60ch]">{question.question}</div>
      {question.type === 'True/False' ? (
        <TrueFalseOptions />
      ) : hasOptions ? (
        <MCQOptions options={question.options ?? []} />
      ) : (
        <FreeResponseLines count={question.type?.toLowerCase().includes('short') ? 3 : 4} />
      )}
      {onExplain && (
        <button
          type="button"
          onClick={() => onExplain(question)}
          className={`mt-4 inline-flex items-center gap-1.5 text-14 font-bold text-np hover:underline bg-transparent border-none rounded-sm cursor-pointer ${FOCUS_RING}`}
        >
          <Quote size={15} strokeWidth={1.75} />
          Explain: show me where this is in the notes
        </button>
      )}
    </div>
  )
}

// ── Answer Key ───────────────────────────────────────────────────────────────
export function AnswerKey({ questions, isOpen, onToggle }: { questions: Question[]; isOpen: boolean; onToggle: () => void }) {
  return (
    <div className="mt-8 border border-bdr rounded-md overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className={`w-full flex items-center gap-3 px-5 py-4 bg-ns2 border-b border-bdr cursor-pointer hover:bg-ns3 transition text-left ${FOCUS_RING}`}
      >
        {isOpen ? <LockOpen size={17} strokeWidth={1.5} className="text-nbl" /> : <Lock size={17} strokeWidth={1.5} className="text-nt3" />}
        <span className="text-15 font-bold text-nt">{isOpen ? 'Answer key' : 'Answers are hidden'}</span>
        <span className="text-13 text-nt3">{isOpen ? 'Hide' : 'Show'}</span>
        <ChevronDown size={15} strokeWidth={1.5} className={`ml-auto text-nt3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      {isOpen && (
        <div className="px-5 py-3 space-y-4">
          {questions.map((q, i) => (
            <div key={q.id ?? i} className="flex items-start gap-4 py-3 border-b border-bdr last:border-none">
              <span className="font-mono text-13 font-semibold text-nt3 min-w-[28px] pt-1">Q{i + 1}</span>
              <div className="text-15 text-nt2 leading-relaxed">
                <span className={`inline-flex items-center justify-center w-6 h-6 rounded-md border mr-2.5 align-middle text-11 font-semibold ${q.type === 'True/False' && q.answer === 'False' ? 'bg-nrb border-nrbr text-nr' : 'bg-npb border-npbr text-np'}`}>
                  {Array.isArray(q.options) && q.options.length > 0 && q.answer
                    ? String.fromCharCode(65 + q.options.indexOf(q.answer))
                    : q.type === 'True/False'
                      ? q.answer[0]
                      : q.answer.slice(0, 1)}
                </span>
                {q.answer}
                {q.explanation && <span className="block mt-1 text-nt3 text-14">{q.explanation}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
import { ChevronDown, Lock, LockOpen, Info } from 'lucide-react'
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
      <span className="inline-flex items-center px-2 py-0.5 rounded-[5px] text-3xs font-semibold uppercase tracking-wide bg-nblb text-nbl">
        {type}
      </span>
      <span className={`inline-flex items-center px-2 py-0.5 rounded-[5px] text-3xs font-semibold uppercase tracking-wide border ${diffColors[difficulty] || 'bg-ns3 text-nt2'}`}>
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
        <div key={i} className="flex items-start gap-3 px-3.5 py-3 rounded-lg bg-nb border border-bdr2 shadow-ev1">
          <span className="w-6 h-6 rounded-md bg-ns3 flex items-center justify-center text-11 font-semibold text-nt2 shrink-0">{letters[i]}</span>
          <span className="text-13 text-nt2 leading-relaxed pt-0.5">{opt}</span>
        </div>
      ))}
    </div>
  )
}

// ── True/False Options ───────────────────────────────────────────────────────
export function TrueFalseOptions() {
  return (
    <div className="flex gap-3 mt-5">
      <div className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg bg-nb border border-bdr2 text-13 font-medium text-nt2 shadow-ev1">
        <span className="text-base">✓</span> True
      </div>
      <div className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg bg-nb border border-bdr2 text-13 font-medium text-nt2 shadow-ev1">
        <span className="text-base">✗</span> False
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
          {i === 0 && <span className="text-13 text-nt4 italic">Write your answer here…</span>}
        </div>
      ))}
      <div className="flex items-start gap-2 mt-4 p-2.5 rounded-md bg-ns2 border border-bdr2 text-xs text-nt2">
        <Info size={12} strokeWidth={1.5} className="text-nt3 mt-0.5 shrink-0" />
        <span>Suggested length: 2–4 sentences.</span>
      </div>
    </div>
  )
}

// ── Question Card ────────────────────────────────────────────────────────────
export function QuestionCard({ question, index }: { question: Question; index: number }) {
  const hasOptions = Array.isArray(question.options) && question.options.length > 0
  return (
    <div className="bg-ns border border-bdr2 rounded-xl p-5 shadow-ev1">
      <div className="flex items-center justify-between mb-4">
        <span className="text-11 font-semibold text-nt3 uppercase tracking-wider">Q{index + 1}</span>
        <Badge type={question.type} difficulty={question.difficulty ?? 'Medium'} />
      </div>
      <div className="text-sm text-nt leading-relaxed mb-5">{question.question}</div>
      {question.type === 'True/False' ? (
        <TrueFalseOptions />
      ) : hasOptions ? (
        <MCQOptions options={question.options ?? []} />
      ) : (
        <FreeResponseLines count={question.type?.toLowerCase().includes('short') ? 3 : 4} />
      )}
    </div>
  )
}

// ── Answer Key ───────────────────────────────────────────────────────────────
export function AnswerKey({ questions, isOpen, onToggle }: { questions: Question[]; isOpen: boolean; onToggle: () => void }) {
  return (
    <div className="mt-8 border border-bdr2 rounded-xl overflow-hidden shadow-ev1">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className={`w-full flex items-center gap-3 px-5 py-4 bg-ns2 border-b border-bdr cursor-pointer hover:bg-ns3 transition text-left ${FOCUS_RING}`}
      >
        {isOpen ? <LockOpen size={17} strokeWidth={1.5} className="text-nbl" /> : <Lock size={17} strokeWidth={1.5} className="text-nt3" />}
        <span className="text-13 font-medium text-nt">{isOpen ? 'Answer Key' : 'Answers are hidden'}</span>
        <span className="text-2xs text-nt3 bg-ns px-2 py-0.5 rounded-md font-medium">Click to toggle</span>
        <ChevronDown size={15} strokeWidth={1.5} className={`ml-auto text-nt3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      {isOpen && (
        <div className="px-5 py-3 space-y-4">
          {questions.map((q, i) => (
            <div key={q.id ?? i} className="flex items-start gap-4 py-3 border-b border-bdr last:border-none">
              <span className="font-mono text-11 font-semibold text-nt3 min-w-[24px] pt-1">Q{i + 1}</span>
              <div className="text-13 text-nt2 leading-relaxed">
                <span className={`inline-flex items-center justify-center w-6 h-6 rounded-md border mr-2.5 align-middle text-11 font-semibold ${q.type === 'True/False' && q.answer === 'False' ? 'bg-nrb border-nrbr text-nr' : 'bg-npb border-npbr text-np'}`}>
                  {Array.isArray(q.options) && q.options.length > 0 && q.answer
                    ? String.fromCharCode(65 + q.options.indexOf(q.answer))
                    : q.type === 'True/False'
                      ? q.answer[0]
                      : q.answer.slice(0, 1)}
                </span>
                {q.answer}
                {q.explanation && <span className="block mt-1 text-nt3 text-xs">{q.explanation}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
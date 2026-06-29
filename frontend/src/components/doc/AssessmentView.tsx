import { useState } from 'react'
import { chapter1Assessment, type AssessmentQuestion } from '../../mocks/assessmentData'
import { Eye, EyeOff, Download, Play, ChevronDown, Lock, LockOpen } from 'lucide-react'

function Badge({ type, difficulty }: { type: string; difficulty: string }) {
  const diffColors: Record<string, string> = {
    Easy: 'text-ng bg-ngb border-ngbr',
    Medium: 'text-na bg-nab border-nabr',
    Hard: 'text-nr bg-nrb border-nrbr',
  }

  return (
    <div className="flex items-center gap-2">
      <span className="inline-flex items-center px-2 py-0.5 rounded-[5px] text-[9.5px] font-semibold uppercase tracking-wide bg-nblb text-nbl">
        {type}
      </span>
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-[5px] text-[9.5px] font-semibold uppercase tracking-wide border ${diffColors[difficulty] || 'bg-ns3 text-nt2'}`}
      >
        {difficulty}
      </span>
    </div>
  )
}

function MCQOptions({ options }: { options: string[] }) {
  const letters = ['A', 'B', 'C', 'D', 'E', 'F']
  return (
    <div className="flex flex-col gap-2.5 mt-5">
      {options.map((opt, i) => (
        <div
          key={i}
          className="flex items-start gap-3 px-3.5 py-3 rounded-lg bg-nb border border-bdr2 cursor-pointer shadow-[0_1px_2px_rgba(0,0,0,0.28)] hover:bg-ns2 hover:border-bdr2 hover:shadow-[0_4px_14px_rgba(0,0,0,0.34)] hover:-translate-y-px transition-all"
        >
          <span className="w-6 h-6 rounded-md bg-ns3 flex items-center justify-center text-[11px] font-semibold text-nt2 shrink-0">
            {letters[i]}
          </span>
          <span className="text-[13.5px] text-nt2 leading-relaxed pt-0.5">{opt}</span>
        </div>
      ))}
    </div>
  )
}

function TrueFalseOptions() {
  return (
    <div className="flex gap-3 mt-5">
      <button className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg bg-nb border border-bdr2 text-[13.5px] font-medium text-nt2 shadow-[0_1px_2px_rgba(0,0,0,0.28)] hover:bg-ns2 hover:text-nt hover:shadow-[0_4px_14px_rgba(0,0,0,0.34)] hover:-translate-y-px transition-all">
        <span className="text-base">✓</span> True
      </button>
      <button className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg bg-nb border border-bdr2 text-[13.5px] font-medium text-nt2 shadow-[0_1px_2px_rgba(0,0,0,0.28)] hover:bg-ns2 hover:text-nt hover:shadow-[0_4px_14px_rgba(0,0,0,0.34)] hover:-translate-y-px transition-all">
        <span className="text-base">✗</span> False
      </button>
    </div>
  )
}

function FreeResponseLines({ count = 4 }: { count?: number }) {
  return (
    <div className="mt-5">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={`h-9 ${i === 0 ? 'border-t' : ''} border-b border-ns4 flex items-end pb-1.5`}
        >
          {i === 0 && <span className="text-[13px] text-nt4 italic">Write your answer here…</span>}
        </div>
      ))}
      <div className="flex items-start gap-2 mt-4 p-2.5 rounded-lg bg-ns2 border border-bdr2 text-[12px] text-nt2">
        <span className="text-nt3 mt-0.5">ⓘ</span>
        <span>Suggested length: 2–4 sentences.</span>
      </div>
    </div>
  )
}

function QuestionCard({ question, index }: { question: AssessmentQuestion; index: number }) {
  return (
    <div className="bg-ns border border-bdr2 rounded-xl p-5 shadow-[0_1px_2px_rgba(0,0,0,0.28)]">
      <div className="flex items-center justify-between mb-4">
        <span className="text-[11px] font-semibold text-nt3 uppercase tracking-wider">
          Q{index + 1}
        </span>
        <Badge type={question.type} difficulty={question.difficulty} />
      </div>

      <div className="text-[14px] text-nt leading-relaxed mb-5">{question.question}</div>

      {question.type === 'MCQ' && <MCQOptions options={question.options} />}
      {question.type === 'True/False' && <TrueFalseOptions />}
      {!['MCQ', 'True/False'].includes(question.type) && (
        <FreeResponseLines count={question.type === 'Short Answer' ? 3 : 4} />
      )}
    </div>
  )
}

function AnswerKey({ questions, isOpen, onToggle }: { questions: AssessmentQuestion[]; isOpen: boolean; onToggle: () => void }) {
  return (
    <div className="mt-8 border border-bdr2 rounded-xl overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.28)]">
      <div
        onClick={onToggle}
        className="flex items-center gap-3 px-5 py-4 bg-ns2 border-b border-bdr cursor-pointer hover:bg-ns3 transition"
      >
        {isOpen ? (
          <LockOpen size={17} className="text-nbl" />
        ) : (
          <Lock size={17} className="text-nt3" />
        )}
        <span className="text-[13.5px] font-medium text-nt">
          {isOpen ? 'Answer Key' : 'Answers are hidden'}
        </span>
        <span className="text-[10px] text-nt3 bg-ns px-2 py-0.5 rounded-md font-medium">
          Click to toggle
        </span>
        <ChevronDown
          size={15}
          className={`ml-auto text-nt3 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </div>

      {isOpen && (
        <div className="px-5 py-3 space-y-4">
          {questions.map((q, i) => (
            <div key={q.question_id} className="flex items-start gap-4 py-3 border-b border-bdr last:border-none">
              <span className="font-mono text-[11.5px] font-semibold text-nt3 min-w-[24px] pt-1">
                Q{i + 1}
              </span>
              <div className="text-[13px] text-nt2 leading-relaxed">
                <span
                  className={`inline-flex items-center justify-center w-6 h-6 rounded-md border mr-2.5 align-middle text-[11.5px] font-semibold ${
                    q.type === 'True/False' && q.answer === 'False'
                      ? 'bg-nrb border-nrbr text-nr'
                      : 'bg-npb border-npbr text-np'
                  }`}
                >
                  {q.type === 'MCQ'
                    ? String.fromCharCode(65 + q.options.indexOf(q.answer))
                    : q.type === 'True/False'
                      ? q.answer[0]
                      : q.answer.slice(0, 1)}
                </span>
                {q.answer}
                {q.explanation && (
                  <span className="block mt-1 text-nt3 text-[12px]">{q.explanation}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function AssessmentView() {
  const questions = chapter1Assessment
  const [showAnswers, setShowAnswers] = useState(false)

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center px-4 h-[40px] border-b border-bdr bg-ns shrink-0 gap-4">
        <div className="flex-1 flex flex-col justify-center">
          <div className="text-[14px] font-semibold text-nt tracking-tight">
            Ch 01 — Segment Trees
          </div>
          <div className="text-[11px] text-nt3">
            {questions.length} questions · MCQ, True/False, free response
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAnswers(!showAnswers)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-bdr2 bg-transparent text-nt2 text-[10px] hover:bg-ns2 hover:text-nt transition active:scale-98"
          >
            {showAnswers ? <EyeOff size={13} /> : <Eye size={13} />}
            {showAnswers ? 'Hide Key' : 'Reveal Key'}
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-bdr2 bg-transparent text-nt2 text-[10px] hover:bg-ns2 hover:text-nt transition active:scale-98">
            <Download size={13} /> PDF
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-np text-white text-[10px] font-medium shadow-[0_2px_10px_rgba(124,111,212,0.3)] hover:bg-[#8E82E0] hover:shadow-[0_4px_14px_rgba(124,111,212,0.4)] active:scale-98 transition">
            <Play size={13} /> Start Quiz
          </button>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto px-8 py-6 pb-20 space-y-7 scroll-smooth doc-content">
        {/* Section divider — MCQ */}
        <div className="flex items-center gap-3 mt-2">
          <span className="flex-1 h-px bg-bdr" />
          <span className="text-[9.5px] font-semibold text-nt3 uppercase tracking-wider">
            Multiple choice
          </span>
          <span className="flex-1 h-px bg-bdr" />
        </div>

        {questions.filter(q => q.type === 'MCQ').map((q, i) => (
          <QuestionCard key={q.question_id} question={q} index={i} />
        ))}

        {/* Section divider — True/False */}
        <div className="flex items-center gap-3 mt-10">
          <span className="flex-1 h-px bg-bdr" />
          <span className="text-[9.5px] font-semibold text-nt3 uppercase tracking-wider">
            True or false
          </span>
          <span className="flex-1 h-px bg-bdr" />
        </div>

        {questions.filter(q => q.type === 'True/False').map((q, i) => (
          <QuestionCard key={q.question_id} question={q} index={i} />
        ))}

        {/* Section divider — Free response */}
        <div className="flex items-center gap-3 mt-10">
          <span className="flex-1 h-px bg-bdr" />
          <span className="text-[9.5px] font-semibold text-nt3 uppercase tracking-wider">
            Free response
          </span>
          <span className="flex-1 h-px bg-bdr" />
        </div>

        {questions.filter(q => !['MCQ', 'True/False'].includes(q.type)).map((q, i) => (
          <QuestionCard key={q.question_id} question={q} index={i} />
        ))}

        {/* Answer Key */}
        <AnswerKey
          questions={questions}
          isOpen={showAnswers}
          onToggle={() => setShowAnswers(!showAnswers)}
        />
      </div>

      {/* Bottom progress bar */}
      <div className="flex items-center justify-between px-6 py-4 border-t border-bdr bg-ns shrink-0">
        <div>
          <div className="text-[11px] font-medium text-nt3 mb-1">3 of 9 questions answered</div>
          <div className="w-[140px] h-1 bg-ns3 rounded-full overflow-hidden">
            <div className="h-full bg-np rounded-full" style={{ width: '33%' }} />
          </div>
        </div>
      </div>
    </div>
  )
}
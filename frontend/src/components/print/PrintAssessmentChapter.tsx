import { QuestionCard, AnswerKey } from '../doc/assessment-cards'
import type { Question } from '../../stores/useQuizStore'

export function PrintAssessmentChapter({ ch, questions }: { ch: number; questions: Question[] }) {
  return (
    <div className="print-chapter px-8 py-6">
      <h1 className="text-[21px] font-semibold text-nt tracking-tight mb-6">Chapter {ch} — Assessment</h1>
      {questions.length === 0 ? (
        <div className="text-nt3 italic text-sm">No questions available for this chapter.</div>
      ) : (
        <>
          {questions.map((q, i) => (
            <div key={q.id ?? i} className="mb-4">
              <QuestionCard question={q} index={i} />
            </div>
          ))}
          <AnswerKey questions={questions} isOpen={true} onToggle={() => {}} />
        </>
      )}
    </div>
  )
}

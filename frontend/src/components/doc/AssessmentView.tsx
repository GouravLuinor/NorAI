import { useState, useEffect } from 'react'
import { Eye, EyeOff, Download, Play } from 'lucide-react'
import { useChapterStore } from '../../stores/useChapterStore'
import { useQuizStore, fetchQuizQuestions } from '../../stores/useQuizStore'
import { QuestionCard, AnswerKey } from './assessment-cards'
import type { Question } from '../../stores/useQuizStore'
import { useToastStore } from '../../stores/useToastStore'


export function AssessmentView() {
  const activeChapterId = useChapterStore(s => s.activeChapterId)
  const { startQuiz } = useQuizStore()
  const addToast = useToastStore(s => s.addToast)
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(false)
  const [showAnswers, setShowAnswers] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchQuizQuestions(activeChapterId)
      .then((data) => {
        if (!cancelled) { setQuestions(data); setShowAnswers(false); setLoading(false) }
      })
      .catch(() => { if (!cancelled) { setQuestions([]); setLoading(false) } })
    return () => { cancelled = true }
  }, [activeChapterId])

  const handleStartQuiz = async () => {
    const qs = await fetchQuizQuestions(activeChapterId)
    if (qs.length > 0) {
      startQuiz(qs, activeChapterId)
      addToast('Quiz started', 'success')
    }
  }

  if (loading) return <div className="flex-1 flex items-center justify-center text-nt3 text-sm">Loading assessment…</div>
  if (questions.length === 0) return <div className="flex-1 flex items-center justify-center text-nt3 text-sm">Assessment not available for this chapter.</div>

  const mcq = questions.filter(q => q.type === 'MCQ')
  const tf = questions.filter(q => q.type === 'True/False')
  const free = questions.filter(q => !['MCQ', 'True/False'].includes(q.type))

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center px-4 h-[40px] border-b border-bdr bg-ns shrink-0 gap-4">
        <div className="flex-1 flex flex-col justify-center">
          <div className="text-[14px] font-semibold text-nt tracking-tight">Ch {String(activeChapterId).padStart(2, '0')} — Assessment</div>
          <div className="text-[11px] text-nt3">{questions.length} questions · MCQ, True/False, free response</div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowAnswers(!showAnswers)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-bdr2 bg-transparent text-nt2 text-[10px] hover:bg-ns2 hover:text-nt transition active:scale-98">
            {showAnswers ? <EyeOff size={13} /> : <Eye size={13} />}
            {showAnswers ? 'Hide Key' : 'Reveal Key'}
          </button>
          <button onClick={handleStartQuiz} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-np text-white text-[10px] font-medium shadow-[0_2px_10px_rgba(124,111,212,0.3)] hover:bg-[#8E82E0] hover:shadow-[0_4px_14px_rgba(124,111,212,0.4)] active:scale-98 transition">
            <Play size={13} /> Start Quiz
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6 pb-20 space-y-7 scroll-smooth doc-content">
        {mcq.length > 0 && (
          <>
            <div className="flex items-center gap-3 mt-2"><span className="flex-1 h-px bg-bdr" /><span className="text-[9.5px] font-semibold text-nt3 uppercase tracking-wider">Multiple choice</span><span className="flex-1 h-px bg-bdr" /></div>
            {mcq.map((q, i) => <QuestionCard key={q.id ?? i} question={q} index={i} />)}
          </>
        )}
        {tf.length > 0 && (
          <>
            <div className="flex items-center gap-3 mt-10"><span className="flex-1 h-px bg-bdr" /><span className="text-[9.5px] font-semibold text-nt3 uppercase tracking-wider">True or false</span><span className="flex-1 h-px bg-bdr" /></div>
            {tf.map((q, i) => <QuestionCard key={q.id ?? i} question={q} index={i} />)}
          </>
        )}
        {free.length > 0 && (
          <>
            <div className="flex items-center gap-3 mt-10"><span className="flex-1 h-px bg-bdr" /><span className="text-[9.5px] font-semibold text-nt3 uppercase tracking-wider">Free response</span><span className="flex-1 h-px bg-bdr" /></div>
            {free.map((q, i) => <QuestionCard key={q.id ?? i} question={q} index={i} />)}
          </>
        )}
        <AnswerKey questions={questions} isOpen={showAnswers} onToggle={() => setShowAnswers(!showAnswers)} />
      </div>

      <div className="flex items-center justify-between px-6 py-4 border-t border-bdr bg-ns shrink-0">
        <div>
          <div className="text-[11px] font-medium text-nt3 mb-1">{questions.length} questions</div>
          <div className="w-[140px] h-1 bg-ns3 rounded-full overflow-hidden"><div className="h-full bg-np rounded-full" style={{ width: '100%' }} /></div>
        </div>
      </div>
    </div>
  )
}
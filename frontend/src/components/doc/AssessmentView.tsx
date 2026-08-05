import { useState, useEffect } from 'react'
import { Eye, EyeOff, Play } from 'lucide-react'
import { useChapterStore } from '../../stores/useChapterStore'
import { useQuizStore, fetchQuizQuestions, fetchQuizIncomplete } from '../../stores/useQuizStore'
import { useLectureStore } from '../../stores/useLectureStore' 
import { QuestionCard, AnswerKey } from './assessment-cards'
import type { Question } from '../../stores/useQuizStore'
import { PartialContentBadge } from '../ui/PartialContentBadge'
import { useToastStore } from '../../stores/useToastStore'
import { Button } from '../ui/Button'


export function AssessmentView() {
  const activeChapterId = useChapterStore(s => s.activeChapterId)
  const { startQuiz } = useQuizStore()
  const addToast = useToastStore(s => s.addToast)
  const lectureId = useLectureStore(s => s.activeLectureId) 
  const [questions, setQuestions] = useState<Question[]>([])
  const [incomplete, setIncomplete] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showAnswers, setShowAnswers] = useState(false)

useEffect(() => {
  if (!lectureId) return  // wait for Workspace to set it
  let cancelled = false
  setLoading(true)
  fetchQuizQuestions(activeChapterId, lectureId)
    .then((data) => {
      if (!cancelled) { setQuestions(data); setShowAnswers(false); setLoading(false) }
    })
    .catch(() => { if (!cancelled) { setQuestions([]); setLoading(false) } })
  fetchQuizIncomplete(activeChapterId, lectureId)
    .then((flag) => { if (!cancelled) setIncomplete(flag) })
    .catch(() => { if (!cancelled) setIncomplete(false) })
  return () => { cancelled = true }
}, [activeChapterId, lectureId])

const handleStartQuiz = async () => {
  if (!lectureId) return
  const qs = await fetchQuizQuestions(activeChapterId, lectureId)
  if (qs.length > 0) {
    startQuiz(qs, activeChapterId)
    addToast('Quiz started', 'success')
  }
}

  if (loading) return <div className="flex-1 flex items-center justify-center text-nt3 text-sm">Loading assessment…</div>
  if (questions.length === 0) return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 text-nt3 text-sm">
      <div>Assessment not available for this chapter.</div>
      {incomplete && <PartialContentBadge />}
    </div>
  )

  const tf = questions.filter(q => q.type === 'True/False')
  const hasOptions = (q: Question) => Array.isArray(q.options) && q.options.length > 0
  const choice = questions.filter(q => q.type !== 'True/False' && hasOptions(q))
  const free = questions.filter(q => q.type !== 'True/False' && !hasOptions(q))

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center px-4 h-[40px] border-b border-bdr bg-ns shrink-0 gap-4">
        <div className="flex-1 flex flex-col justify-center">
          <div className="text-sm font-semibold text-nt tracking-tight">Ch {String(activeChapterId).padStart(2, '0')} — Assessment</div>
          <div className="text-11 text-nt3">{questions.length} questions · MCQ, True/False, free response</div>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => setShowAnswers(!showAnswers)} variant="outline" className="gap-1.5 px-3 py-1.5 rounded-sm text-2xs active:translate-y-[1px] active:shadow-none">
            {showAnswers ? <EyeOff size={13} strokeWidth={1.5} /> : <Eye size={13} strokeWidth={1.5} />}
            {showAnswers ? 'Hide Key' : 'Reveal Key'}
          </Button>
          <Button variant="primarySoft" onClick={handleStartQuiz} className="gap-1.5 px-3 py-1.5 rounded-sm text-2xs">
            <Play size={13} strokeWidth={1.5} /> Start Quiz
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-8 py-6 pb-20 space-y-7 scroll-smooth doc-content">
        {incomplete && <PartialContentBadge className="mb-2" />}
        {choice.length > 0 && (
          <>
            <div className="flex items-center gap-3 mt-2"><span className="flex-1 h-px bg-bdr" /><span className="text-3xs font-semibold text-nt3 uppercase tracking-wider">Multiple choice</span><span className="flex-1 h-px bg-bdr" /></div>
            {choice.map((q, i) => <QuestionCard key={q.id ?? i} question={q} index={i} />)}
          </>
        )}
        {tf.length > 0 && (
          <>
            <div className="flex items-center gap-3 mt-10"><span className="flex-1 h-px bg-bdr" /><span className="text-3xs font-semibold text-nt3 uppercase tracking-wider">True or false</span><span className="flex-1 h-px bg-bdr" /></div>
            {tf.map((q, i) => <QuestionCard key={q.id ?? i} question={q} index={i} />)}
          </>
        )}
        {free.length > 0 && (
          <>
            <div className="flex items-center gap-3 mt-10"><span className="flex-1 h-px bg-bdr" /><span className="text-3xs font-semibold text-nt3 uppercase tracking-wider">Free response</span><span className="flex-1 h-px bg-bdr" /></div>
            {free.map((q, i) => <QuestionCard key={q.id ?? i} question={q} index={i} />)}
          </>
        )}
        <AnswerKey questions={questions} isOpen={showAnswers} onToggle={() => setShowAnswers(!showAnswers)} />
      </div>

      <div className="flex items-center justify-between px-6 py-4 border-t border-bdr bg-ns shrink-0">
        <div>
          <div className="text-11 font-medium text-nt3 mb-1">{questions.length} questions</div>
          <div className="w-[140px] h-1 bg-ns3 rounded-full overflow-hidden"><div className="h-full bg-np rounded-full" style={{ width: '100%' }} /></div>
        </div>
      </div>
    </div>
  )
}
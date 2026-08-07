import { useState, useEffect } from 'react'
import { Eye, EyeOff, Play, History, RefreshCw } from 'lucide-react'
import { useChapterStore } from '../../stores/useChapterStore'
import { useQuizStore, fetchQuizQuestions, fetchQuizIncomplete, explainQuizQuestion, fetchQuizAttempts, fetchQuizMissed, type QuizDifficulty, type QuizCitation, type QuizAttempt } from '../../stores/useQuizStore'
import { useLectureStore } from '../../stores/useLectureStore' 
import { QuestionCard, AnswerKey } from './assessment-cards'
import type { Question } from '../../stores/useQuizStore'
import { PartialContentBadge } from '../ui/PartialContentBadge'
import { useToastStore } from '../../stores/useToastStore'
import { Button } from '../ui/Button'
import { CitationBox } from '../quiz/CitationBox'
import { scrollToHeading } from '../../lib/cite'

const DIFFICULTY_OPTIONS: Array<{ label: string; value: QuizDifficulty | 'All' }> = [
  { label: 'All', value: 'All' },
  { label: 'Easy', value: 'Easy' },
  { label: 'Medium', value: 'Medium' },
  { label: 'Hard', value: 'Hard' },
]

export function AssessmentView() {
  const activeChapterId = useChapterStore(s => s.activeChapterId)
  const { startQuiz, createAttempt } = useQuizStore()
  const addToast = useToastStore(s => s.addToast)
  const lectureId = useLectureStore(s => s.activeLectureId) 
  const [viewMode, setViewMode] = useState<'questions' | 'history'>('questions')
  const [questions, setQuestions] = useState<Question[]>([])
  const [attempts, setAttempts] = useState<QuizAttempt[]>([])
  const [incomplete, setIncomplete] = useState(false)
  const [loading, setLoading] = useState(false)
  const [showAnswers, setShowAnswers] = useState(false)
  const [difficulty, setDifficulty] = useState<QuizDifficulty | 'All'>('All')
  const [citations, setCitations] = useState<Record<number, QuizCitation | null>>({})
  const [citingIds, setCitingIds] = useState<Record<number, boolean>>({})
  const [citeErrors, setCiteErrors] = useState<Record<number, string>>({})

  const handleExplain = async (question: Question) => {
    const qid = question.id ?? -1
    if (citingIds[qid]) return
    setCitingIds((s) => ({ ...s, [qid]: true }))
    setCiteErrors((s) => ({ ...s, [qid]: '' }))
    setCitations((s) => ({ ...s, [qid]: null }))
    try {
      const result = await explainQuizQuestion(question.question, lectureId || 'default', activeChapterId)
      setCitations((s) => ({ ...s, [qid]: result }))
    } catch {
      setCiteErrors((s) => ({ ...s, [qid]: 'Could not fetch a citation — please try again.' }))
    } finally {
      setCitingIds((s) => ({ ...s, [qid]: false }))
    }
  }

  useEffect(() => {
    if (!lectureId) return
    let cancelled = false
    setLoading(true)
    fetchQuizQuestions(activeChapterId, lectureId, difficulty === 'All' ? undefined : difficulty)
      .then((data) => {
        if (!cancelled) { setQuestions(data); setShowAnswers(false); setLoading(false) }
      })
      .catch(() => { if (!cancelled) { setQuestions([]); setLoading(false) } })
    fetchQuizIncomplete(activeChapterId, lectureId)
      .then((flag) => { if (!cancelled) setIncomplete(flag) })
      .catch(() => { if (!cancelled) setIncomplete(false) })
    setCitations({})
    setCitingIds({})
    setCiteErrors({})
    return () => { cancelled = true }
  }, [activeChapterId, lectureId, difficulty])

  useEffect(() => {
    if (!lectureId) return
    fetchQuizAttempts(lectureId, activeChapterId)
      .then(setAttempts)
      .catch(() => setAttempts([]))
  }, [lectureId, activeChapterId, viewMode])

  useEffect(() => {
    setDifficulty('All')
  }, [lectureId])

  const resetFilter = (value: QuizDifficulty | 'All') => {
    setDifficulty(value)
    setShowAnswers(false)
  }

  const handleStartQuiz = async () => {
    if (!lectureId) return
    const difficultyParam = difficulty === 'All' ? undefined : difficulty
    const qs = await fetchQuizQuestions(activeChapterId, lectureId, difficultyParam)
    if (qs.length > 0) {
      await createAttempt(qs, activeChapterId, difficultyParam)
      addToast('Quiz started', 'success')
    }
  }

  const handleRetakeMissed = async (attempt: QuizAttempt) => {
    if (!lectureId) return
    const missedIds = await fetchQuizMissed(attempt.id, lectureId)
    const allQs = await fetchQuizQuestions(activeChapterId, lectureId)
    const missedQs = allQs.filter((q) => missedIds.includes(String(q.id)))
    if (missedQs.length > 0) {
      await createAttempt(missedQs, activeChapterId, (attempt.difficulty as QuizDifficulty) || undefined)
      addToast(`Retaking ${missedQs.length} missed question(s)`, 'info')
    } else {
      addToast('No missed questions found for this attempt', 'info')
    }
  }

  if (loading) return <div className="flex-1 flex items-center justify-center text-nt3 text-sm">Loading assessment…</div>

  const tf = questions.filter(q => q.type === 'True/False')
  const hasOptions = (q: Question) => Array.isArray(q.options) && q.options.length > 0
  const choice = questions.filter(q => q.type !== 'True/False' && hasOptions(q))
  const free = questions.filter(q => q.type !== 'True/False' && !hasOptions(q))

  const renderCard = (q: Question, i: number) => {
    const qid = q.id ?? i
    const citation = citations[qid]
    const citing = citingIds[qid]
    const citeError = citeErrors[qid]
    return (
      <div key={qid}>
        <QuestionCard question={q} index={i} onExplain={handleExplain} />
        {citeError && <div className="mt-1 text-2xs text-nr">{citeError}</div>}
        {citation && (
          <CitationBox
            citation={citation}
            loading={false}
            onScroll={() => scrollToHeading(citation.heading_path || citation.source || '', citation.chapter_id)}
          />
        )}
        {citing && !citation && <CitationBox citation={null} loading />}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center px-4 h-[40px] border-b border-bdr bg-ns shrink-0 gap-4">
        <div className="flex-1 flex flex-col justify-center">
          <div className="text-sm font-semibold text-nt tracking-tight">Ch {String(activeChapterId).padStart(2, '0')} — Assessment</div>
          <div className="text-11 text-nt3">{questions.length} question{questions.length === 1 ? '' : 's'}{difficulty !== 'All' ? ` · ${difficulty}` : ''}</div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 p-0.5 rounded-md bg-ns2 border border-bdr2" role="group">
            <button
              type="button"
              onClick={() => setViewMode('questions')}
              className={`px-2.5 py-1 rounded-[5px] text-2xs font-medium transition ${
                viewMode === 'questions' ? 'bg-np text-ns shadow-sm' : 'text-nt3 hover:text-nt2'
              }`}
            >
              Questions
            </button>
            <button
              type="button"
              onClick={() => setViewMode('history')}
              className={`px-2.5 py-1 rounded-[5px] text-2xs font-medium transition flex items-center gap-1 ${
                viewMode === 'history' ? 'bg-np text-ns shadow-sm' : 'text-nt3 hover:text-nt2'
              }`}
            >
              <History size={12} />
              <span>History ({attempts.length})</span>
            </button>
          </div>

          {viewMode === 'questions' && (
            <>
              <div className="flex items-center gap-1 p-0.5 rounded-md bg-ns2 border border-bdr2" role="group" aria-label="Question difficulty">
                {DIFFICULTY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => resetFilter(opt.value)}
                    className={`px-2 py-1 rounded-[5px] text-2xs font-medium transition ${difficulty === opt.value ? 'bg-np text-ns shadow-sm' : 'text-nt3 hover:text-nt2'}`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>

              <Button onClick={() => setShowAnswers(!showAnswers)} variant="outline" className="gap-1.5 px-3 py-1.5 rounded-sm text-2xs active:translate-y-[1px]">
                {showAnswers ? <EyeOff size={13} strokeWidth={1.5} /> : <Eye size={13} strokeWidth={1.5} />}
                {showAnswers ? 'Hide Key' : 'Reveal Key'}
              </Button>
            </>
          )}

          <Button variant="primarySoft" onClick={handleStartQuiz} className="gap-1.5 px-3 py-1.5 rounded-sm text-2xs">
            <Play size={13} strokeWidth={1.5} /> Start Quiz
          </Button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto px-8 py-6 pb-20 space-y-7 scroll-smooth doc-content">
        {viewMode === 'history' ? (
          <div className="space-y-4 max-w-2xl mx-auto">
            <h3 className="text-sm font-semibold text-nt mb-3">Quiz Attempts History</h3>
            {attempts.length === 0 ? (
              <div className="p-8 text-center bg-ns border border-bdr2 rounded-xl text-nt3 text-sm">
                No quiz attempts recorded for this chapter yet.
              </div>
            ) : (
              attempts.map((att) => {
                const pct = att.total > 0 ? Math.round((att.score / att.total) * 100) : 0
                const dateStr = att.started_at
                  ? new Date(att.started_at).toLocaleString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : 'Recent'

                return (
                  <div
                    key={att.id}
                    className="p-4 bg-ns border border-bdr2 rounded-xl flex items-center justify-between shadow-ev1"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-nt font-mono">
                          Score: {att.score} / {att.total} ({pct}%)
                        </span>
                        <span className="px-2 py-0.5 text-3xs font-medium rounded-full bg-ns2 text-nt2 border border-bdr2">
                          {att.difficulty || 'All'}
                        </span>
                      </div>
                      <p className="text-2xs text-nt3">Attempted on {dateStr}</p>
                    </div>

                    <div className="flex items-center gap-2">
                      {pct < 100 && (
                        <Button
                          variant="surface"
                          onClick={() => handleRetakeMissed(att)}
                          className="gap-1.5 px-3 py-1.5 text-xs bg-ns2 hover:bg-ns3 text-nt"
                        >
                          <RefreshCw size={12} /> Retake Missed
                        </Button>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        ) : questions.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 text-nt3 text-sm py-12">
            <div>{difficulty === 'All' ? 'Assessment not available for this chapter.' : `No ${difficulty} questions in this chapter.`}</div>
            {incomplete && <PartialContentBadge />}
            {difficulty !== 'All' && (
              <Button variant="outline" className="px-3 py-1.5 rounded-sm text-2xs" onClick={() => setDifficulty('All')}>
                Show all questions
              </Button>
            )}
          </div>
        ) : (
          <>
            {incomplete && <PartialContentBadge className="mb-2" />}
            {choice.length > 0 && (
              <section className="space-y-4">
                <h3 className="spec-label tracking-wider">Multiple Choice</h3>
                <div className="space-y-4">{choice.map((q, i) => renderCard(q, i + 1))}</div>
              </section>
            )}
            {tf.length > 0 && (
              <section className="space-y-4">
                <h3 className="spec-label tracking-wider">True / False</h3>
                <div className="space-y-4">{tf.map((q, i) => renderCard(q, choice.length + i + 1))}</div>
              </section>
            )}
            {free.length > 0 && (
              <section className="space-y-4">
                <h3 className="spec-label tracking-wider">Short Answer & Conceptual</h3>
                <div className="space-y-4">{free.map((q, i) => renderCard(q, choice.length + tf.length + i + 1))}</div>
              </section>
            )}
            {showAnswers && <AnswerKey questions={questions} isOpen={showAnswers} onToggle={() => setShowAnswers(!showAnswers)} />}
          </>
        )}
      </div>
    </div>
  )
}
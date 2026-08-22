import { useState, useEffect } from 'react'
import { useQuizStore, type Question, evaluateQuiz, explainQuizQuestion, fetchQuizMissed, type QuizCitation } from '../../stores/useQuizStore'
import { useChapterStore } from '../../stores/useChapterStore'
import { useLectureStore } from '../../stores/useLectureStore'
import { Check, X, RotateCcw, BookOpen, AlertTriangle, Quote, RefreshCw } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { CitationBox } from './CitationBox'
import { QuizSkeleton } from '../ui/SkeletonCard'
import { scrollToHeading } from '../../lib/cite'
import { FOCUS_RING } from '../ui/shared'

export function QuizPanel() {
  // P3.2: narrow selectors — the quiz store also carries evaluation/streaming
  // state; subscribing wholesale cascades re-renders into this panel.
  const questions = useQuizStore((s) => s.questions)
  const currentIndex = useQuizStore((s) => s.currentIndex)
  const confidences = useQuizStore((s) => s.confidences)
  const score = useQuizStore((s) => s.score)
  const evaluation = useQuizStore((s) => s.evaluation)
  const isQuizLoading = useQuizStore((s) => s.isQuizLoading)
  const quizStartTime = useQuizStore((s) => s.quizStartTime)
  const submitAnswer = useQuizStore((s) => s.submitAnswer)
  const nextQuestion = useQuizStore((s) => s.nextQuestion)
  const endQuiz = useQuizStore((s) => s.endQuiz)
  const finishAttempt = useQuizStore((s) => s.finishAttempt)
  const reset = useQuizStore((s) => s.reset)
  const retakeQuiz = useQuizStore((s) => s.retakeQuiz)
  const setConfidence = useQuizStore((s) => s.setConfidence)

  const setDocTab = useChapterStore((s) => s.setDocTab)

  const [selectedAnswer, setSelectedAnswer] = useState('')
  const [showFeedback, setShowFeedback] = useState(false)
  const [confidence, setConfidenceLocal] = useState('')
  const [evaluating, setEvaluating] = useState(false)
  const [evaluateError, setEvaluateError] = useState('')
  const [citation, setCitation] = useState<QuizCitation | null>(null)
  const [citing, setCiting] = useState(false)
  const [citeError, setCiteError] = useState('')

  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'

  // Reset local state when a new quiz starts (retake or fresh)
  useEffect(() => {
    if (currentIndex === 0 && questions.length > 0) {
      setEvaluating(false)
      setSelectedAnswer('')
      setShowFeedback(false)
      setConfidenceLocal('')
      setEvaluateError('')
      setCitation(null)
      setCiting(false)
      setCiteError('')
    }
  }, [currentIndex, questions.length])

  // Clear the per-question citation whenever the active question changes.
  useEffect(() => {
    setCitation(null)
    setCiting(false)
    setCiteError('')
  }, [currentIndex, questions])

  const handleExplain = async () => {
    if (citing) return
    const target = questions[currentIndex]
    if (!target) return
    setCiting(true)
    setCiteError('')
    setCitation(null)
    try {
      const result = await explainQuizQuestion(target.question, lectureId, useQuizStore.getState().quizChapterId)
      setCitation(result)
    } catch {
      setCiteError('Could not fetch a citation — please try again.')
    } finally {
      setCiting(false)
    }
  }

  // ── Evaluation Screen ────────────────────────────────────────────────────
  if (evaluation) {
    const elapsed = quizStartTime ? Math.round((Date.now() - quizStartTime) / 1000) : 0
    const mins = Math.floor(elapsed / 60)
    const secs = elapsed % 60
    const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`

    const finalScore = evaluation.final_score ?? score
    // Fallback: if LLM sent a percentage instead of count, correct it
    const cappedScore = finalScore > evaluation.total_questions
      ? Math.round((finalScore / 100) * evaluation.total_questions)
      : finalScore
    const percentage = evaluation.total_questions > 0
      ? Math.round((cappedScore / evaluation.total_questions) * 100)
      : 0

    const confidenceCount = confidences.filter(Boolean).length
    const confidenceLabel = confidenceCount > 0
      ? `${confidenceCount} of ${questions.length}`
      : 'N/A'

    const handleReviewNotes = () => {
      setDocTab('notes')
      reset()
    }

    const handleReviewMissed = async () => {
      const state = useQuizStore.getState()
      if (!state.attemptId) return
      const lectureId = useLectureStore.getState().activeLectureId || 'default'
      const missedIds = await fetchQuizMissed(state.attemptId, lectureId)
      if (missedIds.length === 0) return
      const missedQuestions = state.questions.filter((q) => missedIds.includes(String(q.id)))
      if (missedQuestions.length > 0) {
        state.startQuiz(missedQuestions, state.quizChapterId, state.quizDifficulty)
      }
    }

    return (
      <div className="flex flex-col h-full">
        <div className="flex-1 overflow-y-auto doc-content px-6 py-8">
          <div className="flex flex-col items-center">
            {/* Score ring */}
            <div className="relative w-24 h-24 mb-5">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15.9155" fill="none" stroke="var(--color-ns3)" strokeWidth="3" />
                <circle cx="18" cy="18" r="15.9155" fill="none" stroke="var(--color-np)" strokeWidth="3"
                  strokeDasharray={`${percentage}, 100`} strokeLinecap="round" />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center text-2xl font-bold text-nt font-mono">
                {percentage}<span className="text-xs">%</span>
              </div>
            </div>

            <h2 className="text-xl font-semibold text-nt mb-1 tracking-tight">
              {percentage >= 80 ? 'Great work!' : percentage >= 50 ? 'Good effort' : 'Keep studying'}
            </h2>
            <p className="text-sm text-nt3 mb-8">
              You scored {cappedScore} out of {evaluation.total_questions} correct.
            </p>

            {/* Breakdown grid */}
            <div className="grid grid-cols-3 gap-4 w-full max-w-md mb-8">
              <div className="bg-nb border border-bdr2 rounded-xl p-4 flex flex-col items-center gap-1.5 shadow-ev1">
                <div className="text-lg font-bold font-mono text-ng">{percentage}%</div>
                <div className="text-2xs text-nt3 uppercase tracking-wider font-semibold">Accuracy</div>
              </div>
              <div className="bg-nb border border-bdr2 rounded-xl p-4 flex flex-col items-center gap-1.5 shadow-ev1">
                <div className="text-lg font-bold font-mono text-nt">{timeStr}</div>
                <div className="text-2xs text-nt3 uppercase tracking-wider font-semibold">Time</div>
              </div>
              <div className="bg-nb border border-bdr2 rounded-xl p-4 flex flex-col items-center gap-1.5 shadow-ev1">
                <div className="text-lg font-bold font-mono text-nbl">{confidenceLabel}</div>
                <div className="spec-label">Confidence</div>
              </div>
            </div>

            {/* Per‑question feedback */}
            {evaluation.per_question_feedback.length > 0 && (
              <div className="w-full max-w-md mb-6 space-y-3">
                {evaluation.per_question_feedback.map((fb) => (
                  <div key={fb.question_number} className="bg-nb border border-bdr2 rounded-lg p-4 shadow-ev1">
                    <div className="flex items-start gap-2">
                      <div className="w-5 h-5 rounded-sm bg-npf flex items-center justify-center text-2xs font-bold text-npfg shrink-0 mt-0.5">
                        {fb.question_number}
                      </div>
                      <p className="text-xs text-nt2 leading-relaxed">{fb.remark}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Nora overall summary */}
            <div className="flex items-start gap-3 w-full max-w-md pt-6 border-t border-bdr mb-8">
              <div className="w-7 h-7 rounded-sm bg-npf flex items-center justify-center text-xs font-bold text-npfg shrink-0 mt-0.5 shadow-ev1">
                N
              </div>
              <p className="text-sm text-nt2 leading-relaxed">{evaluation.overall_insights}</p>
            </div>

            {/* Actions */}
            <div className="flex flex-col gap-2 w-full max-w-md pb-4">
              <div className="flex gap-3 w-full">
                <Button
                  variant="surface"
                  onClick={retakeQuiz}
                  className="flex-1 gap-2 py-2.5 rounded-lg text-sm bg-nb hover:bg-ns2 hover:shadow-ev2"
                >
                  <RotateCcw size={14} strokeWidth={1.5} /> Retake
                </Button>
                {percentage < 100 && (
                  <Button
                    variant="surface"
                    onClick={handleReviewMissed}
                    className="flex-1 gap-2 py-2.5 rounded-lg text-sm bg-ns2 hover:bg-ns3 text-nt"
                  >
                    <RefreshCw size={14} strokeWidth={1.5} /> Review Missed
                  </Button>
                )}
              </div>
              <Button
                variant="primary"
                onClick={handleReviewNotes}
                className="w-full gap-2 py-2.5 rounded-md text-sm"
              >
                <BookOpen size={14} strokeWidth={1.5} /> Review Notes
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ── Quiz Active (questions view) ─────────────────────────────────────────
  if (isQuizLoading) {
    return <QuizSkeleton />
  }

  if (questions.length === 0) {
    return <div className="flex-1 flex items-center justify-center text-nt3 text-sm">No quiz questions loaded.</div>
  }

  const q: Question = questions[currentIndex]
  const isAnswered = showFeedback
  const isAutoGraded = q.type === 'MCQ' || q.type === 'True/False'
  const isCorrect = isAutoGraded && selectedAnswer.trim().toLowerCase() === q.answer.trim().toLowerCase()

  const handleSelectAnswer = (ans: string) => {
    if (isAnswered) return
    setSelectedAnswer(ans)
    if (isAutoGraded) {
      setShowFeedback(true)
      submitAnswer(ans)
    } else {
      submitAnswer(ans)
      setSelectedAnswer('')
      if (currentIndex === questions.length - 1) {
        finishQuiz()
      } else {
        nextQuestion()
      }
    }
  }

  const finishQuiz = async () => {
    setEvaluating(true)
    setEvaluateError('')
    // Pull the LATEST state from the store to avoid stale closure
    const currentState = useQuizStore.getState()
    const payload = currentState.questions.map((q, i) => ({
      ...q,
      user_answer: currentState.answers[i] || '',
    }))
    try {
      const result = await evaluateQuiz(payload, quizStartTime!, currentState.confidences)
      if (result) {
        await finishAttempt(result)
        endQuiz(result)
      } else {
        setEvaluateError('Evaluation came back empty — please retry.')
      }
    } catch {
      setEvaluateError('Evaluation failed — please retry.')
    } finally {
      setEvaluating(false)
    }
  }

  const handleNext = () => {
    if (confidence) setConfidence(confidence)
    setSelectedAnswer('')
    setShowFeedback(false)
    setConfidenceLocal('')
    if (currentIndex === questions.length - 1) {
      finishQuiz()
    } else {
      nextQuestion()
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto doc-content px-6 py-6">
        <div className="flex items-center gap-1.5 mb-6">
          {questions.map((_, i) => (
            <div key={i} className={`flex-1 max-w-[16px] h-1.5 rounded-sm ${i < currentIndex ? 'bg-nt3' : i === currentIndex ? 'bg-np animate-pulse' : 'bg-ns3'}`} />
          ))}
        </div>

        <div className="flex items-center gap-2 mb-4">
          <span className="px-2 py-0.5 rounded text-2xs font-semibold uppercase bg-nblb text-nbl">{q.type}</span>
          <Badge tone="default">{q.difficulty || 'Medium'}</Badge>
        </div>

        <p className="text-15 text-nt leading-relaxed mb-6">{q.question}</p>

        {q.type === 'MCQ' && (
          <div className="space-y-3">
            {q.options?.map((opt, i) => {
              const letter = String.fromCharCode(65 + i)
              const isSelected = selectedAnswer === opt
              let stateClass = ''
              if (showFeedback) {
                if (opt === q.answer) stateClass = 'bg-ngb border-ngbr'
                else if (isSelected) stateClass = 'bg-nrb border-nrbr'
              }
              return (
                <button key={opt} onClick={() => handleSelectAnswer(opt)} disabled={isAnswered}
                  aria-pressed={isSelected}
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border border-bdr2 bg-nb text-left transition ${FOCUS_RING} active:scale-[0.98] disabled:pointer-events-none disabled:opacity-60 ${isSelected && !showFeedback ? 'bg-ns3 border-np' : 'hover:bg-ns2 hover:border-bdr'} ${stateClass}`}>
                  <span className={`w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold tabular-nums ${showFeedback && opt === q.answer ? 'bg-ng text-npfg' : showFeedback && isSelected ? 'bg-nr text-npfg' : 'bg-ns3 text-nt2'}`}>{letter}</span>
                  <span className="text-sm text-nt2">{opt}</span>
                  {showFeedback && opt === q.answer && <Check size={16} strokeWidth={1.5} className="ml-auto text-ng" />}
                  {showFeedback && isSelected && opt !== q.answer && <X size={16} strokeWidth={1.5} className="ml-auto text-nr" />}
                </button>
              )
            })}
          </div>
        )}

        {q.type === 'True/False' && (
          <div className="flex gap-3">
            {['True', 'False'].map((val) => {
              const isSelected = selectedAnswer === val
              let stateClass = ''
              if (showFeedback) {
                if (val === q.answer) stateClass = 'bg-ngb border-ngbr text-ng'
                else if (isSelected) stateClass = 'bg-nrb border-nrbr text-nr'
              }
              return (
                <button key={val} onClick={() => handleSelectAnswer(val)} disabled={isAnswered}
                  aria-pressed={isSelected}
                  className={`flex-1 py-3 rounded-lg border border-bdr2 bg-nb text-sm font-medium text-nt2 transition ${FOCUS_RING} active:scale-[0.98] disabled:pointer-events-none disabled:opacity-60 ${isSelected && !showFeedback ? 'bg-ns3 border-np' : 'hover:bg-ns2'} ${stateClass}`}>
                  {val}
                </button>
              )
            })}
          </div>
        )}

        {!isAutoGraded && (
          <div className="space-y-4">
            <textarea name="quiz-answer" aria-label="Your answer" className={`w-full h-24 bg-nb border border-bdr2 rounded-lg p-3 text-sm text-nt resize-none focus:border-np ${FOCUS_RING}`}
              placeholder="Type your answer…" value={selectedAnswer} onChange={(e) => setSelectedAnswer(e.target.value)} disabled={isAnswered} />
            {!isAnswered && (
              <Button
                variant="primary"
                onClick={() => handleSelectAnswer(selectedAnswer)}
                disabled={!selectedAnswer.trim()}
                className="px-6 py-2 rounded-md text-sm disabled:opacity-50"
              >
                Submit Answer
              </Button>
            )}
          </div>
        )}

        {showFeedback && isAutoGraded && (
          <div role="status" className={`mt-5 p-4 rounded-lg border ${isCorrect ? 'bg-ngb border-ngbr' : 'bg-nrb border-nrbr'}`}>
            <div className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-sm bg-npf flex items-center justify-center text-2xs font-bold text-npfg shrink-0 mt-0.5">N</div>
              <div className="text-sm text-nt2">
                {isCorrect ? `Correct! ${q.explanation}` : `Incorrect. The correct answer is ${q.answer}. ${q.explanation}`}
              </div>
            </div>
          </div>
        )}

        {showFeedback && isAutoGraded && (
          <div className="mt-3">
            <button
              type="button"
              onClick={handleExplain}
              disabled={citing}
              className={`inline-flex items-center gap-1.5 text-2xs font-medium text-nbl hover:text-np bg-transparent border-none cursor-pointer disabled:opacity-60 ${FOCUS_RING}`}
            >
              <Quote size={12} strokeWidth={1.5} />
              {citing ? 'Finding source…' : 'Explain · where is this in the notes?'}
            </button>
            {citeError && <div className="mt-1 text-2xs text-nr">{citeError}</div>}
            {citation && (
              <CitationBox
                citation={citation}
                loading={citing}
                onScroll={() => scrollToHeading(citation.heading_path || citation.source || '', citation.chapter_id)}
              />
            )}
          </div>
        )}

        {showFeedback && isAutoGraded && !evaluating && (
          <div className="mt-5 pt-5 border-t border-dashed border-bdr flex items-center gap-2 flex-wrap">
            <span className="text-xs text-nt3 font-medium mr-2">How confident were you?</span>
            {['Guess', 'Unsure', 'Confident', 'Very Confident'].map((lvl) => (
              <Button key={lvl} variant="outline" onClick={() => setConfidenceLocal(lvl)} aria-pressed={confidence === lvl}
                className={`px-3 py-1 rounded-md text-xs ${confidence === lvl ? 'bg-npb border-npbr text-np' : 'bg-transparent border-bdr2'}`}>
                {lvl}
              </Button>
            ))}
          </div>
        )}

        {showFeedback && isAutoGraded && !evaluating && (
          <div className="mt-6 flex justify-end">
            <Button
              variant="primary"
              onClick={handleNext}
              className="px-6 py-2 rounded-md text-sm"
            >
              {currentIndex < questions.length - 1 ? 'Next Question' : 'Finish Quiz'}
            </Button>
          </div>
        )}

        {evaluating && (
          <div role="status" className="mt-8 flex flex-col items-center gap-2 text-nt3 text-sm">
            <span className="h-4 w-4 rounded-full border-2 border-ns3 border-t-np animate-spin" aria-hidden="true" />
            Evaluating your answers…
          </div>
        )}

        {evaluateError && !evaluating && (
          <div
            role="status"
            className="mt-6 p-4 rounded-lg border border-nrbr bg-nrb text-nt2 text-sm flex items-start gap-3"
          >
            <AlertTriangle size={16} strokeWidth={1.5} className="text-nr shrink-0 mt-0.5" />
            <div>
              <p>{evaluateError}</p>
              <Button variant="ghost" className="mt-2 px-0" onClick={finishQuiz}>
                Retry evaluation
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
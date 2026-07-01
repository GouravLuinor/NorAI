import { useState, useEffect } from 'react'
import { useQuizStore, type Question, evaluateQuiz } from '../../stores/useQuizStore'
import { useChapterStore } from '../../stores/useChapterStore'
import { Check, X, RotateCcw, BookOpen } from 'lucide-react'

export function QuizPanel() {
  const {
    questions,
    currentIndex,
    confidences,
    score,
    evaluation,
    quizStartTime,
    submitAnswer,
    nextQuestion,
    endQuiz,
    reset,
    retakeQuiz,
    setConfidence,
  } = useQuizStore()

  const { setDocTab } = useChapterStore()

  const [selectedAnswer, setSelectedAnswer] = useState('')
  const [showFeedback, setShowFeedback] = useState(false)
  const [confidence, setConfidenceLocal] = useState('')
  const [evaluating, setEvaluating] = useState(false)

  // Reset local state when a new quiz starts (retake or fresh)
  useEffect(() => {
    if (currentIndex === 0 && questions.length > 0) {
      setEvaluating(false)
      setSelectedAnswer('')
      setShowFeedback(false)
      setConfidenceLocal('')
    }
  }, [currentIndex, questions.length])

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
              <div className="bg-nb border border-bdr2 rounded-xl p-4 flex flex-col items-center gap-1.5 shadow-sm">
                <div className="text-lg font-bold font-mono text-ng">{percentage}%</div>
                <div className="text-[10px] text-nt3 uppercase tracking-wider font-semibold">Accuracy</div>
              </div>
              <div className="bg-nb border border-bdr2 rounded-xl p-4 flex flex-col items-center gap-1.5 shadow-sm">
                <div className="text-lg font-bold font-mono text-nt">{timeStr}</div>
                <div className="text-[10px] text-nt3 uppercase tracking-wider font-semibold">Time</div>
              </div>
              <div className="bg-nb border border-bdr2 rounded-xl p-4 flex flex-col items-center gap-1.5 shadow-sm">
                <div className="text-lg font-bold font-mono text-nbl">{confidenceLabel}</div>
                <div className="text-[10px] text-nt3 uppercase tracking-wider font-semibold">Confidence</div>
              </div>
            </div>

            {/* Per‑question feedback */}
            {evaluation.per_question_feedback.length > 0 && (
              <div className="w-full max-w-md mb-6 space-y-3">
                {evaluation.per_question_feedback.map((fb) => (
                  <div key={fb.question_number} className="bg-nb border border-bdr2 rounded-lg p-3.5 shadow-sm">
                    <div className="flex items-start gap-2.5">
                      <div className="w-5 h-5 rounded-md bg-gradient-to-br from-np to-nbl flex items-center justify-center text-[10px] font-bold text-white shrink-0 mt-0.5">
                        {fb.question_number}
                      </div>
                      <p className="text-xs text-nt2 leading-relaxed">{fb.remark}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Nora overall summary */}
            <div className="flex items-start gap-3.5 w-full max-w-md pt-6 border-t border-bdr mb-8">
              <div className="w-7 h-7 rounded-md bg-gradient-to-br from-np to-nbl flex items-center justify-center text-xs font-bold text-white shrink-0 mt-0.5 shadow-sm">
                N
              </div>
              <p className="text-sm text-nt2 leading-relaxed">{evaluation.overall_insights}</p>
            </div>

            {/* Actions */}
            <div className="flex gap-3 w-full max-w-md pb-4">
              <button
                onClick={retakeQuiz}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-nb border border-bdr2 text-nt text-sm font-medium hover:bg-ns2 hover:shadow-md transition"
              >
                <RotateCcw size={14} /> Retake
              </button>
              <button
                onClick={handleReviewNotes}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg bg-np text-white text-sm font-medium hover:bg-[#8E82E0] transition shadow-lg shadow-np/30"
              >
                <BookOpen size={14} /> Review Notes
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // ── Quiz Active (questions view) ─────────────────────────────────────────
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
    // Pull the LATEST state from the store to avoid stale closure
    const currentState = useQuizStore.getState()
    const payload = currentState.questions.map((q, i) => ({
      ...q,
      user_answer: currentState.answers[i] || '',
    }))
    try {
      const result = await evaluateQuiz(payload, quizStartTime!, currentState.confidences)
      if (result) {
        endQuiz(result)
      }
    } catch {
      // silently fail – user can retry
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
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-nblb text-nbl">{q.type}</span>
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-ns3 text-nt2">{q.difficulty || 'Medium'}</span>
        </div>

        <p className="text-[15px] text-nt leading-relaxed mb-6">{q.question}</p>

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
                  className={`w-full flex items-center gap-3 p-3 rounded-lg border border-bdr2 bg-nb text-left transition ${isSelected && !showFeedback ? 'bg-ns3 border-np' : 'hover:bg-ns2 hover:border-bdr'} ${stateClass}`}>
                  <span className={`w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold ${showFeedback && opt === q.answer ? 'bg-ng text-white' : showFeedback && isSelected ? 'bg-nr text-white' : 'bg-ns3 text-nt2'}`}>{letter}</span>
                  <span className="text-sm text-nt2">{opt}</span>
                  {showFeedback && opt === q.answer && <Check size={16} className="ml-auto text-ng" />}
                  {showFeedback && isSelected && opt !== q.answer && <X size={16} className="ml-auto text-nr" />}
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
                  className={`flex-1 py-3 rounded-lg border border-bdr2 bg-nb text-sm font-medium text-nt2 transition ${isSelected && !showFeedback ? 'bg-ns3 border-np' : 'hover:bg-ns2'} ${stateClass}`}>
                  {val}
                </button>
              )
            })}
          </div>
        )}

        {!isAutoGraded && (
          <div className="space-y-4">
            <textarea className="w-full h-24 bg-nb border border-bdr2 rounded-lg p-3 text-sm text-nt resize-none focus:border-np outline-none"
              placeholder="Type your answer…" value={selectedAnswer} onChange={(e) => setSelectedAnswer(e.target.value)} disabled={isAnswered} />
            {!isAnswered && (
              <button onClick={() => handleSelectAnswer(selectedAnswer)} disabled={!selectedAnswer.trim()}
                className="py-2 px-6 rounded-lg bg-np text-white text-sm font-medium hover:bg-[#8E82E0] transition disabled:opacity-50">
                Submit Answer
              </button>
            )}
          </div>
        )}

        {showFeedback && isAutoGraded && (
          <div className={`mt-5 p-4 rounded-lg border ${isCorrect ? 'bg-ngb border-ngbr' : 'bg-nrb border-nrbr'}`}>
            <div className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-md bg-gradient-to-br from-np to-nbl flex items-center justify-center text-[10px] font-bold text-white shrink-0 mt-0.5">N</div>
              <div className="text-sm text-nt2">
                {isCorrect ? `✅ Correct! ${q.explanation}` : `❌ Incorrect. The correct answer is **${q.answer}**. ${q.explanation}`}
              </div>
            </div>
          </div>
        )}

        {showFeedback && isAutoGraded && (
          <div className="mt-5 pt-5 border-t border-dashed border-bdr flex items-center gap-2 flex-wrap">
            <span className="text-xs text-nt3 font-medium mr-2">How confident were you?</span>
            {['Guess', 'Unsure', 'Confident', 'Very Confident'].map((lvl) => (
              <button key={lvl} onClick={() => setConfidenceLocal(lvl)}
                className={`px-3 py-1 rounded-md border text-xs transition ${confidence === lvl ? 'bg-npb border-npbr text-np' : 'border-bdr2 text-nt3 hover:bg-ns2 hover:text-nt2'}`}>
                {lvl}
              </button>
            ))}
          </div>
        )}

        {showFeedback && isAutoGraded && (
          <div className="mt-6 flex justify-end">
            <button onClick={handleNext} className="py-2 px-6 rounded-lg bg-np text-white text-sm font-medium hover:bg-[#8E82E0] transition">
              {currentIndex < questions.length - 1 ? 'Next Question' : 'Finish Quiz'}
            </button>
          </div>
        )}

        {evaluating && (
          <div className="mt-8 text-center text-nt3 text-sm">Evaluating your answers…</div>
        )}
      </div>
    </div>
  )
}
import { useEffect } from 'react'
import { PrintChapter } from './print/PrintChapter'
import { PrintAssessmentChapter } from './print/PrintAssessmentChapter'
import { usePrintData } from './print/usePrintData'
import { PrintErrorBoundary } from './print/PrintErrorBoundary'

// Entry for the print route (`/print?type=notes|revision|assessment&lecture_id=…`).
// Data loading lives in `usePrintData`, per-chapter rendering in `PrintChapter`
// / `PrintAssessmentChapter`, card classification in `cardClassifier.ts`.
function PrintPageContent() {
  const params = new URLSearchParams(window.location.search)
  const rawType = params.get('type') || 'notes'
  const lectureId = params.get('lecture_id') || 'default'

  let type: 'notes' | 'revision' | 'assessment' = 'notes'
  if (rawType.includes('assessment')) type = 'assessment'
  else if (rawType.includes('revision') || rawType.includes('summary')) type = 'revision'

  const { chapters, assessmentChapters, loading, globalError } = usePrintData(lectureId, type)

  useEffect(() => {
    if (!loading && !globalError) {
      const timer = setTimeout(() => window.print(), 3000)
      return () => clearTimeout(timer)
    }
  }, [loading, globalError])

  if (loading) {
    return <div className="bg-nb text-nt p-8 font-mono text-sm">Preparing your PDF…</div>
  }

  if (globalError) {
    return (
      <div className="print-document bg-nb text-nt">
        <div className="print-chapter px-8 py-6">
          <div className="border border-red-500/50 p-6 rounded-lg bg-red-900/10 text-red-400">
            <h1 className="text-xl font-bold mb-2">Data Fetch Error</h1>
            <p className="font-mono text-sm">{globalError}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="print-document bg-nb text-nt">
      {type === 'assessment' && assessmentChapters.map(({ ch, questions }) => (
        <PrintAssessmentChapter key={ch} ch={ch} questions={questions} />
      ))}

      {type !== 'assessment' && chapters.map((item, idx) => (
        <PrintChapter key={idx} item={item} ch={idx + 1} showScreenshots={type === 'notes'} />
      ))}
    </div>
  )
}

export function PrintPage() {
  return (
    <PrintErrorBoundary>
      <PrintPageContent />
    </PrintErrorBoundary>
  )
}

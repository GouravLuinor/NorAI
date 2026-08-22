import { useEffect } from 'react'
import { PrintChapter } from './print/PrintChapter'
import { PrintAssessmentChapter } from './print/PrintAssessmentChapter'
import { PrintConceptMap } from './print/PrintConceptMap'
import { usePrintData } from './print/usePrintData'
import { PrintErrorBoundary } from './print/PrintErrorBoundary'
import type { PrintType } from './print/types'

// Entry for the print route (`/print?type=notes|revision|guide|concepts|assessment&lecture_id=…`).
// Data loading lives in `usePrintData`, per-chapter rendering in `PrintChapter`
// / `PrintAssessmentChapter` / `PrintConceptMap`, card classification in
// `cardClassifier.ts`.
function PrintPageContent() {
  const params = new URLSearchParams(window.location.search)
  const rawType = params.get('type') || 'notes'
  const lectureId = params.get('lecture_id') || 'default'

  let type: PrintType = 'notes'
  if (rawType.includes('assessment')) type = 'assessment'
  else if (rawType.includes('guide')) type = 'guide'
  else if (rawType.includes('concept')) type = 'concepts'
  else if (rawType.includes('revision') || rawType.includes('summary')) type = 'revision'

  const { chapters, assessmentChapters, guideTitle, conceptMaps, loading, globalError } = usePrintData(lectureId, type)

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
          <div className="border border-nrbr p-6 rounded-lg bg-nrb text-nr">
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

      {type === 'guide' && (
        <>
          <div className="print-chapter px-8 py-7">
            <h1 className="text-2xl font-semibold text-nt tracking-tight mb-2">{guideTitle || 'Study Guide'}</h1>
            <p className="text-xs text-nt3">Compiled from this lecture's revision notes.</p>
          </div>
          {chapters.map((item, idx) => (
            <PrintChapter
              key={idx}
              item={typeof item === 'string' ? item : item.markdown ?? item}
              ch={idx + 1}
              continuous
            />
          ))}
        </>
      )}

      {type === 'concepts' && conceptMaps.map(({ ch, data }) => (
        <PrintConceptMap key={ch} data={data} ch={ch} />
      ))}

      {(type === 'notes' || type === 'revision') && chapters.map((item, idx) => (
        <PrintChapter key={idx} item={item} ch={idx + 1} showScreenshots={type === 'notes'} continuous={type === 'revision'} />
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

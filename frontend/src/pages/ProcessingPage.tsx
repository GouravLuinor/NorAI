import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Check, ArrowRight, RotateCcw } from 'lucide-react'
import { motion, useReducedMotion } from 'framer-motion'
import { Button } from '../components/ui/Button'
import { useAuthStore } from '../stores/useAuthStore'
import { apiFetchRaw } from '../lib/http'
import { friendlyError } from '../lib/errorCopy'
import type { ProcessEvent } from '../types'

interface StageInfo {
  label: string
  key: string
}

const STAGES: StageInfo[] = [
  { label: 'Downloading video', key: 'ingestion' },
  { label: 'Transcribing lecture', key: 'transcription' },
  { label: 'Chunking transcript', key: 'chunking' },
  { label: 'Extracting knowledge', key: 'knowledge_extraction' },
  { label: 'Extracting frames', key: 'frame_extraction' },
  { label: 'Detecting scenes', key: 'scene_detection' },
  { label: 'Mapping screenshots', key: 'mapping' },
  { label: 'Generating outline', key: 'outline' },
  { label: 'Visual understanding', key: 'visual_knowledge' },
  { label: 'Merging knowledge', key: 'knowledge_merging' },
  { label: 'Building chapters', key: 'chapter_building' },
  { label: 'Selecting screenshots', key: 'screenshot_selection' },
  { label: 'Writing notes, revision & assessment', key: 'chapter_artifacts' },
  { label: 'Indexing for tutor', key: 'tutor_index' },
  { label: 'Indexing screenshots', key: 'screenshot_index' },
  { label: 'Cleaning up', key: 'cleanup' },
]

const RAIL_X = 'calc(0.75rem + 1.5rem + 0.625rem + 0.4375rem)'

export function ProcessingPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const reduceMotion = useReducedMotion()
  const [activeStage, setActiveStage] = useState<string | null>(null)
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set())
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState('Preparing…')
  const [finished, setFinished] = useState(false)
  const [errored, setErrored] = useState(false)

  useEffect(() => {
    if (!taskId) return

    const controller = new AbortController()
    const BASE_DELAY_MS = 1500
    const MAX_DELAY_MS = 10000
    let timer: ReturnType<typeof setTimeout> | null = null
    let delay = BASE_DELAY_MS
    let lastSignature = ''
    let stopped = false

    const processEventData = (data: ProcessEvent) => {
      const stage = data.stage
      if (stage === 'complete' || (data.progress != null && data.progress >= 100)) {
        setCompletedStages(prev => {
          const next = new Set(prev)
          STAGES.forEach(s => next.add(s.key))
          return next
        })
        setActiveStage(null)
        setProgress(100)
        setMessage('All done! Your workspace is ready.')
        setFinished(true)
        useAuthStore.getState().refreshQuota()
        return
      }
      if (stage === 'retrying') {
        setMessage(data.message || 'Temporary issue encountered. Retrying…')
        return
      }
      if (stage === 'error') {
        setErrored(true)
        setMessage(friendlyError(data.message || 'Something went wrong.'))
        return
      }
      if (!stage) return
      setActiveStage(stage)
      setCompletedStages(prev => {
        const next = new Set(prev)
        const idx = STAGES.findIndex(s => s.key === stage)
        if (idx !== -1) {
          // A stage earlier than the furthest completed one signals a retry
          // re-run (backend restarted the pipeline). Reset so the bar doesn't
          // keep stale checkmarks ahead of the active stage.
          const furthestDone = STAGES.findIndex(s => next.has(s.key))
          if (idx < furthestDone || (idx >= 0 && next.has(stage))) {
            next.clear()
          }
          STAGES.slice(0, idx).forEach(s => next.add(s.key))
          next.add(stage)
        }
        return next
      })
      setProgress(data.progress ?? 0)
      setMessage(data.message || '')
    }

    const scheduleNext = () => {
      // P3.4: hidden tabs don't need live progress — defer polling until the
      // tab is visible again instead of burning a request every 1.5s for an
      // hour-long pipeline.
      if (document.hidden || stopped) return
      timer = setTimeout(poll, delay)
    }

    const poll = async () => {
      timer = null
      if (stopped) return
      if (document.hidden) {
        scheduleNext()  // reschedules only once visible
        return
      }
      try {
        const res = await apiFetchRaw(`/process/${taskId}/status`, { signal: controller.signal })
        if (res.status === 404) {
          // Task no longer exists (e.g. GC'd) — nothing left to poll for.
          stopped = true
          setErrored(true)
          setMessage('This processing task no longer exists — it may have expired. Upload the lecture again to retry.')
          return
        }
        if (!res.ok) {
          // Transient server failure — back off and retry.
          delay = Math.min(delay * 2, MAX_DELAY_MS)
          scheduleNext()
          return
        }
        const data = await res.json()
        processEventData(data)
        if (data.stage === 'complete' || data.stage === 'error') {
          stopped = true
          return
        }
        // P3.4: unchanged payload → stretch the interval; any change snaps
        // back to fast polling so stage transitions still feel instant.
        const signature = `${data.stage}|${data.progress}|${data.message}`
        delay = signature === lastSignature ? Math.min(delay * 1.5, MAX_DELAY_MS) : BASE_DELAY_MS
        lastSignature = signature
        scheduleNext()
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        // Network error — back off and keep trying.
        delay = Math.min(delay * 2, MAX_DELAY_MS)
        scheduleNext()
      }
    }

    const handleVisibility = () => {
      if (!document.hidden && timer === null && !stopped) poll()
    }
    document.addEventListener('visibilitychange', handleVisibility)

    poll()

    return () => {
      stopped = true
      controller.abort()
      document.removeEventListener('visibilitychange', handleVisibility)
      if (timer) clearTimeout(timer)
    }
  }, [taskId])

  const activeIdx = activeStage ? STAGES.findIndex(s => s.key === activeStage) : -1
  const inkHeight = activeIdx >= 0 ? `${((activeIdx + 1) / STAGES.length) * 100}%` : `${Math.min(progress, 100)}%`

  return (
    <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center py-8 px-4 overflow-y-auto">
      <div className="w-full max-w-md relative z-10">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="flex items-center justify-center gap-2 mb-3">
            <div className="w-10 h-10 rounded-md bg-npf flex items-center justify-center text-lg font-semibold text-npfg shadow-ev2 fold-marks relative">
              N
            </div>
            <span className="font-display text-2xl font-semibold text-nt tracking-tight">
              NorAI
            </span>
          </div>
          <p className="text-sm text-nt2 font-serif italic">{message}</p>
          <div className="flex items-center justify-center gap-2 mt-2">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                finished ? 'bg-ng' : errored ? 'bg-nr' : 'bg-np animate-pulse'
              }`}
            />
            <span className="spec-label">
              {finished ? 'Complete' : errored ? 'Aborted' : 'Processing'}
            </span>
          </div>
        </div>

        {/* Progress bar — dashed draft-line → solid ink */}
        <div className="w-full mb-6">
          <div className="h-1.5 bg-transparent border-t border-dashed border-nt4 relative overflow-hidden">
            <div
              className="absolute left-0 top-0 bottom-0 border-t-2 border-np transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between mt-1.5">
            <span className="spec-label">Progress</span>
            <span className="spec-label text-np tabular-nums">{Math.round(progress)}%</span>
          </div>
        </div>

        {/* Stage schematic */}
        <div className="relative">
          {/* Draft rail (dashed, full height) */}
          <div
            className="absolute top-1 bottom-1 w-px border-l border-dashed border-nt4"
            style={{ left: RAIL_X }}
          />
          {/* Ink rail — self-draws down to the active stage */}
          <motion.div
            className="absolute top-1 w-[2px] bg-np"
            style={{ left: `calc(${RAIL_X} - 0.5px)` }}
            initial={{ height: 0 }}
            animate={{ height: inkHeight }}
            transition={reduceMotion ? { duration: 0 } : { duration: 0.5, ease: 'easeOut' }}
          />
          <div className="space-y-0.5">
            {STAGES.map((stage, idx) => {
              const isActive = activeStage === stage.key
              const isComplete = completedStages.has(stage.key) && !isActive

              return (
                <div
                  key={stage.key}
                  className={`relative flex items-center gap-2.5 px-3 py-1.5 rounded-md text-xs transition ${
                    isActive
                      ? 'bg-npb text-nt'
                      : isComplete
                        ? 'text-nt2'
                        : 'text-nt4'
                  }`}
                >
                  <span className="spec-label w-6 text-right shrink-0">
                    {String(idx + 1).padStart(2, '0')}
                  </span>
                  <div className="w-[14px] shrink-0 flex items-center justify-center relative z-10">
                    {isActive ? (
                      <div className="w-2 h-2 bg-np animate-pulse rounded-xs" />
                    ) : isComplete ? (
                      <Check size={12} strokeWidth={1.5} className="text-ng shrink-0" />
                    ) : (
                      <div className="w-1.5 h-1.5 rounded-full border border-nt4 shrink-0" />
                    )}
                  </div>
                  <span className="leading-relaxed">{stage.label}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Go to workspace button */}
        {finished && (
          <Button
            variant="primary"
            onClick={() => navigate(`/workspace/${taskId}`)}
            className="w-full mt-8 gap-2 py-3 rounded-md text-13 fold-marks relative"
          >
            Go to Workspace
            <ArrowRight size={15} strokeWidth={1.5} />
          </Button>
        )}

        {/* P4.3: errored runs get a recovery action, not a dead end. */}
        {errored && (
          <div className="flex flex-col gap-2 mt-8">
            <Button
              variant="primary"
              onClick={() => window.location.reload()}
              className="w-full gap-2 py-3 rounded-md text-13 fold-marks relative"
            >
              <RotateCcw size={14} strokeWidth={1.5} />
              Retry Processing
            </Button>
            <Button
              variant="ghost"
              onClick={() => navigate('/app')}
              className="w-full py-2 rounded-md text-xs"
            >
              Start a new upload instead
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

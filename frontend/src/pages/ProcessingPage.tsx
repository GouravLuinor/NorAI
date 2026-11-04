import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Check, ArrowRight, RotateCcw, AlertTriangle, Clock, Info, Bell, BellRing } from 'lucide-react'
import { Wordmark } from '../components/brand/Wordmark'
import { FOCUS_RING } from '../components/ui/shared'
import { Button } from '../components/ui/Button'
import { useAuthStore } from '../stores/useAuthStore'
import { useRateLimitStore } from '../stores/useRateLimitStore'
import { apiFetchRaw } from '../lib/http'
import { friendlyError } from '../lib/errorCopy'
import type { ProcessEvent } from '../types'

interface StageInfo {
  label: string
  key: string
}

// Stages the pipeline reports. Frames and scenes are captured alongside
// transcription, so they have no row of their own.
const STAGES: StageInfo[] = [
  { label: 'Getting your file', key: 'ingestion' },
  { label: 'Transcribing lecture & capturing slides', key: 'transcription' },
  { label: 'Chunking transcript', key: 'chunking' },
  { label: 'Mapping the chapters', key: 'outline' },
  { label: 'Writing notes, revision & assessment', key: 'chapter_artifacts' },
  { label: 'Indexing for tutor', key: 'tutor_index' },
  { label: 'Cleaning up', key: 'cleanup' },
]

// Documents skip transcription; their text is read during intake.
const DOC_LABELS: Record<string, string> = {
  ingestion: 'Reading your document',
  chunking: 'Splitting the text',
}
const DOC_STAGES: StageInfo[] = STAGES
  .filter((s) => s.key !== 'transcription')
  .map((s) => ({ ...s, label: DOC_LABELS[s.key] ?? s.label }))

function formatCountdown(totalSeconds: number): string {
  if (totalSeconds <= 0) return '00h 00m 00s'
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(hours)}h ${pad(minutes)}m ${pad(seconds)}s`
}

const NOTIFY_KEY = 'norai-notify-ready'

const canNotify = () => typeof Notification !== 'undefined'

/** Opted in earlier (and the browser still allows it). */
const notifyOptedIn = () => {
  try {
    return canNotify() && Notification.permission === 'granted' && localStorage.getItem(NOTIFY_KEY) === '1'
  } catch {
    return false
  }
}

export function ProcessingPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [activeStage, setActiveStage] = useState<string | null>(null)
  const [isDocument, setIsDocument] = useState(false)
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set())
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState('Preparing…')
  const [finished, setFinished] = useState(false)
  const [errored, setErrored] = useState(false)
  const [isRpdLimited, setIsRpdLimited] = useState(false)
  const { remainingSeconds } = useRateLimitStore()
  const [notify, setNotify] = useState(notifyOptedIn)

  const enableNotify = async () => {
    if (!canNotify()) return
    const permission = Notification.permission === 'default' ? await Notification.requestPermission() : Notification.permission
    const on = permission === 'granted'
    setNotify(on)
    try {
      localStorage.setItem(NOTIFY_KEY, on ? '1' : '0')
    } catch {
      /* private mode: this run still notifies */
    }
  }

  // The tab title carries progress, so a backgrounded tab still shows it.
  useEffect(() => {
    const previous = document.title
    return () => {
      document.title = previous
    }
  }, [])
  useEffect(() => {
    document.title = finished
      ? 'Ready: your lecture · NorAI'
      : errored
        ? 'Stopped · NorAI'
        : `${Math.round(progress)}% processing · NorAI`
  }, [finished, errored, progress])

  // Tell a user who went elsewhere that the lecture is ready.
  useEffect(() => {
    if (!finished || !notify || !document.hidden || !canNotify() || Notification.permission !== 'granted') return
    const n = new Notification('Your lecture is ready', {
      body: 'Notes, quiz, flashcards and the tutor are waiting in NorAI.',
      icon: '/favicon.svg',
      tag: `norai-ready-${taskId}`,
    })
    n.onclick = () => {
      window.focus()
      navigate(`/workspace/${taskId}`)
      n.close()
    }
  }, [finished, notify, taskId, navigate])

  useEffect(() => {
    if (!taskId) return

    const controller = new AbortController()
    const BASE_DELAY_MS = 1500
    const MAX_DELAY_MS = 10000
    // Hidden tabs keep a slow poll so the title and the "ready" notification
    // still fire while the user is in another tab.
    const HIDDEN_DELAY_MS = 20000
    let timer: ReturnType<typeof setTimeout> | null = null
    let delay = BASE_DELAY_MS
    let lastSignature = ''
    let stopped = false

    // The status endpoint sends limitType/retryAfterSeconds (camelCase); the
    // snake_case names are kept for older payloads.
    const processEventData = (
      data: ProcessEvent & {
        error?: string
        limitType?: string
        retryAfterSeconds?: number
        limit_type?: string
        retry_after_seconds?: number
      },
    ) => {
      const stage = data.stage
      if ((data as { source_kind?: string }).source_kind === 'document') setIsDocument(true)
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
        const limitType = data.limitType ?? data.limit_type
        if (limitType === 'rpd' || data.error === 'DAILY_QUOTA_EXHAUSTED') {
          setIsRpdLimited(true)
          const retrySecs = data.retryAfterSeconds || data.retry_after_seconds || 3600
          useRateLimitStore.getState().setDailyLimit(retrySecs)
          setMessage('Paused: the AI service hit its daily limit.')
        } else {
          setMessage(friendlyError(data.message || 'Something went wrong.'))
        }
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
      // P3.4: hidden tabs don't need live progress — poll every 20 s instead
      // of every 1.5 s for an hour-long pipeline.
      if (stopped) return
      timer = setTimeout(poll, document.hidden ? Math.max(delay, HIDDEN_DELAY_MS) : delay)
    }

    const poll = async () => {
      timer = null
      if (stopped) return
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
      // Back in view: refresh now instead of waiting out the slow hidden poll.
      if (!document.hidden && !stopped) {
        if (timer) clearTimeout(timer)
        delay = BASE_DELAY_MS
        poll()
      }
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


  return (
    <div id="main" className="min-h-screen bg-nb flex flex-col items-center px-4 pb-16 overflow-y-auto">
      <div className="w-full max-w-lg">
        <div className="py-4 mb-8">
          <Wordmark size="md" />
        </div>

        <h1 className="font-serif font-semibold text-32 leading-tight text-nt">
          {finished ? 'Your lecture is ready' : errored ? 'Processing stopped' : 'Making your notes'}
        </h1>
        <p className="mt-2 text-16 text-nt2" aria-live="polite">{message}</p>

        {/* Progress */}
        <div className="mt-7 mb-7">
          <div
            className="h-2 rounded-full bg-ns3 overflow-hidden"
            role="progressbar"
            aria-valuenow={Math.round(progress)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Processing progress"
          >
            <div
              className={`h-full rounded-full ${errored ? 'bg-nr' : finished ? 'bg-ng' : 'bg-np'}`}
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
          <div className="flex justify-between mt-2 text-14">
            <span className="text-nt3">{finished ? 'Complete' : errored ? 'Stopped' : 'In progress'}</span>
            <span className="font-mono font-semibold text-nt">{Math.round(progress)}%</span>
          </div>
        </div>

        {/* Stages */}
        <ol className="border-y border-bdr divide-y divide-bdr">
          {(isDocument ? DOC_STAGES : STAGES).map((stage, idx) => {
            const isActive = activeStage === stage.key && !finished
            const isComplete = finished || (completedStages.has(stage.key) && !isActive)
            return (
              <li
                key={stage.key}
                aria-current={isActive ? 'step' : undefined}
                className={`flex items-center gap-3 px-2 py-2.5 text-15 ${
                  isActive ? 'bg-brass-soft text-nt font-bold' : isComplete ? 'text-nt2' : 'text-nt3'
                }`}
              >
                <span className="font-mono text-13 w-6 text-right shrink-0 text-nt3">
                  {String(idx + 1).padStart(2, '0')}
                </span>
                <span className="w-4 shrink-0 flex items-center justify-center">
                  {isActive ? (
                    <span className="w-2.5 h-2.5 bg-brass rounded-[2px]" />
                  ) : isComplete ? (
                    <Check size={16} strokeWidth={2} className="text-ng" aria-label="Done" />
                  ) : (
                    <span className="w-2 h-2 rounded-full border-[1.5px] border-nt4" />
                  )}
                </span>
                <span className="leading-snug">{stage.label}</span>
              </li>
            )
          })}
        </ol>

        {!finished && !errored && (
          <p className="mt-6 flex items-start gap-2 text-15 text-nt2 leading-relaxed">
            <Info size={16} strokeWidth={1.75} className="mt-1 shrink-0 text-nt3" aria-hidden="true" />
            <span>
              This usually takes a few minutes. You can close this tab: processing continues on our side and the
              lecture appears in your library when it's ready.
            </span>
          </p>
        )}
        {!finished && !errored && canNotify() && Notification.permission !== 'denied' && (
          <button
            type="button"
            onClick={() => void enableNotify()}
            disabled={notify}
            className={`mt-4 inline-flex items-center gap-2 rounded-md border border-bdr2 bg-ns px-3.5 h-10 text-14 font-bold text-nt2 hover:bg-ns2 hover:text-nt disabled:cursor-default disabled:hover:bg-ns cursor-pointer transition-colors ${FOCUS_RING}`}
          >
            {notify ? <BellRing size={16} strokeWidth={1.75} aria-hidden="true" className="text-np" /> : <Bell size={16} strokeWidth={1.75} aria-hidden="true" />}
            {notify ? "We'll notify you when it's ready" : "Notify me when it's ready"}
          </button>
        )}

        {/* Go to workspace button */}
        {finished && (
          <Button
            variant="primary"
            onClick={() => navigate(`/workspace/${taskId}`)}
            className="w-full mt-8 gap-2 h-12 rounded-md text-16 font-bold"
          >
            Open your notes
            <ArrowRight size={17} strokeWidth={2} />
          </Button>
        )}

        {/* Errored runs: daily-limit countdown, or a way back to start again */}
        {errored && isRpdLimited && (
          <div className="flex flex-col gap-3 mt-8 p-5 rounded-md bg-nab border border-nabr text-nat" role="status">
            <div className="flex items-center gap-2 font-bold text-16">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>Paused for today</span>
            </div>
            <p className="text-15 text-nt2 leading-relaxed">
              Our AI provider's daily limit was reached, so this lecture stopped before it finished. It didn't use
              any of your lecture-minutes. Start it again once processing reopens.
            </p>
            <div className="flex items-center gap-2 bg-ns border border-nabr px-3 h-10 rounded-md text-14 text-nt">
              <Clock size={13} aria-hidden="true" />
              <span>Reopens in</span>
              <span className="font-mono font-semibold">{formatCountdown(remainingSeconds)}</span>
            </div>
            <Button
              variant="primary"
              onClick={() => navigate('/app')}
              className="w-full h-11 mt-1 rounded-md text-15 font-bold"
            >
              Back to my library
            </Button>
          </div>
        )}

        {errored && !isRpdLimited && (
          <div className="flex flex-col gap-2 mt-8">
            <p className="text-15 text-nt2 leading-relaxed mb-1">
              Failed runs don't use any of your lecture-minutes.
            </p>
            <Button
              variant="primary"
              onClick={() => navigate('/app')}
              className="w-full gap-2 h-12 rounded-md text-16 font-bold"
            >
              <RotateCcw size={16} strokeWidth={1.75} />
              Try again
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

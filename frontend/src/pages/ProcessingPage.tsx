import { useEffect, useState} from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Check, Loader2, ArrowRight } from 'lucide-react'
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
  { label: 'Visual understanding', key: 'visual_knowledge' },
  { label: 'Merging knowledge', key: 'knowledge_merging' },
  { label: 'Generating outline', key: 'outline' },
  { label: 'Building chapters', key: 'chapter_building' },
  { label: 'Writing study notes', key: 'study_notes' },
  { label: 'Selecting screenshots', key: 'screenshot_selection' },
  { label: 'Writing revision notes', key: 'revision_notes' },
  { label: 'Creating assessment', key: 'assessment' },
  { label: 'Indexing for tutor', key: 'tutor_index' },
  { label: 'Indexing screenshots', key: 'screenshot_index' },
  { label: 'Cleaning up', key: 'cleanup' },
]

export function ProcessingPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [activeStage, setActiveStage] = useState<string | null>(null)
  const [completedStages, setCompletedStages] = useState<Set<string>>(new Set())
  const [progress, setProgress] = useState(0)
  const [message, setMessage] = useState('Preparing…')
  const [finished, setFinished] = useState(false)


useEffect(() => {
  if (!taskId) return

  let pollTimer: ReturnType<typeof setInterval> | null = null
  let cancelled = false

  const processEventData = (data: ProcessEvent) => {
    const stage = data.stage
    if (stage === 'complete') {
      setCompletedStages(prev => {
        const next = new Set(prev)
        STAGES.forEach(s => next.add(s.key))
        return next
      })
      setActiveStage(null)
      setProgress(100)
      setMessage('All done! Your workspace is ready.')
      setFinished(true)
      return
    }
    if (stage === 'error') {
      setMessage(`Error: ${data.message || 'Something went wrong.'}`)
      return
    }
    if (!stage) return
    setActiveStage(stage)
    setCompletedStages(prev => {
      const next = new Set(prev)
      const idx = STAGES.findIndex(s => s.key === stage)
      if (idx !== -1) STAGES.slice(0, idx).forEach(s => next.add(s.key))
      next.add(stage)
      return next
    })
    setProgress(data.progress ?? 0)
    setMessage(data.message || '')
  }

const poll = async () => {
    if (cancelled) return
    try {
        const res = await fetch(`/process/${taskId}/status`)
        const data = await res.json()
        processEventData(data)
        if (data.stage === 'complete' || data.stage === 'error') {
            if (pollTimer) clearInterval(pollTimer)
        }
    } catch {
        // polling continues; transient network errors should not break the flow
    }
}

  poll()
  pollTimer = setInterval(poll, 1500)

  return () => {
    cancelled = true
    if (pollTimer) clearInterval(pollTimer)
  }
}, [taskId, finished])

  return (
    <div className="min-h-screen bg-nb flex flex-col items-center py-8 px-4 overflow-y-auto">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-4">
            <div className="w-10 h-10 rounded-lg bg-np flex items-center justify-center text-lg font-semibold text-npfg shadow-ev2">
              N
            </div>
            <span className="text-2xl font-semibold text-nt tracking-tight">NorAI</span>
          </div>
          <p className="text-sm text-nt2">{message}</p>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 bg-ns3 rounded-full overflow-hidden mb-8">
          <div
            className="h-full bg-np rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Stage timeline */}
        <div className="space-y-0.5">
          {STAGES.map((stage) => {
            const isActive = activeStage === stage.key
            const isComplete = completedStages.has(stage.key) && !isActive

            return (
              <div
                key={stage.key}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-xs transition ${
                  isActive
                    ? 'bg-npb text-np'
                    : isComplete
                      ? 'text-nt2'
                      : 'text-nt4'
                }`}
              >
                {isActive ? (
                  <Loader2 size={14} className="animate-spin text-np shrink-0" />
                ) : isComplete ? (
                  <Check size={14} className="text-ng shrink-0" />
                ) : (
                  <div className="w-[14px] h-[14px] rounded-full border border-nt4 shrink-0" />
                )}
                <span className="leading-relaxed">{stage.label}</span>
              </div>
            )
          })}
        </div>

        {/* Go to workspace button */}
        {finished && (
          <button
            onClick={() => navigate(`/workspace/${taskId}`)}
            className="w-full mt-8 flex items-center justify-center gap-2 py-3 rounded-lg bg-np text-npfg text-13 font-medium shadow-ev2 hover:bg-nph transition"
          >
            Go to Workspace
            <ArrowRight size={15} />
          </button>
        )}
      </div>
    </div>
  )
}
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Film, Upload, Link2, FileVideo, ArrowRight, BookOpen, Clock, Info, Activity, AlertTriangle } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { SegmentedControl } from '../components/ui/SegmentedControl'
import { FOCUS_RING } from '../components/ui/shared'
import { authHeaders } from '../lib/authHeaders'

type InputType = 'youtube' | 'upload' | 'drive'

interface LectureInfo {
  lecture_id: string
  title: string
  created_at: string
  chapter_count: number
}

interface EstimateResult {
  available?: boolean
  reason?: string
  duration_min?: number
  estimated_chunks?: number
  estimated_chapters?: number
  est_calls?: number
  est_time_min?: number
  free_trial_ok?: boolean
  free_trial_min?: number
  calibrated?: boolean
  n_calibration_runs?: number
  title?: string
}

// Relative time via Intl.RelativeTimeFormat (locale-aware, no custom math).
const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
const rtfUnits: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 31536000],
  ['month', 2592000],
  ['week', 604800],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
]
function getRelativeTime(dateString: string) {
  const date = new Date(dateString)
  const diffSeconds = Math.round((date.getTime() - Date.now()) / 1000)
  const abs = Math.abs(diffSeconds)
  for (const [unit, seconds] of rtfUnits) {
    if (abs >= seconds || unit === 'minute') {
      return rtf.format(Math.round(diffSeconds / seconds), unit)
    }
  }
  return rtf.format(0, 'second')
}

// Read a video file's duration via a hidden <video> element (metadata probe).
function readVideoDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const video = document.createElement('video')
    const objectUrl = URL.createObjectURL(file)
    video.preload = 'metadata'
    video.onloadedmetadata = () => {
      const d = video.duration
      URL.revokeObjectURL(objectUrl)
      resolve(Number.isFinite(d) ? d : null)
    }
    video.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      resolve(null)
    }
    video.src = objectUrl
  })
}

export function UploadPage() {
  const [inputType, setInputType] = useState<InputType>('youtube')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const [lectures, setLectures] = useState<LectureInfo[]>([])
  const [loadingLectures, setLoadingLectures] = useState(true)
  const [estimate, setEstimate] = useState<EstimateResult | null>(null)
  const [estLoading, setEstLoading] = useState(false)
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ── Pre-flight estimate (P1.8) ──────────────────────────────────────────
  // Debounced: fires ~600ms after the user stops typing / selects a file.
  useEffect(() => {
    let cancelled = false
    let timeout: ReturnType<typeof setTimeout> | undefined

    const sourceReady =
      inputType === 'upload'
        ? !!file
        : inputType !== 'drive' && !!url.trim()

    if (!sourceReady) {
      setEstimate(null)
      setEstLoading(false)
      return
    }

    const run = async () => {
      setEstLoading(true)
      const formData = new FormData()
      formData.append('source_type', inputType)
      if (inputType === 'youtube') {
        formData.append('url', url.trim())
      } else if (inputType === 'upload' && file) {
        const duration = await readVideoDuration(file)
        formData.append('duration', String(duration ?? 0))
      }
      try {
        const res = await fetch('/estimate', { method: 'POST', body: formData, headers: authHeaders() })
        const data: EstimateResult = await res.json()
        if (!cancelled) setEstimate(data)
      } catch {
        if (!cancelled) setEstimate({ available: false, reason: 'Could not estimate' })
      } finally {
        if (!cancelled) setEstLoading(false)
      }
    }

    timeout = setTimeout(run, 600)
    return () => {
      cancelled = true
      if (timeout) clearTimeout(timeout)
    }
  }, [inputType, url, file])

  useEffect(() => {
    fetch('/lectures')
      .then((res) => res.json())
      .then((data: LectureInfo[]) => {
        setLectures(data.slice(0, 5)) // Take max 5 most recent
        setLoadingLectures(false)
      })
      .catch((err) => {
        console.error('Failed to fetch lectures:', err)
        setLoadingLectures(false)
      })
  }, [])

  const handleStart = async () => {
    const formData = new FormData()
    formData.append('source_type', inputType)
    if (inputType === 'upload' && file) {
      formData.append('file', file)
    } else {
      formData.append('url', url)
    }

    const res = await fetch('/process', { method: 'POST', body: formData, headers: authHeaders() })
    const { task_id } = await res.json()
    navigate(`/process/${task_id}`)
  }

  const canSubmit =
    (inputType === 'upload' && file) ||
    ((inputType === 'youtube' || inputType === 'drive') && url.trim())

  return (
    <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center py-12 px-6">
      <div className="w-full max-w-lg flex flex-col gap-10 relative z-10">
        
        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Section 1: Upload (Top)                                           */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <section>
          {/* Logo & Tagline */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-2 mb-3">
              <div className="w-10 h-10 rounded-md bg-npf flex items-center justify-center text-lg font-semibold text-npfg shadow-ev2 fold-marks relative">
                N
              </div>
              <span className="font-display text-2xl font-semibold text-nt tracking-tight">
                NorAI
              </span>
            </div>
            <h1 className="sr-only">NorAI — transform a lecture into a complete study experience</h1>
            <p className="text-sm text-nt2 max-w-sm mx-auto leading-relaxed font-serif">
              Transform your lecture into a complete study experience with AI.
            </p>

            {/* Leader-line diagram — Video → Notes → Quiz → Tutor */}
            <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 mt-4">
              {['Video', 'Notes', 'Quiz', 'Tutor'].map((step, i, arr) => (
                <span key={step} className="flex items-center gap-2">
                  <span className="text-2xs font-medium text-nt2 border border-bdr2 rounded-sm px-2 py-0.5">
                    {step}
                  </span>
                  {i < arr.length - 1 && (
                    <span className="dimension-marker text-3xs">[48px]</span>
                  )}
                </span>
              ))}
            </div>
          </div>

          {/* Input Card */}
          <div className="bg-ns border border-bdr2 rounded-lg p-5 shadow-ev2 fold-marks relative">
            <div className="spec-label mb-3">01. Source</div>
            {/* Segmented Control */}
            <SegmentedControl<InputType>
              containerClass="flex bg-nb border border-bdr rounded-md p-1 mb-4"
              itemClass="flex-1 flex items-center justify-center gap-2 py-2 rounded-sm text-xs font-medium transition"
              activeClass="bg-ns3 text-nt shadow-ev1"
              inactiveClass="text-nt3 hover:text-nt2"
              options={[
                { value: 'youtube', label: 'YouTube', prefix: <Film size={14} strokeWidth={1.5} /> },
                { value: 'upload', label: 'Upload', prefix: <Upload size={14} strokeWidth={1.5} /> },
                { value: 'drive', label: 'Drive', prefix: <Link2 size={14} strokeWidth={1.5} /> },
              ]}
              value={inputType}
              onChange={setInputType}
            />

            {/* Input Area */}
            {inputType === 'upload' ? (
              <div
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragActive(true)
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDragActive(false)
                  const dropped = e.dataTransfer.files?.[0]
                  if (dropped) setFile(dropped)
                }}
              >
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  aria-label={file ? `Selected file: ${file.name}` : 'Choose a video file to upload'}
                  className={`w-full flex flex-col items-center justify-center gap-3 p-8 border border-dashed rounded-md transition cursor-pointer hover:border-np ${FOCUS_RING} ${dragActive ? 'border-np bg-npb/50' : 'border-bdr2'}`}
                >
                  <FileVideo size={28} strokeWidth={1.5} className="text-nt3" />
                  <span className="text-xs text-nt2">
                    {file ? file.name : dragActive ? 'Drop the video to upload' : 'Click to choose or drag a video file here'}
                  </span>
                  <span className="text-2xs text-nt4">MP4, MKV, WebM up to 2 GB</span>
                </button>
                <input
                  ref={fileInputRef}
                  name="lecture-file"
                  type="file"
                  accept="video/*"
                  className="hidden"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
            ) : (
              <div className="relative">
                <input
                  type="text"
                  id="lecture-url"
                  name="lecture-url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  aria-label={inputType === 'youtube' ? 'YouTube URL' : 'Google Drive link'}
                  placeholder={
                    inputType === 'youtube'
                      ? 'Paste YouTube URL…'
                      : 'Paste Google Drive share link…'
                  }
                  className={`w-full bg-nb border border-bdr2 rounded-md px-4 py-2.5 pr-12 text-13 text-nt placeholder:text-nt4 focus:border-np transition ${FOCUS_RING}`}
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-nt3">
                  {inputType === 'youtube' ? <Film size={15} strokeWidth={1.5} /> : <Link2 size={15} strokeWidth={1.5} />}
                </div>
              </div>
            )}

            {/* Estimate Panel (P1.8) */}
            {estLoading && (
              <div className="mt-3 flex items-center gap-2 text-2xs text-nt3 animate-pulse">
                <Activity size={11} strokeWidth={1.5} />
                <span>Estimating processing cost…</span>
              </div>
            )}

            {!estLoading && estimate?.available && (
              <div className="mt-3 rounded-md border border-bdr2 bg-nb/60 px-3 py-2.5">
                <div className="flex items-start gap-2">
                  <Info size={12} strokeWidth={1.5} className="text-nt3 mt-0.5 shrink-0" />
                  <div className="text-2xs text-nt2 leading-relaxed">
                    {estimate.duration_min !== undefined && (
                      <span>≈ {estimate.duration_min.toFixed(1)} min lecture</span>
                    )}
                    {estimate.est_calls !== undefined && (
                      <span> · ~{estimate.est_calls} Gemini API calls</span>
                    )}
                    {estimate.est_time_min !== undefined && (
                      <span> · ~{estimate.est_time_min} min processing</span>
                    )}
                    {estimate.estimated_chunks !== undefined && (
                      <span className="text-nt4"> · {estimate.estimated_chunks} chunks</span>
                    )}
                    {estimate.calibrated && estimate.n_calibration_runs !== undefined && (
                      <span className="block text-nt4 mt-0.5">
                        self-calibrating from {estimate.n_calibration_runs} past runs
                      </span>
                    )}
                  </div>
                </div>
                {estimate.free_trial_ok === false && (
                  <div className="mt-2 flex items-center gap-1.5 text-2xs text-red-400">
                    <AlertTriangle size={11} strokeWidth={1.5} />
                    <span>
                      Over the {estimate.free_trial_min ?? 15}-minute free-trial limit — this lecture
                      requires Starter or Pro.
                    </span>
                  </div>
                )}
              </div>
            )}

            {!estLoading && estimate && !estimate.available && (
              <div className="mt-3 flex items-center gap-1.5 text-2xs text-nt4">
                <Info size={11} strokeWidth={1.5} />
                <span>Estimate unavailable for this source.</span>
              </div>
            )}

            {/* Submit Button */}
            <Button
              variant="primary"
              onClick={handleStart}
              disabled={!canSubmit}
              className="w-full mt-4 gap-2 py-2.5 rounded-md text-13 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Sparkles size={14} strokeWidth={1.5} />
              Start Processing
            </Button>
          </div>

          <div className="flex items-center justify-center gap-1.5 text-2xs text-nt4 mt-4">
            <Info size={11} strokeWidth={1.5} />
            <span>Works with lectures up to 3 hours. We'll generate notes, quizzes & more.</span>
          </div>
        </section>


        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Divider                                                           */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="flex items-center gap-4 px-2">
          <div className="flex-1 h-px bg-bdr2" />
          <div className="text-2xs font-medium text-nt4 uppercase tracking-widest">
            Or
          </div>
          <div className="flex-1 h-px bg-bdr2" />
        </div>


        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Section 2: Your Lectures (Bottom)                                 */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <section>
          <h2 className="spec-label mb-4 px-1">02. Your Recent Lectures</h2>
          
          <div className="flex flex-col gap-2.5">
            {loadingLectures ? (
              <div className="flex justify-center p-6 text-nt4">
                <span className="animate-pulse text-xs">Loading…</span>
              </div>
            ) : lectures.length === 0 ? (
              <div className="bg-ns border border-bdr2 rounded-lg p-8 text-center shadow-ev2">
                <BookOpen size={24} strokeWidth={1.5} className="mx-auto text-nt4 mb-3" />
                <h3 className="text-xs font-medium text-nt2 mb-1">No lectures yet</h3>
                <p className="text-11 text-nt4">Your processed lectures will appear here</p>
              </div>
            ) : (
              <>
                {lectures.map((lec) => (
                  <button
                    key={lec.lecture_id}
                    onClick={() => navigate(`/workspace/${lec.lecture_id}`)}
                    className="w-full text-left bg-ns border border-bdr2 rounded-lg p-4 flex items-center gap-4 hover:bg-ns2 transition group cursor-pointer shadow-ev1 fold-marks relative"
                  >
                    <div className="w-10 h-10 rounded-md bg-ns3 border border-bdr flex flex-col items-center justify-center shrink-0">
                      <BookOpen size={16} strokeWidth={1.5} className="text-nt3 group-hover:text-np transition" />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="text-13 font-medium text-nt truncate mb-1">
                        {lec.title || 'Untitled Lecture'}
                      </div>
                      <div className="flex items-center gap-3 text-2xs text-nt4">
                        <span className="flex items-center gap-1">
                          <BookOpen size={10} strokeWidth={1.5} />
                          {lec.chapter_count || 0} chapters
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock size={10} strokeWidth={1.5} />
                          {getRelativeTime(lec.created_at)}
                        </span>
                      </div>
                    </div>

                    <ArrowRight 
                      size={16} 
                      strokeWidth={1.5}
                      className="text-nt4 group-hover:text-nt transition group-hover:translate-x-0.5" 
                    />
                  </button>
                ))}
              </>
            )}
          </div>
        </section>
        
      </div>
    </div>
  )
}
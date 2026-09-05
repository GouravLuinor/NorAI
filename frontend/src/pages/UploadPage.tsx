import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Film, Upload, Link2, FileVideo, ArrowRight, BookOpen, Clock, Info, Activity, AlertTriangle, LogOut } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { SegmentedControl } from '../components/ui/SegmentedControl'
import { Select } from '../components/ui/Select'
import { FOCUS_RING } from '../components/ui/shared'
import { apiFetchRaw } from '../lib/http'
import { useAuthStore } from '../stores/useAuthStore'
import { useCourseStore } from '../stores/useCourseStore'
import { useRateLimitStore } from '../stores/useRateLimitStore'
import { ENABLE_PAYMENTS, DEFAULT_TRIAL_QUOTA_MINUTES } from '../config/features'

type InputType = 'youtube' | 'upload' | 'drive'

interface LectureInfo {
  lecture_id: string
  title: string
  created_at: string
  chapter_count: number
  is_demo?: boolean
  category?: string
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
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [courseId, setCourseId] = useState('')
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { user } = useAuthStore()
  const { courses, loadCourses } = useCourseStore()
  const { isDailyLimited } = useRateLimitStore()

  useEffect(() => {
    if (user) loadCourses()
  }, [user, loadCourses])

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

    setSubmitError(null)
    const run = async () => {
      setEstLoading(true)
      const formData = new FormData()
      formData.append('source_type', inputType)
      if (inputType === 'youtube') {
        formData.append('url', url.trim())
      } else if (inputType === 'upload' && file) {
        const duration = await readVideoDuration(file)
        // Backend contract: `duration` is MINUTES on both /estimate and
        // /process (readVideoDuration returns SECONDS).
        formData.append('duration', String(duration ? duration / 60 : 0))
      }
      try {
        const res = await apiFetchRaw('/estimate', { method: 'POST', body: formData })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
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
    apiFetchRaw('/lectures')
      .then((res) => res.json())
      .then((data: LectureInfo[]) => {
        const valid = data.filter(
          (l) => (l.chapter_count && l.chapter_count > 0) || (l.title && l.title !== 'New Lecture')
        )
        setLectures(valid.length > 0 ? valid : data)
        setLoadingLectures(false)
      })
      .catch((err) => {
        console.error('Failed to fetch lectures:', err)
        setLoadingLectures(false)
      })
  }, [])

  const userLectures = lectures.filter((l) => !l.is_demo)
  const demoLectures = lectures.filter((l) => l.is_demo)


  const handleStart = async () => {
    const formData = new FormData()
    formData.append('source_type', inputType)
    if (inputType === 'upload' && file) {
      formData.append('file', file)
      const duration = await readVideoDuration(file)
      if (duration) formData.append('duration', String(duration / 60))
    } else {
      formData.append('url', url)
    }
    if (courseId) formData.append('course_id', courseId)

    try {
      const res = await apiFetchRaw('/process', { method: 'POST', body: formData })
      if (!res.ok) {
        let detail = `Failed to start processing (HTTP ${res.status})`
        try {
          const body = await res.json()
          if (typeof body.detail === 'string') detail = body.detail
        } catch {
          /* non-JSON error body — keep the generic message */
        }
        if (res.status === 401) {
          useAuthStore.getState().openAuthModal('login')
        }
        setSubmitError(detail)
        return
      }
      const { task_id } = await res.json()
      navigate(`/process/${task_id}`)
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Network error starting processing')
    }
  }

  const canSubmit =
    !isDailyLimited &&
    ((inputType === 'upload' && file) ||
      ((inputType === 'youtube' || inputType === 'drive') && url.trim()))

  const logout = useAuthStore((s) => s.logout)

  return (
    <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center py-6 px-6">
      {/* Top Header with Profile & Sign Out */}
      <header className="w-full max-w-2xl flex items-center justify-between pb-6 mb-6 border-b border-bdr relative z-10">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 hover:opacity-85 transition-opacity cursor-pointer text-left"
          title="Return to NorAI Home"
        >
          <div className="w-7 h-7 rounded bg-npf flex items-center justify-center text-xs font-semibold text-npfg shadow-ev1">
            N
          </div>
          <span className="font-display text-14 font-semibold text-nt tracking-tight">
            NorAI
          </span>
        </button>

        <div className="flex items-center gap-3">
          {user && (
            <span className="font-mono text-11 text-nt3 hidden sm:inline-block">
              {user.email}
            </span>
          )}
          <button
            onClick={async () => {
              await logout()
              navigate('/')
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-bdr bg-ns hover:bg-ns2 text-nt2 hover:text-nt font-display text-11 font-medium uppercase tracking-wider transition-colors cursor-pointer"
            title="Sign out of your account"
          >
            <LogOut size={13} />
            <span>Sign Out</span>
          </button>
        </div>
      </header>

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
            <div className="spec-label mb-3">Source</div>
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
                  <div className="text-2xs text-nt2 leading-relaxed tabular-nums">
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
                  <div className="mt-2 flex items-center gap-1.5 text-2xs text-nr">
                    <AlertTriangle size={11} strokeWidth={1.5} />
                    <span>
                      Over the {estimate.free_trial_min ?? DEFAULT_TRIAL_QUOTA_MINUTES}-minute free-trial limit
                      {ENABLE_PAYMENTS ? ' — this lecture requires Starter or Pro.' : '.'}
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

            {isDailyLimited && (
              <div className="mt-3 flex items-start gap-2 text-2xs text-amber-300 rounded-md border border-amber-600/40 bg-amber-950/40 px-3 py-2">
                <AlertTriangle size={12} strokeWidth={1.5} className="mt-0.5 shrink-0 text-amber-400" />
                <span>
                  Processing is temporarily paused due to Google AI Studio daily quota limits (500 RPD).
                  Processing resumes automatically at Pacific Midnight.
                </span>
              </div>
            )}

            {submitError && (
              <div className="mt-3 flex items-start gap-1.5 text-2xs text-nr rounded-md border border-nrbr bg-nrb px-3 py-2">
                <AlertTriangle size={11} strokeWidth={1.5} className="mt-0.5 shrink-0" />
                <span>{submitError}</span>
              </div>
            )}

            {/* P6.4: file the new lecture into a course (optional) */}
            <div className="mt-4 flex flex-col gap-1">
              <label htmlFor="course-select" className="text-2xs text-nt3">
                Add to course (optional)
              </label>
              <Select
                id="course-select"
                ariaLabel="Add to course"
                value={courseId || ''}
                onChange={(v) => setCourseId(v || '')}
                placeholder="No course"
                options={[
                  { value: '', label: 'No course' },
                  ...courses.map((c) => ({ value: c.course_id, label: c.name })),
                ]}
              />
            </div>

            {/* Submit Button */}
            <Button
              variant="primary"
              onClick={handleStart}
              disabled={!canSubmit}
              className="w-full mt-4 gap-2 py-2.5 rounded-md text-13 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Sparkles size={14} strokeWidth={1.5} />
              {isDailyLimited ? 'Processing Paused (Daily Quota Reached)' : 'Start Processing'}
            </Button>
          </div>

          <div className="flex items-center justify-center gap-1.5 text-2xs text-nt4 mt-4">
            <Info size={11} strokeWidth={1.5} />
            <span>
              {user
                ? `Works with lectures up to 3 hours. New accounts include ${DEFAULT_TRIAL_QUOTA_MINUTES} minutes free trial.`
                : `Free trial: up to ${DEFAULT_TRIAL_QUOTA_MINUTES} min per lecture. Sign in for up to 3h.`}
            </span>
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
        {/* Section 2: Your Personal Lectures                                 */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <section>
          <div className="flex items-center justify-between mb-3 px-1">
            <h2 className="spec-label">Your Lectures</h2>
            {!loadingLectures && (
              <span className="font-mono text-2xs text-nt4">
                {userLectures.length} {userLectures.length === 1 ? 'lecture' : 'lectures'}
              </span>
            )}
          </div>
          
          <div className="flex flex-col gap-2.5">
            {loadingLectures ? (
              <div className="flex justify-center p-6 text-nt4">
                <span className="animate-pulse text-xs">Loading…</span>
              </div>
            ) : userLectures.length === 0 ? (
              <div className="bg-ns border border-bdr2 rounded-lg p-6 text-center shadow-ev1">
                <BookOpen size={24} strokeWidth={1.5} className="mx-auto text-nt4 mb-2" />
                <h3 className="text-12 font-medium text-nt mb-1">No personal lectures yet</h3>
                <p className="text-11 text-nt3 max-w-sm mx-auto leading-relaxed font-sans">
                  Drop a YouTube URL or upload a video file above to process your first lecture using your 45-minute free trial credit.
                </p>
              </div>
            ) : (
              userLectures.map((lec) => (
                <button
                  key={lec.lecture_id}
                  onClick={() => navigate(`/workspace/${lec.lecture_id}`)}
                  className={`w-full text-left bg-ns border border-bdr2 rounded-lg p-4 flex items-center gap-4 hover:bg-ns2 transition group cursor-pointer shadow-ev1 fold-marks relative ${FOCUS_RING} active:translate-y-[1px] active:shadow-none`}
                >
                  <div className="w-10 h-10 rounded-md bg-ns3 border border-bdr flex flex-col items-center justify-center shrink-0">
                    <BookOpen size={16} strokeWidth={1.5} className="text-nt3 group-hover:text-np transition" />
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="text-13 font-medium text-nt truncate mb-1">
                      {lec.title || 'Untitled Lecture'}
                    </div>
                    <div className="flex items-center gap-3 text-2xs text-nt4">
                      <span className="flex items-center gap-1 tabular-nums">
                        <BookOpen size={10} strokeWidth={1.5} />
                        {lec.chapter_count || 0} chapters
                      </span>
                      {lec.created_at && (
                        <span className="flex items-center gap-1">
                          <Clock size={10} strokeWidth={1.5} />
                          {getRelativeTime(lec.created_at)}
                        </span>
                      )}
                    </div>
                  </div>

                  <ArrowRight 
                    size={16} 
                    strokeWidth={1.5}
                    className="text-nt4 group-hover:text-nt transition group-hover:translate-x-0.5" 
                  />
                </button>
              ))
            )}
          </div>
        </section>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Section 3: Featured Demo Workspaces                               */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <section>
          <div className="flex items-center justify-between mb-1.5 px-1">
            <h2 className="spec-label">Featured Demo Workspaces</h2>
            <span className="font-mono text-3xs font-semibold text-np uppercase bg-npb px-2 py-0.5 rounded border border-npbr">
              Free Access
            </span>
          </div>
          <p className="text-11 text-nt3 mb-3 px-1 font-sans">
            Explore ready-to-use study notes, mind maps, quizzes, and flashcards without consuming credits.
          </p>
          
          <div className="flex flex-col gap-2.5">
            {demoLectures.map((lec) => (
              <button
                key={lec.lecture_id}
                onClick={() => navigate(`/workspace/${lec.lecture_id}`)}
                className={`w-full text-left bg-ns border border-bdr2 hover:border-npbr rounded-lg p-4 flex items-center gap-4 hover:bg-ns2 transition group cursor-pointer shadow-ev1 fold-marks relative ${FOCUS_RING} active:translate-y-[1px] active:shadow-none`}
              >
                <div className="w-10 h-10 rounded-md bg-npb border border-npbr flex flex-col items-center justify-center shrink-0">
                  <Sparkles size={16} strokeWidth={1.5} className="text-np" />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="text-13 font-medium text-nt truncate group-hover:text-np transition-colors">
                      {lec.title}
                    </div>
                    <span className="shrink-0 px-1.5 py-0.5 rounded bg-npb border border-npbr text-npt font-mono text-3xs font-semibold uppercase">
                      Demo
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-2xs text-nt4">
                    {lec.category && (
                      <span className="text-nt3 font-mono">{lec.category}</span>
                    )}
                    <span className="flex items-center gap-1 tabular-nums">
                      <BookOpen size={10} strokeWidth={1.5} />
                      {lec.chapter_count || 0} chapters
                    </span>
                  </div>
                </div>

                <ArrowRight 
                  size={16} 
                  strokeWidth={1.5}
                  className="text-nt4 group-hover:text-np transition group-hover:translate-x-0.5" 
                />
              </button>
            ))}
          </div>
        </section>
        
      </div>
    </div>
  )
}
import { useCallback, useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Sparkles, Film, Upload, Link2, FileVideo, ArrowRight, BookOpen, Clock, Info, Activity, AlertTriangle, LogOut, RefreshCw } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { SegmentedControl } from '../components/ui/SegmentedControl'
import { Select } from '../components/ui/Select'
import { FOCUS_RING } from '../components/ui/shared'
import { apiFetchRaw } from '../lib/http'
import { useAuthStore } from '../stores/useAuthStore'
import { useCourseStore } from '../stores/useCourseStore'
import { useRateLimitStore } from '../stores/useRateLimitStore'
import { DEFAULT_TRIAL_QUOTA_MINUTES } from '../config/features'
import { formatMinutes } from '../lib/plans'

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
  // Plan fit for the signed-in caller (backend/main.py:_with_plan_fit)
  plan_name?: string
  plan_max_min?: number
  minutes_needed?: number
  remaining_minutes?: number
  fits_plan?: boolean
}

// The tab says "Drive"; the API's source_type is "gdrive".
const apiSourceType = (t: InputType) => (t === 'drive' ? 'gdrive' : t)

const PLAN_LABEL: Record<string, string> = { free: 'Free', starter: 'Starter', pro: 'Pro' }

/** Pull a readable message out of a FastAPI error body (string or {message}). */
function errorDetail(body: unknown): string | null {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && typeof (detail as { message?: unknown }).message === 'string') {
    return (detail as { message: string }).message
  }
  return null
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
  const [submitErrorIsQuota, setSubmitErrorIsQuota] = useState(false)
  const [submitting, setSubmitting] = useState<null | 'uploading' | 'starting'>(null)
  const [lecturesError, setLecturesError] = useState(false)
  const [courseId, setCourseId] = useState('')
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { user } = useAuthStore()
  const quota = useAuthStore((s) => s.quota)
  const refreshQuota = useAuthStore((s) => s.refreshQuota)
  const { courses, loadCourses } = useCourseStore()
  const { isDailyLimited, expiresAt } = useRateLimitStore()

  useEffect(() => {
    if (user) {
      loadCourses()
      void refreshQuota()
    }
  }, [user, loadCourses, refreshQuota])

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
      formData.append('source_type', apiSourceType(inputType))
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

  const loadLectures = useCallback(() => {
    setLoadingLectures(true)
    setLecturesError(false)
    apiFetchRaw('/lectures')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data: LectureInfo[]) => {
        const valid = data.filter(
          (l) => (l.chapter_count && l.chapter_count > 0) || (l.title && l.title !== 'New Lecture')
        )
        setLectures(valid.length > 0 ? valid : data)
      })
      .catch((err) => {
        console.error('Failed to fetch lectures:', err)
        setLecturesError(true)
      })
      .finally(() => setLoadingLectures(false))
  }, [])

  useEffect(() => {
    loadLectures()
  }, [loadLectures])

  const userLectures = lectures.filter((l) => !l.is_demo)
  const demoLectures = lectures.filter((l) => l.is_demo)


  const handleStart = async () => {
    if (submitting) return
    setSubmitError(null)
    setSubmitErrorIsQuota(false)
    setSubmitting(inputType === 'upload' ? 'uploading' : 'starting')
    const formData = new FormData()
    formData.append('source_type', apiSourceType(inputType))
    if (inputType === 'upload' && file) {
      formData.append('file', file)
      const duration = await readVideoDuration(file)
      if (duration) formData.append('duration', String(duration / 60))
    } else {
      formData.append('url', url.trim())
    }
    if (courseId) formData.append('course_id', courseId)

    try {
      const res = await apiFetchRaw('/process', { method: 'POST', body: formData })
      if (!res.ok) {
        let detail = `Could not start processing (HTTP ${res.status}). Please try again.`
        let isRpd = false
        try {
          const body = await res.json()
          detail = errorDetail(body) ?? detail
          isRpd = (body?.detail as { limitType?: string } | undefined)?.limitType === 'rpd'
        } catch {
          /* non-JSON error body — keep the generic message */
        }
        if (res.status === 401) {
          useAuthStore.getState().openAuthModal('login')
        }
        // Plan/minutes limits (not the shared daily AI limit) can be fixed by a pass.
        setSubmitErrorIsQuota(res.status === 429 && !isRpd)
        setSubmitError(detail)
        setSubmitting(null)
        return
      }
      const { task_id } = await res.json()
      navigate(`/process/${task_id}`)
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Network error starting processing')
      setSubmitting(null)
    }
  }

  const overPlan = estimate?.available === true && estimate.fits_plan === false
  const canSubmit =
    !isDailyLimited &&
    !submitting &&
    !overPlan &&
    ((inputType === 'upload' && file) ||
      ((inputType === 'youtube' || inputType === 'drive') && url.trim()))

  const planLabel = quota ? (PLAN_LABEL[quota.plan_tier] ?? quota.plan_tier) : 'Free'

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
                    <ArrowRight size={11} strokeWidth={1.5} className="text-nt4" aria-hidden="true" />
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
                  <span className="text-2xs text-nt4">MP4, MOV, MKV, AVI or WebM, up to 2 GB</span>
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

            {/* Estimate Panel (P1.8): length, wait time and plan fit */}
            {estLoading && (
              <div className="mt-3 flex items-center gap-2 text-2xs text-nt3 animate-pulse" role="status">
                <Activity size={11} strokeWidth={1.5} />
                <span>Checking the lecture length…</span>
              </div>
            )}

            {!estLoading && estimate?.available && (
              <div className="mt-3 rounded-md border border-bdr2 bg-nb/60 px-3 py-2.5" aria-live="polite">
                <div className="flex items-start gap-2">
                  <Info size={12} strokeWidth={1.5} className="text-nt3 mt-0.5 shrink-0" />
                  <div className="text-2xs text-nt2 leading-relaxed tabular-nums">
                    {estimate.title && <span className="block text-nt font-medium truncate">{estimate.title}</span>}
                    {estimate.duration_min !== undefined && (
                      <span>≈ {Math.max(1, Math.round(estimate.duration_min))} min lecture</span>
                    )}
                    {estimate.est_time_min !== undefined && (
                      <span> · ready in about {Math.max(1, Math.round(estimate.est_time_min))} min</span>
                    )}
                    {estimate.fits_plan && estimate.minutes_needed !== undefined && estimate.remaining_minutes !== undefined && (
                      <span className="block text-nt3 mt-0.5">
                        Uses {estimate.minutes_needed} of your {estimate.remaining_minutes} remaining lecture-minutes.
                      </span>
                    )}
                  </div>
                </div>
                {overPlan && (
                  <div className="mt-2 flex items-start gap-1.5 text-2xs text-nrt">
                    <AlertTriangle size={11} strokeWidth={1.5} className="mt-0.5 shrink-0" />
                    <span>
                      {estimate.plan_max_min !== undefined && (estimate.duration_min ?? 0) > estimate.plan_max_min
                        ? `Longer than the ${estimate.plan_name ?? planLabel} plan's ${estimate.plan_max_min}-minute limit per lecture.`
                        : `Needs ${estimate.minutes_needed} lecture-minutes; you have ${estimate.remaining_minutes} left.`}{' '}
                      <Link to="/billing" className="font-medium underline underline-offset-2 hover:text-nt">
                        See plans
                      </Link>
                    </span>
                  </div>
                )}
              </div>
            )}

            {!estLoading && estimate && !estimate.available && (
              <div className="mt-3 flex items-center gap-1.5 text-2xs text-nt4">
                <Info size={11} strokeWidth={1.5} />
                <span>
                  {inputType === 'drive'
                    ? "We'll check the length once the video downloads."
                    : "Couldn't read the length yet. You can still start; we'll check it during processing."}
                </span>
              </div>
            )}

            {isDailyLimited && (
              <div className="mt-3 flex items-start gap-2 text-2xs text-nat rounded-md border border-nabr bg-nab px-3 py-2" role="status">
                <AlertTriangle size={12} strokeWidth={1.5} className="mt-0.5 shrink-0" />
                <span>
                  New lectures are paused for today because our AI provider's daily limit was reached.
                  Processing reopens automatically
                  {expiresAt
                    ? ` at ${new Date(expiresAt).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`
                    : ' later today'}
                  . Your notes, quizzes and tutor still work.
                </span>
              </div>
            )}

            {submitError && (
              <div className="mt-3 flex items-start gap-1.5 text-2xs text-nr rounded-md border border-nrbr bg-nrb px-3 py-2">
                <AlertTriangle size={11} strokeWidth={1.5} className="mt-0.5 shrink-0" />
                <span>
                  {submitError}
                  {submitErrorIsQuota && (
                    <>
                      {' '}
                      <Link to="/billing" className="font-medium underline underline-offset-2 hover:text-nt">
                        See plans
                      </Link>
                    </>
                  )}
                </span>
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
              <Sparkles size={14} strokeWidth={1.5} className={submitting ? 'animate-pulse' : undefined} />
              {isDailyLimited
                ? 'Paused for today'
                : submitting === 'uploading'
                  ? 'Uploading video…'
                  : submitting === 'starting'
                    ? 'Starting…'
                    : 'Start processing'}
            </Button>
          </div>

          <div className="flex items-center justify-center gap-1.5 text-2xs text-nt4 mt-4">
            <Info size={11} strokeWidth={1.5} />
            <span>
              {quota ? (
                <>
                  {planLabel} plan · {formatMinutes(quota.remaining_minutes)} left
                  {quota.max_lecture_minutes ? ` · lectures up to ${quota.max_lecture_minutes} min` : ''} ·{' '}
                  <Link to="/billing" className="underline underline-offset-2 hover:text-nt2">
                    {quota.plan_tier === 'free' ? 'Get more time' : 'Plan & billing'}
                  </Link>
                </>
              ) : (
                `Free accounts include ${DEFAULT_TRIAL_QUOTA_MINUTES} lecture-minutes every 30 days.`
              )}
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
            {!loadingLectures && !lecturesError && (
              <span className="font-mono text-2xs text-nt4">
                {userLectures.length} {userLectures.length === 1 ? 'lecture' : 'lectures'}
              </span>
            )}
          </div>
          
          <div className="flex flex-col gap-2.5">
            {loadingLectures ? (
              <div className="flex justify-center p-6 text-nt4" role="status">
                <span className="animate-pulse text-xs">Loading your lectures…</span>
              </div>
            ) : lecturesError ? (
              <div className="bg-ns border border-nrbr rounded-lg p-5 text-center shadow-ev1">
                <p className="text-12 text-nrt mb-3">Couldn't load your lectures. Check your connection and try again.</p>
                <Button variant="outline" className="px-3 py-1.5 rounded-md text-11 gap-1.5" onClick={loadLectures}>
                  <RefreshCw size={12} /> Try again
                </Button>
              </div>
            ) : userLectures.length === 0 ? (
              <div className="bg-ns border border-bdr2 rounded-lg p-6 text-center shadow-ev1">
                <BookOpen size={24} strokeWidth={1.5} className="mx-auto text-nt4 mb-2" />
                <h3 className="text-12 font-medium text-nt mb-1">No personal lectures yet</h3>
                <p className="text-11 text-nt3 max-w-sm mx-auto leading-relaxed font-sans">
                  Paste a YouTube link or upload a class recording above. A 30-minute lecture is usually ready in a few
                  minutes. While you wait, open a demo below to see what you'll get.
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
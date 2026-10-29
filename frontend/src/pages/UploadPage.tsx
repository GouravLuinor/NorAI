import { useCallback, useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Film, Upload, Link2, FileVideo, ArrowRight, Info, Activity, AlertTriangle, LogOut, RefreshCw } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { SegmentedControl } from '../components/ui/SegmentedControl'
import { Select } from '../components/ui/Select'
import { Wordmark } from '../components/brand/Wordmark'
import { FOCUS_RING } from '../components/ui/shared'
import { apiFetchRaw } from '../lib/http'
import { useAuthStore } from '../stores/useAuthStore'
import { useCourseStore } from '../stores/useCourseStore'
import { useRateLimitStore } from '../stores/useRateLimitStore'
import { DEFAULT_TRIAL_QUOTA_MINUTES } from '../config/features'
import { formatMinutes, quotaResetLabel } from '../lib/plans'

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


  const logout = useAuthStore((s) => s.logout)

  return (
    <div id="main" className="min-h-screen bg-nb flex flex-col items-center pb-16">
      <header className="w-full border-b border-bdr bg-ns">
        <div className="mx-auto max-w-3xl flex items-center justify-between gap-4 px-4 sm:px-6 py-3">
          <button
            onClick={() => navigate('/')}
            className={`flex items-center rounded-sm cursor-pointer ${FOCUS_RING}`}
            title="NorAI home"
          >
            <Wordmark size="md" />
          </button>

          <div className="flex items-center gap-3 min-w-0">
            {user && (
              <span className="text-14 text-nt3 truncate hidden sm:inline-block">
                {user.email}
              </span>
            )}
            <button
              onClick={async () => {
                await logout()
                navigate('/')
              }}
              className={`shrink-0 flex items-center gap-1.5 px-3 h-9 rounded-md border border-bdr2 hover:bg-ns2 text-nt2 hover:text-nt text-14 font-bold transition-colors cursor-pointer ${FOCUS_RING}`}
              title="Sign out of your account"
            >
              <LogOut size={15} strokeWidth={1.75} />
              <span>Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <div className="w-full max-w-3xl px-4 sm:px-6 pt-10 flex flex-col gap-14">

        {/* Add a lecture */}
        <section aria-labelledby="add-heading">
          <div className="mb-6">
            <h1 id="add-heading" className="font-serif font-semibold text-32 leading-tight text-nt">Add a lecture</h1>
            <p className="mt-2 text-16 text-nt2 max-w-[56ch] leading-relaxed">
              Paste a YouTube link or upload the recording. You get notes, a revision sheet, a quiz, flashcards and a
              tutor for it, usually within a few minutes.
            </p>
          </div>

          {/* Input Card */}
          <div className="bg-ns border border-bdr rounded-lg p-5 sm:p-6 shadow-ev1">
            {/* Segmented Control */}
            <SegmentedControl<InputType>
              containerClass="grid grid-cols-3 gap-1 bg-ns2 rounded-md p-1 mb-4"
              itemClass="flex items-center justify-center gap-2 h-9 rounded-[4px] text-14 font-bold transition-colors cursor-pointer"
              activeClass="bg-ns text-np shadow-ev1"
              inactiveClass="text-nt3 hover:text-nt"
              options={[
                { value: 'youtube', label: 'YouTube', prefix: <Film size={15} strokeWidth={1.75} /> },
                { value: 'upload', label: 'Upload', prefix: <Upload size={15} strokeWidth={1.75} /> },
                { value: 'drive', label: 'Drive', prefix: <Link2 size={15} strokeWidth={1.75} /> },
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
                  className={`w-full flex flex-col items-center justify-center gap-3 p-8 border-[1.5px] border-dashed rounded-md transition cursor-pointer hover:border-np ${FOCUS_RING} ${dragActive ? 'border-np bg-npb/50' : 'border-bdr2'}`}
                >
                  <FileVideo size={28} strokeWidth={1.5} className="text-nt3" />
                  <span className="text-15 text-nt2">
                    {file ? file.name : dragActive ? 'Drop the video to upload' : 'Click to choose or drag a video file here'}
                  </span>
                  <span className="text-13 text-nt3">MP4, MOV, MKV, AVI or WebM, up to 2 GB</span>
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
                      ? 'Paste a YouTube link'
                      : 'Paste a Google Drive share link'
                  }
                  className={`w-full bg-ns border-[1.5px] border-nt rounded-md px-4 h-12 pr-12 text-16 text-nt placeholder:text-nt4 focus:border-np focus:outline-hidden transition-colors ${FOCUS_RING}`}
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-nt3">
                  {inputType === 'youtube' ? <Film size={15} strokeWidth={1.5} /> : <Link2 size={15} strokeWidth={1.5} />}
                </div>
              </div>
            )}

            {/* Estimate Panel (P1.8): length, wait time and plan fit */}
            {estLoading && (
              <div className="mt-3 flex items-center gap-2 text-14 text-nt3" role="status">
                <Activity size={14} strokeWidth={1.75} />
                <span>Checking the lecture length…</span>
              </div>
            )}

            {!estLoading && estimate?.available && (
              <div className="mt-3 rounded-md border border-bdr bg-ns2 px-3.5 py-3" aria-live="polite">
                <div className="flex items-start gap-2">
                  <Info size={15} strokeWidth={1.75} className="text-nt3 mt-0.5 shrink-0" />
                  <div className="text-14 text-nt2 leading-relaxed tabular-nums">
                    {estimate.title && <span className="block text-nt font-medium truncate">{estimate.title}</span>}
                    {estimate.duration_min !== undefined && (
                      <span>About {Math.max(1, Math.round(estimate.duration_min))} min of lecture</span>
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
                  <div className="mt-2 flex items-start gap-1.5 text-14 text-nrt">
                    <AlertTriangle size={14} strokeWidth={1.5} className="mt-0.5 shrink-0" />
                    <span>
                      {estimate.plan_max_min !== undefined && (estimate.duration_min ?? 0) > estimate.plan_max_min
                        ? `Longer than the ${estimate.plan_max_min}-minute limit per lecture.`
                        : `Needs ${estimate.minutes_needed} lecture-minutes; you have ${estimate.remaining_minutes} left.`}
                      {quota?.resets_at && ` Your minutes ${quotaResetLabel(quota.resets_at)}.`}
                    </span>
                  </div>
                )}
              </div>
            )}

            {!estLoading && estimate && !estimate.available && (
              <div className="mt-3 flex items-center gap-1.5 text-14 text-nt3">
                <Info size={14} strokeWidth={1.75} />
                <span>
                  {inputType === 'drive'
                    ? "We'll check the length once the video downloads."
                    : "Couldn't read the length yet. You can still start; we'll check it during processing."}
                </span>
              </div>
            )}

            {isDailyLimited && (
              <div className="mt-3 flex items-start gap-2 text-14 text-nat rounded-md border border-nabr bg-nab px-3.5 py-3" role="status">
                <AlertTriangle size={15} strokeWidth={1.5} className="mt-0.5 shrink-0" />
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
              <div className="mt-3 flex items-start gap-1.5 text-14 text-nrt rounded-md border border-nrbr bg-nrb px-3.5 py-3" role="alert">
                <AlertTriangle size={15} strokeWidth={1.5} className="mt-0.5 shrink-0" />
                <span>
                  {submitError}
                  {submitErrorIsQuota && quota?.resets_at && ` Your minutes ${quotaResetLabel(quota.resets_at)}.`}
                </span>
              </div>
            )}

            {/* P6.4: file the new lecture into a course (optional) */}
            <div className="mt-4 flex flex-col gap-1">
              <label htmlFor="course-select" className="text-14 font-bold text-nt2">
                Add to a course <span className="font-normal text-nt3">(optional)</span>
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
              className="w-full mt-5 gap-2 h-12 rounded-md text-16 font-bold disabled:opacity-40 disabled:cursor-not-allowed"
            >
                            {isDailyLimited
                ? 'Paused for today'
                : submitting === 'uploading'
                  ? 'Uploading video…'
                  : submitting === 'starting'
                    ? 'Starting…'
                    : 'Make my notes'}
            </Button>
          </div>

          <div className="text-14 text-nt3 mt-3">
            <span className="font-mono">
              {quota ? (
                <>
                  {formatMinutes(quota.remaining_minutes)} of lectures left
                  {quota.resets_at ? ` · ${quotaResetLabel(quota.resets_at)}` : ''}
                  {quota.max_lecture_minutes ? ` · lectures up to ${quota.max_lecture_minutes} min` : ''}
                </>
              ) : (
                `Free: ${DEFAULT_TRIAL_QUOTA_MINUTES} lecture-minutes every 30 days.`
              )}
            </span>
          </div>
        </section>


        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Section 2: Your Personal Lectures                                 */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <section aria-labelledby="library-heading">
          <div className="flex items-baseline justify-between mb-3">
            <h2 id="library-heading" className="text-20 font-bold text-nt">Your library</h2>
            {!loadingLectures && !lecturesError && userLectures.length > 0 && (
              <span className="font-mono text-14 text-nt3">
                {userLectures.length} {userLectures.length === 1 ? 'lecture' : 'lectures'}
              </span>
            )}
          </div>

          {loadingLectures ? (
            <div className="space-y-2" role="status" aria-label="Loading your lectures">
              {[0, 1].map((i) => <div key={i} className="h-[68px] rounded-md bg-ns2 animate-pulse" />)}
            </div>
          ) : lecturesError ? (
            <div className="bg-ns border border-nrbr rounded-md p-5">
              <p className="text-15 text-nrt mb-3">Couldn't load your lectures. Check your connection and try again.</p>
              <Button variant="outline" className="px-3 h-9 rounded-md text-14 font-bold gap-1.5 border-bdr2" onClick={loadLectures}>
                <RefreshCw size={14} strokeWidth={1.75} /> Try again
              </Button>
            </div>
          ) : userLectures.length === 0 ? (
            <div className="rounded-md border-[1.5px] border-dashed border-bdr2 p-6">
              <h3 className="text-16 font-bold text-nt mb-1">Nothing on your shelf yet</h3>
              <p className="text-15 text-nt2 max-w-[56ch] leading-relaxed">
                Add a lecture above and it lands here. While it processes, open a demo lecture below to see what
                you'll get.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-bdr border-y border-bdr">
              {userLectures.map((lec) => (
                <li key={lec.lecture_id}>
                  <button
                    onClick={() => navigate(`/workspace/${lec.lecture_id}`)}
                    className={`w-full text-left py-4 px-1 flex items-center gap-4 hover:bg-ns2 transition-colors group cursor-pointer ${FOCUS_RING}`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-16 font-bold text-nt truncate group-hover:text-np transition-colors">
                        {lec.title || 'Untitled lecture'}
                      </div>
                      <div className="mt-0.5 text-14 text-nt3">
                        {lec.chapter_count || 0} {lec.chapter_count === 1 ? 'chapter' : 'chapters'}
                        {lec.created_at && <> · added {getRelativeTime(lec.created_at)}</>}
                      </div>
                    </div>
                    <ArrowRight size={18} strokeWidth={1.75} className="text-nt3 group-hover:text-np shrink-0" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Section 3: Featured Demo Workspaces                               */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <section aria-labelledby="demo-heading">
          <h2 id="demo-heading" className="text-20 font-bold text-nt">Demo lectures</h2>
          <p className="mt-1 mb-3 text-15 text-nt2">
            Already processed, free to open. They never use your minutes.
          </p>
          <ul className="divide-y divide-bdr border-y border-bdr">
            {demoLectures.map((lec) => (
              <li key={lec.lecture_id}>
                <button
                  onClick={() => navigate(`/workspace/${lec.lecture_id}`)}
                  className={`w-full text-left py-4 px-1 flex items-center gap-4 hover:bg-ns2 transition-colors group cursor-pointer ${FOCUS_RING}`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-16 font-bold text-nt truncate group-hover:text-np transition-colors">
                      {lec.title}
                    </div>
                    <div className="mt-0.5 text-14 text-nt3">
                      {lec.category && <>{lec.category} · </>}
                      {lec.chapter_count || 0} chapters
                    </div>
                  </div>
                  <ArrowRight size={18} strokeWidth={1.75} className="text-nt3 group-hover:text-np shrink-0" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
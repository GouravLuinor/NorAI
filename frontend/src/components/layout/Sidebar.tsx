import { useEffect, useCallback, useRef } from 'react'
import { useChapterStore } from '../../stores/useChapterStore'
import { useThreadStore } from '../../stores/useThreadStore'
import { useLectureStore } from '../../stores/useLectureStore'
import { useAuthStore } from '../../stores/useAuthStore'
import { useToastStore } from '../../stores/useToastStore'
import { PanelLeftClose, Trash2, Plus, LogOut } from 'lucide-react'
import { ThemeToggle } from '../ui/ThemeToggle'
import { ShelfMark } from '../ui/ShelfMark'
import { Wordmark } from '../brand/Wordmark'
import { IconButton } from '../ui/IconButton'
import { FOCUS_RING } from '../ui/shared'
import { useVideoStore } from '../../stores/useVideoStore'
import { formatTimestamp } from '../../lib/video'
import { useNavigate } from 'react-router-dom'
import { Select } from '../ui/Select'
import type { QuotaInfo } from '../../stores/useAuthStore'
import { DEFAULT_TRIAL_QUOTA_MINUTES, DEMO_LECTURES_CONFIG } from '../../config/features'
import { quotaResetLabel } from '../../lib/plans'


const planLabel = (tier?: string) =>
  tier === 'pro' ? 'Pro' : tier === 'starter' ? 'Starter' : 'Free'

const quotaUsed = (q: QuotaInfo | null) => q?.used_minutes_this_month ?? 0

const quotaPct = (q: QuotaInfo | null) => {
  const max = Math.max(1, q?.monthly_minutes_quota ?? 1)
  const used = q?.used_minutes_this_month ?? 0
  const pct = Math.min(100, Math.round((used / max) * 100))
  return `${pct}%`
}


interface SidebarProps {
  onToggleCollapse: () => void
  /** Drawer contexts (mobile) always render the expanded sidebar even if the
   *  store has `sidebarCollapsed` set — otherwise the drawer shows blank. */
  forceExpanded?: boolean
}

export function Sidebar({ onToggleCollapse, forceExpanded = false }: SidebarProps) {
  const activeChapterId  = useChapterStore(s => s.activeChapterId)
  const sidebarCollapsed = useChapterStore(s => s.sidebarCollapsed) && !forceExpanded
  const setChapter       = useChapterStore(s => s.setChapter)
  const addToast = useToastStore(s => s.addToast)

  const threads             = useThreadStore(s => s.threads)
  const threadId            = useThreadStore(s => s.threadId)
  const labels              = useThreadStore(s => s.labels)
  const getThreadLabel      = useThreadStore(s => s.getThreadLabel)
  const setThreadId         = useThreadStore(s => s.setThreadId)
  const loadThreads         = useThreadStore(s => s.loadThreads)
  const loadThreadMessages  = useThreadStore(s => s.loadThreadMessages)
  const createThread        = useThreadStore(s => s.createThread)
  const deleteThread        = useThreadStore(s => s.deleteThread)

  // Lecture selection
  const lectures            = useLectureStore(s => s.lectures)
  const activeLectureId     = useLectureStore(s => s.activeLectureId)
  const chapters         = useChapterStore(s => s.chapters)           // ← add
  const chaptersLoading  = useChapterStore(s => s.chaptersLoading)
  const setActiveLecture    = useLectureStore(s => s.setActiveLecture)
  const loadLectures        = useLectureStore(s => s.loadLectures)
  const navigate = useNavigate()

  // P6.3: video seek targets for chapter rows.
  const videoEmbeddable  = useVideoStore(s => s.embeddable)
  const videoMap         = useVideoStore(s => s.map)
  const seekToChapter    = useVideoStore(s => s.seekToChapter)

  // Quota badge (P2.4): live data from GET /quota.
  const user           = useAuthStore(s => s.user)
  const logout         = useAuthStore(s => s.logout)
  const openAuthModal  = useAuthStore(s => s.openAuthModal)
  const quota          = useAuthStore(s => s.quota)
  const refreshQuota   = useAuthStore(s => s.refreshQuota)
  const authToken      = useAuthStore(s => s.token)

  const switchCooldownRef = useRef(false)

  useEffect(() => {
    if (authToken) void refreshQuota()
  }, [authToken, refreshQuota])

  useEffect(() => {
    if (!activeLectureId || activeLectureId === 'default') return
    let active = true
    useThreadStore.getState().resetForLectureChange()
    loadThreads().then(() => {
      if (!active) return
      const current = useThreadStore.getState().threadId
      if (current) {
        loadThreadMessages(current)
      }
    })
    loadLectures()
    // RC-FIX: cleanup flag prevents stale promise callbacks in Strict Mode
    return () => { active = false }
  }, [activeLectureId, user?.id, loadLectures, loadThreads, loadThreadMessages])

  // RC-FIX: Debounce rapid thread clicks to prevent overlapping
  // setThreadId + loadThreadMessages calls that cause layout glitch (Bug 5)
  const handleThreadClick = useCallback((id: string) => {
    if (switchCooldownRef.current || id === threadId) return
    switchCooldownRef.current = true
    setThreadId(id)
    loadThreadMessages(id)
    setTimeout(() => { switchCooldownRef.current = false }, 300)
  }, [setThreadId, loadThreadMessages, threadId])

  // FIX: only call onToggleCollapse — Workspace already toggles the store
  const handleCollapse = useCallback(() => {
    onToggleCollapse()
  }, [onToggleCollapse])

  const handleCreateThread = useCallback(async () => {
    await createThread()
    addToast('Thread created', 'success')
  }, [createThread, addToast])

  const handleDeleteThread = useCallback((t: string) => {
    deleteThread(t)
    addToast('Thread deleted', 'info')
  }, [deleteThread, addToast])

  return (
    <nav aria-label="Lecture navigation" className="rail relative overflow-hidden flex flex-col h-full">
      {/* Expanded — use w-full to prevent overlap when sidebar is narrow */}
      <div
        inert={sidebarCollapsed}
        className={`w-full flex flex-col h-full overflow-y-auto transition-opacity duration-240 ${
          sidebarCollapsed ? 'opacity-0 pointer-events-none' : 'opacity-100'
        }`}
      >
        {/* Header */}
        <div className="px-4 pt-4 pb-2">
          <div className="flex items-center gap-2 mb-5">
            <button
              onClick={() => navigate('/')}
              className={`flex items-center rounded-sm cursor-pointer text-left ${FOCUS_RING}`}
              title="NorAI home"
            >
              <Wordmark size="md" />
            </button>
            <IconButton
              label="Collapse sidebar"
              onClick={handleCollapse}
              className="ml-auto w-7 h-7 rounded-sm"
            >
              <PanelLeftClose size={15} strokeWidth={1.75} />
            </IconButton>
          </div>

          {/* ── Lecture selector ──────────────────────────────── */}
          <div className="mb-5">
            <div className="spec-label mb-1.5">Lecture</div>
            <Select
              ariaLabel="Select lecture"
              value={activeLectureId || ''}
              onChange={(newId) => {
                setActiveLecture(newId)
                navigate(`/workspace/${newId}`)
              }}
              options={
                !user
                  ? DEMO_LECTURES_CONFIG.map((d) => ({ value: d.id, label: d.title }))
                  : lectures.map((l) => ({ value: l.lecture_id, label: l.title }))
              }
            />
          </div>

          {/* Chapters: call ranges. The shelf mark walks the video there. */}
          <div className="spec-label mb-2">Chapters</div>
          {chaptersLoading ? (
            <div className="space-y-2" aria-hidden="true">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-10 rounded-md bg-ns2 animate-pulse" style={{ width: `${92 - i * 8}%` }} />
              ))}
            </div>
          ) : chapters.length === 0 ? (
            <p className="text-13 text-nt3 py-2">No chapters yet. They appear when the lecture finishes processing.</p>
          ) : (
            <ul className="space-y-1">
            {chapters.map((ch) => {
              const chTime = videoMap?.chapters.find((c) => c.chapter_id === ch.id)
              const showSeek = videoEmbeddable && chTime?.start_sec != null
              const isCurrent = activeChapterId === ch.id
              const num = String(ch.id).padStart(2, '0')
              return (
                <li
                  key={ch.id}
                  data-current={isCurrent ? 'true' : undefined}
                  className="rail-range grid grid-cols-[auto_1fr] items-start gap-2.5 px-2 py-2 rounded-md transition-colors"
                >
                  <ShelfMark
                    top={`CH ${num}`}
                    time={chTime?.start_sec != null ? formatTimestamp(chTime.start_sec) : undefined}
                    className="min-w-[52px]"
                    label={showSeek
                      ? `Chapter ${ch.id}: play the video from ${formatTimestamp(chTime.start_sec)}`
                      : `Open chapter ${ch.id}`}
                    onClick={() => {
                      setChapter(ch.id)
                      if (showSeek) seekToChapter(ch.id)
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setChapter(ch.id)}
                    aria-current={isCurrent ? 'true' : undefined}
                    className={`text-left text-14 leading-snug pt-0.5 rounded-sm cursor-pointer ${isCurrent ? 'font-bold' : ''} ${FOCUS_RING}`}
                  >
                    {ch.title}
                  </button>
                </li>
              )
            })}
            </ul>
          )}
        </div>

        {/* Threads */}
        <div className="px-4 py-3 mt-2 border-t border-bdr">
          <div className="flex items-center mb-1.5">
            <div className="spec-label">Conversations</div>
            <button
              type="button"
              onClick={handleCreateThread}
              className={`ml-auto flex items-center gap-1 text-12 font-bold text-np hover:underline rounded-sm cursor-pointer ${FOCUS_RING}`}
            >
              <Plus size={13} strokeWidth={2} /> New
            </button>
          </div>
          {threads.length === 0 && (
            <p className="text-13 text-nt3 py-1.5">
              Ask Nora a question to start one.
            </p>
          )}
          {threads.map((t) => (
            <div
              key={t}
              className="grid grid-cols-[1fr_auto] items-center gap-0.5 mb-0.5 group"
            >
              <button
                type="button"
                onClick={() => handleThreadClick(t)}
                aria-current={threadId === t ? 'true' : undefined}
                className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-left text-13 transition truncate ${FOCUS_RING} ${
                  threadId === t
                    ? 'text-nt bg-ns3 font-bold'
                    : 'text-nt2 hover:bg-ns2'
                }`}
              >
                <span className="truncate flex-1">{labels[t] || getThreadLabel(t)}</span>
              </button>
              <IconButton
                label={`Delete conversation ${labels[t] || getThreadLabel(t)}`}
                variant="bare"
                onClick={() => handleDeleteThread(t)}
                className="opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 p-1 rounded-sm hover:bg-ns2"
              >
                <Trash2 size={13} strokeWidth={1.75} className="text-nt3 hover:text-nr" />
              </IconButton>
            </div>
          ))}
        </div>

        <div className="mt-auto" />

        {/* Account: minutes left, or the demo notice for guests */}
        <div className="px-4 pt-3 pb-2">
          {!user ? (
            <div className="p-3 rounded-md bg-ns3">
              <p className="text-14 font-bold text-nt">This is a demo lecture</p>
              <p className="text-13 text-nt3 mt-1 mb-3 leading-snug">
                Make a free account to turn your own lectures into notes, quizzes and a tutor.
              </p>
              <button
                onClick={() => openAuthModal('signup')}
                className={`w-full py-2 px-3 rounded-md bg-npf hover:bg-npfh text-npfg text-14 font-bold transition-colors cursor-pointer active:translate-y-[1px] ${FOCUS_RING}`}
              >
                Create free account
              </button>
            </div>
          ) : (
            <div className="p-3 rounded-md bg-ns3">
              <div className="flex items-baseline justify-between mb-2">
                <span className="text-13 font-bold text-nt">
                  {planLabel(quota?.plan_tier)} plan
                </span>
                {quota && quota.plan_tier !== 'free' && (
                  <button
                    onClick={() => navigate('/billing')}
                    className={`text-12 text-np font-bold hover:underline rounded-sm cursor-pointer ${FOCUS_RING}`}
                  >
                    Manage
                  </button>
                )}
              </div>
              <div
                className="w-full bg-ns4 h-1.5 rounded-full overflow-hidden mb-1.5"
                role="progressbar"
                aria-valuenow={quotaUsed(quota)}
                aria-valuemin={0}
                aria-valuemax={Math.max(1, quota?.monthly_minutes_quota ?? DEFAULT_TRIAL_QUOTA_MINUTES)}
                aria-label="Lecture minutes used"
              >
                <div
                  className="bg-np h-full rounded-full transition-all duration-200"
                  style={{ width: quotaPct(quota) }}
                />
              </div>
              <div className="text-12 text-nt3 flex justify-between font-mono">
                <span>
                  {quota?.used_minutes_this_month ?? 0} / {quota?.monthly_minutes_quota ?? DEFAULT_TRIAL_QUOTA_MINUTES} min
                </span>
                {quota?.resets_at && (
                  <span className="font-sans">{quotaResetLabel(quota.resets_at)}</span>
                )}
              </div>
              <div className="mt-3 flex gap-4 text-13">
                <button
                  onClick={() => navigate('/courses')}
                  className={`text-nt font-bold hover:underline rounded-sm cursor-pointer ${FOCUS_RING}`}
                >
                  Courses
                </button>
                <button
                  onClick={() => navigate('/usage')}
                  className={`text-nt font-bold hover:underline rounded-sm cursor-pointer ${FOCUS_RING}`}
                >
                  Usage
                </button>
              </div>

              <div className="mt-3 pt-2.5 border-t border-bdr flex items-center justify-between gap-2 text-12">
                <span className="truncate text-nt3" title={user.email}>{user.email}</span>
                <button
                  onClick={async () => {
                    await logout()
                    navigate('/')
                  }}
                  className={`shrink-0 text-nt3 hover:text-nr flex items-center gap-1 font-bold transition-colors rounded-sm cursor-pointer ${FOCUS_RING}`}
                  title="Sign out of NorAI"
                >
                  <LogOut size={13} strokeWidth={1.75} />
                  <span>Sign out</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Theme toggle */}
        <div className="px-4 pb-4 pt-1">
          <ThemeToggle />
        </div>
      </div>

      {/* Collapsed rail bottom actions (P4.3 accessibility) */}
      {sidebarCollapsed && user && (
        <div className="absolute bottom-2 left-0 right-0 flex justify-center pointer-events-auto">
          <IconButton
            label={`Sign out (${user.email})`}
            onClick={async () => {
              await logout()
              navigate('/')
            }}
            className="w-8 h-8 rounded-sm text-nt3 hover:text-nr hover:bg-ns2"
          >
            <LogOut size={15} strokeWidth={1.75} />
          </IconButton>
        </div>
      )}
    </nav>
  )
}
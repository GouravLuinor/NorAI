import { useEffect, useCallback, useRef } from 'react'
import { useChapterStore } from '../../stores/useChapterStore'
import { useThreadStore, getOrCreateLabel } from '../../stores/useThreadStore'
import { useLectureStore } from '../../stores/useLectureStore'
import { PanelLeftClose, Trash2 } from 'lucide-react'
import { useToastStore } from '../../stores/useToastStore'
import { ThemeToggle } from '../ui/ThemeToggle'
import { Button } from '../ui/Button'
import { IconButton } from '../ui/IconButton'
import { FOCUS_RING } from '../ui/shared'
import { useNavigate } from 'react-router-dom'


interface SidebarProps {
  onToggleCollapse: () => void
}

export function Sidebar({ onToggleCollapse }: SidebarProps) {
  const activeChapterId  = useChapterStore(s => s.activeChapterId)
  const sidebarCollapsed = useChapterStore(s => s.sidebarCollapsed)
  const setChapter       = useChapterStore(s => s.setChapter)
  const addToast = useToastStore(s => s.addToast)

  const threads             = useThreadStore(s => s.threads)
  const threadId            = useThreadStore(s => s.threadId)
  const setThreadId         = useThreadStore(s => s.setThreadId)
  const loadThreads         = useThreadStore(s => s.loadThreads)
  const loadThreadMessages  = useThreadStore(s => s.loadThreadMessages)
  const createThread        = useThreadStore(s => s.createThread)
  const deleteThread        = useThreadStore(s => s.deleteThread)

  // Lecture selection
  const lectures            = useLectureStore(s => s.lectures)
  const activeLectureId     = useLectureStore(s => s.activeLectureId)
  const chapters         = useChapterStore(s => s.chapters)           // ← add
  const setActiveLecture    = useLectureStore(s => s.setActiveLecture)
  const loadLectures        = useLectureStore(s => s.loadLectures)
  const navigate = useNavigate()

  const switchCooldownRef = useRef(false)

  useEffect(() => {
    if (!activeLectureId || activeLectureId === 'default') return
    let active = true
    useThreadStore.getState().resetForLectureChange()
    loadThreads().then(() => {
      if (!active) return
      const current = useThreadStore.getState().threadId
      if (current && current !== 'default') {
        loadThreadMessages(current)
      }
    })
    loadLectures()
    // RC-FIX: cleanup flag prevents stale promise callbacks in Strict Mode
    return () => { active = false }
  }, [activeLectureId])

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
    <div className="bg-ns border-r border-bdr relative overflow-hidden flex flex-col h-full">
      {/* Expanded — use w-full to prevent overlap when sidebar is narrow */}
      <div
        inert={sidebarCollapsed}
        className={`w-full flex flex-col h-full transition-opacity duration-240 ${
          sidebarCollapsed ? 'opacity-0 pointer-events-none' : 'opacity-100'
        }`}
      >
        {/* Header */}
        <div className="p-3.5 pb-3">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-5.5 h-5.5 rounded-sm bg-npf flex items-center justify-center text-11 font-medium text-npfg shadow-ev1 tracking-tight fold-marks relative">
              N
            </div>
            <span className="font-display text-13 font-medium text-nt tracking-tight">NorAI</span>
            <IconButton
              label="Collapse sidebar"
              onClick={handleCollapse}
              className="ml-auto w-5 h-5 rounded-sm"
            >
              <PanelLeftClose size={12} strokeWidth={1.5} />
            </IconButton>
          </div>

          <div className="flex items-center gap-1.5 px-1.5 py-1.5 rounded-md bg-ns2 mb-3.5 text-2xs text-nt2 border border-bdr">
            <div className="w-1 h-1 rounded-full bg-np" />
            Now studying{' '}
            <strong className="text-nt font-medium">
              Ch {String(activeChapterId).padStart(2, '0')} ·{' '}
              {chapters.find((c) => c.id === activeChapterId)?.title}
            </strong>
          </div>

          {/* ── Lecture selector ──────────────────────────────── */}
          <div className="mb-3">
            <div className="spec-label mb-1.5">01. Lecture</div>
            <select
              aria-label="Select lecture"
              value={activeLectureId || ''}
              onChange={(e) => {
                const newId = e.target.value
                setActiveLecture(newId)
                navigate(`/workspace/${newId}`)   // ← add this
              }}

              className={`w-full bg-nb border border-bdr2 rounded-md px-2 py-1 text-11 text-nt2 focus:border-np transition ${FOCUS_RING}`}
            >
              {lectures.map((l) => (
                <option key={l.lecture_id} value={l.lecture_id}>
                  {l.title}
                </option>
              ))}
            </select>
          </div>
          {/* ──────────────────────────────────────────────────── */}

          {/* Chapter list */}
          <div className="spec-label mb-1.5">02. Chapters</div>
          <ul className="space-y-0.5">
            {chapters.map((ch) => (
              <li key={ch.id}>
                <button
                  type="button"
                  onClick={() => setChapter(ch.id)}
                  aria-current={activeChapterId === ch.id ? 'true' : undefined}
                  className={`w-full flex items-center gap-2 px-1.5 py-1.5 rounded-md text-left text-11 transition ${FOCUS_RING} ${
                    activeChapterId === ch.id
                      ? 'bg-npb text-nt font-medium'
                      : 'text-nt3 hover:bg-ns2 hover:text-nt2'
                  }`}
                >
                  <span className="text-3xs font-medium w-3.5 text-nt4">
                    {String(ch.id).padStart(2, '0')}
                  </span>
                  <span className="truncate">{ch.title}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="h-px bg-bdr mx-3.5" />

        {/* Thread list */}
        <div className="flex-1 overflow-hidden px-3.5 py-3.5">
          <div className="spec-label mb-1.5">03. Threads</div>
          {threads.map((t) => (
            <div
              key={t}
              className="grid grid-cols-[1fr_auto] items-center gap-0.5 mb-0.5 group"
            >
              <button
                type="button"
                onClick={() => handleThreadClick(t)}
                aria-current={threadId === t ? 'true' : undefined}
                className={`flex items-center gap-2 px-1.5 py-1.5 rounded-md text-left text-11 transition truncate ${FOCUS_RING} ${
                  threadId === t
                    ? 'text-nt bg-ns3'
                    : 'text-nt3 hover:bg-ns2 hover:text-nt2'
                }`}
              >
                <span
                  className={`w-1 h-1 rounded-full shrink-0 ${
                    threadId === t ? 'bg-np' : 'bg-nt4'
                  }`}
                />
                <span className="truncate flex-1">{getOrCreateLabel(t)}</span>
              </button>
              <IconButton
                label={`Delete thread ${getOrCreateLabel(t)}`}
                variant="bare"
                onClick={() => handleDeleteThread(t)}
                className="opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 p-0.5 rounded hover:bg-ns4"
              >
                <Trash2 size={10} strokeWidth={1.5} className="text-nt4 hover:text-nr" />
              </IconButton>
            </div>
          ))}
        </div>

        <div className="h-px bg-bdr mx-3.5" />

        {/* User Quota Badge */}
        <div className="px-3.5 py-2">
          <div className="p-2 rounded-lg bg-ns2 border border-bdr text-11 font-sans">
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold text-nt text-10 uppercase tracking-wider">Free Trial</span>
              <button
                onClick={() => navigate('/pricing')}
                className="text-10 text-np font-medium hover:underline cursor-pointer"
              >
                Upgrade
              </button>
            </div>
            <div className="w-full bg-ns4 h-1.5 rounded-full overflow-hidden mb-1">
              <div className="bg-np h-full rounded-full w-1/4"></div>
            </div>
            <div className="text-10 text-nt3 flex justify-between">
              <span>Used: 0 / 15 mins</span>
            </div>
          </div>
        </div>

        {/* Theme toggle */}
        <div className="px-3.5 pb-1.5">
          <ThemeToggle />
        </div>

        {/* New thread */}
        <div className="p-3.5 pt-2.5">
        <Button
          variant="outline"
          onClick={handleCreateThread}
          className="w-full py-1.5 rounded-md text-11 gap-1.5 bg-transparent border-bdr2 hover:border-nt4 hover:shadow-ev1 active:translate-y-[1px] active:shadow-none"
        >
          <span className="text-xs">+</span> New thread
        </Button>
        </div>

      </div>
    </div>
  )
}
import { useEffect, useCallback, useRef } from 'react'
import { chapters } from '../../mocks/chapters'
import { useChapterStore } from '../../stores/useChapterStore'
import { useThreadStore, getOrCreateLabel } from '../../stores/useThreadStore'
import { PanelLeftClose, PanelLeftOpen, Trash2 } from 'lucide-react'
import { useToastStore } from '../../stores/useToastStore'
import { ThemeToggle } from '../ui/ThemeToggle'

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

  const initialLoadDone = useRef(false)

  useEffect(() => {
    if (initialLoadDone.current) return
    initialLoadDone.current = true

    loadThreads().then(() => {
      const active = useThreadStore.getState().threadId
      if (active && active !== 'default') {
        loadThreadMessages(active)
      }
    })
  }, [])

  const handleThreadClick = useCallback((id: string) => {
    setThreadId(id)
    loadThreadMessages(id)
  }, [setThreadId, loadThreadMessages])

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
      {/* Collapsed: show open button */}
      <div
        className={`absolute inset-0 flex items-start justify-center pt-3.5 transition-opacity duration-240 ${
          sidebarCollapsed ? 'opacity-100 z-10' : 'opacity-0 pointer-events-none -z-10'
        }`}
      >
        <button
          onClick={handleCollapse}
          className="w-8 h-8 rounded-md flex items-center justify-center text-nt3 hover:bg-ns2 hover:text-nt2 transition"
          aria-label="Open sidebar"
        >
          <PanelLeftOpen size={14} />
        </button>
      </div>

      {/* Expanded — use w-full to prevent overlap when sidebar is narrow */}
      <div
        className={`w-full flex flex-col h-full transition-opacity duration-240 ${
          sidebarCollapsed ? 'opacity-0 pointer-events-none' : 'opacity-100'
        }`}
      >
        {/* Header */}
        <div className="p-3.5 pb-3">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-5.5 h-5.5 rounded-md bg-np flex items-center justify-center text-[11px] font-medium text-white shadow-sm tracking-tight">
              N
            </div>
            <span className="text-[13px] font-medium text-nt tracking-tight">NorAI</span>
            <button
              onClick={handleCollapse}
              className="ml-auto w-5 h-5 rounded-md flex items-center justify-center text-nt3 hover:bg-ns2 hover:text-nt2 transition"
              aria-label="Collapse sidebar"
            >
              <PanelLeftClose size={12} />
            </button>
          </div>

          <div className="flex items-center gap-1.5 px-1.5 py-1.5 rounded-lg bg-ns2 mb-3.5 text-[10px] text-nt2">
            <div className="w-1 h-1 rounded-full bg-np" />
            Now studying{' '}
            <strong className="text-nt font-medium">
              Ch {String(activeChapterId).padStart(2, '0')} ·{' '}
              {chapters.find((c) => c.id === activeChapterId)?.title}
            </strong>
          </div>

          {/* Chapter list */}
          <div className="text-[9px] font-medium text-nt4 uppercase tracking-wider mb-1.5">
            Chapters
          </div>
          <ul className="space-y-0.5">
            {chapters.map((ch) => (
              <li
                key={ch.id}
                onClick={() => setChapter(ch.id)}
                className={`flex items-center gap-2 px-1.5 py-1.5 rounded-md cursor-pointer text-[11px] transition ${
                  activeChapterId === ch.id
                    ? 'bg-npb text-np'
                    : 'text-nt3 hover:bg-ns2 hover:text-nt2'
                }`}
              >
                <span className="text-[9px] font-medium w-3.5 opacity-70">
                  {String(ch.id).padStart(2, '0')}
                </span>
                <span className="truncate">{ch.title}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="h-px bg-bdr mx-3.5" />

        {/* Thread list */}
        <div className="flex-1 overflow-hidden px-3.5 py-3.5">
          <div className="text-[9px] font-medium text-nt4 uppercase tracking-wider mb-1.5">
            Threads
          </div>
          {threads.map((t) => (
            <div
              key={t}
              onClick={() => handleThreadClick(t)}
              className={`flex items-center gap-2 px-1.5 py-1.5 rounded-md cursor-pointer text-[11px] transition truncate mb-0.5 group ${
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
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleDeleteThread(t)
                }}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-ns4"
                aria-label="Delete thread"
              >
                <Trash2 size={10} className="text-nt4 hover:text-nr" />
              </button>
            </div>
          ))}
        </div>

        <div className="h-px bg-bdr mx-3.5" />

        {/* Theme toggle */}
        <div className="px-3.5 pb-1.5">
          <ThemeToggle />
        </div>

        {/* New thread */}
        <div className="p-3.5 pt-2.5">
          <button
            onClick={handleCreateThread}
            className="w-full py-1.5 rounded-lg border border-bdr2 bg-transparent text-nt3 text-[11px] flex items-center justify-center gap-1.5 hover:bg-ns2 hover:text-nt2 hover:border-bdr2 transition active:scale-98"
          >
            <span className="text-xs">+</span> New thread
          </button>
        </div>
      </div>
    </div>
  )
}
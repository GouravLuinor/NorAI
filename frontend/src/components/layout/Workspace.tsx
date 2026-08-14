import { useState, useEffect, useRef } from 'react'
import { Sidebar } from './Sidebar'
import { DocPanel } from './DocPanel'
import { AIPanel } from './AIPanel'
import { useChapterStore } from '../../stores/useChapterStore'
import { useQuizStore } from '../../stores/useQuizStore'
import { PanelLeftOpen, HelpCircle, Bot, BookOpen, X, Menu } from 'lucide-react'
import { ShortcutsModal } from '../ui/ShortcutsModal'
import { IconButton } from '../ui/IconButton'
import { useParams } from 'react-router-dom'
import { useLectureStore } from '../../stores/useLectureStore'
import { FOCUS_RING } from '../ui/shared'

const SIDEBAR_MIN = 160
const SIDEBAR_MAX = 400
const AI_MIN_TUTOR = 250
const AI_MIN_QUIZ_CARDS = 400
const AI_MAX = 550

export function Workspace() {
  const { sidebarCollapsed, toggleSidebar } = useChapterStore()
  const { lectureId } = useParams<{ lectureId: string }>()
  const { setActiveLecture, loadLectures } = useLectureStore()
  const { loadChapters } = useChapterStore()
  const { aiMode } = useQuizStore()
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(220)
  const [aiPanelWidth, setAiPanelWidth] = useState(268)
  const [tutorAiWidth, setTutorAiWidth] = useState(268)
  const [isDragging, setIsDragging] = useState(false)

  // Responsive state
  const [windowWidth, setWindowWidth] = useState<number>(
    typeof window !== 'undefined' ? window.innerWidth : 1200
  )
  const [mobileTab, setMobileTab] = useState<'doc' | 'ai'>('doc')
  const [aiDrawerOpenTablet, setAiDrawerOpenTablet] = useState(false)
  const [sidebarDrawerOpenMobile, setSidebarDrawerOpenMobile] = useState(false)

  const workspaceRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef<'left' | 'right' | null>(null)

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const isMobile = windowWidth < 768
  const isTablet = windowWidth >= 768 && windowWidth < 1024

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (sidebarDrawerOpenMobile) {
          setSidebarDrawerOpenMobile(false)
          return
        }
        if (aiDrawerOpenTablet) {
          setAiDrawerOpenTablet(false)
          return
        }
        if (!sidebarCollapsed && !isMobile && !document.querySelector('[role="dialog"]')) {
          toggleSidebar()
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [sidebarCollapsed, toggleSidebar, sidebarDrawerOpenMobile, aiDrawerOpenTablet, isMobile])

  useEffect(() => {
    if (lectureId) {
      setActiveLecture(lectureId)
      loadChapters(lectureId)
    }
    loadLectures()
  }, [lectureId, setActiveLecture, loadLectures, loadChapters])

  const minAiWidth = aiMode === 'tutor' || aiMode === 'socratic' ? AI_MIN_TUTOR : AI_MIN_QUIZ_CARDS

  useEffect(() => {
    if ((aiMode === 'tutor' || aiMode === 'socratic') && !isDragging) {
      setTutorAiWidth(aiPanelWidth)
    }
  }, [aiPanelWidth, aiMode, isDragging])

  useEffect(() => {
    if (aiMode !== 'tutor' && aiMode !== 'socratic') {
      if (aiPanelWidth < AI_MIN_QUIZ_CARDS) {
        setAiPanelWidth(AI_MIN_QUIZ_CARDS)
      }
    } else {
      const restored = Math.max(AI_MIN_TUTOR, Math.min(tutorAiWidth, AI_MAX))
      setAiPanelWidth(restored)
    }
  }, [aiMode, tutorAiWidth])

  const handleMouseDown = (side: 'left' | 'right') => (e: React.MouseEvent) => {
    e.preventDefault()
    draggingRef.current = side
    setIsDragging(true)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }

  const handleResizeKeyDown = (side: 'left' | 'right') => (e: React.KeyboardEvent) => {
    const step = 16
    const apply = (fn: () => void) => {
      e.preventDefault()
      fn()
    }
    switch (e.key) {
      case 'ArrowLeft':
        return apply(() =>
          side === 'left'
            ? setSidebarWidth((w) => Math.max(SIDEBAR_MIN, w - step))
            : setAiPanelWidth((w) => Math.max(minAiWidth, w - step))
        )
      case 'ArrowRight':
        return apply(() =>
          side === 'left'
            ? setSidebarWidth((w) => Math.min(SIDEBAR_MAX, w + step))
            : setAiPanelWidth((w) => Math.min(AI_MAX, w + step))
        )
      case 'Home':
        return apply(() =>
          side === 'left' ? setSidebarWidth(SIDEBAR_MIN) : setAiPanelWidth(minAiWidth)
        )
      case 'End':
        return apply(() =>
          side === 'left' ? setSidebarWidth(SIDEBAR_MAX) : setAiPanelWidth(AI_MAX)
        )
    }
  }

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!draggingRef.current || !workspaceRef.current) return
      const rect = workspaceRef.current.getBoundingClientRect()

      if (draggingRef.current === 'left') {
        const relativeX = e.clientX - rect.left
        const w = Math.max(SIDEBAR_MIN, Math.min(SIDEBAR_MAX, relativeX))
        setSidebarWidth(w)
      } else {
        const relativeRight = rect.right - e.clientX
        const w = Math.max(minAiWidth, Math.min(AI_MAX, relativeRight))
        setAiPanelWidth(w)
      }
    }

    const handleMouseUp = () => {
      if (draggingRef.current) {
        draggingRef.current = null
        setIsDragging(false)
        document.body.style.cursor = 'default'
        document.body.style.userSelect = ''
      }
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [minAiWidth])

  const handleSidebarToggle = () => {
    if (isMobile) {
      setSidebarDrawerOpenMobile((prev) => !prev)
    } else {
      toggleSidebar()
    }
  }

  // ── Render Mobile View (< 768px) ───────────────────────────────────────────
  if (isMobile) {
    return (
      <div id="main" className="flex flex-col h-screen bg-nb text-nt text-xs font-sans overflow-hidden">
        {/* Mobile Header */}
        <header className="flex items-center justify-between px-3 py-2 border-b border-bdr bg-ns shrink-0 z-30">
          <IconButton
            label="Open menu"
            onClick={() => setSidebarDrawerOpenMobile(true)}
            className="w-8 h-8 rounded-md bg-ns2 border border-bdr text-nt"
          >
            <Menu size={16} strokeWidth={1.5} />
          </IconButton>

          <div className="flex bg-nb border border-bdr rounded-lg p-0.5">
            <button
              type="button"
              onClick={() => setMobileTab('doc')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition ${
                mobileTab === 'doc' ? 'bg-ns3 text-nt shadow-ev1' : 'text-nt3'
              }`}
            >
              <BookOpen size={13} strokeWidth={1.5} /> Notes
            </button>
            <button
              type="button"
              onClick={() => setMobileTab('ai')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition ${
                mobileTab === 'ai' ? 'bg-ns3 text-nt shadow-ev1' : 'text-nt3'
              }`}
            >
              <Bot size={13} strokeWidth={1.5} /> AI Tutor
            </button>
          </div>

          <IconButton
            label="Shortcuts"
            onClick={() => setShortcutsOpen(true)}
            className="w-8 h-8 rounded-md bg-ns2 border border-bdr text-nt3"
          >
            <HelpCircle size={15} strokeWidth={1.5} />
          </IconButton>
        </header>

        {/* Content Area */}
        <div className="flex flex-col flex-1 relative overflow-hidden">
          {mobileTab === 'doc' ? <DocPanel /> : <AIPanel />}
        </div>

        {/* Mobile Sidebar Slide-Over Drawer */}
        {sidebarDrawerOpenMobile && (
          <div className="fixed inset-0 z-50 flex">
            <div
              className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity"
              onClick={() => setSidebarDrawerOpenMobile(false)}
            />
            <div className="relative w-72 max-w-[80vw] h-full bg-nb z-10 shadow-ev3 border-r border-bdr2">
              <Sidebar forceExpanded onToggleCollapse={() => setSidebarDrawerOpenMobile(false)} />
            </div>
          </div>
        )}

        <ShortcutsModal isOpen={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      </div>
    )
  }

  // ── Render Tablet View (768px – 1024px) ────────────────────────────────────
  if (isTablet) {
    return (
      <div
        id="main"
        ref={workspaceRef}
        className="workspace grid h-screen bg-nb text-nt text-xs font-sans rounded-xl border border-bdr2 overflow-hidden shadow-ev3 relative bg-blueprint-grid fold-marks"
        style={{ gridTemplateColumns: sidebarCollapsed ? '48px 1fr' : `${sidebarWidth}px 1fr` }}
      >
        {sidebarCollapsed && (
          <IconButton
            label="Open sidebar"
            onClick={handleSidebarToggle}
            className="absolute left-2 top-2 z-30 w-8 h-8 rounded-sm bg-ns2 border border-bdr2 shadow-ev2 hover:bg-ns3 active:translate-y-[1px]"
          >
            <PanelLeftOpen size={14} strokeWidth={1.5} />
          </IconButton>
        )}

        <Sidebar onToggleCollapse={handleSidebarToggle} />

        <div className="flex flex-col h-full overflow-hidden relative">
          <DocPanel />

          {/* Toggle button for AI Drawer on Tablet */}
          <button
            type="button"
            onClick={() => setAiDrawerOpenTablet((prev) => !prev)}
            className={`fixed right-4 bottom-16 z-40 flex items-center gap-1.5 px-3 py-2 rounded-lg bg-npf text-npfg shadow-ev2 font-medium hover:bg-npfh transition cursor-pointer ${FOCUS_RING}`}
          >
            <Bot size={15} strokeWidth={1.5} /> {aiDrawerOpenTablet ? 'Close Tutor' : 'Ask Nora'}
          </button>
        </div>

        {/* AI Panel Slide-Over Drawer for Tablet */}
        {aiDrawerOpenTablet && (
          <div className="fixed inset-y-0 right-0 z-50 w-[380px] max-w-[90vw] bg-ns border-l border-bdr2 shadow-ev3 flex flex-col">
            <div className="flex items-center justify-between px-3 py-2 border-b border-bdr bg-ns2">
              <span className="font-display font-medium text-xs text-nt">Nora AI Tutor</span>
              <IconButton
                label="Close tutor panel"
                onClick={() => setAiDrawerOpenTablet(false)}
                className="w-6 h-6 text-nt3 hover:text-nt"
              >
                <X size={14} strokeWidth={1.5} />
              </IconButton>
            </div>
            <div className="flex-1 overflow-hidden">
              <AIPanel />
            </div>
          </div>
        )}

        <ShortcutsModal isOpen={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
      </div>
    )
  }

  // ── Render Desktop View (≥ 1024px) ─────────────────────────────────────────
  const gridColumns = sidebarCollapsed
    ? `48px 1fr ${aiPanelWidth}px`
    : `${sidebarWidth}px 1fr ${aiPanelWidth}px`

  return (
    <div
      id="main"
      ref={workspaceRef}
      className="workspace grid h-screen bg-nb text-nt text-xs font-sans rounded-xl border border-bdr2 overflow-hidden shadow-ev3 relative bg-blueprint-grid fold-marks"
      style={{
        gridTemplateColumns: gridColumns,
        transition: isDragging ? 'none' : 'grid-template-columns 240ms cubic-bezier(0.4,0,0.2,1)',
      }}
    >
      {sidebarCollapsed && (
        <IconButton
          label="Open sidebar"
          onClick={handleSidebarToggle}
          className="absolute left-2 top-2 z-50 w-8 h-8 rounded-sm bg-ns2 border border-bdr2 shadow-ev2 hover:bg-ns3 active:translate-y-[1px] active:shadow-none"
        >
          <PanelLeftOpen size={14} strokeWidth={1.5} />
        </IconButton>
      )}

      <Sidebar onToggleCollapse={handleSidebarToggle} />
      <DocPanel />
      <AIPanel />

      {/* Resizer Separator - Left (Sidebar) */}
      {!sidebarCollapsed && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          aria-valuenow={sidebarWidth}
          aria-valuemin={SIDEBAR_MIN}
          aria-valuemax={SIDEBAR_MAX}
          tabIndex={0}
          className="group absolute top-0 bottom-0 z-50 w-2 flex items-center justify-center cursor-col-resize hover:bg-[rgba(128,128,128,0.15)] focus-visible:outline-none focus-visible:bg-np/50 transition-colors after:content-[''] after:absolute after:inset-y-0 after:-left-[5px] after:-right-[5px] after:z-50"
          style={{ left: `calc(${sidebarWidth}px - 4px)` }}
          onMouseDown={handleMouseDown('left')}
          onKeyDown={handleResizeKeyDown('left')}
        >
          <div className="w-1 h-8 rounded-full bg-bdr2 group-hover:bg-np group-focus-visible:bg-np transition-colors" />
        </div>
      )}

      {/* Resizer Separator - Right (AI Panel) */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize AI panel"
        aria-valuenow={aiPanelWidth}
        aria-valuemin={minAiWidth}
        aria-valuemax={AI_MAX}
        tabIndex={0}
        className="group absolute top-0 bottom-0 z-50 w-2 flex items-center justify-center cursor-col-resize hover:bg-[rgba(128,128,128,0.15)] focus-visible:outline-none focus-visible:bg-np/50 transition-colors after:content-[''] after:absolute after:inset-y-0 after:-left-[5px] after:-right-[5px] after:z-50"
        style={{ right: `calc(${aiPanelWidth}px - 4px)` }}
        onMouseDown={handleMouseDown('right')}
        onKeyDown={handleResizeKeyDown('right')}
      >
        <div className="w-1 h-8 rounded-full bg-bdr2 group-hover:bg-np group-focus-visible:bg-np transition-colors" />
      </div>

      {/* Keyboard shortcuts help button */}
      <IconButton
        label="Keyboard shortcuts"
        onClick={() => setShortcutsOpen(true)}
        className="absolute bottom-4 left-4 z-50 w-7 h-7 rounded-sm bg-ns2 border border-bdr2 shadow-ev2 hover:bg-ns3 active:translate-y-[1px] active:shadow-none"
      >
        <HelpCircle size={13} strokeWidth={1.5} />
      </IconButton>

      {/* Keyboard shortcuts modal */}
      <ShortcutsModal isOpen={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </div>
  )
}
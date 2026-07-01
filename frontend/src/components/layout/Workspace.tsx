import { useState, useEffect, useRef, useCallback } from 'react'
import { Sidebar } from './Sidebar'
import { DocPanel } from './DocPanel'
import { AIPanel } from './AIPanel'
import { useChapterStore } from '../../stores/useChapterStore'
import { useQuizStore } from '../../stores/useQuizStore'
import { PanelLeftOpen } from 'lucide-react'

// ── Panel size constants ─────────────────────────────────────────────────────
const SIDEBAR_MIN = 160
const SIDEBAR_MAX = 400
const AI_MIN_TUTOR = 250
const AI_MIN_QUIZ_CARDS = 360
const AI_MAX = 550

export function Workspace() {
  const { sidebarCollapsed, toggleSidebar } = useChapterStore()
  const { aiMode } = useQuizStore()   // ← read current mode

  const [sidebarWidth, setSidebarWidth] = useState(220)
  const [aiPanelWidth, setAiPanelWidth] = useState(268)
  const [tutorAiWidth, setTutorAiWidth] = useState(268)   // remembered tutor width
  const [isDragging, setIsDragging] = useState(false)

  const workspaceRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef<'left' | 'right' | null>(null)

  // ── Keyboard shortcuts ─────────────────────────────────────────────────────
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !sidebarCollapsed) {
        toggleSidebar()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [sidebarCollapsed, toggleSidebar])

  // ── Auto‑expand / restore AI panel ────────────────────────────────────────
  const minAiWidth = aiMode === 'tutor' ? AI_MIN_TUTOR : AI_MIN_QUIZ_CARDS

  // Remember the current width whenever the user is in tutor mode and not dragging
  useEffect(() => {
    if (aiMode === 'tutor' && !isDragging) {
      setTutorAiWidth(aiPanelWidth)
    }
  }, [aiPanelWidth, aiMode, isDragging])

  // Expand or restore on mode change
  useEffect(() => {
    if (aiMode !== 'tutor') {
      // Entering quiz/cards – expand if currently too small
      if (aiPanelWidth < AI_MIN_QUIZ_CARDS) {
        setAiPanelWidth(AI_MIN_QUIZ_CARDS)
      }
    } else {
      // Returning to tutor – restore the last tutor width (clamped)
      const restored = Math.max(AI_MIN_TUTOR, Math.min(tutorAiWidth, AI_MAX))
      setAiPanelWidth(restored)
    }
    // We only want to react to mode changes, not width changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiMode])

  // ── Mouse drag resizing ────────────────────────────────────────────────────
  const handleMouseDown = (side: 'left' | 'right') => (e: React.MouseEvent) => {
    e.preventDefault()
    draggingRef.current = side
    setIsDragging(true)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
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
  }, [minAiWidth])   // rebind when the minimum changes

  // ── Collapse button logic ──────────────────────────────────────────────────
  const handleSidebarToggle = () => {
    toggleSidebar()
  }

  // ── Grid template ───────────────────────────────────────────────────────────
  const gridColumns = sidebarCollapsed
    ? `48px 1fr ${aiPanelWidth}px`
    : `${sidebarWidth}px 1fr ${aiPanelWidth}px`

  return (
    <div
      ref={workspaceRef}
      className="workspace grid h-screen bg-nb text-nt text-xs font-sans rounded-xl border border-bdr2 overflow-hidden shadow-2xl relative"
      style={{
        gridTemplateColumns: gridColumns,
        transition: isDragging ? 'none' : 'grid-template-columns 240ms cubic-bezier(0.4,0,0.2,1)',
      }}
    >
      {sidebarCollapsed && (
        <button
          onClick={handleSidebarToggle}
          className="absolute left-2 top-2 z-50 w-8 h-8 rounded-md bg-ns2 border border-bdr2 text-nt3 hover:text-nt hover:bg-ns3 transition flex items-center justify-center shadow-md"
          aria-label="Open sidebar"
        >
          <PanelLeftOpen size={14} />
        </button>
      )}

      <Sidebar />
      <DocPanel />
      <AIPanel />

      {/* Resize handle – sidebar (hidden when collapsed) */}
      {!sidebarCollapsed && (
        <div
          className="absolute top-0 bottom-0 z-50 w-2 cursor-col-resize hover:bg-[rgba(128,128,128,0.2)] transition-colors"
          style={{ left: `calc(${sidebarCollapsed ? 48 : sidebarWidth}px - 4px)` }}
          onMouseDown={handleMouseDown('left')}
          title="Resize sidebar"
        />
      )}

      {/* Resize handle – AI panel */}
      <div
        className="absolute top-0 bottom-0 z-50 w-2 cursor-col-resize hover:bg-[rgba(128,128,128,0.2)] transition-colors"
        style={{ right: `calc(${aiPanelWidth}px - 4px)` }}
        onMouseDown={handleMouseDown('right')}
        title="Resize AI panel"
      />
    </div>
  )
}
import { useState, useEffect, useRef } from 'react'
import { Sidebar } from './Sidebar'
import { DocPanel } from './DocPanel'
import { AIPanel } from './AIPanel'
import { useChapterStore } from '../../stores/useChapterStore'

export function Workspace() {
  const { sidebarCollapsed, toggleSidebar } = useChapterStore()

  // Local state to track dynamic widths and drag status
  const [sidebarWidth, setSidebarWidth] = useState(220)
  const [aiPanelWidth, setAiPanelWidth] = useState(268)
  const [isDragging, setIsDragging] = useState(false)

  // Refs to handle DOM measurements and stable drag targeting
  const workspaceRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef<'left' | 'right' | null>(null)

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape collapses the sidebar if it is currently expanded
      if (e.key === 'Escape' && !sidebarCollapsed) {
        toggleSidebar()
      }
      
      // Note: Enter (without Shift) is natively handled by the focused InputZone's 
      // onKeyDown handler. Because standard event bubbling applies, it works globally 
      // whenever the input has focus without needing a manual interceptor here.
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [sidebarCollapsed, toggleSidebar])

  // Mouse drag resizing logic
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!draggingRef.current || !workspaceRef.current) return

      // Measure relative to the workspace container just in case it isn't full-bleed
      const rect = workspaceRef.current.getBoundingClientRect()

      if (draggingRef.current === 'left') {
        const relativeX = e.clientX - rect.left
        // Sidebar constraints: 160px to 400px
        const newWidth = Math.max(160, Math.min(400, relativeX))
        setSidebarWidth(newWidth)
      } else if (draggingRef.current === 'right') {
        const relativeRight = rect.right - e.clientX
        // AI Panel constraints: 240px to 550px
        const newWidth = Math.max(240, Math.min(550, relativeRight))
        setAiPanelWidth(newWidth)
      }
    }

    const handleMouseUp = () => {
      if (draggingRef.current) {
        draggingRef.current = null
        setIsDragging(false)
        document.body.style.cursor = 'default'
        document.body.style.userSelect = '' // Restore text selection after drag
      }
    }

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [])

  const handleMouseDown = (side: 'left' | 'right') => (e: React.MouseEvent) => {
    e.preventDefault()
    draggingRef.current = side
    setIsDragging(true)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none' // Prevent text highlighting while dragging
  }

  return (
    <div
      ref={workspaceRef}
      className="workspace grid h-screen bg-nb text-nt text-xs font-sans rounded-xl border border-bdr2 overflow-hidden shadow-2xl relative"
      style={{
        '--sidebar-width': sidebarCollapsed ? '48px' : `${sidebarWidth}px`,
        gridTemplateColumns: `var(--sidebar-width) 1fr ${aiPanelWidth}px`,
        // Disable grid transition during drag to prevent jitter, but keep it for toggling
        transition: isDragging ? 'none' : 'grid-template-columns 240ms cubic-bezier(0.4,0,0.2,1)',
      } as React.CSSProperties}
    >
      <Sidebar />
      <DocPanel />
      <AIPanel />

      {/* Left Resize Handle (Sidebar) */}
      {/* Hidden natively when sidebar is collapsed via conditional rendering */}
      {!sidebarCollapsed && (
        <div
          className="absolute top-0 bottom-0 z-50 w-2 cursor-col-resize hover:bg-[rgba(128,128,128,0.2)] transition-colors"
          style={{ left: `calc(var(--sidebar-width) - 4px)` }}
          onMouseDown={handleMouseDown('left')}
          title="Resize sidebar"
        />
      )}

      {/* Right Resize Handle (AI Panel) */}
      <div
        className="absolute top-0 bottom-0 z-50 w-2 cursor-col-resize hover:bg-[rgba(128,128,128,0.2)] transition-colors"
        style={{ right: `calc(${aiPanelWidth}px - 4px)` }}
        onMouseDown={handleMouseDown('right')}
        title="Resize AI panel"
      />
    </div>
  )
}
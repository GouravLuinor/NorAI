import { useState, useEffect, useCallback, useRef } from 'react'
import { useQuizStore } from '../../stores/useQuizStore'
import { useAskNora } from '../../hooks/useAskNora'
import { Sparkles } from 'lucide-react'
import { Button } from '../ui/Button'

export function HighlightAsk() {
  const [selection, setSelection] = useState<{ text: string; x: number; y: number } | null>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const setMode = useQuizStore((s) => s.setMode)
  // Shared send pipeline: streams into the thread the question was asked
  // from (the old direct /chat call wrote the reply into whichever thread was
  // active when it returned) and shares the global one-turn-at-a-time guard.
  const { send, isInFlight: loading } = useAskNora()

  const clearSelection = useCallback(() => {
    setSelection(null)
    window.getSelection()?.removeAllRanges()
  }, [])

  useEffect(() => {
    const handleMouseUp = (e: MouseEvent) => {
      if (buttonRef.current?.contains(e.target as Node)) return

      setTimeout(() => {
        const sel = window.getSelection()
        if (!sel || sel.isCollapsed) {
          setSelection(null)
          return
        }

        const text = sel.toString().trim()
        if (!text) {
          setSelection(null)
          return
        }

        const range = sel.getRangeAt(0)
        const isInDocContent = !!(range.commonAncestorContainer as Element).closest?.('.doc-content')
        if (!isInDocContent) {
          setSelection(null)
          return
        }

        const endRange = range.cloneRange()
        endRange.collapse(false)
        const rect = endRange.getClientRects()
        const lastRect = rect[rect.length - 1] || range.getBoundingClientRect()

        setSelection({
          text,
          x: lastRect.right + 8,
          y: lastRect.bottom + 4,
        })
      }, 10)
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') clearSelection()
    }

    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [clearSelection])

  const handleAsk = useCallback(async () => {
    if (!selection?.text || loading) return

    const question = `Explain this: ${selection.text}`
    clearSelection()

    setMode('tutor')
    await send(question)
  }, [selection, loading, clearSelection, setMode, send])

  if (!selection) return null

  return (
    <Button
      ref={buttonRef}
      variant="primary"
      onClick={handleAsk}
      disabled={loading}
      className={`fixed z-50 flex items-center gap-1.5 px-3 py-1.5 rounded-md text-11 font-medium shadow-ev2 animate-fade-in pointer-events-auto ${
        loading ? 'opacity-50 cursor-not-allowed' : ''
      }`}
      style={{ left: `${selection.x}px`, top: `${selection.y}px` }}
    >
      <Sparkles size={13} strokeWidth={1.5} />
      {loading ? 'Asking…' : 'Ask Nora'}
    </Button>
  )
}
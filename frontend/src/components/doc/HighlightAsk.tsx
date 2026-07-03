import { useState, useEffect, useCallback, useRef } from 'react'
import { useThreadStore, sendChatMessage } from '../../stores/useThreadStore'
import { useQuizStore } from '../../stores/useQuizStore'
import { Sparkles } from 'lucide-react'

export function HighlightAsk() {
  const [selection, setSelection] = useState<{ text: string; x: number; y: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const addMessage = useThreadStore((s) => s.addMessage)
  const setMode = useQuizStore((s) => s.setMode)

  const genId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

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

    // Add user message
    addMessage({
      id: genId(),
      role: 'user',
      content: question,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    })

    // Switch to tutor mode
    setMode('tutor')

    setLoading(true)
    try {
      const data = await sendChatMessage(useThreadStore.getState().threadId, question)

     // ── Build references from the response ──────────────────────────────
      const refs = [
        ...(data.retrieved_chunks ?? []).map((c: any) => {
          const leaf = (c.heading_path ?? '').split('>').pop()!.trim()
          const sectionId = 'sec-' + leaf
            .toLowerCase().replace(/[^a-z0-9\s-]/g, '').trim()
            .replace(/\s+/g, '-').replace(/-+/g, '-')
          return {
            id: c.heading_path,
            title: c.heading_path,
            section: `Ch ${c.chapter_id}`,
            sectionId,
            chapterId: c.chapter_id,
            type: 'note' as const,
          }
        }),
        ...(data.retrieved_images ?? []).map((img: any) => ({
          id: img.path,
          title: img.section,
          section: img.path,
          sectionId: '',
          type: 'screenshot' as const,
        })),
      ]
      useThreadStore.getState().setLiveReferences(refs)
      
      const cleanAnswer = data.answer.replace(/\*\*Sources\*\*[\s\S]*$/, '').trim()
      addMessage({
        id: genId(),
        role: 'assistant',
        content: cleanAnswer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      })
    } catch {
      addMessage({
        id: genId(),
        role: 'assistant',
        content: 'Sorry, something went wrong.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      })
    } finally {
      setLoading(false)
    }
  }, [selection, loading, clearSelection, addMessage, setMode])

  if (!selection) return null

  return (
    <button
      ref={buttonRef}
      onClick={handleAsk}
      disabled={loading}
      className={`fixed z-50 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-np text-white text-[11px] font-medium shadow-lg transition-all animate-fade-in pointer-events-auto ${
        loading ? 'opacity-50 cursor-not-allowed' : 'hover:bg-[#8E82E0]'
      }`}
      style={{ left: `${selection.x}px`, top: `${selection.y}px` }}
    >
      <Sparkles size={13} />
      {loading ? 'Asking…' : 'Ask Nora'}
    </button>
  )
}
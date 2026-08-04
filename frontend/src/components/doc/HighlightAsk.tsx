import { useState, useEffect, useCallback, useRef } from 'react'
import { useThreadStore } from '../../stores/useThreadStore'
import { useQuizStore } from '../../stores/useQuizStore'
import { useLectureStore } from '../../stores/useLectureStore'   // ← added
import { buildReferences } from '../../lib/references'
import { sendChatMessage } from '../../lib/chatApi'
import { Sparkles } from 'lucide-react'
import { Button } from '../ui/Button'

export function HighlightAsk() {
  const [selection, setSelection] = useState<{ text: string; x: number; y: number } | null>(null)
  const [loading, setLoading] = useState(false)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const addMessage = useThreadStore((s) => s.addMessage)
  const setMode = useQuizStore((s) => s.setMode)

  // ── Lecture‑aware ───────────────────────────────────────────────────────
  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'

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
    const userMsgId = genId()
    addMessage({
      id: userMsgId,
      role: 'user',
      content: question,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    })

    // Switch to tutor mode
    setMode('tutor')

    setLoading(true)
    try {
      // Lecture‑scoped request
      const data = await sendChatMessage(
        useThreadStore.getState().threadId,
        question,
        '',
        { lectureId, messageId: userMsgId }
      )

      // ── Build references from the response ──────────────────────────────
      useThreadStore.getState().setLiveReferences(
        buildReferences(data.retrieved_chunks ?? [], data.retrieved_images ?? [])
      )

      const cleanAnswer = data.answer.replace(/\*\*Sources\*\*[\s\S]*$/, '').trim()

      // RC-FIX2: Atomic dedup — same guard as ChatArea.
      // If loadThreadMessages already injected this response from the backend
      // checkpoint, skip the append to avoid duplicates.
      useThreadStore.setState((s) => {
        if (s.messages.some(m => m.role === 'assistant' && m.content === cleanAnswer)) {
          return {}
        }
        const assistantMsg = {
          id: data.assistant_message_id || genId(),
          role: 'assistant' as const,
          content: cleanAnswer,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }
        const messages = [...s.messages, assistantMsg]
        return {
          messages,
          _messagesCache: { ...s._messagesCache, [s.threadId]: messages },
        }
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
  }, [selection, loading, clearSelection, addMessage, setMode, lectureId])

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
import { useState, useRef, useEffect, useCallback } from 'react'
import { useThreadStore, sendChatMessage } from '../../stores/useThreadStore'
import { useChapterStore } from '../../stores/useChapterStore'
import { useLectureStore } from '../../stores/useLectureStore'   // ← added
import { MessageBubble } from './MessageBubble'
import { ReferencesPanel } from './ReferencesPanel'
import { InputZone } from './InputZone'
import { ShimmerLoader } from './ShimmerLoader'
import { Lightbox } from '../ui/Lightbox'

// ── Stable, collision‑free ID generator ────────────────────────────────────
const genId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

export function ChatArea() {
  const messages   = useThreadStore(s => s.messages)
  const addMessage = useThreadStore(s => s.addMessage)
  const setLoading = useThreadStore(s => s.setLoading)
  const threadId   = useThreadStore(s => s.threadId)
  const isLoading  = useThreadStore(s => s.isLoading)

  const liveReferences    = useThreadStore(s => s.liveReferences)
  const setLiveReferences = useThreadStore(s => s.setLiveReferences)

  // ── Lecture‑aware ───────────────────────────────────────────────────────
  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'

  const [lightbox, setLightbox] = useState<{ src: string; caption: string } | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // synchronous in‑flight guard
  const inFlightRef = useRef(false)

  // per‑request abort + stable thread tracker
  const activeThreadRef    = useRef(threadId)
  const abortControllerRef = useRef<AbortController | null>(null)

  // RC-FIX: Keep activeThreadRef in sync so guards in handleSend
  // always compare against the *current* thread, not the one at mount time.
  useEffect(() => {
    activeThreadRef.current = threadId
  }, [threadId])

const handleSend = useCallback(async (text: string) => {
    if (inFlightRef.current) return
    inFlightRef.current = true

    const targetThreadId = threadId

    // 1. Add user message immediately
    const userMsg = {
      id: genId(),
      role: 'user' as const,
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
    addMessage(userMsg)

    setLoading(true)

    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      // 2. Get the full answer — lecture‑scoped
      const data = await sendChatMessage(targetThreadId, text, '', { lectureId, messageId: userMsg.id })

      if (controller.signal.aborted) return

      const cleanAnswer = (data.answer ?? '').replace(/\*\*Sources\*\*[\s\S]*$/, '').trim()

      // 3. Store assistant message under the ORIGINAL thread (targetThreadId),
      //    even if the user navigated away while waiting.
      const assistantMsg = {
        id: data.assistant_message_id || genId(),
        role: 'assistant' as const,
        content: cleanAnswer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }

      // RC-FIX2: Fully atomic read-check-write inside a single setState.
      // This eliminates the race where loadThreadMessages could inject the
      // same assistant message between a getState() snapshot and a separate
      // setState() call, causing duplicates.
      useThreadStore.setState((s) => {
        const currentMessages = s.threadId === targetThreadId
          ? s.messages
          : (s._messagesCache[targetThreadId] ?? [])

        // Guard: if loadThreadMessages already brought in this response
        // (because the backend checkpoint was updated before we got here),
        // skip the append to avoid a duplicate.
        if (currentMessages.some(m => m.role === 'assistant' && m.content === cleanAnswer)) {
          return {}
        }

        const updated = [...currentMessages, assistantMsg]
        return {
          _messagesCache: { ...s._messagesCache, [targetThreadId]: updated },
          ...(s.threadId === targetThreadId ? { messages: updated } : {}),
        }
      })

      // 4. Build references (only show if still on the target thread)
      if (activeThreadRef.current === targetThreadId) {
        setLiveReferences([
          ...(data.retrieved_chunks ?? []).map((c: any) => {
            const headingParts = (c.heading_path || '').split('>')
            const leafHeading  = headingParts[headingParts.length - 1].trim()
            const sectionId    = 'sec-' + leafHeading
              .toLowerCase()
              .replace(/[^a-z0-9\s-]/g, '')
              .trim()
              .replace(/\s+/g, '-')
              .replace(/-+/g, '-')
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
        ])
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') return
      console.error('Chat error:', err)
      if (activeThreadRef.current === targetThreadId) {
        addMessage({
          id: genId(),
          role: 'assistant',
          content: 'Sorry, something went wrong. Please try again.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        })
      }
    } finally {
      // RC-FIX: Always clear loading and inflight state regardless of which
      // thread is active. The old code guarded this behind activeThreadRef
      // which could be stale, leaving the shimmer loader permanently visible.
      setLoading(false)
      inFlightRef.current = false
    }
  }, [threadId, addMessage, setLoading, lectureId])

  // ── Reference handlers ────────────────────────────────────────────────────
  const handleReferenceClick = useCallback((sectionId: string) => {
    const ref = liveReferences.find(r => r.sectionId === sectionId)
    if (!ref) return

    const targetChapterId = ref.chapterId
    const store = useChapterStore.getState()
    const currentChapterId = store.activeChapterId

    const attemptScroll = () => {
      let attempts = 0
      const interval = setInterval(() => {
        const el = document.getElementById(sectionId)
        if (el) {
          clearInterval(interval)
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
          el.classList.remove('scroll-highlight')
          void el.offsetWidth
          el.classList.add('scroll-highlight')
          el.addEventListener('animationend', function h() {
            el.classList.remove('scroll-highlight')
            el.removeEventListener('animationend', h)
          })
        } else if (attempts >= 20) {
          clearInterval(interval)
          console.warn('Reference click — sectionId:', sectionId, 'not found in DOM.')
        }
        attempts++
      }, 100)
    }

    if (targetChapterId && targetChapterId !== currentChapterId) {
      store.setChapter(targetChapterId)
      store.setDocTab('notes')
    }
    attemptScroll()
  }, [liveReferences])

  const handleScreenshotClick = useCallback((ref: any) => {
    const cleanPath = (ref.section || '').replace(/^outputs\//, '')
    setLightbox({ src: `/static/${cleanPath}`, caption: ref.title || '' })
  }, [])

  const isEmpty = messages.length === 0 && !isLoading

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scroll-smooth doc-content">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-12 h-12 rounded-sm bg-npf flex items-center justify-center mb-4 shadow-ev2 fold-marks relative">
              <span className="text-lg font-semibold text-npfg">N</span>
            </div>
            <h3 className="text-sm font-medium text-nt mb-1">What can I help with?</h3>
            <p className="text-xs text-nt3 max-w-[200px]">
              Ask me anything about your lectures — I'll pull answers straight from your notes.
            </p>
          </div>
        ) : (
          <>
            <div className="text-3xs text-nt3 text-center flex items-center gap-2">
              <span className="flex-1 h-px bg-bdr" />
              Today
              <span className="flex-1 h-px bg-bdr" />
            </div>

            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {isLoading && (
              <div className="flex gap-2 items-start">
                <div className="w-5 h-5 rounded-sm bg-npf flex items-center justify-center text-3xs font-medium text-npfg shrink-0 mt-0.5 shadow-ev1">
                  N
                </div>
                <ShimmerLoader />
              </div>
            )}
          </>
        )}

        <div ref={chatEndRef} />
      </div>

      <ReferencesPanel
        references={liveReferences}
        onReferenceClick={handleReferenceClick}
        onScreenshotClick={handleScreenshotClick}
      />
      <InputZone onSend={handleSend} />

      {lightbox && (
        <Lightbox
          src={lightbox.src}
          alt="Lecture screenshot"
          caption={lightbox.caption}
          onClose={() => setLightbox(null)}
        />
      )}
    </div>
  )
}
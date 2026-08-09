import { useState, useRef, useEffect, useCallback } from 'react'
import { useThreadStore } from '../../stores/useThreadStore'
import { useChapterStore } from '../../stores/useChapterStore'
import { useQuizStore } from '../../stores/useQuizStore'
import { sendChatMessageStream } from '../../lib/chatApi'
import { buildReferences } from '../../lib/references'
import { useTutorSettingsStore } from '../../stores/useTutorSettingsStore'
import { MessageBubble } from './MessageBubble'
import { ReferencesPanel } from './ReferencesPanel'
import { InputZone } from './InputZone'
import { ShimmerLoader } from './ShimmerLoader'
import { Lightbox } from '../ui/Lightbox'

// ── Stable, collision‑free ID generator ────────────────────────────────────
const genId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

// Strip the auto-appended Sources appendix (it's surfaced via ReferencesPanel).
export const stripSources = (text: string) =>
  text.replace(/(\*\*Sources\*\*|\n\nSources\b|Sources\s*[\:\•]|Sources\b[\s\S]*$)[\s\S]*$/i, '').trim()

export function ChatArea() {
  const messages   = useThreadStore(s => s.messages)
  const addMessage = useThreadStore(s => s.addMessage)
  const setLoading = useThreadStore(s => s.setLoading)
  const threadId   = useThreadStore(s => s.threadId)
  const isLoading  = useThreadStore(s => s.isLoading)

  const streamingText    = useThreadStore(s => s.streamingText)
  const setStreamingText = useThreadStore(s => s.setStreamingText)

  const liveReferences    = useThreadStore(s => s.liveReferences)
  const setLiveReferences = useThreadStore(s => s.setLiveReferences)

  const studyMode = useQuizStore(s => s.aiMode) === 'socratic' ? 'socratic' : 'default'
  const persona   = useTutorSettingsStore(s => s.persona)

  const [lightbox, setLightbox] = useState<{ src: string; caption: string } | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // synchronous in‑flight guard
  const inFlightRef = useRef(false)

  // per‑request abort + stable thread tracker
  const activeThreadRef    = useRef(threadId)
  const abortControllerRef = useRef<AbortController | null>(null)

  // RC-FIX: Keep activeThreadRef in sync so guards in handleSend
  // always compare against the *current* thread, not the one at mount time.
  // Aborting the in-flight stream on switch stops wasted chunks and leaves no
  // stale streaming bubble behind.
  useEffect(() => {
    const previous = activeThreadRef.current
    activeThreadRef.current = threadId
    if (previous !== threadId) abortControllerRef.current?.abort()
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

    // 2. Stream the answer — chunks feed the transient streaming bubble, the
    //    final event carries the checkpoint refs. Never slower than the
    //    non-stream path (the backend streams an already-computed answer).
    let acc = ''
    try {
      for await (const chunk of sendChatMessageStream(
        targetThreadId,
        text,
        '',
        controller.signal,
        { messageId: userMsg.id, studyMode, persona },
      )) {
        if (controller.signal.aborted) return

        if (typeof chunk === 'string') {
          acc += chunk
          setStreamingText(stripSources(acc))
          continue
        }

        // 3. Final event — commit the real assistant message under the ORIGINAL
        //    thread (targetThreadId), even if the user navigated away while waiting.
        const data = chunk.data
        setStreamingText('')

        const cleanAnswer = stripSources(acc)

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
          setLiveReferences(buildReferences(data.retrieved_chunks ?? [], data.retrieved_images ?? [], '', data.verified_citations ?? []))
        }
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
      setStreamingText('')
      setLoading(false)
      inFlightRef.current = false
    }
  }, [threadId, addMessage, setLoading, setStreamingText, setLiveReferences, studyMode, persona])

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
      <div
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scroll-smooth doc-content"
        role="log"
        aria-live="polite"
        aria-busy={isLoading}
        aria-relevant="additions"
      >
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-12 h-12 rounded-sm bg-npf flex items-center justify-center mb-4 shadow-ev2 fold-marks relative">
              <span className="text-lg font-semibold text-npfg">N</span>
            </div>
            <h2 className="text-sm font-medium text-nt mb-1">What can I help with?</h2>
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

            {streamingText && (
              <MessageBubble
                message={{
                  id: 'streaming',
                  role: 'assistant',
                  content: streamingText,
                  timestamp: '',
                }}
              />
            )}

            {isLoading && !streamingText && (
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
import { useState, useRef, useEffect, useCallback } from 'react'
import { useThreadStore } from '../../stores/useThreadStore'
import { useQuizStore } from '../../stores/useQuizStore'
import { friendlyError } from '../../lib/errorCopy'
import { scrollToHeading } from '../../lib/cite'
import { genId } from '../../lib/id'
import { useAskNora, chatTimestamp } from '../../hooks/useAskNora'
import type { Reference } from '../../types'
import { useTutorSettingsStore } from '../../stores/useTutorSettingsStore'
import { MessageBubble } from './MessageBubble'
import { ReferencesPanel } from './ReferencesPanel'
import { InputZone } from './InputZone'
import { ShimmerLoader } from './ShimmerLoader'
import { Lightbox } from '../ui/Lightbox'

// ── Stable, collision‑free ID generator ────────────────────────────────────
export function ChatArea() {
  const messages   = useThreadStore(s => s.messages)
  const addMessage = useThreadStore(s => s.addMessage)
  const threadId   = useThreadStore(s => s.threadId)
  const isLoading  = useThreadStore(s => s.isLoading)

  const streamingText    = useThreadStore(s => s.streamingText)

  const liveReferences    = useThreadStore(s => s.liveReferences)
  const setLiveReferences = useThreadStore(s => s.setLiveReferences)

  const studyMode = useQuizStore(s => s.aiMode) === 'socratic' ? 'socratic' : 'default'
  const persona   = useTutorSettingsStore(s => s.persona)

  const [lightbox, setLightbox] = useState<{ src: string; caption: string } | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // stable thread tracker
  const activeThreadRef = useRef(threadId)

  const { send, abort } = useAskNora({
    onReferences: (refs, targetThreadId) => {
      if (activeThreadRef.current === targetThreadId) {
        setLiveReferences(refs)
      }
    },
    onStreamError: (err, targetThreadId) => {
      console.error('Chat error:', err)
      if (activeThreadRef.current === targetThreadId) {
        addMessage({
          id: genId(),
          role: 'assistant',
          content: friendlyError(err),
          timestamp: chatTimestamp(),
        })
      }
    },
  })

  // RC-FIX: Keep activeThreadRef in sync so guards in handleSend
  // always compare against the *current* thread, not the one at mount time.
  // Aborting the in-flight stream on switch stops wasted chunks and leaves no
  // stale streaming bubble behind.
  useEffect(() => {
    const previous = activeThreadRef.current
    activeThreadRef.current = threadId
    if (previous !== threadId) abort()
  }, [threadId, abort])

const handleSend = useCallback(async (text: string) => {
    await send(text, { studyMode, persona })
  }, [send, studyMode, persona])

  // ── Reference handlers ────────────────────────────────────────────────────
  const handleReferenceClick = useCallback((ref: Reference) => {
    scrollToHeading(ref.title || ref.sectionId, ref.chapterId, ref.sectionId)
  }, [])

  const handleScreenshotClick = useCallback((ref: Reference) => {
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
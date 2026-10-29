import { useState, useRef, useEffect, useCallback } from 'react'
import { useThreadStore } from '../../stores/useThreadStore'
import { useQuizStore } from '../../stores/useQuizStore'
import { scrollToHeading } from '../../lib/cite'
import { useVideoStore } from '../../stores/useVideoStore'
import { useAskNora } from '../../hooks/useAskNora'
import type { Reference } from '../../types'
import { useTutorSettingsStore } from '../../stores/useTutorSettingsStore'
import { MessageBubble } from './MessageBubble'
import { ReferencesPanel } from './ReferencesPanel'
import { InputZone } from './InputZone'
import { ShimmerLoader } from './ShimmerLoader'
import { Lightbox } from '../ui/Lightbox'

export function ChatArea() {
  const messages        = useThreadStore(s => s.messages)
  const threadId        = useThreadStore(s => s.threadId)
  const isLoadingHistory = useThreadStore(s => s.isLoading)
  // The in-flight turn (and its partial text) belongs to ONE thread; only
  // render it there. Switching threads no longer aborts it — the reply lands
  // in the thread it was asked from.
  const isSendingHere   = useThreadStore(s => s.sendingThreadId !== null && s.sendingThreadId === s.threadId)
  const streamingText   = useThreadStore(s => (s.sendingThreadId === s.threadId ? s.streamingText : ''))
  const liveReferences  = useThreadStore(s => s.liveReferences)
  const retryMessage    = useThreadStore(s => s.retryMessage)

  const studyMode = useQuizStore(s => s.aiMode) === 'socratic' ? 'socratic' : 'default'
  const persona   = useTutorSettingsStore(s => s.persona)

  const [lightbox, setLightbox] = useState<{ src: string; caption: string } | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  const { send, isInFlight } = useAskNora()

  const handleSend = useCallback(async (text: string) => {
    await send(text, { studyMode, persona })
  }, [send, studyMode, persona])

  const handleRetry = useCallback((userMessageId: string) => {
    retryMessage(userMessageId, { studyMode, persona }).catch((err: unknown) => {
      console.error('Chat retry failed:', err)
    })
  }, [retryMessage, studyMode, persona])

  // Keep the newest message / streaming text in view.
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, streamingText, isSendingHere, threadId])

  // ── Reference handlers ────────────────────────────────────────────────────
  const handleReferenceClick = useCallback((ref: Reference) => {
    // Transcript citations point at a moment in the lecture, not a note heading.
    if (ref.transcript && ref.startSec != null) {
      useVideoStore.getState().requestSeek(ref.startSec)
      return
    }
    scrollToHeading(ref.title || ref.sectionId, ref.chapterId, ref.sectionId)
  }, [])

  const handleScreenshotClick = useCallback((ref: Reference) => {
    const cleanPath = (ref.section || '').replace(/^outputs\//, '')
    setLightbox({ src: `/static/${cleanPath}`, caption: ref.title || '' })
  }, [])

  const isEmpty = messages.length === 0 && !isLoadingHistory && !isSendingHere

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full">
      <div
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4 doc-content"
        role="log"
        aria-live="polite"
        aria-busy={isLoadingHistory || isSendingHere}
        aria-relevant="additions"
      >
        {isLoadingHistory && messages.length === 0 ? (
          <div className="flex items-center justify-center h-full gap-2 text-xs text-nt3" role="status">
            <span className="h-3.5 w-3.5 rounded-full border-2 border-ns3 border-t-np animate-spin" />
            Loading conversation…
          </div>
        ) : isEmpty ? (
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
              <MessageBubble
                key={msg.id}
                message={msg}
                onRetry={
                  msg.status === 'error' && msg.role === 'assistant' && !isInFlight
                    ? () => handleRetry(msg.id.replace(/^err-/, ''))
                    : undefined
                }
              />
            ))}

            {isSendingHere && streamingText && (
              <MessageBubble
                message={{
                  id: 'streaming',
                  role: 'assistant',
                  content: streamingText,
                  timestamp: '',
                }}
              />
            )}

            {isSendingHere && !streamingText && (
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
      <InputZone onSend={handleSend} disabled={isInFlight} />

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
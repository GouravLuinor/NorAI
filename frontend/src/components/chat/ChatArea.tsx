import { useState, useRef, useEffect, useCallback } from 'react'
import { useThreadStore } from '../../stores/useThreadStore'
import { useQuizStore } from '../../stores/useQuizStore'
import { scrollToHeading } from '../../lib/cite'
import { useVideoStore } from '../../stores/useVideoStore'
import { useAskNora } from '../../hooks/useAskNora'
import type { Reference } from '../../types'
import { useTutorSettingsStore } from '../../stores/useTutorSettingsStore'
import { useLectureStore } from '../../stores/useLectureStore'
import { apiGet } from '../../lib/http'
import { MessageBubble } from './MessageBubble'
import { ReferencesPanel } from './ReferencesPanel'
import { InputZone } from './InputZone'
import { ShimmerLoader } from './ShimmerLoader'
import { Lightbox } from '../ui/Lightbox'

export function ChatArea() {
  const activeLectureId = useLectureStore(s => s.activeLectureId)
  const isDocument      = useVideoStore(s => s.sourceKind === 'document')
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
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([])
  const [guestRemaining, setGuestRemaining] = useState<number | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  const { send, isInFlight } = useAskNora()

  useEffect(() => {
    if (!activeLectureId) {
      setSuggestedQuestions([])
      setGuestRemaining(null)
      return
    }
    let active = true
    apiGet<{
      suggested_questions: string[]
      is_guest: boolean
      guest_questions_remaining: number | null
    }>(`/lectures/${activeLectureId}/suggested-questions`)
      .then((data) => {
        if (!active || !data) return
        setSuggestedQuestions(data.suggested_questions || [])
        setGuestRemaining(data.guest_questions_remaining)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [activeLectureId, messages.length])

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
          <div className="flex items-center justify-center h-full gap-2 text-14 text-nt3" role="status">
            <span className="h-3.5 w-3.5 rounded-full border-2 border-ns3 border-t-np animate-spin" />
            Loading conversation…
          </div>
        ) : isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div aria-hidden="true" className="w-10 h-10 rounded-[4px] bg-brass text-[#16181A] flex items-center justify-center mb-4 text-18 font-bold">
              N
            </div>
            <h2 className="text-16 font-bold text-nt mb-1.5">Ask Nora about this {isDocument ? 'document' : 'lecture'}</h2>
            <p className="text-14 text-nt3 max-w-[280px] leading-relaxed">
              {isDocument
                ? 'Answers come from what the document says, with the page or slide it says it on.'
                : 'Answers come from what the lecturer said, with the moment they said it.'}
            </p>

            {guestRemaining != null && (
              <div className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-12 font-medium bg-np/10 text-np border border-np/20">
                <span className="w-1.5 h-1.5 rounded-full bg-np" />
                <span>{guestRemaining} free guest question{guestRemaining === 1 ? '' : 's'} today</span>
              </div>
            )}

            {suggestedQuestions.length > 0 && (
              <div className="mt-5 w-full max-w-sm flex flex-col gap-2">
                <div className="text-11 uppercase tracking-wider font-mono text-nt3 text-left px-1">
                  Suggested questions
                </div>
                {suggestedQuestions.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => void handleSend(q)}
                    disabled={isInFlight}
                    className="text-left text-13 px-3 py-2 rounded-md bg-ns2 hover:bg-ns3 text-nt hover:text-np border border-bdr transition-colors cursor-pointer disabled:opacity-50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="text-12 text-nt3 text-center flex items-center gap-2">
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
              <div className="flex gap-2.5 items-start">
                <div aria-hidden="true" className="w-7 h-7 rounded-[4px] bg-brass text-[#16181A] flex items-center justify-center text-13 font-bold shrink-0">
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
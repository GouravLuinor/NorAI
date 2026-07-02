/**
 * ChatArea.tsx — v3
 *
 * RC-A fix: ChatArea no longer calls loadThreadMessages on thread switch.
 * Sidebar owns that responsibility. ChatArea only handles its own local
 * streaming state cleanup when threadId changes.
 *
 * Added lightbox support for screenshot references.
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { useThreadStore, type Message, sendChatMessage } from '../../stores/useThreadStore'
import { useChapterStore } from '../../stores/useChapterStore'
import { MessageBubble } from './MessageBubble'
import { ReferencesPanel } from './ReferencesPanel'
import { InputZone } from './InputZone'
import { ShimmerLoader } from './ShimmerLoader'
import { Lightbox } from '../ui/Lightbox'

const genId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

export function ChatArea() {
  const messages   = useThreadStore(s => s.messages)
  const addMessage = useThreadStore(s => s.addMessage)
  const setLoading = useThreadStore(s => s.setLoading)
  const threadId   = useThreadStore(s => s.threadId)
  const isLoading  = useThreadStore(s => s.isLoading)

  const [streamingText, setStreamingText]    = useState('')
  const [isStreaming, setIsStreaming]        = useState(false)
  const [liveReferences, setLiveReferences] = useState<any[]>([])
  const [lightbox, setLightbox] = useState<{ src: string; caption: string } | null>(null)

  const chatEndRef = useRef<HTMLDivElement>(null)

  // synchronous in‑flight guard — immune to React batching delays
  const inFlightRef = useRef(false)

  // per‑request abort + stable thread tracker
  const activeThreadRef    = useRef(threadId)
  const streamIntervalRef  = useRef<ReturnType<typeof setInterval> | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // -------------------------------------------------------------------------
  // Thread‑switch cleanup: cancel streaming only.
  // RC‑A: do NOT call loadThreadMessages here — Sidebar owns that.
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (activeThreadRef.current !== threadId) {
      abortControllerRef.current?.abort()

      if (streamIntervalRef.current != null) {
        clearInterval(streamIntervalRef.current)
        streamIntervalRef.current = null
      }

      // Reset local streaming state only — messages come from the store
      setIsStreaming(false)
      setStreamingText('')
      setLiveReferences([])
      setLoading(false)
      inFlightRef.current = false
    }
    activeThreadRef.current = threadId
  }, [threadId, setLoading])

  // Unmount cleanup
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
      if (streamIntervalRef.current != null) clearInterval(streamIntervalRef.current)
    }
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  // -------------------------------------------------------------------------
  // handleSend
  // -------------------------------------------------------------------------
  const handleSend = useCallback(async (text: string) => {
    // synchronous guard set BEFORE any await
    if (inFlightRef.current) return
    inFlightRef.current = true

    const targetThreadId = threadId

    addMessage({
      id: genId(),
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    })

    setIsStreaming(true)
    setStreamingText('')
    setLoading(true)

    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      const data = await sendChatMessage(targetThreadId, text)

      if (activeThreadRef.current !== targetThreadId || controller.signal.aborted) return

      const fullAnswer  = data.answer ?? ''
      const cleanAnswer = fullAnswer.replace(/\*\*Sources\*\*[\s\S]*$/, '').trim()
      let charIndex = 0

      if (streamIntervalRef.current != null) clearInterval(streamIntervalRef.current)

      streamIntervalRef.current = setInterval(() => {
        if (activeThreadRef.current !== targetThreadId) {
          clearInterval(streamIntervalRef.current!)
          streamIntervalRef.current = null
          return
        }

        if (charIndex < cleanAnswer.length) {
          setStreamingText(cleanAnswer.slice(0, charIndex + 1))
          charIndex++
        } else {
          clearInterval(streamIntervalRef.current!)
          streamIntervalRef.current = null

          addMessage({
            id: genId(),
            role: 'assistant',
            content: cleanAnswer,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          })

          setStreamingText('')
          setIsStreaming(false)
          setLoading(false)
          inFlightRef.current = false

          setLiveReferences([
            ...(data.retrieved_chunks ?? []).map((c: any) => {
              // Extract only the leaf heading after the last '>'
              const headingParts = (c.heading_path || '').split('>')
              const leafHeading = headingParts[headingParts.length - 1].trim()
              
              // Normalise heading to match NotesView ID exactly
              const sectionId = 'sec-' + leafHeading
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
      }, 20)

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
      if (activeThreadRef.current === targetThreadId && streamIntervalRef.current == null) {
        setIsStreaming(false)
        setLoading(false)
        inFlightRef.current = false
      }
    }
  }, [threadId, addMessage, setLoading])

  // -------------------------------------------------------------------------
  // Reference handlers
  // -------------------------------------------------------------------------
  const handleReferenceClick = useCallback((sectionId: string) => {
    const ref = liveReferences.find(r => r.sectionId === sectionId)
    if (!ref) return
    
    const targetChapterId = ref.chapterId
    const store = useChapterStore.getState()
    const currentChapterId = store.activeChapterId

    const attemptScroll = () => {
      let attempts = 0
      // Poll every 100ms for up to 2 seconds to wait for DOM updates
      const interval = setInterval(() => {
        const el = document.getElementById(sectionId)
        if (el) {
          clearInterval(interval)
          el.scrollIntoView({ behavior: 'smooth', block: 'center' })
          el.classList.remove('scroll-highlight')
          void el.offsetWidth // trigger reflow
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
      // Trigger store updates to mount the new chapter and set active tab to Notes
      store.setChapter(targetChapterId)
      store.setDocTab('notes')
    }

    attemptScroll()
  }, [liveReferences])

  const handleScreenshotClick = useCallback((ref: any) => {
    // ref is the reference object from liveReferences (type 'screenshot')
    // Clean the path: remove "outputs/" prefix if present, then prepend "/static/"
    const cleanPath = (ref.section || '').replace(/^outputs\//, '')
    const src = `/static/${cleanPath}`
    const caption = ref.title || ''
    setLightbox({ src, caption })
  }, [])

  const isEmpty = messages.length === 0 && !isStreaming && !isLoading

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scroll-smooth doc-content">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-np to-nbl flex items-center justify-center mb-4 shadow-lg">
              <span className="text-lg font-semibold text-white">N</span>
            </div>
            <h3 className="text-sm font-medium text-nt mb-1">What can I help with?</h3>
            <p className="text-xs text-nt3 max-w-[200px]">
              Ask me anything about your lectures — I'll pull answers straight from your notes.
            </p>
          </div>
        ) : (
          <>
            <div className="text-[9px] text-nt3 text-center flex items-center gap-2">
              <span className="flex-1 h-px bg-bdr" />
              Today
              <span className="flex-1 h-px bg-bdr" />
            </div>

            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {isStreaming && streamingText && (
              <div className="flex gap-2 items-start">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-np to-nbl flex items-center justify-center text-[9px] font-medium text-white shrink-0 mt-0.5 shadow-sm">
                  N
                </div>
                <div className="max-w-full text-[12px] leading-relaxed text-nt2 py-0.5 whitespace-pre-wrap">
                  {streamingText}
                </div>
              </div>
            )}

            {(isStreaming && !streamingText) || isLoading ? (
              <div className="flex gap-2 items-start">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-np to-nbl flex items-center justify-center text-[9px] font-medium text-white shrink-0 mt-0.5 shadow-sm">
                  N
                </div>
                <ShimmerLoader />
              </div>
            ) : null}
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

      {/* Lightbox overlay */}
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
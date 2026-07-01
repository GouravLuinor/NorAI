import { useState, useRef, useEffect } from 'react'
import { mockMessages } from '../../mocks/messages'
import { useThreadStore, type Message, sendChatMessage } from '../../stores/useThreadStore'
import { MessageBubble } from './MessageBubble'
import { ReferencesPanel } from './ReferencesPanel'
import { InputZone } from './InputZone'
import { ShimmerLoader } from './ShimmerLoader'

let idCounter = 0
const genId = () => `msg-${++idCounter}`

export function ChatArea() {
  const { messages, addMessage, setLoading, threadId } = useThreadStore()
  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [liveReferences, setLiveReferences] = useState<any[]>([])
  const chatEndRef = useRef<HTMLDivElement>(null)
  const initialized = useRef(false)



  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  const handleSend = async (text: string) => {
    // 1. Add user message
    const userMsg: Message = {
      id: genId(),
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
    addMessage(userMsg)

    // 2. Show shimmer
    setIsStreaming(true)
    setStreamingText('')
    setLoading(true)

    try {
      const data = await sendChatMessage(threadId, text)
      const fullAnswer = data.answer
      const cleanAnswer = fullAnswer.replace(/\*\*Sources\*\*[\s\S]*$/, '').trim()
      let i = 0
      const interval = setInterval(() => {
        if (i < fullAnswer.length) {
          setStreamingText(cleanAnswer.slice(0, i + 1))
          i++
        } else {
          clearInterval(interval)

          const assistantMsg: Message = {
            id: genId(),
            role: 'assistant',
            content: cleanAnswer,         // ← FIX
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          }
          addMessage(assistantMsg)
          setStreamingText('')
          setIsStreaming(false)
          setLoading(false)

          // Populate references with real data
          const refs = [
            ...data.retrieved_chunks.map((c: any) => ({
              id: c.heading_path,
              title: c.heading_path,
              section: `Ch ${c.chapter_id}`,
              sectionId: '',
              type: 'note' as const,
            })),
            ...data.retrieved_images.map((img: any) => ({
              id: img.path,
              title: img.section,
              section: img.path,
              sectionId: '',
              type: 'screenshot' as const,
            })),
          ]
          setLiveReferences(refs)
        }
      }, 20)
    } catch (err) {
      console.error('Chat error:', err)
      addMessage({
        id: genId(),
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      })
      setIsStreaming(false)
      setLoading(false)
    }
  }

  const handleReferenceClick = (sectionId: string) => {
    const el = document.getElementById(sectionId)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.remove('scroll-highlight')
      void el.offsetWidth
      el.classList.add('scroll-highlight')
      el.addEventListener('animationend', function handler() {
        el.classList.remove('scroll-highlight')
        el.removeEventListener('animationend', handler)
      })
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scroll-smooth doc-content">
        {messages.length === 0 && !isStreaming ? (
          /* ── Welcome screen ── */
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

            {/* streaming & shimmer sections unchanged */}
            {isStreaming && streamingText && (
              <div className="flex gap-2 items-start">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-np to-nbl flex items-center justify-center text-[9px] font-medium text-white shrink-0 mt-0.5 shadow-sm">
                  N
                </div>
                <div className="max-w-full text-[12px] leading-relaxed text-nt2 py-0.5">
                  {streamingText}
                </div>
              </div>
            )}

            {isStreaming && !streamingText && (
              <div className="flex gap-2 items-start">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-np to-nbl flex items-center justify-center text-[9px] font-medium text-white shrink-0 mt-0.5 shadow-sm">
                  N
                </div>
                <ShimmerLoader />
              </div>
            )}
          </>
        )}

        <div ref={chatEndRef} />
      </div>

      <ReferencesPanel references={liveReferences} onReferenceClick={handleReferenceClick} />
      <InputZone onSend={handleSend} />
    </div>
  )
}
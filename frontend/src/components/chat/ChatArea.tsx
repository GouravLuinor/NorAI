import { useRef, useEffect } from 'react'
import { useThreadStore, sendChatMessageStream } from '../../stores/useThreadStore'
import { MessageBubble } from './MessageBubble'
import { ReferencesPanel } from './ReferencesPanel'
import { InputZone } from './InputZone'
import { ShimmerLoader } from './ShimmerLoader'

let idCounter = 0
const genId = () => `msg-${++idCounter}`

// 🚨 FIX: Stable reference to prevent infinite getSnapshot loops
const EMPTY_MESSAGES: any[] = []

export function ChatArea() {
  const threadId = useThreadStore((s) => s.threadId)
  
  // 🚨 FIX: Use nullish coalescing to the stable empty array
  const messages = useThreadStore((s) => s.messagesByThread[threadId] ?? EMPTY_MESSAGES)
  const isLoading = useThreadStore((s) => s.loadingByThread[threadId] || false)
  const streamingText = useThreadStore((s) => s.streamingByThread[threadId] || '')
  
  const { addMessage, setLoading, setStreamingText } = useThreadStore()
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  const handleSend = async (text: string) => {
    const targetThreadId = threadId 

    const userMsg = {
      id: genId(),
      role: 'user' as const,
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
    addMessage(targetThreadId, userMsg)
    setLoading(targetThreadId, true)
    setStreamingText(targetThreadId, '')

    try {
      const generator = sendChatMessageStream(targetThreadId, text)
      let fullAnswer = ''

      for await (const chunk of generator) {
        if (typeof chunk === 'string') {
          fullAnswer += chunk
          setStreamingText(targetThreadId, fullAnswer)
        } else if (chunk.type === 'final') {
          const cleanAnswer = fullAnswer.replace(/\*\*Sources\*\*[\s\S]*$/, '').trim()
          
          const refs = [
            ...(chunk.data.retrieved_chunks || []).map((c: any) => ({
              id: c.heading_path,
              title: c.heading_path,
              section: `Ch ${c.chapter_id}`,
              sectionId: '',
              type: 'note' as const,
            })),
            ...(chunk.data.retrieved_images || []).map((img: any) => ({
              id: img.path,
              title: img.section,
              section: img.path,
              sectionId: '',
              type: 'screenshot' as const,
            })),
          ]

          addMessage(targetThreadId, {
            id: genId(),
            role: 'assistant',
            content: cleanAnswer,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            references: refs
          })
          
          setStreamingText(targetThreadId, '')
          setLoading(targetThreadId, false)
        }
      }
    } catch (err) {
      console.error('Chat error:', err)
      addMessage(targetThreadId, {
        id: genId(),
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      })
      setStreamingText(targetThreadId, '')
      setLoading(targetThreadId, false)
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

  const reversedMessages = [...messages].reverse()
  const lastMsgWithRefs = reversedMessages.find(m => m.role === 'assistant' && m.references && m.references.length > 0)
  const displayReferences = lastMsgWithRefs?.references || []

  const isStreaming = isLoading || streamingText.length > 0

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scroll-smooth doc-content">
        {messages.length === 0 && !isStreaming ? (
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

            {isLoading && !streamingText && (
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

      <ReferencesPanel references={displayReferences} onReferenceClick={handleReferenceClick} />
      <InputZone onSend={handleSend} />
    </div>
  )
}
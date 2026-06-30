import { useState, useRef, useEffect } from 'react'
import { mockMessages } from '../../mocks/messages'
import { mockReferences } from '../../mocks/references'
import { useThreadStore, type Message } from '../../stores/useThreadStore'
import { MessageBubble } from './MessageBubble'
import { ReferencesPanel } from './ReferencesPanel'
import { InputZone } from './InputZone'
import { ShimmerLoader } from './ShimmerLoader'

let idCounter = 0
const genId = () => `msg-${++idCounter}`

const getMockResponse = (): string => {
  const responses = [
    'A Segment Tree is a specialized **full binary tree** designed to represent an array through a hierarchy of intervals.',
    'Segment Trees handle both range queries and point updates in **O(log N)** time.',
    'The key advantage is that both operations stay efficient even when the array is frequently modified.',
    'Think of it as storing information about ranges instead of individual values.',
  ]
  return responses[Math.floor(Math.random() * responses.length)]
}

export function ChatArea() {
  const { messages, addMessage, setLoading } = useThreadStore()
  const [streamingText, setStreamingText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const initialized = useRef(false)

  useEffect(() => {
    if (!initialized.current && messages.length === 0) {
      mockMessages.forEach((m) => addMessage(m))
      initialized.current = true
    }
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  const handleSend = (text: string) => {
    const userMsg: Message = {
      id: genId(),
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
    addMessage(userMsg)

    setIsStreaming(true)
    setStreamingText('')
    setLoading(true)

    setTimeout(() => {
      const response = getMockResponse()
      let i = 0
      const interval = setInterval(() => {
        if (i < response.length) {
          setStreamingText(response.slice(0, i + 1))
          i++
        } else {
          clearInterval(interval)
          const assistantMsg: Message = {
            id: genId(),
            role: 'assistant',
            content: response,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          }
          addMessage(assistantMsg)
          setStreamingText('')
          setIsStreaming(false)
          setLoading(false)
        }
      }, 20)
    }, 800)
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

        <div ref={chatEndRef} />
      </div>

      <ReferencesPanel references={mockReferences} onReferenceClick={handleReferenceClick} />
      <InputZone onSend={handleSend} />
    </div>
  )
}
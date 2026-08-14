import { memo } from 'react'
import type { Message } from '../../stores/useThreadStore'
import { Markdown } from '../ui/Markdown'
import { stripSources } from '../../lib/references'

export const MessageBubble = memo(function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  const displayContent = isUser ? message.content : stripSources(message.content)

  return (
    <div className={`flex gap-2 items-start ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`w-5 h-5 rounded-full flex items-center justify-center text-3xs font-medium text-npfg shrink-0 mt-0.5 ${
          isUser
            ? 'bg-ns3 text-nt2'
            : 'bg-npf shadow-ev1'
        }`}
      >
        {isUser ? '' : 'N'}
      </div>

      <div className={`${isUser ? 'items-end' : ''}`}>
        <div
          className={`text-xs leading-relaxed text-nt2 ${
            isUser
              ? 'bg-ns3 border border-bdr2 rounded-xl px-2.5 py-2 text-nt max-w-[85%]'
              : 'py-0.5 max-w-full'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose-chat">
              <Markdown variant="chat">{displayContent}</Markdown>
            </div>
          )}
        </div>
        <div className={`text-3xs text-nt4 mt-1 ${isUser ? 'text-right' : ''}`}>
          {message.timestamp}
        </div>
      </div>
    </div>
  )
})
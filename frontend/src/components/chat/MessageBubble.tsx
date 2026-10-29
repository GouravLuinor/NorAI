import { memo } from 'react'
import { RotateCcw } from 'lucide-react'
import type { Message } from '../../stores/useThreadStore'
import { Markdown } from '../ui/Markdown'
import { stripSources } from '../../lib/references'

interface MessageBubbleProps {
  message: Message
  /** Shown on a failed assistant turn: re-sends the original question. */
  onRetry?: () => void
}

export const MessageBubble = memo(function MessageBubble({ message, onRetry }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isError = message.status === 'error'
  const displayContent = isUser ? message.content : stripSources(message.content)

  return (
    <div className={`flex gap-2.5 items-start ${isUser ? 'justify-end' : ''}`}>
      {!isUser && (
        <div
          aria-hidden="true"
          className="w-7 h-7 rounded-[4px] bg-brass text-[#16181A] flex items-center justify-center text-13 font-bold shrink-0"
        >
          N
        </div>
      )}

      <div className={`min-w-0 ${isUser ? 'flex flex-col items-end max-w-[85%]' : 'flex-1'}`}>
        <div
          className={`text-15 leading-relaxed ${
            isUser
              ? `bg-npb rounded-md px-3.5 py-2.5 text-nt ${message.status === 'pending' ? 'opacity-70' : ''}`
              : isError
                ? 'bg-nrb border border-nrbr text-nrt rounded-md px-3.5 py-2.5'
                : 'text-nt pt-0.5'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : isError ? (
            <div className="flex flex-col gap-2">
              <p>{message.content}</p>
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="self-start inline-flex items-center gap-1.5 text-13 font-bold text-nrt hover:underline cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 rounded"
                >
                  <RotateCcw size={13} strokeWidth={1.75} /> Try again
                </button>
              )}
            </div>
          ) : (
            <div className="prose-chat">
              <Markdown variant="chat">{displayContent}</Markdown>
            </div>
          )}
        </div>
        <div className={`text-12 mt-1 ${isUser && isError ? 'text-nrt' : 'text-nt4'}`}>
          {isUser && isError ? 'Not answered' : message.timestamp}
        </div>
      </div>
    </div>
  )
})
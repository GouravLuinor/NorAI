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
              ? `bg-ns3 border border-bdr2 rounded-xl px-2.5 py-2 text-nt max-w-[85%] ${message.status === 'pending' ? 'opacity-70' : ''}`
              : isError
                ? 'bg-nrb border border-nrbr text-nrt rounded-lg px-2.5 py-2 max-w-full'
                : 'py-0.5 max-w-full'
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
                  className="self-start inline-flex items-center gap-1 text-3xs font-semibold uppercase tracking-wide text-nrt hover:underline cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 rounded"
                >
                  <RotateCcw size={11} /> Retry
                </button>
              )}
            </div>
          ) : (
            <div className="prose-chat">
              <Markdown variant="chat">{displayContent}</Markdown>
            </div>
          )}
        </div>
        <div className={`text-3xs mt-1 ${isUser ? 'text-right' : ''} ${isUser && isError ? 'text-nrt' : 'text-nt4'}`}>
          {isUser && isError ? 'Not answered' : message.timestamp}
        </div>
      </div>
    </div>
  )
})
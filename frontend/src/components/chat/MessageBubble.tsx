import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import type { Message } from '../../stores/useThreadStore'
import { chatMarkdownComponents } from '../../lib/markdown'

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

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
              <ReactMarkdown
                remarkPlugins={[remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={chatMarkdownComponents}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
        <div className={`text-3xs text-nt4 mt-1 ${isUser ? 'text-right' : ''}`}>
          {message.timestamp}
        </div>
      </div>
    </div>
  )
}
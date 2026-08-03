import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import type { Message } from '../../stores/useThreadStore'

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-2 items-start ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-medium text-white shrink-0 mt-0.5 ${
          isUser
            ? 'bg-ns3 text-nt2'
            : 'bg-gradient-to-br from-np to-nbl shadow-sm'
        }`}
      >
        {isUser ? '' : 'N'}
      </div>

      <div className={`${isUser ? 'items-end' : ''}`}>
        <div
          className={`text-[12px] leading-relaxed text-nt2 ${
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
                components={{
                  p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                  strong: ({ children }) => <strong className="text-nt font-medium">{children}</strong>,
                  ul: ({ children }) => <ul className="list-none pl-0 space-y-1 mt-1">{children}</ul>,
                  li: ({ children }) => <li className="relative pl-4 text-[12px] text-nt2 leading-relaxed"><span className="absolute left-0 top-2 w-1 h-1 rounded-full bg-ns3 border border-bdr2" />{children}</li>,
                  code: ({ children }: any) => <code className="font-mono text-[10px] bg-ns2 px-1 py-0.5 rounded text-nt border border-bdr">{children}</code>,
                  img: ({ src, alt }: any) => {
                    let cleanSrc = src || ''
                    if (cleanSrc.startsWith('outputs/')) {
                      cleanSrc = `/static/${cleanSrc.replace(/^outputs\//, '')}`
                    } else if (!cleanSrc.startsWith('/') && !cleanSrc.startsWith('http')) {
                      cleanSrc = `/static/${cleanSrc}`
                    }
                    return (
                      <img
                        src={cleanSrc}
                        alt={alt || ''}
                        className="rounded-lg border border-bdr my-2 max-h-60 object-contain shadow-sm"
                        loading="lazy"
                      />
                    )
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
        <div className={`text-[9px] text-nt4 mt-1 ${isUser ? 'text-right' : ''}`}>
          {message.timestamp}
        </div>
      </div>
    </div>
  )
}
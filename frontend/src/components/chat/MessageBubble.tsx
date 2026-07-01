import type { Message } from '../../stores/useThreadStore'

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  const displayContent = message.content
  return (
    <div
      className={`flex gap-2 items-start ${
        isUser ? 'flex-row-reverse' : ''
      }`}
    >
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
          <p className="whitespace-pre-wrap">{displayContent}</p>
        </div>
        <div
          className={`text-[9px] text-nt4 mt-1 ${isUser ? 'text-right' : ''}`}
        >
          {message.timestamp}
        </div>
      </div>
    </div>
  )
}
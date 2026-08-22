import { useState, useRef } from 'react'
import { ArrowUp } from 'lucide-react'
import { IconButton } from '../ui/IconButton'

interface InputZoneProps {
  onSend: (text: string) => void
}

export function InputZone({ onSend }: InputZoneProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 120) + 'px'
    }
  }

  return (
    <div className="px-3 py-2.5 border-t border-bdr shrink-0">
      <div className="flex items-end gap-2 bg-ns2 border border-bdr2 rounded-lg px-2.5 py-2 focus-within:shadow-[0_0_0_1px_var(--color-np)] transition">
        <textarea
          ref={textareaRef}
          name="chat-message"
          aria-label="Chat message"
          className="flex-1 bg-transparent border-none outline-none text-11 text-nt font-sans resize-none leading-relaxed min-h-[18px] max-h-[60px] placeholder:text-nt3"
          placeholder="Ask Nora anything…"
          rows={1}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            handleInput()
          }}
          onKeyDown={handleKeyDown}
        />
        <IconButton
          label="Send message"
          variant="primary"
          onClick={handleSend}
          disabled={!value.trim()}
          className="w-7 h-7 rounded-sm"
        >
          <ArrowUp size={13} strokeWidth={1.5} />
        </IconButton>
      </div>
      <div className="text-3xs text-nt4 text-center mt-1.5">
        ⌃ Enter to send
      </div>
    </div>
  )
}
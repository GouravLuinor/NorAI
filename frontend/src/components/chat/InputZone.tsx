import { useState, useRef } from 'react'
import { ArrowUp } from 'lucide-react'

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
      <div className="flex items-end gap-2 bg-ns2 border border-bdr2 rounded-lg px-2.5 py-2 focus-within:border-npbr transition">
        <textarea
          ref={textareaRef}
          className="flex-1 bg-transparent border-none outline-none text-[11.5px] text-nt font-sans resize-none leading-relaxed min-h-[18px] max-h-[60px] placeholder:text-nt3"
          placeholder="Ask Nora anything…"
          rows={1}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            handleInput()
          }}
          onKeyDown={handleKeyDown}
        />
        <button
          aria-label="Send message"
          onClick={handleSend}
          /* Added "ripple" class here */
          className="ripple w-6.5 h-6.5 rounded-md bg-np flex items-center justify-center text-white hover:bg-[#8E82E0] transition active:scale-93 shrink-0"
        >
          <ArrowUp size={13} />
        </button>
      </div>
      <div className="text-[9px] text-nt4 text-center mt-1.5">
        ⌃ Enter to send
      </div>
    </div>
  )
}
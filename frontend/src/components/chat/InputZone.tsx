import { useVideoStore } from '../../stores/useVideoStore'
import { useState, useRef } from 'react'
import { Button } from '../ui/Button'

interface InputZoneProps {
  onSend: (text: string) => void
  disabled?: boolean
}

export function InputZone({ onSend, disabled = false }: InputZoneProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = () => {
    if (disabled) return
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

  const noun = useVideoStore((s) => s.sourceKind === 'document') ? 'document' : 'lecture'

  return (
    <div className="px-4 pt-2.5 pb-3 border-t border-bdr shrink-0">
      <div className="flex items-end gap-2 bg-ns border-[1.5px] border-nt rounded-md pl-3 pr-1.5 py-1.5 focus-within:border-np transition-colors">
        <textarea
          ref={textareaRef}
          name="chat-message"
          aria-label={`Ask Nora about this ${noun}`}
          className="flex-1 bg-transparent border-none outline-none text-15 text-nt font-sans resize-none leading-snug py-1.5 min-h-[22px] max-h-[120px] placeholder:text-nt4 disabled:opacity-60"
          placeholder={disabled ? 'Nora is answering…' : `Ask about this ${noun}…`}
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(e) => {
            setValue(e.target.value)
            handleInput()
          }}
          onKeyDown={handleKeyDown}
        />
        <Button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="h-8 px-3.5 rounded-[4px] text-14 font-bold shrink-0"
        >
          Ask
        </Button>
      </div>
      <div className="text-12 text-nt4 mt-1.5">
        Enter to ask · Shift+Enter for a new line
      </div>
    </div>
  )
}
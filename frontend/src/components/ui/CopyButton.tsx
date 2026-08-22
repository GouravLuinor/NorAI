import { useEffect, useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { FOCUS_RING } from './shared'

interface CopyButtonProps {
  /** Lazily read the text to copy at click time (e.g. from a <pre> ref). */
  getValue: () => string
  label?: string
}

export function CopyButton({ getValue, label = 'Copy' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    },
    [],
  )

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(getValue())
      setCopied(true)
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard unavailable (permissions / insecure context) — no-op.
    }
  }

  return (
    <button
      onClick={handleCopy}
      aria-label={copied ? 'Copied' : `Copy ${label}`}
      className={`flex items-center gap-1 bg-transparent border-none text-nt3 hover:text-nt cursor-pointer font-inherit ${FOCUS_RING}`}
    >
      {copied ? <Check size={11} /> : <Copy size={11} />}
      {copied ? 'Copied' : label}
    </button>
  )
}

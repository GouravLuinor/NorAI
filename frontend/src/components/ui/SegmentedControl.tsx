import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import { FOCUS_RING } from './shared'

export interface SegmentedOption<T extends string> {
  value: T
  label: ReactNode
  prefix?: ReactNode
}

interface SegmentedControlProps<T extends string> {
  options: SegmentedOption<T>[]
  value: T | null
  onChange: (value: T) => void
  containerClass?: string
  itemClass?: string
  activeClass?: string
  inactiveClass?: string
}

// The two segmented switches (doc tabs / AI-panel mode) share structure but
// differ in chrome and active styling — both are injected via props so the
// swap is strictly token-preserving.
//
// P4.1: full keyboard ergonomics — Arrow/Home/End move the selection and
// focus (roving), matching the house tablist idiom so both segmented
// switches behave identically.
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  containerClass = 'flex items-center gap-0.5',
  itemClass = 'px-2.5 py-1 rounded-sm text-11 transition',
  activeClass = 'text-nt bg-ns3 shadow-ev1',
  inactiveClass = 'text-nt3 hover:text-nt2',
}: SegmentedControlProps<T>) {
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([])

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const idx = options.findIndex((o) => o.value === value)
    let next: number | null = null
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (idx + 1) % options.length
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (idx - 1 + options.length) % options.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = options.length - 1
    if (next === null || idx === -1) return
    e.preventDefault()
    onChange(options[next].value)
    itemRefs.current[next]?.focus()
  }

  return (
    <div className={containerClass} role="group" onKeyDown={handleKeyDown}>
      {options.map((opt, i) => (
        <button
          key={opt.value}
          ref={(el) => {
            itemRefs.current[i] = el
          }}
          type="button"
          onClick={() => onChange(opt.value)}
          aria-pressed={value === opt.value}
          className={`${itemClass} ${FOCUS_RING} active:translate-y-[1px] ${value === opt.value ? activeClass : inactiveClass}`
            .replace(/\s+/g, ' ')
            .trim()}
        >
          {opt.prefix}
          {opt.label}
        </button>
      ))}
    </div>
  )
}

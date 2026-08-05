import type { ReactNode } from 'react'
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
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  containerClass = 'flex items-center gap-0.5',
  itemClass = 'px-2.5 py-1 rounded-sm text-11 transition',
  activeClass = 'text-nt bg-ns3 shadow-ev1',
  inactiveClass = 'text-nt3 hover:text-nt2',
}: SegmentedControlProps<T>) {
  return (
    <div className={containerClass}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          aria-pressed={value === opt.value}
          className={`${itemClass} ${FOCUS_RING} ${value === opt.value ? activeClass : inactiveClass}`
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

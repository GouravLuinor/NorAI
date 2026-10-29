/**
 * NorAI brand mark: a call-number label. A green tile carries a white N over a
 * brass shelf bar. Inside the green rail the tile inverts (see `.rail` in
 * index.css, which sets --mark-bg / --mark-fg).
 */
export function BrandMark({ size = 24, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={`shrink-0 ${className}`}
    >
      <rect width="24" height="24" rx="4" fill="var(--mark-bg, var(--color-npf))" />
      <path
        d="M7.5 15.5V6.5L16.5 15.5V6.5"
        fill="none"
        stroke="var(--mark-fg, #FFFFFF)"
        strokeWidth="2.4"
        strokeLinecap="square"
        strokeLinejoin="miter"
      />
      <rect x="7.5" y="18" width="9" height="2" fill="var(--color-brass)" />
    </svg>
  )
}

interface WordmarkProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZES = {
  sm: { mark: 20, text: 'text-15' },
  md: { mark: 24, text: 'text-18' },
  lg: { mark: 32, text: 'text-24' },
} as const

export function Wordmark({ size = 'md', className = '' }: WordmarkProps) {
  const s = SIZES[size]
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <BrandMark size={s.mark} />
      <span className={`font-sans font-bold tracking-tight text-nt ${s.text}`}>NorAI</span>
    </span>
  )
}

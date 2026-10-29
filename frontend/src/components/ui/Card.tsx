import type { HTMLAttributes, ReactNode } from 'react'

// Sheet surface: hairline ink border, soft low shadow. Geometry
// (padding/margin) and accents (e.g. `border-l-2 border-l-np`) stay at the
// call site via props so migration is strictly token-preserving.
interface CardProps extends HTMLAttributes<HTMLDivElement> {
  accent?: string
  surface?: 'ns' | 'nb'
}

export function Card({
  accent = '',
  surface = 'ns',
  className = '',
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={`${surface === 'nb' ? 'bg-nb' : 'bg-ns'} border border-bdr rounded-md ${accent} ${className}`
        .replace(/\s+/g, ' ')
        .trim()}
      {...rest}
    >
      {children}
    </div>
  )
}

// Section heading row used atop cards: bold sentence-case label + icon.
// `tone` sets the label color; icons inherit currentColor unless they carry
// their own className.
export type CardTone = 'np' | 'nbl' | 'ng' | 'na' | 'nb' | 'nr' | 'nt3' | 'default'

const toneClass: Record<CardTone, string> = {
  np: 'text-np',
  nbl: 'text-nbl',
  ng: 'text-ng',
  na: 'text-na',
  nb: 'text-nb',
  nr: 'text-nr',
  nt3: 'text-nt3',
  default: 'text-nt3',
}

export function CardHeader({
  icon,
  tone = 'default',
  className = '',
  action,
  children,
}: {
  icon?: ReactNode
  tone?: CardTone
  className?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <div
      className={`flex items-center justify-between gap-2 text-14 font-bold ${toneClass[tone]} mb-2 ${className}`
        .replace(/\s+/g, ' ')
        .trim()}
    >
      <div className="flex items-center gap-1.5 min-w-0">
        {icon}
        <span className="truncate">{children}</span>
      </div>
      {action && <div className="shrink-0 font-normal">{action}</div>}
    </div>
  )
}

import type { ReactNode } from 'react'

// Small ALL-CAPS status chip (question type, difficulty, …).
export type BadgeTone = 'np' | 'nbl' | 'ns' | 'default'

const toneClass: Record<BadgeTone, string> = {
  np: 'bg-npb text-np',
  nbl: 'bg-nblb text-nbl',
  ns: 'bg-ns3 text-nt2',
  default: 'bg-ns3 text-nt2',
}

export function Badge({
  tone = 'default',
  className = '',
  children,
}: {
  tone?: BadgeTone
  className?: string
  children: ReactNode
}) {
  return (
    <span
      className={`px-2 py-0.5 rounded text-2xs font-semibold uppercase ${toneClass[tone]} ${className}`
        .replace(/\s+/g, ' ')
        .trim()}
    >
      {children}
    </span>
  )
}

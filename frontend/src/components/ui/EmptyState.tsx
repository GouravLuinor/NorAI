import type { ReactNode } from 'react'

// P4.5: honest empty/error state — icon chip + title + one-line hint +
// optional action. Replaces blank space and bare one-liners.
export function EmptyState({
  icon,
  title,
  hint,
  action,
  className = '',
}: {
  icon?: ReactNode
  title: string
  hint?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center gap-2 py-8 px-4 ${className}`}
    >
      {icon && (
        <div className="w-9 h-9 rounded-md bg-ns3 border border-bdr flex items-center justify-center text-nt3 mb-0.5">
          {icon}
        </div>
      )}
      <p className="text-xs font-medium text-nt">{title}</p>
      {hint && <p className="text-11 text-nt3 max-w-[220px] leading-relaxed">{hint}</p>}
      {action && <div className="mt-1.5">{action}</div>}
    </div>
  )
}

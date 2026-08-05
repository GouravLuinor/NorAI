import { AlertTriangle } from 'lucide-react'

// Subtle warning shown when a chapter's content came back partially
// generated (graceful-degradation fallback), rather than silently rendering
// an empty/shortened pane.
export function PartialContentBadge({ className = '' }: { className?: string }) {
  return (
    <div
      role="status"
      className={`inline-flex items-start gap-2 rounded-lg border border-nrbr bg-nrb px-3 py-2 text-13 text-nt2 ${className}`}
    >
      <AlertTriangle size={14} strokeWidth={1.5} className="text-nr shrink-0 mt-0.5" />
      <span>Partially generated — some content may be missing for this chapter.</span>
    </div>
  )
}
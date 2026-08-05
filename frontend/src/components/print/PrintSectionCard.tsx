import type { ReactNode } from 'react'
import { Bookmark, Clock, Lightbulb, Code, List, FileText } from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'

// Renders a section body inside the card chrome its type maps to. Callout is
// the one deliberately non-Card variant (tinted accent callout, not a surface).
export function PrintSectionCard({
  type,
  heading,
  children,
}: {
  type: string
  heading: string
  children: ReactNode
}) {
  switch (type) {
    case 'definition':
      return (
        <Card className="p-4 mb-4">
          <CardHeader icon={<Bookmark size={13} strokeWidth={1.5} className="text-np" />}>{heading}</CardHeader>
          {children}
        </Card>
      )
    case 'table':
      return (
        <Card className="p-5 mb-5">
          <CardHeader icon={<Clock size={13} strokeWidth={1.5} className="text-ng" />}>{heading}</CardHeader>
          {children}
        </Card>
      )
    case 'callout':
      return (
        <div className="flex gap-2.5 bg-nblb border border-nblbr rounded-lg p-3 mb-4">
          <Lightbulb size={14} strokeWidth={1.5} className="text-nbl mt-0.5 shrink-0" />
          <div>
            <div className="text-3xs font-semibold text-nt3 uppercase tracking-wider mb-1">{heading}</div>
            <div className="text-xs text-nt2 leading-relaxed">{children}</div>
          </div>
        </div>
      )
    case 'list':
      return (
        <div className="mb-5">
          <CardHeader icon={<List size={13} strokeWidth={1.5} className="text-np" />}>{heading}</CardHeader>
          <div className="pl-1.5 space-y-2.5">{children}</div>
        </div>
      )
    case 'code':
      return (
        <div className="mb-6">
          <CardHeader icon={<Code size={13} strokeWidth={1.5} className="text-nbl" />}>{heading}</CardHeader>
          <Card surface="nb" className="overflow-hidden">
            <pre className="p-4 m-0 overflow-x-auto font-mono text-13 text-nt2 leading-relaxed">{children}</pre>
          </Card>
        </div>
      )
    default:
      return (
        <Card className="p-5 mb-5">
          <CardHeader icon={<FileText size={13} strokeWidth={1.5} className="text-nt3" />}>{heading}</CardHeader>
          {children}
        </Card>
      )
  }
}

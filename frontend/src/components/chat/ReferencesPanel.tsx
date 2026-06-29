import { useState } from 'react'
import type { Reference } from '../../mocks/references'
import { Bookmark, ChevronUp, FileText, Image } from 'lucide-react'

interface ReferencesPanelProps {
  references: Reference[]
  onReferenceClick?: (sectionId: string) => void
}

export function ReferencesPanel({ references, onReferenceClick }: ReferencesPanelProps) {
  const [collapsed, setCollapsed] = useState(true)

  return (
    <div
      className={`border-t border-bdr px-3.5 py-2.5 shrink-0 transition-all duration-240 ${
        collapsed ? 'max-h-[34px] overflow-hidden' : 'max-h-[240px]'
      }`}
    >
      <div
        className="flex items-center justify-between mb-2 cursor-pointer"
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="flex items-center gap-1 text-[10px] font-medium text-nt3">
          <Bookmark size={12} />
          References
          <span className="text-[9px] bg-ns3 px-1.5 py-0.5 rounded-sm text-nt2">
            {references.length}
          </span>
        </div>
        <ChevronUp
          size={11}
          className={`text-nt3 transition-transform ${collapsed ? 'rotate-180' : ''}`}
        />
      </div>

      {references.map((ref) => (
        <div
          key={ref.id}
          onClick={() => onReferenceClick?.(ref.sectionId)}
          className="flex items-center gap-2 px-1.5 py-1.5 rounded-md cursor-pointer hover:bg-ns3 transition mb-0.5"
        >
          {ref.type === 'note' ? (
            <FileText size={12} className="text-nt3" />
          ) : (
            <Image size={12} className="text-nt3" />
          )}
          <span className="text-[10px] text-nt2 flex-1 truncate">{ref.title}</span>
          <span className="text-[9px] text-nt3">{ref.section}</span>
        </div>
      ))}

      <div className="flex gap-1.5 mt-2">
        {references
          .filter((r) => r.type === 'screenshot')
          .map((ref) => (
            <div
              key={ref.id}
              onClick={() => onReferenceClick?.(ref.sectionId)}
              className="w-11 h-7 rounded-md border border-bdr2 bg-ns3 flex items-center justify-center cursor-pointer hover:border-np transition"
            >
              <Image size={14} className="text-nt3" />
            </div>
          ))}
      </div>
    </div>
  )
}
import { useState } from 'react'
import type { Reference } from '../../types'
import { Bookmark, ChevronUp, FileText, Image } from 'lucide-react'

interface ReferencesPanelProps {
  references: Reference[]
  onReferenceClick?: (sectionId: string) => void
  onScreenshotClick?: (ref: Reference) => void
}

export function ReferencesPanel({ references, onReferenceClick, onScreenshotClick }: ReferencesPanelProps) {
  const [collapsed, setCollapsed] = useState(true)

  return (
    <div
      className={`border-t border-bdr px-3.5 py-2.5 shrink-0 transition-all duration-240 ${
        collapsed ? 'max-h-[34px] overflow-hidden' : 'max-h-[300px]'
      }`}
    >
      {/* Header toggle */}
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

      {/* Reference rows — note rows scroll, screenshot rows open lightbox */}
      <div className="space-y-0.5 max-h-[240px] overflow-y-auto">
        {references.map((ref) => {
          const isScreenshot = ref.type === 'screenshot'
          return (
            <div
              key={ref.id}
              onClick={() => {
                if (isScreenshot) {
                  onScreenshotClick?.(ref)
                } else {
                  onReferenceClick?.(ref.sectionId)
                }
              }}
              className="flex items-center gap-2 px-1.5 py-1.5 rounded-md cursor-pointer hover:bg-ns3 transition"
            >
              {isScreenshot ? (
                <Image size={12} className="text-nt3 shrink-0" />
              ) : (
                <FileText size={12} className="text-nt3 shrink-0" />
              )}
              <span className="text-[10px] text-nt2 flex-1 truncate">{ref.title}</span>
              <span className="text-[9px] text-nt3 shrink-0">{ref.section}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
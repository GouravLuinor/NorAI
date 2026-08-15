import { memo, useState } from 'react'
import type { Reference } from '../../types'
import { Bookmark, ChevronUp, FileText, Image, Play } from 'lucide-react'
import { FOCUS_RING } from '../ui/shared'
import { useVideoStore } from '../../stores/useVideoStore'
import { formatTimestamp } from '../../lib/video'

interface ReferencesPanelProps {
  references: Reference[]
  onReferenceClick?: (ref: Reference) => void
  onScreenshotClick?: (ref: Reference) => void
}

export const ReferencesPanel = memo(function ReferencesPanel({ references, onReferenceClick, onScreenshotClick }: ReferencesPanelProps) {
  const [collapsed, setCollapsed] = useState(true)
  // P6.3: exact-moment chunk seek with chapter fallback.
  const videoEmbeddable = useVideoStore((s) => s.embeddable)
  const chunkStart = useVideoStore((s) => s.chunkStart)
  const chapterStart = useVideoStore((s) => s.chapterStart)
  const requestSeek = useVideoStore((s) => s.requestSeek)

  return (
    <div
      className={`border-t border-bdr px-3.5 py-2.5 shrink-0 transition-all duration-240 ${
        collapsed ? 'max-h-[34px] overflow-hidden' : 'max-h-[300px]'
      }`}
    >
      {/* Header toggle */}
      <button
        type="button"
        className={`w-full flex items-center justify-between mb-2 cursor-pointer ${FOCUS_RING}`}
        onClick={() => setCollapsed(!collapsed)}
        aria-expanded={!collapsed}
      >
        <div className="flex items-center gap-1 text-2xs font-medium text-nt3">
          <Bookmark size={12} strokeWidth={1.5} />
          References
          <span className="text-3xs bg-ns3 px-1.5 py-0.5 rounded-sm text-nt2">
            {references.length}
          </span>
        </div>
        <ChevronUp
          size={11}
          strokeWidth={1.5}
          className={`text-nt3 transition-transform ${collapsed ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Reference rows — note rows scroll, screenshot rows open lightbox */}
      <div inert={collapsed} className="space-y-0.5 max-h-[240px] overflow-y-auto">
        {references.map((ref, index) => {
          const isScreenshot = ref.type === 'screenshot'
          const seekSec = videoEmbeddable && !isScreenshot
            ? (chunkStart(ref.chunkId, ref.chapterId) ?? chapterStart(ref.chapterId))
            : null
          return (
            <div key={`${ref.type}-${ref.id}-${index}`} className="group flex items-center gap-1">
              <button
                type="button"
                onClick={() => {
                  if (isScreenshot) {
                    onScreenshotClick?.(ref)
                  } else {
                    onReferenceClick?.(ref)
                  }
                }}
                className={`flex-1 flex items-center gap-2 px-1.5 py-1.5 rounded-md cursor-pointer hover:bg-ns3 transition text-left ${FOCUS_RING}`}
              >
                {isScreenshot ? (
                  <Image size={12} strokeWidth={1.5} className="text-nt3 shrink-0" />
                ) : (
                  <FileText size={12} strokeWidth={1.5} className="text-nt3 shrink-0" />
                )}
                <span className="text-2xs text-nt2 flex-1 truncate">{ref.title}</span>
                <span className="text-3xs text-nt3 shrink-0">{ref.section}</span>
              </button>
              {seekSec != null && (
                <button
                  type="button"
                  title={`Jump the video to ${formatTimestamp(seekSec)}`}
                  aria-label={`Play ${ref.section} in the lecture video`}
                  onClick={() => requestSeek(seekSec)}
                  className={`flex items-center gap-1 px-1.5 py-1 rounded-sm bg-ns3 border border-bdr text-3xs text-nt3 hover:text-nt hover:border-nt4 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition cursor-pointer shrink-0 ${FOCUS_RING}`}
                >
                  <Play size={9} strokeWidth={1.5} />
                  {formatTimestamp(seekSec)}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
})
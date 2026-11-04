import { memo, useState } from 'react'
import type { Reference } from '../../types'
import { ChevronUp } from 'lucide-react'
import { ShelfMark } from '../ui/ShelfMark'
import { FOCUS_RING } from '../ui/shared'
import { useVideoStore } from '../../stores/useVideoStore'
import { formatTimestamp } from '../../lib/video'

/** "Chapter > 2. The input layer" -> "The input layer": the shelf mark
 *  already says which chapter it is. */
function sourceLabel(ref: Reference): string {
  const raw = ref.title || ref.section || ''
  const leaf = raw.split('>').pop()?.trim() || raw
  return leaf.replace(/^\s*\d+(?:\.\d+)*[.)]\s+/, '')
}

interface ReferencesPanelProps {
  references: Reference[]
  onReferenceClick?: (ref: Reference) => void
  onScreenshotClick?: (ref: Reference) => void
}

export const ReferencesPanel = memo(function ReferencesPanel({ references, onReferenceClick, onScreenshotClick }: ReferencesPanelProps) {
  const [collapsed, setCollapsed] = useState(false)
  // P6.3: exact-moment chunk seek with chapter fallback.
  const videoEmbeddable = useVideoStore((s) => s.embeddable)
  const isDocument = useVideoStore((s) => s.sourceKind === 'document')
  const chunkStart = useVideoStore((s) => s.chunkStart)
  const chapterStart = useVideoStore((s) => s.chapterStart)
  const requestSeek = useVideoStore((s) => s.requestSeek)

  if (references.length === 0) return null

  return (
    <div className="border-t border-bdr px-4 py-2.5 shrink-0">
      {/* Header toggle */}
      <button
        type="button"
        className={`w-full flex items-center justify-between py-1 rounded-sm cursor-pointer ${FOCUS_RING}`}
        onClick={() => setCollapsed(!collapsed)}
        aria-expanded={!collapsed}
      >
        <span className="text-13 font-bold text-nt2">
          Sources from this {isDocument ? 'document' : 'lecture'} <span className="font-mono text-nt3">{references.length}</span>
        </span>
        <ChevronUp
          size={15}
          strokeWidth={1.75}
          className={`text-nt3 transition-transform ${collapsed ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Each source carries its shelf mark: press it to play that moment */}
      {!collapsed && (
        <ul className="mt-1.5 space-y-1 max-h-[180px] overflow-y-auto">
          {references.map((ref, index) => {
            const isScreenshot = ref.type === 'screenshot'
            const seekSec = videoEmbeddable && !isScreenshot
              ? (ref.startSec ?? chunkStart(ref.chunkId, ref.chapterId) ?? chapterStart(ref.chapterId))
              : null
            const top = ref.chapterId != null ? `CH ${String(ref.chapterId).padStart(2, '0')}` : undefined
            return (
              <li key={`${ref.type}-${ref.id}-${index}`} className="flex items-center gap-2">
                {seekSec != null ? (
                  <ShelfMark
                    inline
                    top={top}
                    time={formatTimestamp(seekSec)}
                    label={`Play ${sourceLabel(ref)} from ${formatTimestamp(seekSec)}`}
                    onClick={() => requestSeek(seekSec)}
                    className="shrink-0 py-0.5"
                  />
                ) : (
                  <ShelfMark inline top={top ?? (isScreenshot ? 'IMG' : 'NOTE')} className="shrink-0 py-0.5" />
                )}
                <button
                  type="button"
                  onClick={() => {
                    if (isScreenshot) {
                      onScreenshotClick?.(ref)
                    } else {
                      onReferenceClick?.(ref)
                    }
                  }}
                  className={`flex-1 min-w-0 text-left text-13 text-nt2 hover:text-nt hover:underline truncate first-letter:uppercase rounded-sm cursor-pointer ${FOCUS_RING}`}
                  title={isScreenshot ? 'Open the slide' : 'Show this section in the notes'}
                >
                  {sourceLabel(ref)}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
})
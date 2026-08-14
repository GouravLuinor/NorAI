import { BookOpen, Loader, MoveUpRight, Quote, Play } from 'lucide-react'
import type { QuizCitation } from '../../stores/useQuizStore'
import { FOCUS_RING } from '../ui/shared'
import { useVideoStore } from '../../stores/useVideoStore'
import { formatTimestamp } from '../../lib/video'

interface CitationBoxProps {
  citation: QuizCitation | null
  loading: boolean
  onScroll?: () => void
}

/**
 * Inline "where is this in the notes?" box for quiz questions. Reused by
 * QuizPanel and AssessmentView. Renders the retrieved source heading, a short
 * snippet, a click-to-scroll affordance, and a click-to-video seek button when
 * a video is available.
 */
export function CitationBox({ citation, loading, onScroll }: CitationBoxProps) {
  const videoEmbeddable = useVideoStore((s) => s.embeddable)
  const chunkStart = useVideoStore((s) => s.chunkStart)
  const chapterStart = useVideoStore((s) => s.chapterStart)
  const requestSeek = useVideoStore((s) => s.requestSeek)

  if (loading) {
    return (
      <div className="mt-3 flex items-center gap-2 text-xs text-nt3">
        <Loader size={13} strokeWidth={1.5} className="animate-spin" />
        Finding this in the notes…
      </div>
    )
  }

  if (!citation) return null

  if (!citation.source) {
    return (
      <div className="mt-3 text-xs text-nt3">
        {citation.message || 'No source found for this question in the lecture.'}
      </div>
    )
  }

  const seekSec = videoEmbeddable
    ? (chunkStart(citation.chunk_id, citation.chapter_id) ?? chapterStart(citation.chapter_id ?? undefined))
    : null

  return (
    <div className="group relative mt-3 p-3 rounded-lg bg-nb border border-bdr2 shadow-ev1 transition-all hover:border-nt4">
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        <BookOpen size={13} strokeWidth={1.5} className="text-nbl shrink-0" />
        <span className="text-2xs font-semibold text-nt3 uppercase tracking-wider">In the notes</span>
        <div className="ml-auto flex items-center gap-2">
          {seekSec != null && (
            <button
              type="button"
              title={`Jump the video to ${formatTimestamp(seekSec)}`}
              aria-label={`Play this concept in the lecture video at ${formatTimestamp(seekSec)}`}
              onClick={() => requestSeek(seekSec)}
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm bg-ns2 border border-bdr text-3xs font-medium text-nt2 hover:text-np hover:border-np/40 transition cursor-pointer ${FOCUS_RING}`}
            >
              <Play size={9} strokeWidth={1.5} />
              {formatTimestamp(seekSec)}
            </button>
          )}
          {onScroll && (
            <button
              type="button"
              onClick={onScroll}
              className={`inline-flex items-center gap-1 text-2xs font-medium text-nbl hover:text-np bg-transparent border-none cursor-pointer ${FOCUS_RING}`}
            >
              Jump to section <MoveUpRight size={11} strokeWidth={1.5} />
            </button>
          )}
        </div>
      </div>
      <div className="text-xs font-medium text-nt leading-snug">{citation.source}</div>
      {citation.text && <p className="mt-1 text-2xs text-nt3 leading-relaxed line-clamp-3">{citation.text}</p>}

      {/* Hover preview popover card */}
      {citation.text && (
        <div className="pointer-events-none opacity-0 group-hover:opacity-100 group-hover:pointer-events-auto transition-all duration-200 absolute left-0 right-0 bottom-full mb-2 z-50 p-3 rounded-lg bg-ns border border-bdr2 shadow-ev3 text-2xs text-nt fold-marks">
          <div className="flex items-center gap-1.5 text-np font-mono text-3xs uppercase tracking-wider mb-1">
            <Quote size={10} strokeWidth={1.5} /> Grounded Citation Transcript Snippet
          </div>
          <p className="text-nt2 leading-relaxed italic">{`"${citation.text}"`}</p>
          <div className="mt-1.5 text-3xs text-nt4 font-mono">Source section: {citation.source}</div>
        </div>
      )}
    </div>
  )
}

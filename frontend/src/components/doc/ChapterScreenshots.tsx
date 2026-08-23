import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, Image as ImageIcon } from 'lucide-react'
import { Lightbox } from '../ui/Lightbox'
import { FOCUS_RING } from '../ui/shared'
import { useLectureStore } from '../../stores/useLectureStore'
import { apiGet } from '../../lib/http'

interface Screenshot {
  path: string
  reason: string
  section: string
  importance: number
}

export function ChapterScreenshots({
  chapterId,
  startExpanded = false,
  lazyLoad = true,
}: {
  chapterId: number | null
  startExpanded?: boolean
  lazyLoad?: boolean
}) {
  const [open, setOpen] = useState(startExpanded)
  const [screenshots, setScreenshots] = useState<Screenshot[]>([])
  const [lightbox, setLightbox] = useState<{ src: string; caption: string } | null>(null)

  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'

  useEffect(() => {
    if (!chapterId) {
      setScreenshots([])
      return
    }
    let cancelled = false
    apiGet<Screenshot[]>(`/screenshots/${chapterId}?lecture_id=${lectureId}`)
      .then((data) => {
        if (!cancelled) setScreenshots(data ?? [])
      })
      .catch(() => {
        if (!cancelled) setScreenshots([])
      })
    return () => {
      cancelled = true
    }
  }, [chapterId, lectureId])

  if (!screenshots.length) return null

  const toggleOpen = () => {
    setOpen((prev) => !prev)
  }

  const cleanPath = (raw: string) => raw.replace(/^outputs\//, '')

  return (
    <div className="mt-8">
      <button
        onClick={toggleOpen}
        aria-expanded={open}
        className={`flex items-center gap-2 text-3xs font-semibold text-nt3 uppercase tracking-wider hover:text-nt transition ${FOCUS_RING}`}
      >
        <ImageIcon size={13} strokeWidth={1.5} />
        Important Visuals ({screenshots.length})
        {open ? <ChevronUp size={13} strokeWidth={1.5} /> : <ChevronDown size={13} strokeWidth={1.5} />}
      </button>

      {open && (
        <div className="mt-3 space-y-4">
          {screenshots.map((shot, i) => {
            const imgUrl = `/static/${cleanPath(shot.path)}`
            return (
              <div
                key={i}
                className="bg-ns border border-bdr2 rounded-lg overflow-hidden shadow-ev1"
              >
                <button
                  type="button"
                  aria-label={`View screenshot: ${shot.reason}`}
                  className={`w-full block cursor-zoom-in ${FOCUS_RING}`}
                  onClick={() =>
                    setLightbox({ src: imgUrl, caption: shot.reason })
                  }
                >
                  <img
                    src={imgUrl}
                    alt=""
                    width="1600"
                    height="900"
                    className="w-full aspect-video object-cover"
                    loading={lazyLoad ? "lazy" : "eager"}
                    decoding="async"
                    onError={(e) => {
                      const target = e.currentTarget
                      target.style.display = 'none'
                      target.nextElementSibling?.classList.remove('hidden')
                    }}
                  />
                  <div className="hidden p-4 text-center text-nt4 text-xs">
                    <ImageIcon size={24} strokeWidth={1.5} className="mx-auto mb-1 opacity-40" />
                    Screenshot unavailable
                  </div>
                </button>
                <div className="p-3 text-xs text-nt2 leading-relaxed">
                  <span className="text-2xs font-semibold text-nt3 uppercase tracking-wider block mb-1">
                    {shot.section}
                  </span>
                  {shot.reason}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Lightbox overlay */}
      {lightbox && (
        <Lightbox
          src={lightbox.src}
          alt="Lecture screenshot"
          caption={lightbox.caption}
          onClose={() => setLightbox(null)}
        />
      )}
    </div>
  )
}
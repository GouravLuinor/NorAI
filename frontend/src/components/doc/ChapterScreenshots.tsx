import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, Image as ImageIcon } from 'lucide-react'
import { Lightbox } from '../ui/Lightbox'
import { useLectureStore } from '../../stores/useLectureStore'  

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
  const [loading, setLoading] = useState(false)
  const [lightbox, setLightbox] = useState<{ src: string; caption: string } | null>(null)

  const lectureId = useLectureStore(s => s.activeLectureId) || 'default' 

  useEffect(() => {
    if (!chapterId) return
    setLoading(true)
    fetch(`/screenshots/${chapterId}?lecture_id=${lectureId}`) 
      .then((res) => res.json())
      .then((data) => setScreenshots(data))
      .catch(() => setScreenshots([]))
      .finally(() => setLoading(false))
  }, [chapterId, lectureId])  

  if (!screenshots.length) return null

  const cleanPath = (raw: string) => raw.replace(/^outputs\//, '')

  return (
    <div className="mt-8">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider hover:text-nt transition"
      >
        <ImageIcon size={13} />
        Important Visuals ({screenshots.length})
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
      </button>

      {open && (
        <div className="mt-3 space-y-4">
          {screenshots.map((shot, i) => {
            const imgUrl = `/static/${cleanPath(shot.path)}`
            return (
              <div
                key={i}
                className="bg-ns border border-bdr2 rounded-lg overflow-hidden shadow-sm"
              >
                <div
                  className="cursor-zoom-in"
                  onClick={() =>
                    setLightbox({ src: imgUrl, caption: shot.reason })
                  }
                >
                  <img
                    src={imgUrl}
                    alt={shot.reason}
                    className="w-full object-cover"
                    loading={lazyLoad ? "lazy" : "eager"}
                    onError={(e) => {
                      const target = e.currentTarget
                      target.style.display = 'none'
                      target.nextElementSibling?.classList.remove('hidden')
                    }}
                  />
                  <div className="hidden p-4 text-center text-nt4 text-xs">
                    <ImageIcon size={24} className="mx-auto mb-1 opacity-40" />
                    Screenshot unavailable
                  </div>
                </div>
                <div className="p-3 text-xs text-nt2 leading-relaxed">
                  <span className="text-[10px] font-semibold text-nt3 uppercase tracking-wider block mb-1">
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
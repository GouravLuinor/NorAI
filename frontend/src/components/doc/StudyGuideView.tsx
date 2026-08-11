import { useState, useEffect } from 'react'
import { BookMarked } from 'lucide-react'
import { useLectureStore } from '../../stores/useLectureStore'
import { apiGet } from '../../lib/http'
import { Markdown } from '../ui/Markdown'
import { Card, CardHeader } from '../ui/Card'

interface GuideChapter {
  chapter_id: number
  title: string
  markdown: string
}

/**
 * Study Guide tab — a zero-generation catalog of the lecture's already-written
 * per-chapter revision notes, concatenated into one navigable document.
 */
export function StudyGuideView() {
  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'
  const [title, setTitle] = useState('')
  const [chapters, setChapters] = useState<GuideChapter[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    apiGet<{ title?: string; chapters?: GuideChapter[] }>(`/study-guide?lecture_id=${lectureId}`, { signal: controller.signal })
      .then((data) => {
        setTitle(data.title || '')
        setChapters(Array.isArray(data.chapters) ? data.chapters : [])
        setLoading(false)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setChapters([])
        setError('Study guide is not available for this lecture yet.')
        setLoading(false)
      })
    return () => controller.abort()
  }, [lectureId])

  if (loading) {
    return <div className="flex-1 flex items-center justify-center text-nt3 text-sm">Loading study guide…</div>
  }

  if (chapters.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 text-nt3 text-sm">
        <div>{error || 'No revision notes yet to compile into a study guide.'}</div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto doc-content px-8 py-7 pb-16 scroll-smooth">
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-2">
          <BookMarked size={15} strokeWidth={1.5} className="text-np" />
          <span className="text-3xs font-semibold text-nt3 uppercase tracking-wider">Study Guide</span>
        </div>
        <h1 className="font-serif text-hero font-medium text-nt tracking-tight leading-snug">
          {title || 'Study Guide'}
        </h1>
        <p className="text-xs text-nt3 mt-2">
          Compiled from this lecture's revision notes — {chapters.length} chapter{chapters.length === 1 ? '' : 's'}.
        </p>
      </div>

      {chapters.map((ch) => (
        <section key={ch.chapter_id} className="mb-10" aria-label={ch.title}>
          <Card className="p-6 mb-4" accent="border-l-2 border-l-np">
            <CardHeader icon={<BookMarked size={13} strokeWidth={1.5} />}>
              {ch.title}
            </CardHeader>
            <Markdown variant="revision">{ch.markdown}</Markdown>
          </Card>
        </section>
      ))}
    </div>
  )
}

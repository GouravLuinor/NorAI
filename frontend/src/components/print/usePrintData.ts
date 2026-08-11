import { useState, useEffect } from 'react'
import { fetchQuizQuestions, type Question } from '../../stores/useQuizStore'
import { useLectureStore } from '../../stores/useLectureStore'
import { apiFetchRaw, apiGet } from '../../lib/http'
import type { PrintData, PrintType, PrintChapterPayload } from './types'
import type { ConceptMapResponse } from '../../lib/conceptMapLayout'

// Loads every chapter's print payload once. Primary path: data injected by the
// calling window via `__PRINT_DATA__` (or the `printDataReady` event). Fallback:
// a 500ms-window fetch of each chapter's notes/revision/assessment endpoint.
export function usePrintData(lectureId: string, type: PrintType) {
  const [chapters, setChapters] = useState<PrintChapterPayload[]>([])
  const [assessmentChapters, setAssessmentChapters] = useState<{ ch: number; questions: Question[] }[]>([])
  const [guideTitle, setGuideTitle] = useState('')
  const [conceptMaps, setConceptMaps] = useState<{ ch: number; data: ConceptMapResponse }[]>([])
  const [loading, setLoading] = useState(true)
  const [globalError, setGlobalError] = useState<string | null>(null)
  const [numChapters, setNumChapters] = useState(6)

  const setActiveLecture = useLectureStore(s => s.setActiveLecture)

  useEffect(() => {
    setActiveLecture(lectureId)
  }, [lectureId, setActiveLecture])

  useEffect(() => {
    apiGet<{ chapters?: unknown[] }>(`/outline?lecture_id=${lectureId}`)
      .then(data => {
        const count = data.chapters?.length || 6
        setNumChapters(count)
      })
      .catch(() => setNumChapters(6))
  }, [lectureId])

  useEffect(() => {
    let cancelled = false

    const applyData = (data: PrintData) => {
      if (cancelled) return
      if (data.type === 'assessment') {
        setAssessmentChapters(data.assessmentChapters)
      } else if (data.type === 'guide') {
        setGuideTitle(data.title)
        setChapters(data.chapters)
      } else if (data.type === 'concepts') {
        setConceptMaps(data.maps)
      } else {
        setChapters(data.chapters)
      }
      setLoading(false)
    }

    if (window.__PRINT_DATA__) {
      applyData(window.__PRINT_DATA__)
      return
    }

    const onReady = () => {
      if (window.__PRINT_DATA__) applyData(window.__PRINT_DATA__)
    }
    window.addEventListener('printDataReady', onReady)

    const fallbackTimer = setTimeout(async () => {
      if (cancelled || window.__PRINT_DATA__) return
      try {
        if (type === 'assessment') {
          const promises = Array.from({ length: numChapters }, async (_, i) => {
            const ch = i + 1
            const questions = await fetchQuizQuestions(ch, lectureId).catch(() => [] as Question[])
            return { ch, questions }
          })
          const all = await Promise.all(promises)
          if (!cancelled) setAssessmentChapters(all)
        } else if (type === 'guide') {
          const data = await apiGet<{ title?: string; chapters?: PrintChapterPayload[] }>(
            `/study-guide?lecture_id=${lectureId}`,
          )
          if (!cancelled) {
            setGuideTitle(data.title || '')
            setChapters(Array.isArray(data.chapters) ? data.chapters : [])
          }
        } else if (type === 'concepts') {
          const promises = Array.from({ length: numChapters }, async (_, i) => {
            const ch = i + 1
            try {
              const data = await apiGet<ConceptMapResponse>(
                `/concept-map?chapter_id=${ch}&lecture_id=${lectureId}`,
              )
              return { ch, data }
            } catch {
              return null
            }
          })
          const all = await Promise.all(promises)
          if (!cancelled) setConceptMaps(all.filter((m): m is { ch: number; data: ConceptMapResponse } => !!m))
        } else {
          const endpoint = type === 'revision' ? '/summary' : '/notes'
          const promises = Array.from({ length: numChapters }, async (_, i) => {
            const ch = i + 1
            try {
              const url = type === 'revision'
                ? `${endpoint}?chapter_id=${ch}&lecture_id=${lectureId}`
                : `${endpoint}/${ch}?lecture_id=${lectureId}`
              const res = await apiFetchRaw(url)
              if (!res.ok) throw new Error(`HTTP ${res.status}`)
              const contentType = res.headers.get('content-type') || ''
              if (contentType.includes('application/json')) {
                return (await res.json()) as PrintChapterPayload
              }
              const raw = await res.text()
              try {
                return JSON.parse(raw) as PrintChapterPayload
              } catch {
                return raw as PrintChapterPayload
              }
            } catch (err) {
              const message = err instanceof Error ? err.message : String(err)
              return `# Chapter ${ch}\n\n*Content not yet generated or failed to load. (${message})*`
            }
          })
          const texts = await Promise.all(promises)
          if (!cancelled) setChapters(texts)
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err)
        if (!cancelled) setGlobalError(message || 'An unexpected error occurred.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 500)

    return () => {
      cancelled = true
      window.removeEventListener('printDataReady', onReady)
      clearTimeout(fallbackTimer)
    }
  }, [type, lectureId, numChapters])

  return { chapters, assessmentChapters, guideTitle, conceptMaps, loading, globalError }
}

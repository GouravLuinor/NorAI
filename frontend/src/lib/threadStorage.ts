import { useLectureStore } from '../stores/useLectureStore'

// ---------------------------------------------------------------------------
// localStorage keys
// ---------------------------------------------------------------------------

const LABELS_KEY = 'norai-thread-labels'
const COUNTER_KEY = 'norai-thread-counter'
const THREADS_KEY = 'norai-threads'

// One-time migration: move old global keys to default lecture scope
try {
  const oldLabels = localStorage.getItem('norai-thread-labels')
  const oldCounter = localStorage.getItem('norai-thread-counter')
  const oldThreads = localStorage.getItem('norai-threads')

  if (oldLabels) {
    localStorage.setItem('norai-thread-labels-default', oldLabels)
    localStorage.removeItem('norai-thread-labels')
  }
  if (oldCounter) {
    localStorage.setItem('norai-thread-counter-default', oldCounter)
    localStorage.removeItem('norai-thread-counter')
  }
  if (oldThreads) {
    localStorage.setItem('norai-threads-default', oldThreads)
    localStorage.removeItem('norai-threads')
  }
} catch {
  // ignore — migration is best-effort
}

// ---------------------------------------------------------------------------
// lecture-scoped helpers
// ---------------------------------------------------------------------------

export function getLectureId(): string {
  return useLectureStore.getState().activeLectureId || 'default'
}

function getLabels(): Record<string, string> {
  const lectureId = getLectureId()
  try { return JSON.parse(localStorage.getItem(`${LABELS_KEY}-${lectureId}`) || '{}') } catch { return {} }
}

function saveLabels(labels: Record<string, string>) {
  const lectureId = getLectureId()
  localStorage.setItem(`${LABELS_KEY}-${lectureId}`, JSON.stringify(labels))
}

function getNextCounter(): number {
  const lectureId = getLectureId()
  const key = `${COUNTER_KEY}-${lectureId}`
  const next = parseInt(localStorage.getItem(key) || '0', 10) + 1
  localStorage.setItem(key, String(next))
  return next
}

export function getPersistedThreads(): string[] {
  const lectureId = getLectureId()
  try { return JSON.parse(localStorage.getItem(`${THREADS_KEY}-${lectureId}`) || '[]') } catch { return [] }
}

export function persistThreads(threads: string[]) {
  const lectureId = getLectureId()
  localStorage.setItem(`${THREADS_KEY}-${lectureId}`, JSON.stringify(threads))
}

// ---------------------------------------------------------------------------
// Labels
// ---------------------------------------------------------------------------

export function getOrCreateLabel(threadId: string): string {
  const labels = getLabels()
  if (labels[threadId]) return labels[threadId]
  const label = `Thread ${getNextCounter()}`
  labels[threadId] = label
  saveLabels(labels)
  return label
}

export function setThreadLabel(threadId: string, label: string) {
  const labels = getLabels()
  labels[threadId] = label
  saveLabels(labels)
}

export function removeThreadLabel(threadId: string) {
  const labels = getLabels()
  delete labels[threadId]
  saveLabels(labels)
}

export function isDefaultLabel(threadId: string): boolean {
  const labels = getLabels()
  const label = labels[threadId]
  if (!label) return true
  return /^Thread \d+$/i.test(label.trim()) || label.trim().toLowerCase() === 'default'
}

export function generateThreadTitle(question: string): string {
  if (!question || !question.trim()) return 'New Thread'
  let cleaned = question.trim()
  cleaned = cleaned.replace(/^(what is|what are|how to|how do|why is|why does|can you|explain|tell me about|describe)\s+/i, '')
  cleaned = cleaned.replace(/[?.,!:]+$/, '').trim()
  if (!cleaned) cleaned = question.trim().replace(/[?.,!:]+$/, '')

  const words = cleaned.split(/\s+/).filter(Boolean)
  if (words.length === 0) return 'New Thread'

  const titleWords = words.slice(0, 6).map((w) => {
    if (w === w.toUpperCase() && w.length > 1) return w
    return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()
  })

  let title = titleWords.join(' ')
  if (title.length > 38) {
    title = title.slice(0, 35) + '...'
  }
  return title
}

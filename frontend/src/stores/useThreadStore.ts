/**
 * useThreadStore.ts — v3
 *
 * Root causes fixed this revision:
 *
 * RC-A  setThreadId() was calling loadThreadMessages() internally.
 *       React Strict Mode double-invokes effects, so Sidebar's useEffect fired
 *       loadThreads() twice → two concurrent responses each calling setThreadId
 *       for every persisted thread → N×2 simultaneous GET /threads/{id} requests.
 *       Fix: setThreadId is now a pure state mutation. The caller (Sidebar) is
 *       responsible for triggering loadThreadMessages exactly once.
 *
 * RC-B  loadThreadMessages() had no AbortController, so two in-flight requests
 *       for the same threadId would both write their responses to state. The
 *       slower one always won, duplicating or overwriting messages.
 *       Fix: a module-level AbortController (_loadAbortController) is replaced
 *       on every loadThreadMessages call, cancelling the previous in-flight
 *       request. A generation counter (_loadGeneration) additionally guards
 *       against any response that escaped the abort.
 *
 * RC-C  Initial threadId was seeded as getPersistedThreads()[0] (oldest thread).
 *       Fix: seed from the LAST element (most recent thread).
 *
 * RC-D  On thread switch, messages flashed to [] before the cached version was
 *       shown. Fix: messagesCache stores the last-known messages per threadId
 *       and restores them instantly on switch, before the fetch completes.
 */

import { create } from 'zustand'
import { useQuizStore } from './useQuizStore'
import { useLectureStore } from './useLectureStore'
// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// API_BASE is intentionally NOT used inside apiFetch — all internal store
// calls use bare relative paths so the Vite dev proxy routes them correctly.
// It IS used in the exported sendChatMessage helpers for production builds.
export const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || ''

const LABELS_KEY  = 'norai-thread-labels'
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
} catch (e) {
  // ignore — migration is best-effort
}

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------



// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

function getLabels(): Record<string, string> {
  const lectureId = useLectureStore.getState().activeLectureId || 'default'
  try { return JSON.parse(localStorage.getItem(`${LABELS_KEY}-${lectureId}`) || '{}') } catch { return {} }
}
function getLectureId(): string {
  return useLectureStore.getState().activeLectureId || 'default'
}
function saveLabels(labels: Record<string, string>) {
  const lectureId = useLectureStore.getState().activeLectureId || 'default'
  localStorage.setItem(`${LABELS_KEY}-${lectureId}`, JSON.stringify(labels))
}
function getNextCounter(): number {
  const lectureId = useLectureStore.getState().activeLectureId || 'default'
  const key = `${COUNTER_KEY}-${lectureId}`
  const next = parseInt(localStorage.getItem(key) || '0', 10) + 1
  localStorage.setItem(key, String(next))
  return next
}
function getPersistedThreads(): string[] {
  const lectureId = useLectureStore.getState().activeLectureId || 'default'
  try { return JSON.parse(localStorage.getItem(`${THREADS_KEY}-${lectureId}`) || '[]') } catch { return [] }
}
function persistThreads(threads: string[]) {
  const lectureId = useLectureStore.getState().activeLectureId || 'default'
  localStorage.setItem(`${THREADS_KEY}-${lectureId}`, JSON.stringify(threads))
}

export function getOrCreateLabel(threadId: string): string {
  const labels = getLabels()
  if (labels[threadId]) return labels[threadId]
  const label = `Thread ${getNextCounter()}`
  labels[threadId] = label
  saveLabels(labels)
  return label
}

// ---------------------------------------------------------------------------
// apiFetch — bare relative paths only, Vite proxy handles routing
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(path, options)
    const ct = res.headers.get('content-type') || ''
    if (!ct.includes('application/json')) {
      console.warn(`apiFetch: non-JSON response for ${path} (${res.status})`)
      return null
    }
    if (!res.ok) {
      console.error(`apiFetch ${path} ${res.status}:`, await res.json().catch(() => ({})))
      return null
    }
    return res.json() as Promise<T>
  } catch (err: any) {
    if (err?.name !== 'AbortError') console.error(`apiFetch error for ${path}:`, err)
    return null
  }
}

// ---------------------------------------------------------------------------
// In-flight request cancellation (RC-B)
// Only ONE loadThreadMessages request is allowed to be in-flight at a time.
// Starting a new one aborts the previous regardless of threadId.
// ---------------------------------------------------------------------------

let _loadAbortController: AbortController | null = null
let _loadGeneration = 0   // incremented on every call; stale responses are dropped
let _loadThreadsInFlight = false
// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface ThreadState {
  threadId: string
  threads: string[]
  messages: Message[]
  isLoading: boolean

  // RC-D: cache so switching back to a thread shows messages instantly
  _messagesCache: Record<string, Message[]>
  liveReferences: any[]
  setLiveReferences: (refs: any[]) => void
  setThreadId: (id: string) => void
  addMessage: (msg: Message) => void
  setMessages: (msgs: Message[]) => void
  setLoading: (loading: boolean) => void
  streamingText: string
  setStreamingText: (text: string) => void
  setThreads: (threads: string[]) => void

  loadThreads: () => Promise<void>
  loadThreadMessages: (threadId: string) => Promise<void>
  createThread: () => Promise<string>
  deleteThread: (threadId: string) => Promise<void>
  getThreadLabel: (threadId: string) => string
}

const genId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

// ---------------------------------------------------------------------------
// Initial seed
// ---------------------------------------------------------------------------

const _seedThreads = getPersistedThreads()
// RC-C: use the LAST (most recent) thread as the active one
const _seedThreadId = _seedThreads.length > 0
  ? _seedThreads[_seedThreads.length - 1]
  : 'default'

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useThreadStore = create<ThreadState>((set, get) => ({
  threadId: _seedThreadId,
  threads:  _seedThreads.length > 0 ? _seedThreads : ['default'],
  messages: [],
  isLoading: false,
  streamingText: '',
  _messagesCache: {},
  liveReferences: [],
  // -------------------------------------------------------------------------
  // RC-A: setThreadId is now a PURE STATE MUTATION.
  // It does NOT call loadThreadMessages — the caller does that explicitly.
  // This breaks the Strict Mode double-invoke cascade entirely.
  // -------------------------------------------------------------------------
  setThreadId: (id) => {
    useQuizStore.getState().reset()

    // Cancel any in-flight message load immediately (RC-B)
    _loadAbortController?.abort()

    const cached = get()._messagesCache[id] ?? []
    // RC-D: restore cached messages instantly (no flash to empty state)
    set({ threadId: id, messages: cached, isLoading: cached.length === 0 })
  },

  addMessage: (msg) =>
    set((s) => {
      const messages = [...s.messages, msg]
      return {
        messages,
        _messagesCache: { ...s._messagesCache, [s.threadId]: messages },
      }
    }),

  setMessages: (msgs) =>
    set((s) => {
      // Deduplicate by content — never add the same message twice
      const existingContents = new Set(s.messages.map(m => m.content))
      const unique = msgs.filter(m => !existingContents.has(m.content))
      const all = [...s.messages, ...unique]
      return {
        messages: all,
        _messagesCache: { ...s._messagesCache, [s.threadId]: all },
      }
    }),

  setLoading: (loading) => set({ isLoading: loading }),
  setLiveReferences: (refs) => set({ liveReferences: refs }),   // ← add this line
  setStreamingText: (text) => set({ streamingText: text }),

  setThreads: (threads) => {
    persistThreads(threads)
    set({ threads })
  },

  // -------------------------------------------------------------------------
  // loadThreads — fetches the sidebar list only; never loads any messages.
  // Falls back to localStorage if the backend is unreachable.
  // -------------------------------------------------------------------------


loadThreads: async () => {
    if (_loadThreadsInFlight) return
    _loadThreadsInFlight = true
    
    try {
      console.log('🔍 lecture_id being sent:', getLectureId())
      const data = await apiFetch<{ threads: string[] }>(`/threads?lecture_id=${getLectureId()}`)

      let threads: string[] = data?.threads ?? []

      console.log('🔍 loadThreads called. Backend returned:', threads)

      if (threads.length === 0) {
        const local = getPersistedThreads()
        console.log('🔍 localStorage fallback:', local)
        threads = local.length > 0 ? local : ['default']
      }

      console.log('🔍 Final threads to set:', threads)
      // ... rest unchanged

        threads.forEach((id) => getOrCreateLabel(id))
        persistThreads(threads)
        set({ threads })
      } finally {
        _loadThreadsInFlight = false
      }
    },

  // -------------------------------------------------------------------------
  // RC-B: AbortController + generation counter.
  // Every call cancels the previous one. Even if abort races, the generation
  // check ensures the stale response is silently dropped.
  // -------------------------------------------------------------------------
  loadThreadMessages: async (threadId) => {
    // Cancel previous in-flight request
    _loadAbortController?.abort()
    const controller = new AbortController()
    _loadAbortController = controller

    // Capture generation BEFORE any await
    const gen = ++_loadGeneration

    set({ isLoading: true })

    const data = await apiFetch<{ messages: { role: string; content: string }[] }>(
      `/threads/${threadId}?lecture_id=${getLectureId()}`,
      { signal: controller.signal },
    )

    // Drop stale responses (RC-B): either a newer call started, or we were aborted
    if (gen !== _loadGeneration || controller.signal.aborted) return
    // Drop if user switched away while fetching
    if (get().threadId !== threadId) return

    const msgs: Message[] = (data?.messages ?? []).map((m) => ({
      id: genId(),
      role: m.role as 'user' | 'assistant',
      content: m.content,
      timestamp: '',
    }))

    set((s) => ({
      messages: msgs,
      isLoading: false,
      _messagesCache: { ...s._messagesCache, [threadId]: msgs },
    }))
  },

  // -------------------------------------------------------------------------
  // createThread — optimistic-first, persist-first
  // -------------------------------------------------------------------------
  createThread: async () => {
    const threadId = `thread-${Date.now()}`

    getOrCreateLabel(threadId)
    const next = [...get().threads, threadId]
    persistThreads(next)

    useQuizStore.getState().reset()
    // RC-A: don't call loadThreadMessages here — new thread has no messages
    set({ threads: next, threadId, messages: [], isLoading: false })

    apiFetch(`/threads?lecture_id=${getLectureId()}`, { method: 'POST' }).catch(() => {})

    return threadId
  },

  // -------------------------------------------------------------------------
  // deleteThread — optimistic-first
  // -------------------------------------------------------------------------
  deleteThread: async (threadId) => {
    const { threads, threadId: currentId, _messagesCache } = get()
    const remaining = threads.filter((t) => t !== threadId)
    const nextId = remaining.length > 0 ? remaining[remaining.length - 1] : 'default'

    const labels = getLabels()
    delete labels[threadId]
    saveLabels(labels)

    // Remove from cache
    const newCache = { ..._messagesCache }
    delete newCache[threadId]

    persistThreads(remaining)

    if (currentId === threadId) {
      useQuizStore.getState().reset()
      const cached = newCache[nextId] ?? []
      set({
        threads: remaining,
        threadId: nextId,
        messages: cached,
        isLoading: false,
        _messagesCache: newCache,
      })
      // Load fresh messages for the thread we're switching to
      if (nextId !== 'default') get().loadThreadMessages(nextId)
    } else {
      set({ threads: remaining, _messagesCache: newCache })
    }

    apiFetch(`/threads/${threadId}?lecture_id=${getLectureId()}`, { method: 'DELETE' }).catch(() => {})
  },

  getThreadLabel: (id) => getOrCreateLabel(id),
}))

// ---------------------------------------------------------------------------
// Exported API helpers (use API_BASE for production; proxy handles dev)
// ---------------------------------------------------------------------------

export async function sendChatMessage(
  threadId: string,
  userQuestion: string,
  lectureTitle = '',
  opts?: { lectureId?: string },
): Promise<{ answer: string; retrieved_chunks: any[]; retrieved_images: any[] }> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      user_question: userQuestion,
      lecture_title: lectureTitle,
      lecture_id: opts?.lectureId || 'default',
    }),
  })
  const ct = res.headers.get('content-type') || ''
  if (!ct.includes('application/json'))
    throw new Error(`Unexpected response type: ${ct} (status ${res.status})`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as any).detail || `Chat request failed: ${res.status}`)
  }
  return res.json()
}

export async function* sendChatMessageStream(
  threadId: string,
  userQuestion: string,
  lectureTitle = '',
  signal?: AbortSignal,
): AsyncGenerator<string | { type: 'final'; data: any }> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      user_question: userQuestion,
      lecture_title: lectureTitle,
      lecture_id: useLectureStore.getState().activeLectureId || 'default',
    }),
    signal,
  })
  if (!res.ok) throw new Error('Chat stream failed')

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const payload = line.slice(6)
      if (payload === '[DONE]') return
      if (payload.startsWith('[ERROR]')) throw new Error(payload.slice(8))
      try { yield { type: 'final', data: JSON.parse(payload) } }
      catch { yield payload }
    }
  }
}
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

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

function getLabels(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem(LABELS_KEY) || '{}') } catch { return {} }
}
function saveLabels(labels: Record<string, string>) {
  localStorage.setItem(LABELS_KEY, JSON.stringify(labels))
}
function getNextCounter(): number {
  const next = parseInt(localStorage.getItem(COUNTER_KEY) || '0', 10) + 1
  localStorage.setItem(COUNTER_KEY, String(next))
  return next
}
function getPersistedThreads(): string[] {
  try { return JSON.parse(localStorage.getItem(THREADS_KEY) || '[]') } catch { return [] }
}
function persistThreads(threads: string[]) {
  localStorage.setItem(THREADS_KEY, JSON.stringify(threads))
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

  setThreadId: (id: string) => void
  addMessage: (msg: Message) => void
  setMessages: (msgs: Message[]) => void
  setLoading: (loading: boolean) => void
  setThreads: (threads: string[]) => void

  loadThreads: () => Promise<void>
  loadThreadMessages: (threadId: string) => Promise<void>
  createThread: () => Promise<string>
  deleteThread: (threadId: string) => Promise<void>
  getThreadLabel: (threadId: string) => string
}

let _msgIdCounter = 0
const genId = () => `msg-${++_msgIdCounter}`

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
  _messagesCache: {},

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
    set((s) => ({
      messages: msgs,
      _messagesCache: { ...s._messagesCache, [s.threadId]: msgs },
    })),

  setLoading: (loading) => set({ isLoading: loading }),

  setThreads: (threads) => {
    persistThreads(threads)
    set({ threads })
  },

  // -------------------------------------------------------------------------
  // loadThreads — fetches the sidebar list only; never loads any messages.
  // Falls back to localStorage if the backend is unreachable.
  // -------------------------------------------------------------------------
  loadThreads: async () => {
    const data = await apiFetch<{ threads: string[] }>('/threads')
    let threads: string[] = data?.threads ?? []

    if (threads.length === 0) {
      const local = getPersistedThreads()
      threads = local.length > 0 ? local : ['default']
    }

    threads.forEach((id) => getOrCreateLabel(id))
    persistThreads(threads)
    set({ threads })
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
      `/threads/${threadId}`,
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

    apiFetch(`/threads?id=${threadId}`, { method: 'POST' }).catch(() => {})

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

    apiFetch(`/threads/${threadId}`, { method: 'DELETE' }).catch(() => {})
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
): Promise<{ answer: string; retrieved_chunks: any[]; retrieved_images: any[] }> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      user_question: userQuestion,
      lecture_title: lectureTitle,
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
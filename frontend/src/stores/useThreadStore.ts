/**
 * useThreadStore.ts — v4
 *
 * v4: decomposed. localStorage/label helpers live in `src/lib/threadStorage.ts`
 * and the API layer (apiFetch, sendChatMessage, sendChatMessageStream) lives in
 * `src/lib/chatApi.ts`. This file is now store-only, re-exporting the helpers
 * for backward compatibility with existing imports.
 *
 * v3 root causes (kept):
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
import { apiFetch, sendChatMessage, sendChatMessageStream } from '../lib/chatApi'
import { buildReferences } from '../lib/references'
import {
  getLectureId,
  getPersistedThreads,
  getOrCreateLabel,
  getLabels,
  setThreadLabel as setThreadLabelStorage,
  persistThreads,
  removeThreadLabel,
} from '../lib/threadStorage'
import type { Reference, RetrievedChunk, RetrievedImage, ChatResponse } from '../types'

// Re-export the API layer + label helpers so existing call sites keep working.
export { sendChatMessage, sendChatMessageStream, getOrCreateLabel }

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
  labels: Record<string, string>
  messages: Message[]
  isLoading: boolean

  // RC-D: cache so switching back to a thread shows messages instantly
  _messagesCache: Record<string, Message[]>
  liveReferences: Reference[]
  setLiveReferences: (refs: Reference[]) => void
  setThreadId: (id: string) => void
  addMessage: (msg: Message) => void
  setMessages: (msgs: Message[]) => void
  setLoading: (loading: boolean) => void
  streamingText: string
  setStreamingText: (text: string) => void
  setThreads: (threads: string[]) => void
  setThreadLabel: (id: string, label: string) => void

  loadThreads: () => Promise<void>
  loadThreadMessages: (threadId: string) => Promise<void>
  createThread: () => Promise<string>
  deleteThread: (threadId: string) => Promise<void>
  getThreadLabel: (threadId: string) => string
  resetForLectureChange: () => void
}

const genId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useThreadStore = create<ThreadState>((set, get) => ({
  threadId: 'default',
  threads:  ['default'],
  labels: {},
  messages: [],
  isLoading: false,
  streamingText: '',
  _messagesCache: {},
  liveReferences: [],

  resetForLectureChange: () => {
    _loadAbortController?.abort()
    _loadGeneration++
    useQuizStore.getState().reset()
    set({
      threadId: 'default',
      threads: ['default'],
      labels: getLabels(),
      messages: [],
      liveReferences: [],
      streamingText: '',
      isLoading: false,
      _messagesCache: {},
    })
  },
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
    // Fix: clear liveReferences so sources from previous thread don't persist,
    // and clear streamingText so no stale streaming bubble follows the switch.
    set({ threadId: id, messages: cached, isLoading: cached.length === 0, liveReferences: [], streamingText: '' })
  },

  addMessage: (msg) =>
    set((s) => {
      const messages = [...s.messages, msg]
      return {
        messages,
        _messagesCache: { ...s._messagesCache, [s.threadId]: messages },
      }
    }),

  // RC-FIX: setMessages is a full REPLACEMENT, not an append.
  // The only caller is loadThreadMessages which already has the complete list.
  // Append-with-dedup was causing duplicates when backend data overlapped
  // with optimistically-inserted messages.
  setMessages: (msgs) =>
    set((s) => ({
      messages: msgs,
      _messagesCache: { ...s._messagesCache, [s.threadId]: msgs },
    })),

  setLoading: (loading) => set({ isLoading: loading }),
  setLiveReferences: (refs) => set({ liveReferences: refs }),
  setStreamingText: (text) => set({ streamingText: text }),

  setThreads: (threads) => {
    persistThreads(threads)
    set({ threads })
  },

  setThreadLabel: (id, label) => {
    setThreadLabelStorage(id, label)
    set((s) => ({
      labels: { ...s.labels, [id]: label },
    }))
  },

  // -------------------------------------------------------------------------
  // loadThreads — fetches the sidebar list only; never loads any messages.
  // Falls back to localStorage if the backend is unreachable.
  // -------------------------------------------------------------------------

  loadThreads: async () => {
    if (_loadThreadsInFlight) return
    _loadThreadsInFlight = true

    try {
      const lectureId = getLectureId()
      const data = await apiFetch<{ threads: string[] }>(`/threads?lecture_id=${lectureId}`)

      const backendThreads = data?.threads ?? []
      const localThreads = getPersistedThreads()

      // Merge backend threads with local threads (maintaining uniqueness, preserving default first if present)
      const threadSet = new Set<string>()
      const merged: string[] = []

      // If 'default' exists in either backend or local, place it first
      if (backendThreads.includes('default') || localThreads.includes('default')) {
        threadSet.add('default')
        merged.push('default')
      }

      for (const t of backendThreads) {
        if (!threadSet.has(t)) {
          threadSet.add(t)
          merged.push(t)
        }
      }

      for (const t of localThreads) {
        if (!threadSet.has(t)) {
          threadSet.add(t)
          merged.push(t)
        }
      }

      if (merged.length === 0) {
        merged.push('default')
      }

      merged.forEach((id) => getOrCreateLabel(id))
      persistThreads(merged)

      // Set the active thread to the most recent one if current is stale
      const current = get().threadId
      const threadId = merged.includes(current)
        ? current
        : merged[merged.length - 1] || 'default'

      set({
        threads: merged,
        threadId,
        labels: getLabels(),
      })
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

    const data = await apiFetch<{
      messages: Array<{ id: string; role: string; content: string }>
      last_retrieved_chunks?: RetrievedChunk[]
      last_retrieved_images?: RetrievedImage[]
      verified_citations?: import('../types').VerifiedCitation[]
    }>(
      `/threads/${threadId}?lecture_id=${getLectureId()}`,
      { signal: controller.signal },
    )

    // Drop stale responses (RC-B): either a newer call started, or we were aborted
    if (gen !== _loadGeneration || controller.signal.aborted) return
    // Drop if user switched away while fetching
    if (get().threadId !== threadId) return

    const msgs: Message[] = (data?.messages ?? []).map((m) => ({
      id: m.id || genId(),
      role: m.role as 'user' | 'assistant',
      content: m.content,
      timestamp: '',
    }))

    const lastAssistant = [...msgs].reverse().find((m) => m.role === 'assistant')
    const answerText = lastAssistant?.content || ''

    set((s) => {
      // Phase 4: Cache resilience - merge incoming messages with optimistic UI messages
      const existing = s._messagesCache[threadId] || []
      const merged = [...msgs]
      const backendContents = new Set(merged.map((m) => `${m.role}:${m.content.trim()}`))
      const backendIds = new Set(merged.map((m) => m.id))

      for (const msg of existing) {
        if (!backendIds.has(msg.id) && !backendContents.has(`${msg.role}:${msg.content.trim()}`)) {
          merged.push(msg)
        }
      }

      const isCurrentThread = s.threadId === threadId

      let refs = s.liveReferences
      if (isCurrentThread) {
        refs = buildReferences(
          data?.last_retrieved_chunks ?? [],
          data?.last_retrieved_images ?? [],
          answerText,
          data?.verified_citations ?? []
        )
      }

      return {
        messages: isCurrentThread ? merged : s.messages,
        liveReferences: refs,
        isLoading: false,
        _messagesCache: { ...s._messagesCache, [threadId]: merged },
      }
    })
  },

  // -------------------------------------------------------------------------
  // createThread — optimistic-first, persist-first
  // -------------------------------------------------------------------------
  createThread: async () => {
    const threadId = `thread-${Date.now()}`

    const label = getOrCreateLabel(threadId)
    const next = [...get().threads, threadId]
    persistThreads(next)

    useQuizStore.getState().reset()
    // RC-A: don't call loadThreadMessages here — new thread has no messages
    set({
      threads: next,
      threadId,
      messages: [],
      isLoading: false,
      labels: { ...get().labels, [threadId]: label },
    })

    apiFetch(`/threads?lecture_id=${getLectureId()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: threadId })
    }).catch(() => {})

    return threadId
  },

  // -------------------------------------------------------------------------
  // deleteThread — optimistic-first
  // -------------------------------------------------------------------------
  deleteThread: async (threadId) => {
    const { threads, threadId: currentId, _messagesCache, labels } = get()
    const remaining = threads.filter((t) => t !== threadId)
    const nextId = remaining.length > 0 ? remaining[remaining.length - 1] : 'default'

    // Remove label
    removeThreadLabel(threadId)
    const nextLabels = { ...labels }
    delete nextLabels[threadId]

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
        labels: nextLabels,
      })
      // Load fresh messages for the thread we're switching to
      if (nextId) get().loadThreadMessages(nextId)
    } else {
      set({ threads: remaining, _messagesCache: newCache, labels: nextLabels })
    }

    apiFetch(`/threads/${threadId}?lecture_id=${getLectureId()}`, { method: 'DELETE' }).catch(() => {})
  },

  getThreadLabel: (id) => get().labels[id] || getOrCreateLabel(id),
}))

export type { ChatResponse }

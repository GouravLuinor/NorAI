/**
 * useThreadStore.ts — v5
 *
 * localStorage/label helpers live in `src/lib/threadStorage.ts`; the HTTP layer
 * lives in `src/lib/chatApi.ts`. This file owns thread state AND the single
 * send pipeline (`sendMessage`) every chat entry point goes through.
 *
 * v5 root causes of duplicated / glitching messages (fixed here):
 *
 * RC-1  Three independent senders (ChatArea, ConceptMapView, HighlightAsk)
 *       each had their own in-flight guard, so turns could overlap; HighlightAsk
 *       wrote its reply into whichever thread was active when the response
 *       landed, and ConceptMapView added the user message twice.
 *       Fix: one `sendMessage` with a store-wide guard (`sendingThreadId`)
 *       that always writes to the thread the turn was sent from.
 *
 * RC-2  Reconciliation compared message *content*: the history merge
 *       re-appended any cached message the server list lacked (out of order,
 *       duplicated after summarisation), and the assistant append dropped
 *       legitimately identical replies. Message ids are deterministic end to
 *       end (user = client id, assistant = "ai-" + client id), so everything
 *       reconciles by id; only this client's unconfirmed turns (status
 *       pending/error) survive a history reload.
 *
 * RC-3  `isLoading` meant both "history loading" and "answer streaming"; a
 *       history load finishing mid-stream hid the typing indicator, and the
 *       global `streamingText` bubble followed the user into other threads.
 *       Fix: `isLoading` is history only; `sendingThreadId` scopes the
 *       in-flight turn and its streaming text to one thread.
 *
 * RC-4  `loadThreads` silently dropped calls made while one was in flight, so
 *       the reload after sign-in could be skipped (stale thread list).
 *       Fix: generation counter — the latest call wins.
 *
 * Kept from v3: setThreadId is a pure state mutation (callers load messages
 * explicitly), loadThreadMessages aborts the previous request and drops stale
 * responses, and a per-thread cache restores messages instantly on switch.
 */

import { create } from 'zustand'
import { useQuizStore } from './useQuizStore'
import { useLectureStore } from './useLectureStore'
import { apiFetch, sendChatMessage, sendChatMessageStream } from '../lib/chatApi'
import { buildReferences, stripSources } from '../lib/references'
import { genId } from '../lib/id'
import { friendlyError } from '../lib/errorCopy'
import {
  getLectureId,
  getPersistedThreads,
  getOrCreateLabel,
  getLabels,
  setThreadLabel as setThreadLabelStorage,
  persistThreads,
  removeThreadLabel,
} from '../lib/threadStorage'
import type { Reference, RetrievedChunk, RetrievedImage, ChatResponse, VerifiedCitation } from '../types'

// Re-export the API layer + label helpers so existing call sites keep working.
export { sendChatMessage, sendChatMessageStream, getOrCreateLabel }

let _loadAbortController: AbortController | null = null
let _loadGeneration = 0        // stale loadThreadMessages responses are dropped
let _threadsGeneration = 0     // stale loadThreads responses are dropped
let _sendAbortController: AbortController | null = null

const STREAM_FLUSH_MS = 100

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  /** Local-only turn state; absent once the server has confirmed the turn. */
  status?: 'pending' | 'error'
}

export interface SendOptions {
  studyMode?: string
  persona?: string
  /** Fallback text when the reply streams back empty. */
  emptyAnswerFallback?: string
  /** Text used to resolve citations (defaults to the cleaned answer). */
  referenceAnswer?: (cleanAnswer: string) => string
  /** Re-send a failed turn under its original message id (idempotent server-side). */
  retryOf?: string
}

export interface SendResult {
  threadId: string
  references: Reference[]
}

interface ThreadState {
  threadId: string
  threads: string[]
  labels: Record<string, string>
  messages: Message[]
  /** History is being fetched for the active thread. */
  isLoading: boolean
  /** Thread whose turn is in flight (at most one at a time), else null. */
  sendingThreadId: string | null
  /** Partial reply of the in-flight turn; belongs to `sendingThreadId`. */
  streamingText: string

  _messagesCache: Record<string, Message[]>
  liveReferences: Reference[]
  setLiveReferences: (refs: Reference[]) => void
  setThreadId: (id: string) => void
  addMessage: (msg: Message) => void
  setMessages: (msgs: Message[]) => void
  setThreads: (threads: string[]) => void
  setThreadLabel: (id: string, label: string) => void

  sendMessage: (text: string, opts?: SendOptions) => Promise<SendResult | null>
  retryMessage: (userMessageId: string, opts?: SendOptions) => Promise<SendResult | null>
  abortSend: () => void

  loadThreads: () => Promise<void>
  loadThreadMessages: (threadId: string) => Promise<void>
  createThread: () => Promise<string>
  deleteThread: (threadId: string) => Promise<void>
  getThreadLabel: (threadId: string) => string
  resetForLectureChange: () => void
}

export const chatTimestamp = () =>
  new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

/** The user-message id a message belongs to ("ai-x" / "err-x" -> "x"). */
const turnIdOf = (id: string) => id.replace(/^(ai-|err-)/, '')

/**
 * Server history is the source of truth. Local messages survive only while
 * their turn is unconfirmed (pending / failed) and the server hasn't got it.
 */
export function reconcileMessages(server: Message[], local: Message[]): Message[] {
  const serverTurns = new Set(server.map((m) => turnIdOf(m.id)))
  const unconfirmed = local.filter((m) => m.status && !serverTurns.has(turnIdOf(m.id)))
  return [...server, ...unconfirmed]
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useThreadStore = create<ThreadState>((set, get) => {
  /** Apply `fn` to one thread's messages (cache + visible list if active). */
  const updateThread = (threadId: string, fn: (msgs: Message[]) => Message[]) =>
    set((s) => {
      const current = s.threadId === threadId ? s.messages : (s._messagesCache[threadId] ?? [])
      const next = fn(current)
      return {
        _messagesCache: { ...s._messagesCache, [threadId]: next },
        ...(s.threadId === threadId ? { messages: next } : {}),
      }
    })

  /** Insert or replace by id — the same message can never appear twice. */
  const upsert = (threadId: string, msg: Message) =>
    updateThread(threadId, (msgs) =>
      msgs.some((m) => m.id === msg.id) ? msgs.map((m) => (m.id === msg.id ? msg : m)) : [...msgs, msg],
    )

  const runTurn = async (
    targetThreadId: string,
    userMsg: Message,
    opts: SendOptions,
  ): Promise<SendResult | null> => {
    const controller = new AbortController()
    _sendAbortController = controller
    set({ sendingThreadId: targetThreadId, streamingText: '' })

    let acc = ''
    let pendingFlush: number | null = null
    const flush = () => {
      if (pendingFlush !== null) {
        window.clearTimeout(pendingFlush)
        pendingFlush = null
      }
      if (get().sendingThreadId === targetThreadId) set({ streamingText: stripSources(acc) })
    }

    try {
      const currentLectureId = getLectureId()
      const lectureTitle =
        useLectureStore.getState().lectures.find((l) => l.lecture_id === currentLectureId)?.title ?? ''

      let final: ChatResponse | null = null
      for await (const chunk of sendChatMessageStream(
        targetThreadId,
        userMsg.content,
        lectureTitle,
        controller.signal,
        { messageId: userMsg.id, studyMode: opts.studyMode, persona: opts.persona },
      )) {
        if (typeof chunk === 'string') {
          acc += chunk
          if (pendingFlush === null) pendingFlush = window.setTimeout(flush, STREAM_FLUSH_MS)
          continue
        }
        final = chunk.data
      }
      if (!final) throw new Error('The answer was interrupted. Please retry.')

      const cleanAnswer = stripSources(acc) || opts.emptyAnswerFallback || ''
      upsert(targetThreadId, { ...userMsg, status: undefined })
      upsert(targetThreadId, {
        id: final.assistant_message_id || `ai-${userMsg.id}`,
        role: 'assistant',
        content: cleanAnswer,
        timestamp: chatTimestamp(),
      })

      const references = buildReferences(
        final.retrieved_chunks ?? [],
        final.retrieved_images ?? [],
        opts.referenceAnswer ? opts.referenceAnswer(cleanAnswer) : cleanAnswer,
        final.verified_citations ?? [],
      )
      if (get().threadId === targetThreadId) set({ liveReferences: references })
      return { threadId: targetThreadId, references }
    } catch (err: unknown) {
      // Aborted by a lecture switch / reset: the thread state is gone anyway.
      if (controller.signal.aborted) return null
      upsert(targetThreadId, { ...userMsg, status: 'error' })
      upsert(targetThreadId, {
        id: `err-${userMsg.id}`,
        role: 'assistant',
        content: friendlyError(err),
        timestamp: chatTimestamp(),
        status: 'error',
      })
      throw err
    } finally {
      if (pendingFlush !== null) window.clearTimeout(pendingFlush)
      if (_sendAbortController === controller) _sendAbortController = null
      if (get().sendingThreadId === targetThreadId) set({ sendingThreadId: null, streamingText: '' })
    }
  }

  return {
    threadId: 'default',
    threads: ['default'],
    labels: {},
    messages: [],
    isLoading: false,
    sendingThreadId: null,
    streamingText: '',
    _messagesCache: {},
    liveReferences: [],

    resetForLectureChange: () => {
      _loadAbortController?.abort()
      _sendAbortController?.abort()
      _loadGeneration++
      _threadsGeneration++
      useQuizStore.getState().reset()
      set({
        threadId: 'default',
        threads: ['default'],
        labels: getLabels(),
        messages: [],
        liveReferences: [],
        streamingText: '',
        sendingThreadId: null,
        isLoading: false,
        _messagesCache: {},
      })
    },

    // Pure state mutation — callers trigger loadThreadMessages explicitly.
    setThreadId: (id) => {
      useQuizStore.getState().reset()
      _loadAbortController?.abort()
      const cached = get()._messagesCache[id] ?? []
      set({ threadId: id, messages: cached, isLoading: cached.length === 0, liveReferences: [] })
    },

    addMessage: (msg) => upsert(get().threadId, msg),

    setMessages: (msgs) =>
      set((s) => ({
        messages: msgs,
        _messagesCache: { ...s._messagesCache, [s.threadId]: msgs },
      })),

    setLiveReferences: (refs) => set({ liveReferences: refs }),

    setThreads: (threads) => {
      persistThreads(threads)
      set({ threads })
    },

    setThreadLabel: (id, label) => {
      setThreadLabelStorage(id, label)
      set((s) => ({ labels: { ...s.labels, [id]: label } }))
    },

    // -----------------------------------------------------------------------
    // sendMessage — the ONLY way a chat turn is started.
    // -----------------------------------------------------------------------
    sendMessage: async (text, opts = {}) => {
      const content = text.trim()
      // One turn at a time: the backend serialises turns per lecture anyway,
      // and overlapping client turns are what interleaved/duplicated replies.
      if (!content || get().sendingThreadId) return null
      const targetThreadId = get().threadId || 'default'
      const userMsg: Message = {
        id: genId(),
        role: 'user',
        content,
        timestamp: chatTimestamp(),
        status: 'pending',
      }
      upsert(targetThreadId, userMsg)
      return runTurn(targetThreadId, userMsg, opts)
    },

    retryMessage: async (userMessageId, opts = {}) => {
      if (get().sendingThreadId) return null
      const targetThreadId = get().threadId
      const original = get().messages.find((m) => m.id === userMessageId && m.role === 'user')
      if (!original) return null
      const userMsg: Message = { ...original, status: 'pending' }
      updateThread(targetThreadId, (msgs) =>
        msgs.filter((m) => m.id !== `err-${userMessageId}`).map((m) => (m.id === userMessageId ? userMsg : m)),
      )
      return runTurn(targetThreadId, userMsg, opts)
    },

    abortSend: () => _sendAbortController?.abort(),

    // -----------------------------------------------------------------------
    // loadThreads — sidebar list only; the latest call wins (RC-4).
    // -----------------------------------------------------------------------
    loadThreads: async () => {
      const gen = ++_threadsGeneration
      const lectureId = getLectureId()
      const data = await apiFetch<{ threads: string[] }>(`/threads?lecture_id=${lectureId}`)
      if (gen !== _threadsGeneration) return

      const backendThreads = data?.threads ?? []
      const localThreads = getPersistedThreads()

      // Union of backend + locally created threads, "default" first.
      const merged: string[] = []
      if (backendThreads.includes('default') || localThreads.includes('default')) merged.push('default')
      for (const t of [...backendThreads, ...localThreads]) {
        if (!merged.includes(t)) merged.push(t)
      }
      if (merged.length === 0) merged.push('default')

      merged.forEach((id) => getOrCreateLabel(id))
      persistThreads(merged)

      const current = get().threadId
      const threadId = merged.includes(current) ? current : merged[merged.length - 1] || 'default'
      set({ threads: merged, threadId, labels: getLabels() })
    },

    // -----------------------------------------------------------------------
    // loadThreadMessages — abort previous request; reconcile by id (RC-2).
    // -----------------------------------------------------------------------
    loadThreadMessages: async (threadId) => {
      _loadAbortController?.abort()
      const controller = new AbortController()
      _loadAbortController = controller
      const gen = ++_loadGeneration

      if (get().threadId === threadId) set({ isLoading: true })

      const data = await apiFetch<{
        messages: Array<{ id: string; role: string; content: string }>
        last_retrieved_chunks?: RetrievedChunk[]
        last_retrieved_images?: RetrievedImage[]
        verified_citations?: VerifiedCitation[]
      }>(`/threads/${threadId}?lecture_id=${getLectureId()}`, { signal: controller.signal })

      if (gen !== _loadGeneration || controller.signal.aborted) return

      const server: Message[] = (data?.messages ?? []).map((m) => ({
        id: m.id || genId(),
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content,
        timestamp: '',
      }))
      const lastAssistant = [...server].reverse().find((m) => m.role === 'assistant')

      set((s) => {
        const local = s.threadId === threadId ? s.messages : (s._messagesCache[threadId] ?? [])
        const merged = reconcileMessages(server, local)
        const isCurrent = s.threadId === threadId
        return {
          _messagesCache: { ...s._messagesCache, [threadId]: merged },
          ...(isCurrent
            ? {
                messages: merged,
                isLoading: false,
                liveReferences: buildReferences(
                  data?.last_retrieved_chunks ?? [],
                  data?.last_retrieved_images ?? [],
                  lastAssistant?.content || '',
                  data?.verified_citations ?? [],
                ),
              }
            : {}),
        }
      })
    },

    createThread: async () => {
      const threadId = `thread-${Date.now()}`
      const label = getOrCreateLabel(threadId)
      const next = [...get().threads, threadId]
      persistThreads(next)

      useQuizStore.getState().reset()
      set({
        threads: next,
        threadId,
        messages: [],
        isLoading: false,
        liveReferences: [],
        labels: { ...get().labels, [threadId]: label },
      })

      apiFetch(`/threads?lecture_id=${getLectureId()}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: threadId }),
      }).catch(() => {})

      return threadId
    },

    deleteThread: async (threadId) => {
      const { threads, threadId: currentId, _messagesCache, labels } = get()
      const remaining = threads.filter((t) => t !== threadId)
      const nextId = remaining.length > 0 ? remaining[remaining.length - 1] : 'default'

      removeThreadLabel(threadId)
      const nextLabels = { ...labels }
      delete nextLabels[threadId]
      const newCache = { ..._messagesCache }
      delete newCache[threadId]
      persistThreads(remaining)

      if (get().sendingThreadId === threadId) _sendAbortController?.abort()

      if (currentId === threadId) {
        useQuizStore.getState().reset()
        set({
          threads: remaining,
          threadId: nextId,
          messages: newCache[nextId] ?? [],
          isLoading: false,
          _messagesCache: newCache,
          labels: nextLabels,
        })
        if (nextId) void get().loadThreadMessages(nextId)
      } else {
        set({ threads: remaining, _messagesCache: newCache, labels: nextLabels })
      }

      apiFetch(`/threads/${threadId}?lecture_id=${getLectureId()}`, { method: 'DELETE' }).catch(() => {})
    },

    getThreadLabel: (id) => get().labels[id] || getOrCreateLabel(id),
  }
})

export type { ChatResponse }

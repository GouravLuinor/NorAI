import { create } from 'zustand'
import { useQuizStore } from './useQuizStore'

// 🚨 The crucial fix: Explicitly define the backend URL to bypass the proxy trap
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export interface Reference {
  id: string
  title: string
  section: string
  sectionId: string
  type: 'note' | 'screenshot'
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  references?: Reference[]
}

interface ThreadState {
  threadId: string
  threads: string[]
  
  messagesByThread: Record<string, Message[]>
  loadingByThread: Record<string, boolean>
  streamingByThread: Record<string, string>

  setThreadId: (id: string) => void
  addMessage: (threadId: string, msg: Message) => void
  setLoading: (threadId: string, loading: boolean) => void
  setStreamingText: (threadId: string, text: string) => void
  
  loadThreads: () => Promise<void>
  loadThreadMessages: (threadId: string) => Promise<void>
  createThread: () => Promise<string>
  deleteThread: (threadId: string) => Promise<void>
  getThreadLabel: (threadId: string) => string
}

const genId = () => `msg-${Math.random().toString(36).substring(2, 9)}`

const LABELS_KEY = 'norai-thread-labels'
const COUNTER_KEY = 'norai-thread-counter'

function getLabels(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(LABELS_KEY) || '{}')
  } catch {
    return {}
  }
}

function saveLabels(labels: Record<string, string>) {
  localStorage.setItem(LABELS_KEY, JSON.stringify(labels))
}

function getNextCounter(): number {
  const current = parseInt(localStorage.getItem(COUNTER_KEY) || '0', 10)
  const next = current + 1
  localStorage.setItem(COUNTER_KEY, String(next))
  return next
}

export function getOrCreateLabel(threadId: string): string {
  const labels = getLabels()
  if (labels[threadId]) return labels[threadId]
  const counter = getNextCounter()
  const label = `Thread ${counter}`
  labels[threadId] = label
  saveLabels(labels)
  return label
}

export const useThreadStore = create<ThreadState>((set, get) => ({
  threadId: 'default',
  threads: [],
  messagesByThread: {},
  loadingByThread: {},
  streamingByThread: {},

  setThreadId: (id) => {
    set({ threadId: id })
    useQuizStore.getState().reset()
    if (!get().messagesByThread[id]) {
      get().loadThreadMessages(id)
    }
  },

  addMessage: (threadId, msg) => set((s) => ({ 
    messagesByThread: { 
      ...s.messagesByThread, 
      [threadId]: [...(s.messagesByThread[threadId] || []), msg] 
    } 
  })),
  
  setLoading: (threadId, loading) => set((s) => ({
    loadingByThread: { ...s.loadingByThread, [threadId]: loading }
  })),

  setStreamingText: (threadId, text) => set((s) => ({
    streamingByThread: { ...s.streamingByThread, [threadId]: text }
  })),

  loadThreads: async () => {
    try {
      const res = await fetch(`${API_BASE}/threads`)
      if (!res.ok) throw new Error('Network response was not ok')
      
      const data = await res.json()
      let fetchedThreads = data.threads || []
      
      if (fetchedThreads.length === 0) {
        await get().createThread()
        return 
      } else {
        fetchedThreads.forEach((id: string) => getOrCreateLabel(id))
        set({ threads: fetchedThreads })
        
        const currentThread = get().threadId
        if (!fetchedThreads.includes(currentThread)) {
          get().setThreadId(fetchedThreads[fetchedThreads.length - 1])
        }
      }
    } catch (err) {
      console.error("Failed to load threads. Backend might be down:", err)
      if (get().threads.length === 0) {
        const fallbackId = `thread-${Date.now()}`
        getOrCreateLabel(fallbackId)
        set({ threads: [fallbackId], threadId: fallbackId })
      }
    }
  },

  loadThreadMessages: async (threadId: string) => {
    set((s) => ({ loadingByThread: { ...s.loadingByThread, [threadId]: true } }))
    try {
      const res = await fetch(`${API_BASE}/threads/${threadId}`)
      if (!res.ok) throw new Error('Thread not found')
      const data = await res.json()
      const msgs: Message[] = (data.messages || []).map((m: any) => ({
        id: genId(),
        role: m.role,
        content: m.content,
        timestamp: '',
      }))
      set((s) => ({ 
        messagesByThread: { ...s.messagesByThread, [threadId]: msgs },
        loadingByThread: { ...s.loadingByThread, [threadId]: false }
      }))
    } catch {
      set((s) => ({ 
        messagesByThread: { ...s.messagesByThread, [threadId]: [] },
        loadingByThread: { ...s.loadingByThread, [threadId]: false }
      }))
    }
  },

  createThread: async () => {
    let newThreadId: string
    try {
      const res = await fetch(`${API_BASE}/threads`, { method: 'POST' })
      const data = await res.json()
      newThreadId = data.thread_id
    } catch {
      newThreadId = `thread-${Date.now()}`
    }
    
    getOrCreateLabel(newThreadId)
    
    set((s) => {
      if (s.threads.includes(newThreadId)) return s;
      return { 
        threads: [...s.threads, newThreadId], 
        threadId: newThreadId,
        messagesByThread: { ...s.messagesByThread, [newThreadId]: [] } 
      }
    })
    
    return newThreadId
  },

  deleteThread: async (targetId: string) => {
    try {
      await fetch(`${API_BASE}/threads/${targetId}`, { method: 'DELETE' })
    } catch {
      // Proceed with optimistic frontend deletion
    }
    
    const { threads, threadId: currentActiveId } = get()
    const remaining = threads.filter((t) => t !== targetId)
    
    const nextId = remaining.length > 0 ? remaining[remaining.length - 1] : null
    
    if (!nextId) {
       await get().createThread()
    } else {
       set({ threads: remaining })
       if (currentActiveId === targetId) {
         get().setThreadId(nextId)
       }
    }
    
    const labels = getLabels()
    delete labels[targetId]
    saveLabels(labels)
  },

  getThreadLabel: (threadId: string) => {
    return getOrCreateLabel(threadId)
  },
}))

export async function* sendChatMessageStream(
  threadId: string,
  userQuestion: string,
  lectureTitle: string = ''
): AsyncGenerator<string | { type: 'final'; data: any }> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      user_question: userQuestion,
      lecture_title: lectureTitle,
    }),
  })
  
  if (!res.ok) throw new Error('Chat request failed')

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          if (data.startsWith('[ERROR]')) throw new Error(data.slice(8))
          try {
            const parsed = JSON.parse(data)
            yield { type: 'final', data: parsed }
          } catch {
            yield data
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
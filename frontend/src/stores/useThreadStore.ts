import { create } from 'zustand'

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
  setThreadId: (id: string) => void
  addMessage: (msg: Message) => void
  setLoading: (loading: boolean) => void
}

export const useThreadStore = create<ThreadState>((set) => ({
  threadId: 'thread-1',
  threads: ['thread-1', 'thread-2', 'thread-3'],
  messages: [],
  isLoading: false,
  setThreadId: (id) => set({ threadId: id }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  setLoading: (loading) => set({ isLoading: loading }),
}))
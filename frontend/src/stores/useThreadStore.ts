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

export async function sendChatMessage(
  threadId: string,
  userQuestion: string,
  lectureTitle: string = ''
): Promise<{
  answer: string
  retrieved_chunks: any[]
  retrieved_images: any[]
}> {
  const res = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      user_question: userQuestion,
      lecture_title: lectureTitle,
    }),
  })
  if (!res.ok) throw new Error('Chat request failed')
  return res.json()
}


export async function* sendChatMessageStream(
  threadId: string,
  userQuestion: string,
  lectureTitle: string = ''
): AsyncGenerator<string | { type: 'final'; data: any }> {
  const res = await fetch('/chat/stream', {
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
        // Try to parse as JSON (final event with chunks/images)
        try {
          const parsed = JSON.parse(data)
          yield { type: 'final', data: parsed }
        } catch {
          // It's a character
          yield data
        }
      }
    }
  }
}
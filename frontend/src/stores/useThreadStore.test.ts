import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChatResponse } from '../types'

// Controllable stand-ins for the network layer.
type Frame = string | { type: 'final'; data: ChatResponse }
let streamImpl: (threadId: string, text: string, opts?: { messageId?: string }) => AsyncGenerator<Frame>
let apiFetchImpl: (path: string) => Promise<unknown>

vi.mock('../lib/chatApi', () => ({
  apiFetch: (path: string) => apiFetchImpl(path),
  sendChatMessage: vi.fn(),
  sendChatMessageStream: (
    threadId: string,
    text: string,
    _title: string,
    _signal: AbortSignal,
    opts?: { messageId?: string },
  ) => streamImpl(threadId, text, opts),
}))

const { useThreadStore, reconcileMessages } = await import('./useThreadStore')
type Message = import('./useThreadStore').Message

const final = (messageId: string): Frame => ({
  type: 'final',
  data: { answer: '', assistant_message_id: `ai-${messageId}`, retrieved_chunks: [], retrieved_images: [] },
})

/** A stream that waits for `release()` before finishing — lets tests act mid-turn. */
function gatedStream(answer: string) {
  let release!: () => void
  const gate = new Promise<void>((r) => (release = r))
  const seen: Array<string | undefined> = []
  streamImpl = async function* (_threadId, _text, opts) {
    seen.push(opts?.messageId)
    yield answer
    await gate
    yield final(opts?.messageId ?? '')
  }
  return { release, seen }
}

const msg = (id: string, role: Message['role'], content: string, status?: Message['status']): Message => ({
  id, role, content, timestamp: '', status,
})

beforeEach(() => {
  useThreadStore.getState().resetForLectureChange()
  apiFetchImpl = async () => ({ messages: [] })
  streamImpl = async function* (_t, _x, opts) {
    yield 'Hello'
    yield final(opts?.messageId ?? '')
  }
})

describe('reconcileMessages', () => {
  it('keeps server order and drops confirmed local copies', () => {
    const server = [msg('m1', 'user', 'q'), msg('ai-m1', 'assistant', 'a')]
    const local = [msg('m1', 'user', 'q'), msg('ai-m1', 'assistant', 'a')]
    expect(reconcileMessages(server, local).map((m) => m.id)).toEqual(['m1', 'ai-m1'])
  })

  it('keeps an unconfirmed pending turn exactly once', () => {
    const server = [msg('m1', 'user', 'q'), msg('ai-m1', 'assistant', 'a')]
    const local = [...server, msg('m2', 'user', 'q2', 'pending')]
    expect(reconcileMessages(server, local).map((m) => m.id)).toEqual(['m1', 'ai-m1', 'm2'])
  })

  it('drops a local error bubble once the server has the completed turn', () => {
    const server = [msg('m2', 'user', 'q2'), msg('ai-m2', 'assistant', 'a2')]
    const local = [msg('m2', 'user', 'q2', 'error'), msg('err-m2', 'assistant', 'failed', 'error')]
    expect(reconcileMessages(server, local).map((m) => m.id)).toEqual(['m2', 'ai-m2'])
  })

  it('does not collapse two turns that have identical text', () => {
    const server = [
      msg('m1', 'user', 'Explain again'), msg('ai-m1', 'assistant', 'Same'),
      msg('m2', 'user', 'Explain again'), msg('ai-m2', 'assistant', 'Same'),
    ]
    expect(reconcileMessages(server, []).length).toBe(4)
  })
})

describe('sendMessage', () => {
  it('produces exactly one user and one assistant message per turn', async () => {
    await useThreadStore.getState().sendMessage('What is a stack?')
    const msgs = useThreadStore.getState().messages
    expect(msgs.map((m) => m.role)).toEqual(['user', 'assistant'])
    expect(msgs[1].id).toBe(`ai-${msgs[0].id}`)
    expect(msgs[0].status).toBeUndefined()
    expect(useThreadStore.getState().sendingThreadId).toBeNull()
  })

  it('ignores a second send while a turn is in flight (double submit)', async () => {
    const { release, seen } = gatedStream('A')
    const first = useThreadStore.getState().sendMessage('one')
    const second = await useThreadStore.getState().sendMessage('two')
    expect(second).toBeNull()
    release()
    await first
    expect(seen.length).toBe(1)
    expect(useThreadStore.getState().messages.filter((m) => m.role === 'user').map((m) => m.content)).toEqual(['one'])
  })

  it('writes the reply into the thread it was asked from, not the active one', async () => {
    useThreadStore.setState({ threadId: 'thread-a', threads: ['thread-a', 'thread-b'] })
    const { release } = gatedStream('Answer for A')
    const turn = useThreadStore.getState().sendMessage('question in A')
    useThreadStore.getState().setThreadId('thread-b')
    release()
    await turn
    const s = useThreadStore.getState()
    expect(s.messages).toEqual([])
    expect(s._messagesCache['thread-a'].map((m) => m.role)).toEqual(['user', 'assistant'])
  })

  it('a history reload mid-turn neither drops nor duplicates the pending turn', async () => {
    const { release } = gatedStream('Partial')
    const turn = useThreadStore.getState().sendMessage('new question')
    const pendingId = useThreadStore.getState().messages[0].id

    // Server has an older turn but not this one yet.
    apiFetchImpl = async () => ({
      messages: [{ id: 'old', role: 'user', content: 'old q' }, { id: 'ai-old', role: 'assistant', content: 'old a' }],
    })
    await useThreadStore.getState().loadThreadMessages('default')
    expect(useThreadStore.getState().messages.map((m) => m.id)).toEqual(['old', 'ai-old', pendingId])

    release()
    await turn
    // Server now also returns the completed turn: still exactly one copy.
    apiFetchImpl = async () => ({
      messages: [
        { id: 'old', role: 'user', content: 'old q' }, { id: 'ai-old', role: 'assistant', content: 'old a' },
        { id: pendingId, role: 'user', content: 'new question' }, { id: `ai-${pendingId}`, role: 'assistant', content: 'Partial' },
      ],
    })
    await useThreadStore.getState().loadThreadMessages('default')
    expect(useThreadStore.getState().messages.map((m) => m.id)).toEqual(['old', 'ai-old', pendingId, `ai-${pendingId}`])
  })

  it('marks a failed turn and retries it under the same message id', async () => {
    streamImpl = async function* () {
      yield 'partial'
      throw new Error('network down')
    }
    await expect(useThreadStore.getState().sendMessage('q')).rejects.toThrow('network down')
    let msgs = useThreadStore.getState().messages
    const userId = msgs[0].id
    expect(msgs.map((m) => [m.id, m.status])).toEqual([[userId, 'error'], [`err-${userId}`, 'error']])

    const seen: Array<string | undefined> = []
    streamImpl = async function* (_t, _x, opts) {
      seen.push(opts?.messageId)
      yield 'Recovered'
      yield final(opts?.messageId ?? '')
    }
    await useThreadStore.getState().retryMessage(userId)
    msgs = useThreadStore.getState().messages
    expect(seen).toEqual([userId])
    expect(msgs.map((m) => [m.id, m.status])).toEqual([[userId, undefined], [`ai-${userId}`, undefined]])
  })

  it('treats a stream that ends without a final frame as a failure', async () => {
    streamImpl = async function* () {
      yield 'cut off'
    }
    await expect(useThreadStore.getState().sendMessage('q')).rejects.toThrow()
    expect(useThreadStore.getState().messages.map((m) => m.status)).toEqual(['error', 'error'])
  })
})

describe('loadThreads', () => {
  it('lets the latest call win instead of dropping it', async () => {
    let resolveFirst!: (v: unknown) => void
    apiFetchImpl = () => new Promise((r) => (resolveFirst = r))
    const first = useThreadStore.getState().loadThreads()
    apiFetchImpl = async () => ({ threads: ['default', 'thread-new'] })
    await useThreadStore.getState().loadThreads()
    resolveFirst({ threads: ['default', 'thread-stale'] })
    await first
    expect(useThreadStore.getState().threads).toContain('thread-new')
    expect(useThreadStore.getState().threads).not.toContain('thread-stale')
  })
})

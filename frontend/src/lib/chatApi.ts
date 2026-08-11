import type { ChatResponse } from '../types'
import { getLectureId, generateThreadTitle, isDefaultLabel, setThreadLabel } from './threadStorage'
import { authHeaders } from './authHeaders'
import { apiFetch, ApiError, apiGet, apiPost, apiDelete, API_BASE } from './http'

// API_BASE comes from ./http (shared single source). It is intentionally NOT
// used inside apiFetch — all internal store calls use bare relative paths so
// the Vite dev proxy routes them correctly. It IS used in the exported
// sendChatMessage helpers for production builds.
export { apiFetch, apiGet, apiPost, apiDelete, ApiError, API_BASE }

function ensureLabel(threadId: string, userQuestion: string) {
  if (isDefaultLabel(threadId)) {
    setThreadLabel(threadId, generateThreadTitle(userQuestion))
  }
}

export async function sendChatMessage(
  threadId: string,
  userQuestion: string,
  lectureTitle = '',
  opts?: { lectureId?: string; messageId?: string; studyMode?: string; persona?: string },
): Promise<ChatResponse> {
  ensureLabel(threadId, userQuestion)

  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      thread_id: threadId,
      user_question: userQuestion,
      lecture_title: lectureTitle,
      lecture_id: opts?.lectureId || 'default',
      message_id: opts?.messageId,
      study_mode: opts?.studyMode || 'default',
      persona_instructions: opts?.persona || '',
    }),
  })
  const ct = res.headers.get('content-type') || ''
  if (!ct.includes('application/json'))
    throw new Error(`Unexpected response type: ${ct} (status ${res.status})`)
  if (!res.ok) {
    const err: unknown = await res.json().catch(() => ({}))
    const detail = typeof err === 'object' && err !== null && 'detail' in err ? (err as { detail?: string }).detail : undefined
    throw new Error(detail || `Chat request failed: ${res.status}`)
  }
  return res.json()
}

export async function* sendChatMessageStream(
  threadId: string,
  userQuestion: string,
  lectureTitle = '',
  signal?: AbortSignal,
  opts?: { messageId?: string; studyMode?: string; persona?: string },
): AsyncGenerator<string | { type: 'final'; data: ChatResponse }> {
  ensureLabel(threadId, userQuestion)

  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      thread_id: threadId,
      user_question: userQuestion,
      lecture_title: lectureTitle,
      lecture_id: getLectureId(),
      message_id: opts?.messageId,
      study_mode: opts?.studyMode || 'default',
      persona_instructions: opts?.persona || '',
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
      try {
        const parsed = JSON.parse(payload) as unknown
        if (parsed && typeof parsed === 'object') {
          const obj = parsed as { t?: string; final?: ChatResponse }
          if (typeof obj.t === 'string') yield obj.t
          else if (obj.final) yield { type: 'final', data: obj.final }
        }
      } catch {
        // non-JSON payload (legacy/unexpected) — pass through raw
        yield payload
      }
    }
  }
}

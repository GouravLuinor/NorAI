import { useCallback, useEffect, useRef, useState } from 'react'
import { useThreadStore, type Message } from '../stores/useThreadStore'
import { sendChatMessageStream } from '../lib/chatApi'
import { buildReferences, stripSources } from '../lib/references'
import { genId } from '../lib/id'
import type { Reference } from '../types'

export const chatTimestamp = () =>
  new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

export interface AskNoraSendOptions {
  studyMode?: string
  persona?: string
}

export interface UseAskNoraOptions {
  onReferences?: (refs: Reference[], targetThreadId: string) => void
  onStreamError?: (err: unknown, targetThreadId: string) => void
  emptyAnswerFallback?: string
  referenceAnswer?: (cleanAnswer: string) => string
}

const STREAM_FLUSH_MS = 100

export const appendAssistantMessageAtomically = (targetThreadId: string, assistantMsg: Message) => {
  useThreadStore.setState((s) => {
    const currentMessages = s.threadId === targetThreadId
      ? s.messages
      : (s._messagesCache[targetThreadId] ?? [])

    if (currentMessages.some(m => m.role === 'assistant' && m.content === assistantMsg.content)) {
      return {}
    }

    const updated = [...currentMessages, assistantMsg]
    return {
      _messagesCache: { ...s._messagesCache, [targetThreadId]: updated },
      ...(s.threadId === targetThreadId ? { messages: updated } : {}),
    }
  })
}

export function useAskNora(options: UseAskNoraOptions = {}) {
  const [isInFlight, setIsInFlight] = useState(false)
  const inflightRef = useRef(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const optionsRef = useRef(options)
  useEffect(() => {
    optionsRef.current = options
  })

  const send = useCallback(async (text: string, sendOpts?: AskNoraSendOptions): Promise<void> => {
    if (inflightRef.current) return
    inflightRef.current = true
    setIsInFlight(true)

    const store = useThreadStore.getState()
    const targetThreadId = store.threadId || 'default'

    const userMsg: Message = {
      id: genId(),
      role: 'user',
      content: text,
      timestamp: chatTimestamp(),
    }
    store.addMessage(userMsg)
    store.setLoading(true)

    const controller = new AbortController()
    abortControllerRef.current = controller

    let acc = ''
    let pendingFlush: number | null = null
    const flushNow = () => {
      if (pendingFlush !== null) {
        window.clearTimeout(pendingFlush)
        pendingFlush = null
      }
      store.setStreamingText(stripSources(acc))
    }
    const scheduleFlush = () => {
      if (pendingFlush !== null) return
      pendingFlush = window.setTimeout(() => {
        pendingFlush = null
        store.setStreamingText(stripSources(acc))
      }, STREAM_FLUSH_MS)
    }

    try {
      for await (const chunk of sendChatMessageStream(
        targetThreadId,
        text,
        '',
        controller.signal,
        { messageId: userMsg.id, studyMode: sendOpts?.studyMode, persona: sendOpts?.persona },
      )) {
        if (controller.signal.aborted) return

        if (typeof chunk === 'string') {
          acc += chunk
          scheduleFlush()
          continue
        }

        const data = chunk.data
        flushNow()
        store.setStreamingText('')

        const cleanAnswer = stripSources(acc) || optionsRef.current.emptyAnswerFallback || ''

        appendAssistantMessageAtomically(targetThreadId, {
          id: data.assistant_message_id || genId(),
          role: 'assistant',
          content: cleanAnswer,
          timestamp: chatTimestamp(),
        })

        const refs = buildReferences(
          data.retrieved_chunks ?? [],
          data.retrieved_images ?? [],
          optionsRef.current.referenceAnswer ? optionsRef.current.referenceAnswer(cleanAnswer) : cleanAnswer,
          data.verified_citations ?? [],
        )
        if (optionsRef.current.onReferences) {
          optionsRef.current.onReferences(refs, targetThreadId)
        } else {
          useThreadStore.getState().setLiveReferences(refs)
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return
      if (optionsRef.current.onStreamError) {
        optionsRef.current.onStreamError(err, targetThreadId)
      } else {
        console.error('[useAskNora] stream failed:', err)
      }
    } finally {
      if (pendingFlush !== null) {
        window.clearTimeout(pendingFlush)
        pendingFlush = null
      }
      useThreadStore.getState().setStreamingText('')
      useThreadStore.getState().setLoading(false)
      inflightRef.current = false
      setIsInFlight(false)
    }
  }, [])

  const abort = useCallback(() => {
    abortControllerRef.current?.abort()
  }, [])

  return { send, isInFlight, inflightRef, abortControllerRef, abort }
}

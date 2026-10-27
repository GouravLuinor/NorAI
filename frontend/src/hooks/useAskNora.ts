import { useCallback, useEffect, useRef } from 'react'
import { useThreadStore, chatTimestamp } from '../stores/useThreadStore'
import type { Reference } from '../types'

export { chatTimestamp }

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

/**
 * Thin component-facing wrapper around useThreadStore.sendMessage. The store
 * owns the in-flight guard, so every caller (chat input, concept map,
 * highlight-to-ask) shares one queue and can never start overlapping turns.
 */
export function useAskNora(options: UseAskNoraOptions = {}) {
  const isInFlight = useThreadStore((s) => s.sendingThreadId !== null)

  const optionsRef = useRef(options)
  useEffect(() => {
    optionsRef.current = options
  })

  const send = useCallback(async (text: string, sendOpts?: AskNoraSendOptions): Promise<void> => {
    const targetThreadId = useThreadStore.getState().threadId
    try {
      const result = await useThreadStore.getState().sendMessage(text, {
        studyMode: sendOpts?.studyMode,
        persona: sendOpts?.persona,
        emptyAnswerFallback: optionsRef.current.emptyAnswerFallback,
        referenceAnswer: optionsRef.current.referenceAnswer,
      })
      if (result) optionsRef.current.onReferences?.(result.references, result.threadId)
    } catch (err: unknown) {
      // The store already rendered an inline error + retry for this turn.
      if (optionsRef.current.onStreamError) optionsRef.current.onStreamError(err, targetThreadId)
      else console.error('[useAskNora] turn failed:', err)
    }
  }, [])

  const abort = useCallback(() => useThreadStore.getState().abortSend(), [])

  return { send, isInFlight, abort }
}

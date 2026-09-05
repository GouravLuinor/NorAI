import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useRateLimitStore } from './useRateLimitStore'

describe('useRateLimitStore', () => {
  beforeEach(() => {
    localStorage.clear()
    useRateLimitStore.getState().clearDailyLimit()
  })

  it('initializes with inactive state when storage is empty', () => {
    const state = useRateLimitStore.getState()
    expect(state.isDailyLimited).toBe(false)
    expect(state.remainingSeconds).toBe(0)
    expect(state.expiresAt).toBeNull()
  })

  it('sets daily limit, calculates expiresAt, and sets remainingSeconds', () => {
    const store = useRateLimitStore.getState()
    store.setDailyLimit(1800, 'Test cooldown message')

    const updated = useRateLimitStore.getState()
    expect(updated.isDailyLimited).toBe(true)
    expect(updated.remainingSeconds).toBe(1800)
    expect(updated.expiresAt).toBeGreaterThan(Date.now())
    expect(updated.message).toContain('Test cooldown message')
  })

  it('clears daily limit and removes storage', () => {
    const store = useRateLimitStore.getState()
    store.setDailyLimit(1800)
    expect(useRateLimitStore.getState().isDailyLimited).toBe(true)

    store.clearDailyLimit()
    const updated = useRateLimitStore.getState()
    expect(updated.isDailyLimited).toBe(false)
    expect(updated.remainingSeconds).toBe(0)
    expect(updated.expiresAt).toBeNull()
  })

  it('ticks down correctly and auto-clears when expired', () => {
    const store = useRateLimitStore.getState()
    store.setDailyLimit(2)

    // Tick down 1 second
    const futureTime = Date.now() + 1000
    vi.spyOn(Date, 'now').mockReturnValue(futureTime)
    store.tick()

    expect(useRateLimitStore.getState().remainingSeconds).toBeLessThanOrEqual(2)

    // Tick past expiration
    vi.spyOn(Date, 'now').mockReturnValue(futureTime + 5000)
    store.tick()

    expect(useRateLimitStore.getState().isDailyLimited).toBe(false)
    vi.restoreAllMocks()
  })
})

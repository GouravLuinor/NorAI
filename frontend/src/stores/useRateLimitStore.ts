import { create } from 'zustand'

const STORAGE_KEY = 'norai_daily_rate_limit_expires_at'

export interface RateLimitState {
  isDailyLimited: boolean
  remainingSeconds: number
  expiresAt: number | null
  message: string | null
  setDailyLimit: (retryAfterSeconds: number, message?: string) => void
  clearDailyLimit: () => void
  checkSystemStatus: () => Promise<void>
  tick: () => void
}

const getStoredExpiresAt = (): number | null => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const val = parseInt(raw, 10)
    if (isNaN(val) || val <= Date.now()) {
      localStorage.removeItem(STORAGE_KEY)
      return null
    }
    return val
  } catch {
    return null
  }
}

const initialExpiresAt = getStoredExpiresAt()
const initialRemaining = initialExpiresAt ? Math.max(0, Math.ceil((initialExpiresAt - Date.now()) / 1000)) : 0

export const useRateLimitStore = create<RateLimitState>((set, get) => ({
  isDailyLimited: initialRemaining > 0,
  remainingSeconds: initialRemaining,
  expiresAt: initialExpiresAt,
  message: null,

  setDailyLimit: (retryAfterSeconds: number, message?: string) => {
    const safeSecs = Math.max(1, retryAfterSeconds)
    const expiresAt = Date.now() + safeSecs * 1000
    try {
      localStorage.setItem(STORAGE_KEY, expiresAt.toString())
    } catch {
      // ignore localStorage quota errors
    }
    set({
      isDailyLimited: true,
      remainingSeconds: safeSecs,
      expiresAt,
      message: message || 'Google AI Studio daily quota reached. Resets at Pacific Midnight.',
    })
  },

  clearDailyLimit: () => {
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
    set({
      isDailyLimited: false,
      remainingSeconds: 0,
      expiresAt: null,
      message: null,
    })
  },

  tick: () => {
    const { expiresAt, isDailyLimited } = get()
    if (!isDailyLimited || !expiresAt) return

    const now = Date.now()
    if (now >= expiresAt) {
      get().clearDailyLimit()
      // Verify with backend
      void get().checkSystemStatus()
    } else {
      const remaining = Math.max(0, Math.ceil((expiresAt - now) / 1000))
      set({ remainingSeconds: remaining })
    }
  },

  checkSystemStatus: async () => {
    try {
      const res = await fetch('/system/rate-limit')
      if (!res.ok) return
      const data = await res.json()
      if (data.rateLimited && data.limitType === 'rpd') {
        get().setDailyLimit(data.retryAfterSeconds)
      } else if (!data.rateLimited && get().isDailyLimited) {
        get().clearDailyLimit()
      }
    } catch {
      // offline or backend unreachable; keep local timer intact
    }
  },
}))

// Start interval ticking for accurate countdown
if (typeof window !== 'undefined') {
  setInterval(() => {
    useRateLimitStore.getState().tick()
  }, 1000)

  // Periodic check of backend status every 5 minutes
  setInterval(() => {
    void useRateLimitStore.getState().checkSystemStatus()
  }, 5 * 60 * 1000)
}

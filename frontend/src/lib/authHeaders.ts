import { useAuthStore } from '../stores/useAuthStore'

const GUEST_KEY = 'norai_guest_id'

export function getOrCreateGuestId(): string {
  if (typeof window === 'undefined' || !window.localStorage) {
    return 'anon-guest'
  }
  let guestId = localStorage.getItem(GUEST_KEY)
  if (!guestId) {
    guestId = `guest_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`
    localStorage.setItem(GUEST_KEY, guestId)
  }
  return guestId
}

export function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().token
  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  } else {
    headers['X-Guest-Id'] = getOrCreateGuestId()
  }
  return headers
}

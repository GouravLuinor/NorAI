import { useAuthStore } from '../stores/useAuthStore'
import { getGuestId } from './guestId'

export function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().token
  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  headers['X-Guest-Id'] = getGuestId()
  return headers
}

import { useAuthStore } from '../stores/useAuthStore'

export function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().token
  const headers: Record<string, string> = {}
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

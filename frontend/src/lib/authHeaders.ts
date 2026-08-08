import { useAuthStore } from '../stores/useAuthStore'

export function authHeaders(): Record<string, string> {
  const token = useAuthStore.getState().token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

import { create } from 'zustand'

export interface Toast {
  id: string
  message: string
  type: 'info' | 'success' | 'error'
}

interface ToastState {
  toasts: Toast[]
  addToast: (message: string, type?: Toast['type']) => void
  removeToast: (id: string) => void
}

let toastId = 0

// P4.3: errors need reading time — they self-dismiss in 8s (vs 3s for
// info/success). Pass `persistent` via the error copy containing '[sticky]'
// is NOT supported; callers needing a permanent toast should render inline
// instead. 8s covers ~2x the average reading time for a failure sentence.
const ERROR_TOAST_MS = 8000
const TOAST_MS = 3000

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (message, type = 'info') => {
    const id = `toast-${++toastId}`
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }))
    setTimeout(
      () => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
      },
      type === 'error' ? ERROR_TOAST_MS : TOAST_MS,
    )
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

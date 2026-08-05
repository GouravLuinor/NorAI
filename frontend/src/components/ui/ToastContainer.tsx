import { useToastStore } from '../../stores/useToastStore'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'
import { IconButton } from './IconButton'

const icons = {
  success: <CheckCircle size={14} strokeWidth={1.5} className="text-ng" />,
  error: <AlertCircle size={14} strokeWidth={1.5} className="text-nr" />,
  info: <Info size={14} strokeWidth={1.5} className="text-nbl" />,
}

export function ToastContainer() {
  const { toasts, removeToast } = useToastStore()

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-lg bg-ns border border-bdr2 shadow-ev2 text-xs text-nt2 animate-slide-in`}
        >
          {icons[toast.type]}
          <span className="flex-1">{toast.message}</span>
          <IconButton
            label="Dismiss notification"
            variant="bare"
            onClick={() => removeToast(toast.id)}
          >
            <X size={12} strokeWidth={1.5} />
          </IconButton>
        </div>
      ))}
    </div>
  )
}
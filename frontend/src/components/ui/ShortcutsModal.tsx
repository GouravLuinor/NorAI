import { useEffect } from 'react'
import { X, Command } from 'lucide-react'

interface ShortcutsModalProps {
  isOpen: boolean
  onClose: () => void
}

const shortcuts = [
  { keys: 'Enter', description: 'Send chat message' },
  { keys: 'Shift + Enter', description: 'New line in chat' },
  { keys: 'Escape', description: 'Close sidebar / Cancel' },
  { keys: 'Ctrl + F', description: 'Search in document' },
]

export function ShortcutsModal({ isOpen, onClose }: ShortcutsModalProps) {
  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-ns border border-bdr2 rounded-xl p-6 w-80 shadow-ev3" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-nt flex items-center gap-2">
            <Command size={14} /> Keyboard Shortcuts
          </h3>
          <button onClick={onClose} className="text-nt3 hover:text-nt transition"><X size={14} /></button>
        </div>
        <div className="space-y-2">
          {shortcuts.map((s) => (
            <div key={s.keys} className="flex items-center justify-between text-xs">
              <span className="text-nt2">{s.description}</span>
              <kbd className="px-1.5 py-0.5 rounded bg-ns3 text-nt3 font-mono text-2xs">{s.keys}</kbd>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
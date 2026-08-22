import { X, Command } from 'lucide-react'
import { IconButton } from './IconButton'
import { Dialog } from './Dialog'

interface ShortcutsModalProps {
  isOpen: boolean
  onClose: () => void
}

const shortcuts = [
  { keys: 'Enter', description: 'Send chat message' },
  { keys: 'Shift + Enter', description: 'New line in chat' },
  { keys: 'Escape', description: 'Close sidebar / Cancel' },
]

export function ShortcutsModal({ isOpen, onClose }: ShortcutsModalProps) {
  if (!isOpen) return null

  return (
    <Dialog
      ariaLabel="Keyboard shortcuts"
      onClose={onClose}
      panelClassName="bg-ns border border-bdr2 rounded-xl p-6 w-80 shadow-ev3"
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-medium text-nt flex items-center gap-2">
          <Command size={14} strokeWidth={1.5} /> Keyboard Shortcuts
        </h2>
        <IconButton label="Close shortcuts" variant="bare" onClick={onClose}>
          <X size={14} strokeWidth={1.5} />
        </IconButton>
      </div>
      <div className="space-y-2">
        {shortcuts.map((s) => (
          <div key={s.keys} className="flex items-center justify-between text-xs">
            <span className="text-nt2">{s.description}</span>
            <kbd className="px-1.5 py-0.5 rounded bg-ns3 text-nt3 font-mono text-2xs">{s.keys}</kbd>
          </div>
        ))}
      </div>
    </Dialog>
  )
}

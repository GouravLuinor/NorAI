import { useEffect, useState } from 'react'
import { Dialog } from '../ui/Dialog'
import { useTutorSettingsStore } from '../../stores/useTutorSettingsStore'
import { Button } from '../ui/Button'
import { X } from 'lucide-react'
import { FOCUS_RING } from '../ui/shared'

interface PersonaModalProps {
  open: boolean
  onClose: () => void
}

export function PersonaModal({ open, onClose }: PersonaModalProps) {
  const persona = useTutorSettingsStore(s => s.persona)
  const setPersona = useTutorSettingsStore(s => s.setPersona)

  const [draft, setDraft] = useState(persona)

  useEffect(() => {
    if (open) setDraft(persona)
  }, [open, persona])

  if (!open) return null

  const handleSave = () => {
    setPersona(draft)
    onClose()
  }

  return (
    <Dialog
      ariaLabel="Tutor settings"
      onClose={onClose}
      panelClassName="w-full max-w-md rounded-xl bg-ns border border-bdr shadow-ev1 overflow-hidden"
    >
      <div className="flex items-center justify-between px-5 py-4 border-b border-bdr bg-ns2/40">
        <div>
          <div className="font-display text-sm font-medium text-nt">Tutor settings</div>
          <div className="spec-label mt-0.5">Persona instructions · per lecture</div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close tutor settings"
          className={`p-1.5 rounded-md text-nt3 hover:text-nt2 hover:bg-ns3 transition ${FOCUS_RING}`}
        >
          <X size={16} strokeWidth={1.5} />
        </button>
      </div>

      <div className="px-5 py-4 space-y-5">
        <div>
          <label htmlFor="persona-input" className="text-2xs font-semibold uppercase tracking-wider text-nt3">
            Persona instructions
          </label>
          <textarea
            id="persona-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="e.g. Explain like I'm preparing for an interview…"
            rows={5}
            className={`mt-2 w-full rounded-lg bg-ns2 border border-bdr2 px-3 py-2.5 text-13 text-nt placeholder:text-nt4 outline-none focus:border-np resize-none ${FOCUS_RING}`}
          />
          <p className="text-2xs text-nt3 mt-1.5">
            Free-text standing instructions appended to the tutor's system prompt for this lecture. Switch to Study mode (Socratic) via the panel tabs.
          </p>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-bdr bg-ns2/40">
        <Button variant="outline" onClick={onClose} className="px-4 py-2 rounded-md text-xs">
          Cancel
        </Button>
        <Button variant="primary" onClick={handleSave} className="px-4 py-2 rounded-md text-xs">
          Save
        </Button>
      </div>
    </Dialog>
  )
}
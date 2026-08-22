import { useEffect, useRef, type KeyboardEvent, type ReactNode } from 'react'

// Modal dialog primitive: real `role="dialog"` semantics, focus trap
// (Tab/Shift+Tab cycle), focus restore on close, Escape-to-close and body
// scroll lock. Overlay + panel chrome stay at the call site via props.
interface DialogProps {
  ariaLabel?: string
  labelledBy?: string
  ariaDescribedBy?: string
  onClose: () => void
  overlayClassName?: string
  panelClassName?: string
  children: ReactNode
}

const FOCUSABLE =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

export function Dialog({
  ariaLabel,
  labelledBy,
  ariaDescribedBy,
  onClose,
  overlayClassName = 'flex items-center justify-center bg-black/50 backdrop-blur-sm',
  panelClassName = '',
  children,
}: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const restoreFocusRef = useRef<Element | null>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    if (import.meta.env.DEV && !ariaLabel && !labelledBy) {
      console.warn('Dialog: role="dialog" has no accessible name — pass ariaLabel or labelledBy.')
    }
  }, [ariaLabel, labelledBy])

  useEffect(() => {
    restoreFocusRef.current = document.activeElement

    const panel = panelRef.current
    if (panel) {
      const focusables = panel.querySelectorAll<HTMLElement>(FOCUSABLE)
      const target = [...focusables].find((el) => !el.hasAttribute('disabled'))
      ;(target ?? panel).focus()
    }

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const handleKeyDown = (e: globalThis.KeyboardEvent) => {
      if (e.defaultPrevented) return
      if (e.key === 'Escape') onCloseRef.current()
    }
    document.addEventListener('keydown', handleKeyDown)

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
      if (restoreFocusRef.current instanceof HTMLElement) {
        restoreFocusRef.current.focus()
      }
    }
  }, [])

  const handlePanelKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== 'Tab') return
    const panel = panelRef.current
    if (!panel) return
    const focusables = [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
      (el) => !el.hasAttribute('disabled')
    )
    if (focusables.length === 0) {
      e.preventDefault()
      return
    }
    const first = focusables[0]
    const last = focusables[focusables.length - 1]
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault()
      last.focus()
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault()
      first.focus()
    }
  }

  return (
    // P4.4: alignment lives in the (overridable) overlay classes so drawers
    // can anchor to an edge instead of centering.
    <div className={`fixed inset-0 z-50 flex ${overlayClassName}`} onClick={onClose}>
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        aria-labelledby={labelledBy}
        aria-describedby={ariaDescribedBy}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handlePanelKeyDown}
        className={`outline-none ${panelClassName}`.replace(/\s+/g, ' ').trim()}
      >
        {children}
      </div>
    </div>
  )
}

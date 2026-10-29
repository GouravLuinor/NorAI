import type { MouseEventHandler, ReactNode } from 'react'

interface ShelfMarkProps {
  /** First line of the label: "CH 02", "1.2". Shown in the primary colour. */
  top?: ReactNode
  /** Second line: usually a timestamp such as "5:04". */
  time?: ReactNode
  /** One line, sitting in running text (tutor citations, quiz references). */
  inline?: boolean
  /** The current item: brass fill. */
  current?: boolean
  onClick?: MouseEventHandler<HTMLButtonElement>
  /** Accessible name for the button; required when onClick is set. */
  label?: string
  title?: string
  className?: string
}

/**
 * Shelf mark: the stacked call-number label that marks every chapter,
 * section, citation and timestamp in NorAI. With onClick it is a button that
 * walks the video (or the notes) to that place.
 */
export function ShelfMark({ top, time, inline, current, onClick, label, title, className = '' }: ShelfMarkProps) {
  const cls = `shelf-mark ${inline ? 'shelf-mark-inline' : ''} ${className}`.trim()
  const body = (
    <>
      {top != null && <span className="shelf-mark-top">{top}</span>}
      {time != null && <span>{time}</span>}
    </>
  )
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-label={label}
        aria-current={current ? 'true' : undefined}
        title={title}
        className={cls}
      >
        {body}
      </button>
    )
  }
  return (
    <span className={cls} aria-current={current ? 'true' : undefined} title={title}>
      {body}
    </span>
  )
}

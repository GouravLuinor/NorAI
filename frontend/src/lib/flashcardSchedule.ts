import type { FlashcardSchedule } from '../stores/useQuizStore'

// SM-2 due-date helpers (P6.2). Cards are due today when their due date has
// arrived; never-reviewed cards count as due (they're new learning material).

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

/** Parse "YYYY-MM-DD" into a *local* Date (avoids UTC parsing skew). */
function parseDueDate(dueAt?: string): Date | null {
  if (!dueAt) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(dueAt)
  if (!m) return null
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
}

export function isCardDue(schedule?: FlashcardSchedule | null, today?: Date): boolean {
  const due = parseDueDate(schedule?.due_at)
  if (!due) return true // brand-new or unparseable → review now
  return due.getTime() <= startOfDay(today ?? new Date()).getTime()
}

export function dueLabel(schedule?: FlashcardSchedule | null, today?: Date): string {
  const due = parseDueDate(schedule?.due_at)
  if (!due) return 'New'
  const diffDays = Math.round(
    (due.getTime() - startOfDay(today ?? new Date()).getTime()) / 86_400_000,
  )
  if (diffDays < 0) return `${-diffDays}d overdue`
  if (diffDays === 0) return 'Due today'
  return `in ${diffDays}d`
}
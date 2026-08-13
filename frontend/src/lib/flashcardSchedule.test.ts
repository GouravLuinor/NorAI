import { describe, it, expect } from 'vitest'
import { isCardDue, dueLabel } from './flashcardSchedule'
import type { FlashcardSchedule } from '../stores/useQuizStore'

const LOCAL_DATE = new Date(2026, 7, 12) // Aug 12 2026, local

function sched(dueAt: string): FlashcardSchedule {
  return { rating: 'Good', easiness: 2.5, reps: 1, interval_days: 1, due_at: dueAt, due_in_days: 0, last_reviewed_at: '' }
}

describe('isCardDue', () => {
  it('treats never-reviewed cards as due', () => {
    expect(isCardDue(undefined, LOCAL_DATE)).toBe(true)
    expect(isCardDue(null, LOCAL_DATE)).toBe(true)
    expect(isCardDue({} as FlashcardSchedule, LOCAL_DATE)).toBe(true)
  })

  it('resolves due today / overdue / future', () => {
    expect(isCardDue(sched('2026-08-12'), LOCAL_DATE)).toBe(true) // today
    expect(isCardDue(sched('2026-08-01'), LOCAL_DATE)).toBe(true) // overdue
    expect(isCardDue(sched('2026-08-13'), LOCAL_DATE)).toBe(false) // tomorrow
  })
})

describe('dueLabel', () => {
  it('labels the three states', () => {
    expect(dueLabel(undefined, LOCAL_DATE)).toBe('New')
    expect(dueLabel(sched('2026-08-12'), LOCAL_DATE)).toBe('Due today')
    expect(dueLabel(sched('2026-08-09'), LOCAL_DATE)).toBe('3d overdue')
    expect(dueLabel(sched('2026-08-15'), LOCAL_DATE)).toBe('in 3d')
  })

  it('handles an unparseable date', () => {
    expect(dueLabel(sched('garbage'), LOCAL_DATE)).toBe('New')
  })
})
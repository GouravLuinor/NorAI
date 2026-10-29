/**
 * Plan catalogue types and the static fallback. Dependency-free so the build
 * (vite-plugin-seo: JSON-LD offers, llms.txt) can import it too.
 */
import { FREE_MINUTES } from './faq.ts'

/** Mirrors backend/plans.py `Plan.public()`. */
export interface Plan {
  id: 'free' | 'starter' | 'pro'
  name: string
  tagline: string
  price_inr: number
  minutes: number
  max_lecture_min: number
  period_days: number
  features: string[]
  purchasable: boolean
}

export interface PlansResponse {
  currency: 'INR'
  payments_enabled: boolean
  plans: Plan[]
}

/**
 * Shown until GET /billing/plans answers (and if it fails), so the public
 * pricing page never renders empty. Keep in step with backend/plans.py.
 */
export const FALLBACK_PLANS: PlansResponse = {
  currency: 'INR',
  payments_enabled: false,
  plans: [
    {
      id: 'free', name: 'Free', tagline: 'Everything NorAI does, free. No card needed.',
      price_inr: 0, minutes: FREE_MINUTES, max_lecture_min: FREE_MINUTES, period_days: 30, purchasable: false,
      features: [
        `${FREE_MINUTES} lecture-minutes every 30 days`,
        `Lectures up to ${FREE_MINUTES} minutes long`,
        'Study notes, revision sheet, quiz & flashcards',
        'Lecture-grounded AI tutor and PDF export',
      ],
    },
    {
      id: 'starter', name: 'Starter', tagline: 'For a regular weekly course load.',
      price_inr: 149, minutes: 300, max_lecture_min: 90, period_days: 30, purchasable: true,
      features: [
        '300 lecture-minutes (5 hours) for 30 days',
        'Lectures up to 90 minutes long',
        'Everything in Free',
        'Unused minutes carry over when you buy again',
      ],
    },
    {
      id: 'pro', name: 'Pro', tagline: 'For exam season and heavy semesters.',
      price_inr: 449, minutes: 1200, max_lecture_min: 180, period_days: 30, purchasable: true,
      features: [
        '1,200 lecture-minutes (20 hours) for 30 days',
        'Lectures up to 3 hours long',
        'Everything in Starter',
        'Lowest price per lecture-minute',
      ],
    },
  ],
}

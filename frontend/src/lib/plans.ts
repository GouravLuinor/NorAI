import { useEffect, useState } from 'react'
import { apiGet } from './http'

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
      id: 'free', name: 'Free', tagline: 'Try NorAI on your own lectures. No card needed.',
      price_inr: 0, minutes: 45, max_lecture_min: 45, period_days: 30, purchasable: false,
      features: [
        '45 lecture-minutes every 30 days',
        'Lectures up to 45 minutes long',
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

let cache: PlansResponse | null = null
let inflight: Promise<PlansResponse> | null = null

export function fetchPlans(): Promise<PlansResponse> {
  if (cache) return Promise.resolve(cache)
  inflight ??= apiGet<PlansResponse>('/billing/plans')
    .then((r) => (cache = r))
    .catch(() => FALLBACK_PLANS)
    .finally(() => (inflight = null))
  return inflight
}

/** Plan catalogue with an immediate static fallback (no loading flash). */
export function usePlans(): PlansResponse & { loaded: boolean } {
  const [data, setData] = useState<PlansResponse | null>(cache)
  useEffect(() => {
    if (cache) return
    let active = true
    void fetchPlans().then((r) => active && setData(r))
    return () => {
      active = false
    }
  }, [])
  return { ...(data ?? FALLBACK_PLANS), loaded: data !== null }
}

export const formatInr = (rupees: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(rupees)

export const formatMinutes = (min: number) =>
  min >= 60 ? `${+(min / 60).toFixed(1)} h` : `${min} min`

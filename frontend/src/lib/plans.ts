import { useEffect, useState } from 'react'
import { apiGet } from './http'
import { FALLBACK_PLANS, type Plan, type PlansResponse } from '../content/plans'

export { FALLBACK_PLANS }
export type { Plan, PlansResponse }

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

/** "resets Nov 28" for a quota with used minutes; '' when nothing is used yet. */
export const quotaResetLabel = (resetsAt?: string | null) =>
  resetsAt
    ? `resets ${new Date(resetsAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
    : ''

export const formatInr = (rupees: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(rupees)

export const formatMinutes = (min: number) =>
  min >= 600
    ? `${Math.round(min / 60).toLocaleString()} h`
    : min >= 60
      ? `${+(min / 60).toFixed(1)} h`
      : `${min} min`

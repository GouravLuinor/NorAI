import { Check, Loader2 } from 'lucide-react'
import { FOCUS_RING } from '../ui/shared'
import { formatInr, formatMinutes, type Plan } from '../../lib/plans'

interface PlanSheetProps {
  plans: Plan[]
  paymentsEnabled: boolean
  /** Signed-in user's current plan (undefined for visitors). */
  currentPlanId?: string
  busyPlanId?: string | null
  onChoose: (plan: Plan) => void
  /** Plan to emphasise (e.g. picked on the public pricing page before sign-up). */
  highlightId?: string
}

const RECOMMENDED = 'pro'

function ctaLabel(plan: Plan, paymentsEnabled: boolean, currentPlanId?: string) {
  if (!plan.purchasable) {
    if (!currentPlanId) return 'Start free'
    return currentPlanId === 'free' ? 'Your current plan' : 'Included'
  }
  if (!paymentsEnabled) return 'Opening soon'
  if (currentPlanId === plan.id) return `Add 30 days · ${formatInr(plan.price_inr)}`
  return `Get ${plan.name} · ${formatInr(plan.price_inr)}`
}

/**
 * The plan catalogue drawn as one ruled spec sheet (the app's drafting-paper
 * look) rather than three floating cards. Used by /pricing, /billing and the
 * landing page so prices are never duplicated in copy.
 */
export function PlanSheet({ plans, paymentsEnabled, currentPlanId, busyPlanId, onChoose, highlightId }: PlanSheetProps) {
  const emphasis = highlightId ?? RECOMMENDED
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 border border-bdr2 rounded-lg bg-ns shadow-ev1 overflow-hidden">
      {plans.map((plan, i) => {
        const isCurrent = currentPlanId === plan.id
        const isEmph = plan.id === emphasis
        const disabled =
          busyPlanId != null ||
          (plan.purchasable ? !paymentsEnabled : Boolean(currentPlanId))
        const perMin = plan.purchasable ? plan.price_inr / plan.minutes : 0
        return (
          <section
            key={plan.id}
            aria-labelledby={`plan-${plan.id}`}
            className={`relative flex flex-col p-6 sm:p-7 ${i > 0 ? 'border-t md:border-t-0 md:border-l border-bdr2' : ''} ${isEmph ? 'bg-nb' : ''}`}
          >
            {isEmph && (
              <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-np" />
            )}
            <div className="flex items-baseline justify-between gap-3">
              <h3 id={`plan-${plan.id}`} className="font-serif text-22 text-nt">
                {plan.name}
              </h3>
              {isCurrent ? (
                <span className="text-12 text-ngt bg-ngb border border-ngbr px-1.5 py-0.5 rounded">
                  Current
                </span>
              ) : isEmph && !highlightId ? (
                <span className="text-12 text-npt">Best value</span>
              ) : null}
            </div>
            <p className="text-12 text-nt2 mt-1 min-h-[2.5em]">{plan.tagline}</p>

            <div className="mt-5 flex items-baseline gap-1.5">
              <span className="font-serif text-44 leading-none text-nt tabular-nums">{formatInr(plan.price_inr)}</span>
              <span className="text-12 text-nt3">/ {plan.period_days} days</span>
            </div>
            <p className="mt-2 font-mono text-11 text-nt3 tabular-nums">
              {formatMinutes(plan.minutes)} of lectures
              {perMin > 0 && <> · ₹{perMin.toFixed(2)}/min</>}
            </p>

            <ul className="mt-5 space-y-2.5 text-13 text-nt flex-1">
              {plan.features.map((f) => (
                <li key={f} className="flex gap-2.5">
                  <Check size={15} className="text-ng shrink-0 mt-0.5" aria-hidden="true" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>

            <button
              type="button"
              disabled={disabled}
              onClick={() => onChoose(plan)}
              aria-busy={busyPlanId === plan.id}
              className={`mt-7 w-full py-2.5 px-4 rounded-md font-display text-12 font-semibold tracking-wide inline-flex items-center justify-center gap-2 transition-[background-color,transform] ${FOCUS_RING} ${
                disabled
                  ? 'bg-ns2 text-nt3 border border-bdr cursor-not-allowed'
                  : isEmph || (plan.purchasable && isCurrent)
                    ? 'bg-npf hover:bg-npfh text-npfg shadow-ev1 active:translate-y-px cursor-pointer'
                    : 'bg-ns hover:bg-ns2 border border-bdr2 text-nt active:translate-y-px cursor-pointer'
              }`}
            >
              {busyPlanId === plan.id && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
              {busyPlanId === plan.id ? 'Opening secure checkout…' : ctaLabel(plan, paymentsEnabled, currentPlanId)}
            </button>
          </section>
        )
      })}
    </div>
  )
}

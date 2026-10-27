import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, BarChart3, Receipt, RefreshCw } from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '../stores/useAuthStore'
import { useToastStore } from '../stores/useToastStore'
import { apiGet } from '../lib/http'
import { friendlyError } from '../lib/errorCopy'
import { formatInr, formatMinutes, usePlans, type Plan } from '../lib/plans'
import { startCheckout } from '../lib/razorpay'
import { PlanSheet } from '../components/billing/PlanSheet'
import { SkeletonCard } from '../components/ui/SkeletonCard'
import { Button } from '../components/ui/Button'
import { usePageMeta } from '../lib/usePageMeta'

interface PaymentRow {
  order_id: string
  plan_id: string
  plan_name: string
  amount_inr: number
  status: 'paid' | 'failed' | 'refunded'
  method: string | null
  failure_reason: string | null
  refunded_inr: number
  created_at: string | null
  paid_at: string | null
}

interface BillingData {
  plan_tier: Plan['id']
  plan: Plan
  subscription_status: string
  payments_enabled: boolean
  monthly_minutes_quota: number
  used_minutes_this_month: number
  remaining_minutes: number
  current_period_end: string | null
  payments: PaymentRow[]
}

const STATUS_COPY: Record<PaymentRow['status'], { label: string; cls: string }> = {
  paid: { label: 'Paid', cls: 'text-ngt bg-ngb border-ngbr' },
  failed: { label: 'Failed', cls: 'text-nrt bg-nrb border-nrbr' },
  refunded: { label: 'Refunded', cls: 'text-nat bg-nab border-nabr' },
}

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

function daysLeft(iso: string | null) {
  if (!iso) return null
  return Math.max(0, Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000))
}

export function BillingPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const user = useAuthStore((s) => s.user)
  const refreshQuota = useAuthStore((s) => s.refreshQuota)
  const addToast = useToastStore((s) => s.addToast)
  const { plans } = usePlans()
  const [data, setData] = useState<BillingData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const pickedPlan = params.get('plan') ?? undefined

  usePageMeta({ title: 'Plan & billing — NorAI', description: 'Your NorAI plan, remaining lecture minutes and payments.', path: '/billing', noindex: true })

  const userId = user?.id
  const load = useCallback(async () => {
    setError(null)
    try {
      setData(await apiGet<BillingData>('/billing'))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    if (userId) void load()
  }, [userId, load])

  const choose = async (plan: Plan) => {
    if (!plan.purchasable) return
    setBusy(plan.id)
    try {
      const result = await startCheckout(plan.id)
      if (result.status === 'paid') {
        addToast(`${plan.name} is active. Enjoy your extra lecture time!`, 'success')
        if (pickedPlan) setParams({}, { replace: true })
      } else if (result.status === 'pending') {
        addToast(result.message, 'info')
      } else if (result.status === 'failed') {
        addToast(result.message, 'error')
      }
      if (result.status !== 'dismissed') await Promise.all([load(), refreshQuota()])
    } catch (e) {
      addToast(friendlyError(e instanceof Error ? e.message : String(e)), 'error')
    } finally {
      setBusy(null)
    }
  }

  if (error) {
    return (
      <div id="main" className="min-h-screen bg-nb flex flex-col items-center justify-center gap-4 px-6 py-16 text-center">
        <p className="text-14 text-nrt max-w-md">{friendlyError(error)}</p>
        <div className="flex gap-3">
          <Button variant="primary" className="px-4 py-2 rounded-md text-12 gap-2" onClick={() => void load()}>
            <RefreshCw size={14} /> Try again
          </Button>
          <Button variant="outline" className="px-4 py-2 rounded-md text-12 gap-2 bg-transparent border-bdr2" onClick={() => navigate('/app')}>
            Back to workspace
          </Button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div id="main" className="min-h-screen bg-nb flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-3xl space-y-3" aria-busy="true" aria-label="Loading billing">
          <SkeletonCard lines={3} />
          <SkeletonCard lines={5} />
        </div>
      </div>
    )
  }

  const isPaid = data.plan_tier !== 'free'
  const left = daysLeft(data.current_period_end)
  const pct = Math.min(100, Math.round((data.used_minutes_this_month / Math.max(1, data.monthly_minutes_quota)) * 100))
  const picked = plans.find((p) => p.id === pickedPlan && p.purchasable)

  return (
    <div id="main" className="min-h-screen bg-nb text-nt">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-10 flex flex-col gap-10">
        <button
          onClick={() => navigate('/app')}
          className="inline-flex items-center gap-1.5 text-12 text-nt3 hover:text-nt self-start cursor-pointer"
        >
          <ArrowLeft size={14} /> Back to workspace
        </button>

        <header className="grid gap-6 md:grid-cols-[1fr_minmax(0,22rem)] md:items-end">
          <div>
            <p className="font-mono text-11 uppercase tracking-wider text-npt">Plan &amp; billing</p>
            <h1 className="mt-2 font-serif text-36 tracking-tight">
              {data.plan.name} plan
            </h1>
            <p className="mt-2 text-14 text-nt2">
              {isPaid && data.current_period_end
                ? `Your pass runs until ${fmtDate(data.current_period_end)}${left !== null ? ` (${left} day${left === 1 ? '' : 's'} left)` : ''}. After that you move to Free; nothing is charged automatically.`
                : `${data.plan.minutes} lecture-minutes every 30 days, lectures up to ${data.plan.max_lecture_min} minutes long.`}
            </p>
          </div>

          <section aria-label="Lecture minutes" className="rounded-lg border border-bdr bg-ns p-5">
            <div className="flex items-baseline justify-between">
              <span className="font-serif text-28 tabular-nums">{formatMinutes(data.remaining_minutes)}</span>
              <span className="text-11 text-nt3 tabular-nums">
                {data.used_minutes_this_month} / {data.monthly_minutes_quota} min used
              </span>
            </div>
            <div
              className="mt-3 h-2 w-full overflow-hidden rounded-full bg-ns4"
              role="progressbar"
              aria-valuenow={data.used_minutes_this_month}
              aria-valuemin={0}
              aria-valuemax={data.monthly_minutes_quota}
              aria-label="Lecture minutes used"
            >
              <div className="h-full rounded-full bg-np transition-[width] duration-200" style={{ width: `${pct}%` }} />
            </div>
            <p className="mt-2 text-11 text-nt3">
              {data.remaining_minutes > 0 ? 'left to process' : 'Used up. Buy a pass below to keep going.'}
            </p>
            <button
              onClick={() => navigate('/usage')}
              className="mt-3 inline-flex items-center gap-1.5 text-11 font-medium text-npt hover:underline cursor-pointer"
            >
              <BarChart3 size={13} /> Detailed usage
            </button>
          </section>
        </header>

        {picked && data.payments_enabled && (
          <div className="flex flex-col gap-3 rounded-lg border border-npbr bg-npb p-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-13 text-nt">
              You picked <strong>{picked.name}</strong>: {formatMinutes(picked.minutes)} for {picked.period_days} days at {formatInr(picked.price_inr)}.
            </p>
            <Button variant="primary" className="px-4 py-2 rounded-md text-12" disabled={busy !== null} onClick={() => void choose(picked)}>
              {busy === picked.id ? 'Opening checkout…' : `Pay ${formatInr(picked.price_inr)}`}
            </Button>
          </div>
        )}

        <section aria-labelledby="buy-heading">
          <h2 id="buy-heading" className="font-serif text-22 mb-4">
            {isPaid ? 'Extend or switch your pass' : 'Get more lecture time'}
          </h2>
          <PlanSheet
            plans={plans}
            paymentsEnabled={data.payments_enabled}
            currentPlanId={data.plan_tier}
            busyPlanId={busy}
            onChoose={(p) => void choose(p)}
            highlightId={picked?.id}
          />
          {!data.payments_enabled && (
            <p className="mt-3 text-12 text-nt3">Paid passes open shortly. Your Free minutes work as usual.</p>
          )}
        </section>

        <section aria-labelledby="payments-heading">
          <h2 id="payments-heading" className="font-serif text-22 mb-4 flex items-center gap-2">
            <Receipt size={18} className="text-nt3" aria-hidden="true" /> Payments
          </h2>
          {data.payments.length === 0 ? (
            <p className="rounded-lg border border-dashed border-bdr2 bg-ns px-5 py-6 text-13 text-nt2">
              No payments yet. Passes you buy will show up here with their receipt details.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-bdr bg-ns">
              <table className="w-full text-left text-12">
                <thead className="border-b border-bdr text-11 uppercase tracking-wider text-nt3 font-mono">
                  <tr>
                    <th scope="col" className="px-4 py-2.5 font-medium">Date</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Pass</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Amount</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Method</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
                    <th scope="col" className="px-4 py-2.5 font-medium">Order</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-bdr">
                  {data.payments.map((p) => (
                    <tr key={p.order_id}>
                      <td className="px-4 py-3 whitespace-nowrap tabular-nums">{fmtDate(p.paid_at ?? p.created_at)}</td>
                      <td className="px-4 py-3">{p.plan_name}</td>
                      <td className="px-4 py-3 tabular-nums">
                        {formatInr(p.amount_inr)}
                        {p.refunded_inr > 0 && p.status !== 'refunded' && (
                          <span className="block text-11 text-nt3">{formatInr(p.refunded_inr)} refunded</span>
                        )}
                      </td>
                      <td className="px-4 py-3 uppercase text-11 text-nt2">{p.method ?? '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block rounded border px-1.5 py-0.5 font-mono text-3xs uppercase tracking-wider ${STATUS_COPY[p.status].cls}`}>
                          {STATUS_COPY[p.status].label}
                        </span>
                        {p.status === 'failed' && p.failure_reason && (
                          <span className="block mt-1 text-11 text-nt3">{p.failure_reason}</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono text-11 text-nt3">{p.order_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-11 text-nt3">
            Payments are processed by Razorpay. For a refund or an invoice, email support with the order id.
          </p>
        </section>
      </div>
    </div>
  )
}

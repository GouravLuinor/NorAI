import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Lock, RotateCcw, Smartphone } from 'lucide-react'
import { useAuthStore } from '../stores/useAuthStore'
import { useToastStore } from '../stores/useToastStore'
import { PlanSheet } from '../components/billing/PlanSheet'
import { FaqList } from '../components/marketing/FaqList'
import { PRICING_FAQ } from '../content/faq'
import { usePlans, type Plan } from '../lib/plans'
import { startCheckout } from '../lib/razorpay'
import { friendlyError } from '../lib/errorCopy'
import { LINK_RING } from '../components/ui/shared'
import { usePageMeta } from '../lib/usePageMeta'

export function PricingPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const quota = useAuthStore((s) => s.quota)
  const refreshQuota = useAuthStore((s) => s.refreshQuota)
  const addToast = useToastStore((s) => s.addToast)
  const { plans, payments_enabled } = usePlans()
  const [busy, setBusy] = useState<string | null>(null)

  usePageMeta({
    title: 'Pricing — NorAI | Lecture notes & AI tutor from ₹149',
    description:
      'NorAI pricing in rupees: free for 45 lecture-minutes, Starter ₹149 for 5 hours, Pro ₹449 for 20 hours. One-time 30-day passes, pay by UPI or card, no auto-debit.',
    path: '/pricing',
  })

  const signedIn = Boolean(user && !user.isAnonymous)
  useEffect(() => {
    if (signedIn) void refreshQuota()
  }, [signedIn, refreshQuota])

  const choose = async (plan: Plan) => {
    if (!plan.purchasable) {
      navigate(signedIn ? '/app' : '/signup')
      return
    }
    if (!signedIn) {
      // Come back to billing with the plan pre-selected after sign-up.
      navigate('/signup', { state: { from: { pathname: '/billing', search: `?plan=${plan.id}` } } })
      return
    }
    setBusy(plan.id)
    try {
      const result = await startCheckout(plan.id)
      if (result.status === 'paid') {
        await refreshQuota()
        addToast(`${plan.name} is active. Enjoy your extra lecture time!`, 'success')
        navigate('/billing')
      } else if (result.status === 'pending') {
        addToast(result.message, 'info')
        navigate('/billing')
      } else if (result.status === 'failed') {
        addToast(result.message, 'error')
      }
    } catch (e) {
      addToast(friendlyError(e instanceof Error ? e.message : String(e)), 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div id="main" className="min-h-screen bg-nb text-nt font-sans selection:bg-npb selection:text-npt">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-10 sm:py-14">
        <Link to="/" className={`inline-flex items-center gap-1.5 text-12 text-nt3 hover:text-nt ${LINK_RING}`}>
          <ArrowLeft size={14} aria-hidden="true" /> NorAI home
        </Link>

        <header className="mt-8 max-w-2xl">
          <p className="font-mono text-11 uppercase tracking-wider text-npt">Pricing · in rupees</p>
          <h1 className="mt-2 font-serif text-36 sm:text-44 leading-tight tracking-tight text-balance">
            Pay for the lecture hours you study. Nothing renews.
          </h1>
          <p className="mt-4 text-15 leading-relaxed text-nt2">
            Start free with 45 minutes every month. When the semester gets heavy, buy a 30-day pass with UPI or a card:
            no mandate, no auto-debit, unused minutes carry over.
          </p>
        </header>

        <div className="mt-10">
          <PlanSheet
            plans={plans}
            paymentsEnabled={payments_enabled}
            currentPlanId={signedIn ? quota?.plan_tier : undefined}
            busyPlanId={busy}
            onChoose={choose}
          />
        </div>

        <ul className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-4 text-12 text-nt2">
          <li className="flex items-start gap-2">
            <Smartphone size={15} className="mt-0.5 shrink-0 text-np" aria-hidden="true" />
            UPI, RuPay / Visa / Mastercard, netbanking and wallets via Razorpay.
          </li>
          <li className="flex items-start gap-2">
            <RotateCcw size={15} className="mt-0.5 shrink-0 text-np" aria-hidden="true" />
            Unused pass? Full refund within 7 days of purchase.
          </li>
          <li className="flex items-start gap-2">
            <Lock size={15} className="mt-0.5 shrink-0 text-np" aria-hidden="true" />
            Card and UPI details stay with Razorpay. NorAI never sees them.
          </li>
        </ul>
        {!payments_enabled && (
          <p className="mt-4 text-12 text-nt3">
            Paid passes open shortly. The Free plan is fully available today.
          </p>
        )}

        <section aria-labelledby="pricing-faq" className="mt-16 max-w-3xl">
          <h2 id="pricing-faq" className="font-serif text-28 tracking-tight">Questions about paying</h2>
          <div className="mt-5">
            <FaqList items={PRICING_FAQ} />
          </div>
        </section>
      </div>
    </div>
  )
}

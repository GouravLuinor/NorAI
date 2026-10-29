import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Lock, RotateCcw, Smartphone } from 'lucide-react'
import { useAuthStore } from '../stores/useAuthStore'
import { useToastStore } from '../stores/useToastStore'
import { PlanSheet } from '../components/billing/PlanSheet'
import { Wordmark } from '../components/brand/Wordmark'
import { FaqList } from '../components/marketing/FaqList'
import { FREE_FAQ, FREE_MINUTES, PRICING_FAQ } from '../content/faq'
import { PAGE_META } from '../content/pages'
import { usePlans, type Plan } from '../lib/plans'
import { startCheckout } from '../lib/razorpay'
import { friendlyError } from '../lib/errorCopy'
import { FOCUS_RING, LINK_RING } from '../components/ui/shared'
import { usePageMeta } from '../lib/usePageMeta'

export function PricingPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const quota = useAuthStore((s) => s.quota)
  const refreshQuota = useAuthStore((s) => s.refreshQuota)
  const addToast = useToastStore((s) => s.addToast)
  const { plans, payments_enabled } = usePlans()
  const [busy, setBusy] = useState<string | null>(null)

  usePageMeta(PAGE_META.pricing)

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

  // NorAI launches free-only: the paid-pass sheet below only shows once the
  // backend reports payments_enabled.
  if (!payments_enabled) {
    return (
      <div id="main" className="min-h-screen bg-nb text-nt font-sans">
        <header className="border-b border-bdr">
          <div className="mx-auto max-w-3xl px-4 sm:px-6 py-3 flex items-center justify-between">
            <Link to="/" className={`rounded-sm ${LINK_RING}`} aria-label="NorAI home">
              <Wordmark size="md" />
            </Link>
            <Link to="/" className={`inline-flex items-center gap-1.5 text-15 text-nt2 hover:text-nt ${LINK_RING}`}>
              <ArrowLeft size={15} aria-hidden="true" /> Home
            </Link>
          </div>
        </header>
        <div className="mx-auto max-w-3xl px-4 sm:px-6 py-10 sm:py-14">

          <div>
            <h1 className="font-serif font-semibold text-44 sm:text-[3.5rem] leading-[1.05] tracking-tight text-balance">
              NorAI is free.
            </h1>
            <p className="mt-5 max-w-xl text-18 leading-relaxed text-nt2">
              Every account gets {FREE_MINUTES} lecture-minutes every 30 days, with every feature included. There is
              no paid tier holding anything back, and no card to enter.
            </p>
          </div>

          <dl className="mt-12 divide-y divide-bdr border-y border-bdr">
            {[
              [`${FREE_MINUTES} lecture-minutes`, 'Of new video, every 30 days. A 45-minute class uses 45 of them.'],
              ['Study notes', 'Chapter by chapter, with formulas typeset and the slides that mattered.'],
              ['Revision sheet, quiz, flashcards', 'Built from the same lecture; flashcards come back on a spaced-repetition schedule.'],
              ['AI tutor', 'Answers only from your lecture and links each answer to the moment in the video.'],
              ['Mind map and PDF export', 'For seeing the whole chapter at once, or studying offline.'],
            ].map(([term, body]) => (
              <div key={term} className="grid gap-1 py-5 sm:grid-cols-[14rem_1fr] sm:gap-8">
                <dt className="text-17 font-bold text-nt">{term}</dt>
                <dd className="text-16 leading-relaxed text-nt2">{body}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-10 flex flex-col sm:flex-row sm:items-center gap-4">
            <button
              onClick={() => navigate(signedIn ? '/app' : '/signup')}
              className={`inline-flex items-center justify-center gap-2 rounded-md bg-npf px-6 h-12 text-16 font-bold text-npfg hover:bg-npfh active:translate-y-px cursor-pointer transition-colors ${FOCUS_RING}`}
            >
              {signedIn ? 'Open your library' : 'Create a free account'} <ArrowRight size={17} aria-hidden="true" />
            </button>
            {signedIn && quota && (
              <p className="text-15 text-nt2">
                You have <span className="font-mono font-semibold text-nt">{quota.remaining_minutes}</span> of {quota.monthly_minutes_quota} minutes left.
              </p>
            )}
          </div>

          <section aria-labelledby="free-faq" className="mt-20">
            <h2 id="free-faq" className="font-serif font-semibold text-28 tracking-tight">Questions about the free plan</h2>
            <div className="mt-5">
              <FaqList items={FREE_FAQ} />
            </div>
          </section>
        </div>
      </div>
    )
  }

  return (
    <div id="main" className="min-h-screen bg-nb text-nt font-sans selection:bg-npb selection:text-npt">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-10 sm:py-14">
        <Link to="/" className={`inline-flex items-center gap-1.5 text-12 text-nt3 hover:text-nt ${LINK_RING}`}>
          <ArrowLeft size={14} aria-hidden="true" /> NorAI home
        </Link>

        <header className="mt-8 max-w-2xl">
          <p className="text-13 text-npt">Pricing · in rupees</p>
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

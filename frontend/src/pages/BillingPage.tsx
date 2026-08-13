import { useState, useEffect } from 'react'
import { ArrowLeft, ExternalLink, Sparkles, CreditCard, BarChart3 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/useAuthStore'
import { apiGet } from '../lib/http'
import { Button } from '../components/ui/Button'

interface BillingData {
  plan_tier: 'free' | 'starter' | 'pro'
  subscription_status: string
  monthly_minutes_quota: number
  used_minutes_this_month: number
  remaining_minutes: number
  is_anonymous: boolean
  lemon_squeezy_subscription_id: string | null
  checkout_urls: { starter: string | null; pro: string | null }
  manage_url: string | null
}

const TIER_LABEL: Record<string, string> = {
  free: 'Free Trial',
  starter: 'Starter',
  pro: 'Pro Student',
}

const TIER_DESC: Record<string, string> = {
  free: 'Your first lecture is on us — full output, no card required.',
  starter: '5 lecture-hours / month for regular course capture.',
  pro: '25 lecture-hours / month with priority processing.',
}

const STATUS_LABEL: Record<string, string> = {
  trial: 'Trial',
  active: 'Active',
  cancelled: 'Cancelled',
  past_due: 'Past due',
  paused: 'Paused',
}

function fmtHours(min: number) {
  return min >= 60 ? `${(min / 60).toFixed(min % 60 === 0 ? 0 : 1)} h` : `${min} min`
}

export function BillingPage() {
  const navigate = useNavigate()
  const { user, openAuthModal, refreshQuota } = useAuthStore()
  const [data, setData] = useState<BillingData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    if (!user) {
      setData(null)
      return
    }
    apiGet<BillingData>('/billing')
      .then((d) => {
        if (active) setData(d)
      })
      .catch((e) => {
        if (active) setError(String(e instanceof Error ? e.message : e))
      })
    return () => {
      active = false
    }
  }, [user])

  useEffect(() => {
    if (user) void refreshQuota()
  }, [user, refreshQuota])

  if (!user) {
    return (
      <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center justify-center px-6 py-16">
        <div className="max-w-md w-full text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-npb border border-npbr text-npt font-mono text-11 font-medium mb-6">
            <Sparkles size={12} className="text-np" />
            <span>BILLING</span>
          </div>
          <h1 className="text-28 font-bold font-serif text-nt tracking-tight mb-3">Sign in to manage your plan</h1>
          <p className="text-13 text-nt2 mb-6">Your plan, usage, and subscription live here once you're signed in.</p>
          <div className="flex justify-center gap-3">
            <Button variant="primary" className="px-5 py-2 rounded-md text-12 gap-2" onClick={() => openAuthModal('login')}>
              Log in
            </Button>
            <Button variant="outline" className="px-5 py-2 rounded-md text-12 gap-2 bg-transparent border-bdr2 hover:border-nt4" onClick={() => openAuthModal('signup')}>
              Create account
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center justify-center px-6 py-16">
        <p className="text-13 text-nr mb-4">Couldn't load billing info ({error}).</p>
        <Button variant="outline" className="px-4 py-2 rounded-md text-12 bg-transparent border-bdr2" onClick={() => navigate('/workspace')}>
          <ArrowLeft size={14} /> Back to workspace
        </Button>
      </div>
    )
  }

  if (!data) {
    return (
      <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center justify-center px-6 py-16">
        <div className="text-13 text-nt3">Loading billing…</div>
      </div>
    )
  }

  const pct = Math.min(100, Math.round((data.used_minutes_this_month / Math.max(1, data.monthly_minutes_quota)) * 100))
  const isPaid = data.plan_tier !== 'free'
  const starterUrl = data.checkout_urls?.starter
  const proUrl = data.checkout_urls?.pro

  return (
    <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center py-12 px-6">
      <div className="w-full max-w-3xl flex flex-col gap-8 relative z-10">
        <button
          onClick={() => navigate('/workspace')}
          className="inline-flex items-center gap-1.5 text-12 text-nt3 hover:text-nt self-start cursor-pointer"
        >
          <ArrowLeft size={14} /> Back to workspace
        </button>

        <div className="text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-npb border border-npbr text-npt font-mono text-11 font-medium mb-4">
            <Sparkles size={12} className="text-np" />
            <span>BILLING &amp; PLAN</span>
          </div>
          <h1 className="text-32 font-bold font-serif text-nt tracking-tight mb-2 text-balance">
            {TIER_LABEL[data.plan_tier] ?? 'Free Trial'}
          </h1>
          <p className="text-14 text-nt2 max-w-xl mx-auto">{TIER_DESC[data.plan_tier] ?? ''}</p>
          <div className="mt-3 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-ns2 border border-bdr text-11 text-nt2">
            <CreditCard size={12} className="text-np" />
            Status: <strong className="text-nt font-medium">{STATUS_LABEL[data.subscription_status] ?? data.subscription_status}</strong>
          </div>
        </div>

        {/* Usage card */}
        <section className="rounded-lg bg-ns border border-bdr p-5">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-13 font-semibold text-nt">Monthly usage</h2>
            <span className="text-11 text-nt3 tabular-nums">
              {data.used_minutes_this_month} / {data.monthly_minutes_quota} mins
            </span>
          </div>
          <div
            className="w-full bg-ns4 h-2.5 rounded-full overflow-hidden mb-2"
            role="progressbar"
            aria-valuenow={data.used_minutes_this_month}
            aria-valuemin={0}
            aria-valuemax={data.monthly_minutes_quota}
            aria-label="Monthly lecture minutes used"
          >
            <div className="bg-np h-full rounded-full transition-all duration-300" style={{ width: `${pct}%` }} />
          </div>
          <p className="text-11 text-nt3">
            {data.remaining_minutes > 0
              ? `${fmtHours(data.remaining_minutes)} of processing remaining this month.`
              : 'You\'ve used your monthly allowance — upgrade to keep processing.'}
          </p>
          <button
            onClick={() => navigate('/usage')}
            className="mt-3 inline-flex items-center gap-1.5 text-11 text-np font-medium hover:underline cursor-pointer"
          >
            <BarChart3 size={13} /> See detailed usage &amp; cost
          </button>
        </section>

        {/* Plan actions */}
        <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="rounded-lg bg-ns border border-bdr p-5">
            <h2 className="text-12 font-semibold text-nt uppercase tracking-wider mb-1">Starter</h2>
            <p className="text-11 text-nt3 mb-4">5 lecture-hours / month.</p>
            {starterUrl ? (
              <a href={starterUrl} target="_blank" rel="noreferrer">
                <Button variant={data.plan_tier === 'starter' ? 'surface' : 'primary'} className="w-full py-2 rounded-md text-12 gap-2">
                  {data.plan_tier === 'starter' ? 'Current plan' : 'Choose Starter'} <ExternalLink size={13} />
                </Button>
              </a>
            ) : (
              <Button variant="outline" className="w-full py-2 rounded-md text-12 bg-transparent border-bdr2" onClick={() => navigate('/pricing')}>
                See pricing
              </Button>
            )}
          </div>

          <div className="rounded-lg bg-ns border border-npbr p-5">
            <h2 className="text-12 font-semibold text-nt uppercase tracking-wider mb-1">Pro Student</h2>
            <p className="text-11 text-nt3 mb-4">25 lecture-hours / month, priority queue.</p>
            {proUrl ? (
              <a href={proUrl} target="_blank" rel="noreferrer">
                <Button variant={data.plan_tier === 'pro' ? 'surface' : 'primary'} className="w-full py-2 rounded-md text-12 gap-2">
                  {data.plan_tier === 'pro' ? 'Current plan' : 'Choose Pro'} <ExternalLink size={13} />
                </Button>
              </a>
            ) : (
              <Button variant="outline" className="w-full py-2 rounded-md text-12 bg-transparent border-bdr2" onClick={() => navigate('/pricing')}>
                See pricing
              </Button>
            )}
          </div>
        </section>

        {isPaid && data.manage_url && (
          <section className="rounded-lg bg-ns border border-bdr p-5 flex items-center justify-between gap-4">
            <div>
              <h2 className="text-12 font-semibold text-nt mb-0.5">Manage subscription</h2>
              <p className="text-11 text-nt3">Update billing, cancel, or change plans.</p>
            </div>
            <a href={data.manage_url} target="_blank" rel="noreferrer">
              <Button variant="outline" className="px-4 py-2 rounded-md text-12 gap-2 bg-transparent border-bdr2 hover:border-nt4">
                Manage <ExternalLink size={13} />
              </Button>
            </a>
          </section>
        )}

        <p className="text-center text-10 text-nt4">Payments processed securely by Lemon Squeezy.</p>
      </div>
    </div>
  )
}

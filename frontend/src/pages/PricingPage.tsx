import { useState } from 'react'
import { motion } from 'framer-motion'
import { Check, Sparkles, ShieldCheck, ArrowRight } from 'lucide-react'
import { useAuthStore } from '../stores/useAuthStore'
import { FOCUS_RING } from '../components/ui/shared'

interface PricingPageProps {
  onStartWorkspace?: () => void
}

export function PricingPage({ onStartWorkspace }: PricingPageProps) {
  const [isAnnual, setIsAnnual] = useState(true)
  const { user, openAuthModal } = useAuthStore()

  const plans = [
    {
      id: 'free',
      name: 'Free Trial',
      tagline: 'Process your first lecture free, no card required',
      priceMonthly: '$0',
      priceAnnual: '$0',
      period: 'forever',
      minutes: '15 Minutes (1 Video)',
      features: [
        '1 Lecture Video (≤15 mins)',
        'Full Chapter Study Notes',
        'Revision Cheat-Sheet & PDF export',
        'Assessment & Interactive Quizzes',
        '3D Flashcards Deck',
        'Grounded AI Tutor Chat',
      ],
      cta: 'Try 1 Video Free',
      popular: false,
    },
    {
      id: 'starter',
      name: 'Starter',
      tagline: 'Ideal for regular course capture & weekly classes',
      priceMonthly: '$11',
      priceAnnual: '$9',
      period: 'per month',
      minutes: '5 Lecture-Hours / mo',
      features: [
        '5 Lecture-Hours processed / mo',
        'Unlimited Chapter Notes & Quizzes',
        'Full PDF & Revision Cheat-Sheet Export',
        'Concept Map / Mind Map Visualization',
        'Full Tutor RAG Chat with Timestamp Citations',
        'Standard Processing Queue',
      ],
      cta: 'Start 7-Day Free Trial',
      popular: false,
    },
    {
      id: 'pro',
      name: 'Pro Student',
      tagline: 'For heavy course loads, exams, & research study',
      priceMonthly: '$29',
      priceAnnual: '$23',
      period: 'per month',
      minutes: '25 Lecture-Hours / mo',
      features: [
        '25 Lecture-Hours processed / mo',
        'Everything in Starter Plan',
        'Priority Pipeline Processing Queue',
        'Unlimited Tutor Chat History Sync',
        'Multi-Lecture Comparative Tutor',
        'Dedicated Email & Discord Support',
      ],
      cta: 'Get Pro Access',
      popular: true,
    },
  ]

  const handlePlanSelect = () => {
    if (!user) {
      openAuthModal('signup')
    } else if (onStartWorkspace) {
      onStartWorkspace()
    }
  }

  return (
    <div id="main" className="min-h-screen bg-nb text-nt font-sans py-12 px-4 sm:px-6 lg:px-8 selection:bg-npb selection:text-npt">
      {/* Header */}
      <div className="max-w-4xl mx-auto text-center mb-12">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-npb border border-npbr text-npt font-mono text-11 font-medium mb-4">
          <Sparkles size={12} className="text-np" />
          <span>TRANSPARENT STUDENT PRICING</span>
        </div>

        <h1 className="text-36 sm:text-44 font-bold font-serif text-nt tracking-tight mb-3 text-balance">
          Pricing Built for the Semester
        </h1>
        <p className="text-15 text-nt2 max-w-2xl mx-auto font-sans">
          Start with a 100% free video trial. Upgrade anytime to process your full course schedule.
        </p>

        {/* Annual / Monthly Toggle */}
        <div className="flex items-center justify-center gap-3 mt-8">
          <span className={`text-12 font-medium font-display uppercase ${!isAnnual ? 'text-nt font-bold' : 'text-nt3'}`}>
            Monthly Billing
          </span>
          <button
            onClick={() => setIsAnnual(!isAnnual)}
            role="switch"
            aria-checked={isAnnual}
            aria-label="Billing period"
            className={`relative w-12 h-6 bg-ns2 border border-bdr rounded-full p-0.5 transition-colors cursor-pointer hover:border-nt4 ${FOCUS_RING}`}
          >
            <motion.div
              animate={{ x: isAnnual ? 24 : 0 }}
              transition={{ type: 'spring', stiffness: 500, damping: 30 }}
              className="w-4 h-4 bg-np rounded-full shadow-xs"
            />
          </button>
          <span className={`text-12 font-medium font-display uppercase ${isAnnual ? 'text-nt font-bold' : 'text-nt3'}`}>
            Annual Billing
          </span>
          <span className="px-2 py-0.5 rounded bg-ngb text-ngt font-mono text-3xs font-bold uppercase">
            SAVE 20%
          </span>
        </div>
      </div>

      {/* Pricing Cards Grid */}
      <h2 className="sr-only">Plans and pricing</h2>
      <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6 mb-16">
        {plans.map((plan, idx) => (
          <motion.div
            key={plan.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.1 }}
            className={`relative flex flex-col justify-between rounded-lg p-6 border transition-[border-color,transform] ${
              plan.popular
                ? 'bg-ns border-np shadow-bp scale-102 z-10'
                : 'bg-ns border-bdr shadow-ev1 hover:border-bdr2'
            }`}
          >
            {plan.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded bg-np text-npfg font-display text-3xs font-bold tracking-widest uppercase shadow-xs">
                Most Popular
              </div>
            )}

            <div>
              <div className="mb-6">
                <h3 className="text-20 font-bold font-serif text-nt mb-1">{plan.name}</h3>
                <p className="text-12 text-nt2 min-h-[36px] font-sans">{plan.tagline}</p>
              </div>

              <div className="mb-6 pb-6 border-b border-bdr">
                <div className="flex items-baseline gap-1">
                  <span className="text-36 font-bold font-serif text-nt tabular-nums">
                    {isAnnual ? plan.priceAnnual : plan.priceMonthly}
                  </span>
                  <span className="text-12 text-nt3">/{plan.period}</span>
                </div>
                <div className="mt-2 text-11 font-medium font-mono text-npt bg-npb px-2.5 py-1 rounded inline-block">
                  ⚡ {plan.minutes}
                </div>
              </div>

              <ul className="space-y-3 mb-8 text-12 text-nt font-sans">
                {plan.features.map((feat, fIdx) => (
                  <li key={fIdx} className="flex items-start gap-2.5">
                    <Check size={14} className="text-ng shrink-0 mt-0.5" />
                    <span>{feat}</span>
                  </li>
                ))}
              </ul>
            </div>

            <button
              onClick={() => handlePlanSelect()}
              className={`w-full py-2.5 px-4 rounded font-display text-11 font-semibold uppercase tracking-wider flex items-center justify-center gap-2 transition-[background-color,transform] cursor-pointer ${
                plan.popular
                  ? 'bg-np hover:bg-nph text-npfg shadow-bp active:translate-y-0.5'
                  : 'bg-ns2 hover:bg-ns3 border border-bdr text-nt'
              }`}
            >
              <span>{plan.cta}</span>
              <ArrowRight size={14} />
            </button>
          </motion.div>
        ))}
      </div>

      {/* Guarantee & Trust Banner */}
      <div className="max-w-3xl mx-auto rounded-lg bg-ns border border-bdr p-6 text-center shadow-ev1 mb-16">
        <div className="flex items-center justify-center gap-2 text-np mb-2">
          <ShieldCheck size={20} />
          <span className="text-14 font-bold font-serif">No-Risk 7-Day Money-Back Guarantee</span>
        </div>
        <p className="text-12 text-nt2 font-sans">
          Cancel anytime with 1 click. If NorAI doesn’t save you hours of study time in your first week, get a full refund.
        </p>
      </div>
    </div>
  )
}

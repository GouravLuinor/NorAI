/**
 * Application feature flags and defaults.
 * Non-destructively controls feature availability across UI and routing.
 */
export const ENABLE_PAYMENTS = import.meta.env.VITE_ENABLE_PAYMENTS === 'true'
export const DEFAULT_TRIAL_QUOTA_MINUTES = 45

export const PRIMARY_DEMO_LECTURE_ID = 'ab648382-638f-4dde-b7c1-4007a2e638bb'

export const DEMO_LECTURES_CONFIG = [
  {
    id: 'ab648382-638f-4dde-b7c1-4007a2e638bb',
    title: 'Foundations of Neural Networks & Deep Learning',
    category: 'Computer Science & AI',
    chapterCount: 4,
    duration: '18 mins',
    summary: 'Perceptrons, backpropagation gradients, loss surfaces, and activation architectures with mathematical derivations.',
    badge: 'Deep Learning',
  },
  {
    id: 'e54d7376-0e7b-472a-9ca6-9b21ad0b2710',
    title: 'Foundations of Economic Thinking: Incentives & Opportunity Cost',
    category: 'Economics & Market Theory',
    chapterCount: 6,
    duration: '19 mins',
    summary: 'Marginal utility, trade-offs, market equilibrium, and price elasticity with visual chapter charts.',
    badge: 'Economics',
  },
  {
    id: '506dd685-05f9-43df-8d09-5b944c7392f5',
    title: 'The Rise of Open-Weights Models & Local Deployment',
    category: 'Modern AI Engineering',
    chapterCount: 3,
    duration: '10 mins',
    summary: 'Open-weights architecture, quantization techniques, local inference benchmarks, and system tradeoffs.',
    badge: 'AI Systems',
  },
] as const

export const DEMO_LECTURE_IDS: readonly string[] = DEMO_LECTURES_CONFIG.map((d) => d.id)


/**
 * Application feature flags and defaults.
 * Non-destructively controls feature availability across UI and routing.
 */
import { FREE_MINUTES } from '../content/faq'

export const DEFAULT_TRIAL_QUOTA_MINUTES = FREE_MINUTES

export const PRIMARY_DEMO_LECTURE_ID = 'ab648382-638f-4dde-b7c1-4007a2e638bb'

export const DEMO_LECTURES_CONFIG = [
  {
    id: 'ab648382-638f-4dde-b7c1-4007a2e638bb',
    title: 'Foundations of Neural Networks & Deep Learning',
    category: 'Computer Science & AI',
    chapterCount: 4,
    duration: '18 min',
    summary: 'How a network reads a handwritten digit: the input layer, hidden layers that build up features, weights, biases and activations, and the linear algebra underneath.',
    badge: 'Deep Learning',
  },
  {
    id: 'e54d7376-0e7b-472a-9ca6-9b21ad0b2710',
    title: 'Foundations of Economic Thinking: Incentives & Opportunity Cost',
    category: 'Economics & Market Theory',
    chapterCount: 6,
    duration: '19 min',
    summary: 'Incentives and opportunity cost, how prices coordinate a market, what price controls and taxes distort, and how wages are set.',
    badge: 'Economics',
  },
  {
    id: '506dd685-05f9-43df-8d09-5b944c7392f5',
    title: 'The Rise of Open-Weights Models & Local Deployment',
    category: 'Modern AI Engineering',
    chapterCount: 3,
    duration: '10 min',
    summary: 'Why open-weights models took off, how the main players differ, and how they compare on benchmarks, latency and usability.',
    badge: 'AI Systems',
  },
] as const

export const DEMO_LECTURE_IDS: readonly string[] = DEMO_LECTURES_CONFIG.map((d) => d.id)


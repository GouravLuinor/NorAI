/**
 * Application feature flags and defaults.
 * Non-destructively controls feature availability across UI and routing.
 */
import { FREE_MINUTES } from '../content/faq'

export const DEFAULT_TRIAL_QUOTA_MINUTES = FREE_MINUTES

export const PRIMARY_DEMO_LECTURE_ID = '8821152f-f6de-49e9-a885-0adaac6ba4cb'

export const DEMO_LECTURES_CONFIG = [
  {
    id: '8821152f-f6de-49e9-a885-0adaac6ba4cb',
    title: 'Algorithms and Computation',
    category: 'Computer Science & Algorithms',
    chapterCount: 9,
    duration: '46 min',
    summary: 'What an algorithm is, why correctness needs a proof, and how to argue efficiency: induction, asymptotic running times and the word RAM model, using the birthday paradox as a running example.',
    badge: 'Algorithms',
  },
  {
    id: '01b04840-fddb-4b31-a211-7bb28f189621',
    title: 'Introduction to Differentiation',
    category: 'Mathematics & Calculus',
    chapterCount: 8,
    duration: '52 min',
    summary: 'The derivative from first principles: secant lines becoming tangents, the limit definition, differentiating 1/x and power functions, and a geometry problem worked from scratch.',
    badge: 'Calculus',
  },
  {
    id: 'c8cab2e7-52b7-4cdc-8386-f440d02f3f45',
    title: 'Newtonian Mechanics: Motion and Calculus',
    category: 'Physics & Mechanics',
    chapterCount: 10,
    duration: '73 min',
    summary: 'Position, velocity and acceleration, the calculus that connects them, constant-acceleration equations, and a method for setting up mechanics problems without guessing.',
    badge: 'Mechanics',
  },
  {
    id: '2e983ee0-ae41-4910-9239-099b34dee04c',
    title: 'Finance and Insurance in the Modern Economy',
    category: 'Economics & Finance',
    chapterCount: 10,
    duration: '74 min',
    summary: 'Why finance and insurance are forces in the economy: risk and portfolio theory, efficient markets, behavioral finance, debt and equity, banking, and the subprime crisis.',
    badge: 'Finance',
  },
  {
    id: '5f7225bf-ba41-46b9-aea9-da91c032b515',
    title: 'The Civil War and Reconstruction in American Memory',
    category: 'History & Humanities',
    chapterCount: 10,
    duration: '53 min',
    summary: 'Why the Civil War and Reconstruction still shape American memory: Yale\u2019s slavery project, how institutions confront their past, the founders\u2019 compromises, and an unfinished social contract.',
    badge: 'History',
  },
] as const

export const DEMO_LECTURE_IDS: readonly string[] = DEMO_LECTURES_CONFIG.map((d) => d.id)


/**
 * Title / description / path for every public page. Read by the pages
 * (usePageMeta) and by the build (vite-plugin-seo: sitemap, llms.txt; and
 * scripts/prerender.mjs: per-route static <head>), so crawlers that never run
 * JS see the same metadata as the live app. Dependency-free on purpose.
 */
import { FREE_MINUTES } from './faq.ts'

export interface PageMeta {
  path: string
  title: string
  description: string
  /** sitemap.xml priority; omitted pages are left out of the sitemap. */
  priority?: string
}

export const PAGE_META = {
  home: {
    path: '/',
    title: 'NorAI: Turn lecture videos into notes, quizzes & an AI tutor',
    description:
      'Upload a lecture recording, PDF or slide deck. NorAI writes chapter notes, a quiz and flashcards, plus an AI tutor that answers from your material. Free.',
    priority: '1.0',
  },
  pricing: {
    path: '/pricing',
    title: `NorAI is free: ${FREE_MINUTES} lecture-minutes a month, every feature`,
    description: `NorAI is free. Every account gets ${FREE_MINUTES} lecture-minutes every 30 days with notes, quizzes, flashcards and the AI tutor included. No credit card.`,
    priority: '0.8',
  },
  signup: {
    path: '/signup',
    title: 'Create your free NorAI account',
    description: `Sign up free and turn your first lecture video into study notes, a quiz, flashcards and an AI tutor. ${FREE_MINUTES} minutes a month, no card.`,
    priority: '0.6',
  },
  login: {
    path: '/login',
    title: 'Log in to NorAI',
    description: 'Log in to your NorAI library of lecture notes, quizzes, flashcards and your AI tutor.',
    priority: '0.3',
  },
  demoAlgorithms: {
    path: '/demo/algorithms-and-computation',
    title: 'MIT 6.006: Algorithms and Computation — Lecture Notes, Quiz & AI Tutor',
    description:
      'Complete study pack for MIT 6.006 Lecture 1. Mathematical induction, correctness proofs, asymptotic running times, word-RAM model, and the birthday problem.',
    priority: '0.9',
  },
  demoCalculus: {
    path: '/demo/calculus-differentiation',
    title: 'MIT 18.01: Differentiation & Limits — Lecture Notes, Quiz & AI Tutor',
    description:
      'Complete study pack for MIT 18.01 Single Variable Calculus Lecture 1. The derivative from first principles, limit definitions, secant to tangent slopes, and power rules.',
    priority: '0.9',
  },
  demoMechanics: {
    path: '/demo/newtonian-mechanics',
    title: 'Yale PHYS 200: Newtonian Mechanics — Lecture Notes, Quiz & AI Tutor',
    description:
      'Complete study pack for Yale PHYS 200 Lecture 1. Kinematics, position, velocity, acceleration, calculus connections, and systematic problem-solving methods.',
    priority: '0.9',
  },
  demoFinance: {
    path: '/demo/financial-markets',
    title: 'Yale ECON 252: Financial Markets — Lecture Notes, Quiz & AI Tutor',
    description:
      'Complete study pack for Yale ECON 252 Lecture 1. Risk pooling, insurance theory, Modern Portfolio Theory, debt vs. equity, behavioral finance, and banking crises.',
    priority: '0.9',
  },
  demoCivilWar: {
    path: '/demo/civil-war-reconstruction',
    title: 'Yale HIST 119: Civil War & Reconstruction — Lecture Notes, Quiz & AI Tutor',
    description:
      'Complete study pack for Yale HIST 119 Lecture 1 with Professor David Blight. Constitutional compromises, sectionalism, memory, and the unfinished revolution of Reconstruction.',
    priority: '0.9',
  },
} satisfies Record<string, PageMeta>

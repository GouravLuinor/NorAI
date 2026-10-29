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
      'Paste a YouTube lecture or upload a recording. NorAI writes chapter notes, a quiz and flashcards, plus an AI tutor that answers from your lecture. Free.',
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
} satisfies Record<string, PageMeta>

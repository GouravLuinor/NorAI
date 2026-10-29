/**
 * SSR entry used only by scripts/prerender.mjs at build time: renders a
 * public page to static HTML for crawlers and for a no-spinner first paint.
 * Pages rendered here must not depend on auth or fetched data for their
 * markup (they render the signed-out, fallback-data state).
 */
import { renderToString } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom'
import { LandingPage } from './pages/LandingPage'
import { PricingPage } from './pages/PricingPage'

const PAGES: Record<string, () => React.ReactElement> = {
  '/': () => <LandingPage onStartWorkspace={() => {}} />,
  '/pricing': () => <PricingPage />,
}

export const PRERENDER_PATHS = Object.keys(PAGES)

export function renderPage(path: string): string {
  const page = PAGES[path]
  if (!page) throw new Error(`No prerender page for ${path}`)
  return renderToString(<StaticRouter location={path}>{page()}</StaticRouter>)
}

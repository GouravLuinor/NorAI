/**
 * Build-time SEO / AEO / GEO for the SPA.
 *
 * AI answer-engine crawlers (GPTBot, ClaudeBot, PerplexityBot, …) and some
 * search bots do not execute JavaScript, so a client-rendered page is empty to
 * them. This plugin puts the product's answer-style content into the static
 * HTML and emits the crawler files, all from the same sources the pages render
 * (src/content/faq.ts, src/content/plans.ts) so copy never drifts:
 *
 *   index.html  JSON-LD (Organization, WebSite, SoftwareApplication with INR
 *               offers, FAQPage) + a <noscript> summary + absolute OG URLs
 *   robots.txt  allow all (incl. AI crawlers), disallow private app routes
 *   sitemap.xml public routes
 *   llms.txt    plain-markdown product summary for LLMs (llmstxt.org)
 *
 * Absolute URLs come from VITE_SITE_URL (e.g. https://norai.in). Without it
 * the build still works but warns, and URLs stay relative.
 */
import type { Plugin } from 'vite'
import { PRICING_FAQ, PRODUCT_FAQ, type FaqItem } from './src/content/faq.ts'
import { FALLBACK_PLANS } from './src/content/plans.ts'

const NAME = 'NorAI'
const TAGLINE = 'Turn lecture videos into notes, quizzes & an AI tutor'
const DESCRIPTION =
  'Paste a YouTube lecture or upload a class recording. NorAI writes chapter-wise study notes, a revision sheet, quiz and flashcards, plus a tutor that answers from your lecture. Free to start; passes from ₹149.'

/** Same list the landing page renders in its FAQ section. */
const HOME_FAQ: FaqItem[] = [...PRODUCT_FAQ, PRICING_FAQ[0], PRICING_FAQ[1]]

const PUBLIC_ROUTES = [
  { path: '/', priority: '1.0' },
  { path: '/pricing', priority: '0.9' },
  { path: '/signup', priority: '0.6' },
  { path: '/login', priority: '0.3' },
]

const PRIVATE_PREFIXES = ['/app', '/billing', '/usage', '/courses', '/process/', '/print', '/reset-password', '/api/']

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

/** JSON inside <script> must not be able to close the tag. */
const jsonLd = (data: unknown) => JSON.stringify(data).replace(/</g, '\\u003c')

function structuredData(site: string) {
  const paid = FALLBACK_PLANS.plans
  return [
    {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: NAME,
      url: `${site}/`,
      logo: `${site}/favicon.svg`,
    },
    {
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: NAME,
      url: `${site}/`,
      inLanguage: 'en-IN',
    },
    {
      '@context': 'https://schema.org',
      '@type': 'SoftwareApplication',
      name: NAME,
      applicationCategory: 'EducationalApplication',
      operatingSystem: 'Web browser',
      url: `${site}/`,
      image: `${site}/og.jpg`,
      description: DESCRIPTION,
      audience: { '@type': 'EducationalAudience', educationalRole: 'student' },
      offers: paid.map((p) => ({
        '@type': 'Offer',
        name: `${p.name} (${p.period_days} days)`,
        price: String(p.price_inr),
        priceCurrency: 'INR',
        description: p.features.join('; '),
        url: `${site}/pricing`,
      })),
    },
    {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: HOME_FAQ.map((f) => ({
        '@type': 'Question',
        name: f.q,
        acceptedAnswer: { '@type': 'Answer', text: f.a },
      })),
    },
  ]
}

function noscriptSummary(site: string) {
  const plans = FALLBACK_PLANS.plans
    .map((p) => `<li><strong>${esc(p.name)}</strong>: ₹${p.price_inr} for ${p.period_days} days. ${esc(p.features.join('; '))}.</li>`)
    .join('')
  const faq = HOME_FAQ.map((f) => `<h3>${esc(f.q)}</h3><p>${esc(f.a)}</p>`).join('')
  return `<noscript>
      <main>
        <h1>${esc(NAME)}: ${esc(TAGLINE)}</h1>
        <p>${esc(DESCRIPTION)}</p>
        <h2>Pricing</h2>
        <ul>${plans}</ul>
        <p><a href="${site}/pricing">Full pricing</a> · <a href="${site}/signup">Start free</a></p>
        <h2>Frequently asked questions</h2>
        ${faq}
        <p>NorAI needs JavaScript to run the study workspace.</p>
      </main>
    </noscript>`
}

function llmsTxt(site: string) {
  const plans = FALLBACK_PLANS.plans
    .map((p) => `- **${p.name}**: ₹${p.price_inr} for ${p.period_days} days. ${p.features.join('; ')}.`)
    .join('\n')
  const faq = [...PRODUCT_FAQ, ...PRICING_FAQ].map((f) => `### ${f.q}\n\n${f.a}`).join('\n\n')
  return `# ${NAME}

> ${NAME} turns a lecture video into chapter-wise study notes, a revision sheet, a quiz, flashcards and an AI tutor that answers only from that lecture. Built for college students in India; prices in rupees.

## Key pages

- [Home](${site}/): what NorAI does, demo lectures, how it works
- [Pricing](${site}/pricing): plans in INR and payment FAQ (UPI, cards, netbanking; one-time 30-day passes, no auto-debit)
- [Sign up](${site}/signup): free account, 45 lecture-minutes every 30 days

## Plans

${plans}

## FAQ

${faq}
`
}

function robotsTxt(site: string) {
  const disallow = PRIVATE_PREFIXES.map((p) => `Disallow: ${p}`).join('\n')
  return `# NorAI — public marketing pages are open to search and AI crawlers.
User-agent: *
Allow: /
${disallow}

Sitemap: ${site}/sitemap.xml
`
}

function sitemapXml(site: string) {
  const today = new Date().toISOString().slice(0, 10)
  const urls = PUBLIC_ROUTES.map(
    (r) => `  <url><loc>${site}${r.path}</loc><lastmod>${today}</lastmod><priority>${r.priority}</priority></url>`,
  ).join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`
}

export function seoPlugin(siteUrl: string | undefined): Plugin {
  const site = (siteUrl ?? '').replace(/\/$/, '')
  return {
    name: 'norai-seo',
    configResolved(config) {
      if (config.command === 'build' && !site) {
        config.logger.warn('[norai-seo] VITE_SITE_URL is not set: canonical/OG/sitemap URLs will be relative.')
      }
    },
    transformIndexHtml(html) {
      const scripts = structuredData(site)
        .map((d) => `<script type="application/ld+json">${jsonLd(d)}</script>`)
        .join('\n    ')
      return html
        .replaceAll('__SITE_URL__', site)
        .replace('</head>', `    ${scripts}\n  </head>`)
        .replace('<div id="root"></div>', `<div id="root"></div>\n    ${noscriptSummary(site)}`)
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'robots.txt', source: robotsTxt(site) })
      this.emitFile({ type: 'asset', fileName: 'sitemap.xml', source: sitemapXml(site) })
      this.emitFile({ type: 'asset', fileName: 'llms.txt', source: llmsTxt(site) })
    },
    configureServer(server) {
      // Serve the generated files in dev too, so they can be checked locally.
      const files: Record<string, [string, () => string]> = {
        '/robots.txt': ['text/plain', () => robotsTxt(site || 'http://localhost:5173')],
        '/sitemap.xml': ['application/xml', () => sitemapXml(site || 'http://localhost:5173')],
        '/llms.txt': ['text/plain', () => llmsTxt(site || 'http://localhost:5173')],
      }
      server.middlewares.use((req, res, next) => {
        const hit = req.url ? files[req.url] : undefined
        if (!hit) return next()
        res.setHeader('Content-Type', `${hit[0]}; charset=utf-8`)
        res.end(hit[1]())
      })
    },
  }
}

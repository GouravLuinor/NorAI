/**
 * Build-time SEO / AEO / GEO for the SPA.
 *
 * AI answer-engine crawlers (GPTBot, ClaudeBot, PerplexityBot, …) and some
 * search bots do not execute JavaScript, so a client-rendered page is empty to
 * them. This plugin puts the product's answer-style content into the static
 * HTML and emits the crawler files, all from the same sources the pages render
 * (src/content/faq.ts, src/content/pages.ts) so copy never drifts:
 *
 *   index.html  JSON-LD (Organization, WebSite, SoftwareApplication with a
 *               free Offer, FAQPage) + a <noscript> summary + absolute OG URLs
 *   robots.txt  allow all (incl. AI crawlers), disallow private app routes
 *   sitemap.xml public routes
 *   llms.txt    plain-markdown product summary for LLMs (llmstxt.org)
 *
 * scripts/prerender.mjs then renders each public page into its own HTML file
 * after the build, swapping in that page's <head> and FAQ (see routeHead()).
 *
 * Absolute URLs come from VITE_SITE_URL (e.g. https://norai.app). Without it
 * the build still works but warns, and URLs stay relative.
 */
import type { Plugin } from 'vite'
import { FREE_FAQ, FREE_MINUTES, HOME_FAQ, PRODUCT_FAQ, type FaqItem } from './src/content/faq.ts'
import { PAGE_META, type PageMeta } from './src/content/pages.ts'

const NAME = 'NorAI'
const TAGLINE = 'Turn lecture videos into notes, quizzes & an AI tutor'
const DESCRIPTION = PAGE_META.home.description

/** FAQ shown (and marked up as FAQPage) on each public route. */
export const ROUTE_FAQ: Record<string, FaqItem[]> = {
  '/': HOME_FAQ,
  '/pricing': FREE_FAQ,
}

const PRIVATE_PREFIXES = ['/app', '/billing', '/usage', '/courses', '/process/', '/print', '/reset-password', '/forgot-password', '/api/', '/_prerender/']

export const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

/** JSON inside <script> must not be able to close the tag. */
const jsonLd = (data: unknown) => JSON.stringify(data).replace(/</g, '\\u003c')

const ldScript = (data: unknown, id?: string) =>
  `<script type="application/ld+json"${id ? ` id="${id}"` : ''}>${jsonLd(data)}</script>`

export function faqJsonLd(items: FaqItem[]) {
  return ldScript(
    {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: items.map((f) => ({
        '@type': 'Question',
        name: f.q,
        acceptedAnswer: { '@type': 'Answer', text: f.a },
      })),
    },
    'ld-faq',
  )
}

function structuredData(site: string) {
  return [
    {
      '@context': 'https://schema.org',
      '@type': 'Organization',
      name: NAME,
      url: `${site}/`,
      logo: `${site}/icon-512.png`,
    },
    {
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      name: NAME,
      url: `${site}/`,
      inLanguage: 'en',
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
      isAccessibleForFree: true,
      offers: {
        '@type': 'Offer',
        name: 'Free',
        price: '0',
        priceCurrency: 'USD',
        description: `${FREE_MINUTES} lecture-minutes every 30 days, every feature included`,
        url: `${site}/pricing`,
      },
    },
  ]
}

/**
 * The route-specific part of <head>: title, description, canonical, OG/Twitter
 * text. index.html carries the home values; prerender.mjs swaps them per route.
 */
export function routeHead(site: string, meta: PageMeta) {
  const url = `${site}${meta.path}`
  return [
    `<title>${esc(meta.title)}</title>`,
    `<meta name="description" content="${esc(meta.description)}" />`,
    `<link rel="canonical" href="${url}" />`,
    `<meta property="og:title" content="${esc(meta.title)}" />`,
    `<meta property="og:description" content="${esc(meta.description)}" />`,
    `<meta property="og:url" content="${url}" />`,
    `<meta name="twitter:title" content="${esc(meta.title)}" />`,
    `<meta name="twitter:description" content="${esc(meta.description)}" />`,
  ].join('\n    ')
}

function noscriptSummary(site: string) {
  const faq = HOME_FAQ.map((f) => `<h3>${esc(f.q)}</h3><p>${esc(f.a)}</p>`).join('')
  return `<noscript>
      <main>
        <h1>${esc(NAME)}: ${esc(TAGLINE)}</h1>
        <p>${esc(DESCRIPTION)}</p>
        <p><a href="${site}/pricing">It's free: ${FREE_MINUTES} lecture-minutes a month</a> · <a href="${site}/signup">Start free</a></p>
        <h2>Frequently asked questions</h2>
        ${faq}
        <p>NorAI needs JavaScript to run the study workspace.</p>
      </main>
    </noscript>`
}

function llmsTxt(site: string) {
  const faq = [...PRODUCT_FAQ, ...FREE_FAQ].map((f) => `### ${f.q}\n\n${f.a}`).join('\n\n')
  return `# ${NAME}

> ${NAME} turns a lecture video into chapter-by-chapter study notes, a revision sheet, a quiz, flashcards, a mind map and an AI tutor that answers only from that lecture, with timestamps back to the video. It is free: ${FREE_MINUTES} lecture-minutes every 30 days per account, no credit card.

## Key pages

- [Home](${site}/): what NorAI does, demo lectures, how it works
- [Free plan](${site}/pricing): what the free allowance includes and how lecture-minutes work
- [Sign up](${site}/signup): free account, ${FREE_MINUTES} lecture-minutes every 30 days

## What you get from one lecture

- Study notes, chapter by chapter, in the order the lecture taught them, with formulas and the key slides
- A revision sheet of takeaways and definitions per chapter
- A quiz (multiple choice and true/false) linked back to the notes
- Flashcards with spaced-repetition review, exportable to Anki
- A mind map of each chapter
- An AI tutor grounded in the lecture transcript and slides that cites timestamps

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
  const urls = Object.values(PAGE_META as Record<string, PageMeta>)
    .filter((p) => p.priority)
    .map((r) => `  <url><loc>${site}${r.path}</loc><lastmod>${today}</lastmod><priority>${r.priority}</priority></url>`)
    .join('\n')
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
      const scripts = [...structuredData(site).map((d) => ldScript(d)), faqJsonLd(ROUTE_FAQ['/'])].join('\n    ')
      return html
        .replace('<!--seo:head-->', routeHead(site, PAGE_META.home))
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

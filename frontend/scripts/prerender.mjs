/**
 * Post-build prerender (runs after `vite build`, see package.json "build").
 *
 * For each public route it writes dist/_prerender/<name>.html: the built
 * index.html with that route's <head> (title, description, canonical, OG,
 * FAQPage JSON-LD) and, for pages in src/prerender.tsx, the page's real
 * markup rendered with React. The backend serves these files for HTML
 * navigations to those routes (backend/main.py spa_middleware); every other
 * route keeps the plain dist/index.html shell.
 *
 * The rendered markup sits in #prerender just before an empty #root, which a
 * CSS rule hides while #prerender exists. When React mounts the real page
 * (#main inside #root) a tiny inline script drops #prerender, so visitors see
 * the finished page immediately and crawlers that never run JS get the full
 * content. A route that fails to render falls back to head-only, never a
 * failed build.
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { JSDOM } from 'jsdom'
import { createServer, loadEnv } from 'vite'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = resolve(root, 'dist')

// Browser globals the app's modules touch at import time (stores, supabase).
const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', { url: 'http://localhost/' })
for (const key of ['window', 'document', 'localStorage', 'sessionStorage', 'HTMLElement', 'Node', 'matchMedia']) {
  Object.defineProperty(globalThis, key, { value: dom.window[key], configurable: true, writable: true })
}
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
dom.window.matchMedia ??= () => ({ matches: false, addEventListener() {}, removeEventListener() {} })

const SWAP_STYLE = '<style>#prerender+#root{display:none}</style>'
// Must sit after #root: it runs while the body is still parsing.
const SWAP_SCRIPT = `<script>(function(){var p=document.getElementById('prerender'),r=document.getElementById('root');if(!p||!r)return;var o=new MutationObserver(function(){if(r.querySelector('#main')){p.remove();o.disconnect()}});o.observe(r,{childList:true,subtree:true})})()</script>`

const vite = await createServer({
  root,
  configFile: resolve(root, 'vite.config.ts'),
  server: { middlewareMode: true, hmr: false },
  appType: 'custom',
  logLevel: 'error',
})

let failed = 0
try {
  const site = (loadEnv('production', resolve(root, '..'), 'VITE_').VITE_SITE_URL ?? '').replace(/\/$/, '')
  const seo = await vite.ssrLoadModule('/vite-plugin-seo.ts')
  const { PAGE_META } = await vite.ssrLoadModule('/src/content/pages.ts')
  const { renderPage, PRERENDER_PATHS } = await vite.ssrLoadModule('/src/prerender.tsx')

  const template = readFileSync(resolve(dist, 'index.html'), 'utf8')
  const homeHead = seo.routeHead(site, PAGE_META.home)
  if (!template.includes(homeHead)) throw new Error('dist/index.html has no seo head block; was the seo plugin skipped?')

  mkdirSync(resolve(dist, '_prerender'), { recursive: true })
  for (const [name, meta] of Object.entries(PAGE_META)) {
    let html = template.replace(homeHead, seo.routeHead(site, meta))
    const faq = seo.ROUTE_FAQ[meta.path]
    html = html.replace(/<script type="application\/ld\+json" id="ld-faq">[\s\S]*?<\/script>/, faq ? seo.faqJsonLd(faq) : '')

    let body = ''
    if (PRERENDER_PATHS.includes(meta.path)) {
      try {
        body = renderPage(meta.path)
      } catch (err) {
        failed++
        console.warn(`[prerender] ${meta.path}: render failed, head only (${err?.message ?? err})`)
      }
    }
    // The noscript summary is the home page's; rendered markup replaces it.
    html = html.replace(/<noscript>[\s\S]*?<\/noscript>/, (body || meta.path !== '/') ? '' : '$&')
    if (body) {
      html = html
        .replace('<div id="root"></div>', `<div id="prerender">${body}</div><div id="root"></div>${SWAP_SCRIPT}`)
        .replace('</head>', `    ${SWAP_STYLE}\n  </head>`)
    }
    writeFileSync(resolve(dist, '_prerender', `${name}.html`), html)
    console.log(`[prerender] ${meta.path} -> _prerender/${name}.html${body ? ` (${(body.length / 1024).toFixed(0)} KB markup)` : ' (head only)'}`)
  }
} finally {
  await vite.close()
}
if (failed) console.warn(`[prerender] ${failed} page(s) fell back to head-only.`)
// App modules loaded above (e.g. the Supabase client's token refresh) leave
// timers running that would keep Node alive after the work is done.
process.exit(0)

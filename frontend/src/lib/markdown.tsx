import React from 'react'
import type { Components } from 'react-markdown'

// ---------------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------------

export function headingToId(heading: string): string {
  return 'sec-' + heading
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

export function extractText(node: React.ReactNode): string {
  if (typeof node === 'string') return node
  if (typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(extractText).join('')
  if (React.isValidElement(node)) {
    const element = node as React.ReactElement<{ children?: React.ReactNode }>
    return extractText(element.props.children)
  }
  return ''
}

// Rewrite `outputs/...` and bare paths to the Vite-proxied `/static/` mount.
export function cleanImageSrc(src: string): string {
  if (src.startsWith('outputs/')) {
    return `/static/${src.replace(/^outputs\//, '')}`
  }
  if (!src.startsWith('/') && !src.startsWith('http')) {
    return `/static/${src}`
  }
  return src
}

// P1.8: remote image allowlist — LLM-generated markdown may point at arbitrary
// hosts (tracking pixels, mixed content, surprise payloads). Mirrors the
// backend CSP img-src list (backend/middleware.py) — keep both in sync.
const ALLOWED_IMAGE_HOSTS = new Set([
  'i.ytimg.com',
  'img.youtube.com',
  'upload.wikimedia.org',
  'commons.wikimedia.org',
])

export interface ResolvedImage {
  src: string
  blockedHost?: string
}

export function resolveImageSrc(src: string): ResolvedImage {
  const resolved = cleanImageSrc(src)
  if (/^https?:\/\//i.test(resolved)) {
    try {
      const host = new URL(resolved).hostname.toLowerCase()
      if (!ALLOWED_IMAGE_HOSTS.has(host)) {
        return { src: resolved, blockedHost: host }
      }
    } catch {
      return { src: resolved, blockedHost: '(invalid url)' }
    }
  }
  return { src: resolved }
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

interface MarkdownComponentsOptions {
  // Tight, compact styling used in chat bubbles (smaller bullets, no table
  // chrome needed).
  chat?: boolean
  // Deep headings (h3–h6) get generated `id`s for anchor linking. Only doc
  // views opt in; revision/print reuse the same base styles without them.
  headingIds?: boolean
  // Reading pane (study notes): Literata at reading size, a 68ch measure.
  reading?: boolean
}

// Single source of truth for the shared ReactMarkdown `components` object.
export function createMarkdownComponents(options: MarkdownComponentsOptions = {}): Components {
  const isChat = options.chat === true
  const withHeadingIds = options.headingIds === true
  const reading = options.reading === true
  const pClass = isChat
    ? 'mb-1.5 last:mb-0'
    : reading
      ? 'font-serif text-17 text-nt leading-[1.65] mb-3 last:mb-0 max-w-[68ch]'
      : 'text-15 text-nt2 leading-relaxed mb-2 last:mb-0 max-w-[72ch]'
  const liClass = isChat
    ? 'relative pl-4 leading-relaxed'
    : reading
      ? 'relative pl-5 font-serif text-17 text-nt leading-[1.6] max-w-[66ch]'
      : 'relative pl-5 text-15 text-nt2 leading-relaxed max-w-[70ch]'

  // De-dupe generated heading ids within a single render (repeated heading
  // text, e.g. "Introduction"/"Conclusion", must not share a DOM id).
  const seenHeadingIds = new Map<string, number>()
  const uniqueHeadingId = (heading: string): string => {
    const base = headingToId(heading)
    const count = seenHeadingIds.get(base) ?? 0
    seenHeadingIds.set(base, count + 1)
    return count === 0 ? base : `${base}-${count + 1}`
  }

  return {
    p: ({ children }) => (
      <p className={pClass}>
        {children}
      </p>
    ),
    strong: ({ children }) => <strong className="text-nt font-semibold">{children}</strong>,
    ul: ({ children }) => (
      <ul className={isChat ? 'list-none pl-0 space-y-1 mt-1' : 'list-none pl-0 space-y-2'}>
        {children}
      </ul>
    ),
    li: ({ children }) => (
      <li className={liClass}>
        <span className={`absolute left-0 rounded-[1px] bg-np ${isChat ? 'top-2 w-1 h-1' : reading ? 'top-[0.7em] w-1.5 h-1.5' : 'top-[0.6em] w-1.5 h-1.5'}`} />
        {children}
      </li>
    ),
    code: ({ children, className }) => {
      if (!className) {
        return (
          <code className={isChat ? 'font-mono text-[0.9em] bg-ns2 px-1 py-0.5 rounded text-nt border border-bdr' : 'font-mono text-[0.85em] bg-ns2 px-1.5 py-0.5 rounded text-nt border border-bdr'}>
            {children}
          </code>
        )
      }
      return <code className={className}>{children}</code>
    },
    table: ({ children }) => (
      <div className="my-3 max-w-full overflow-x-auto">
        <table className="w-full text-14 text-nt2 tabular-nums">{children}</table>
      </div>
    ),
    thead: ({ children }) => (
      <thead className="text-13 font-bold text-nt border-b border-bdr2">
        {children}
      </thead>
    ),
    th: ({ children }) => <th className="p-2 text-left">{children}</th>,
    td: ({ children }) => (
      <td className="p-2 border-b border-bdr last:border-none">{children}</td>
    ),
    img: ({ src, alt }) => {
      const resolved = resolveImageSrc(src || '')
      if (resolved.blockedHost) {
        return (
          <span className="inline-flex items-center gap-1 rounded border border-bdr bg-ns px-2 py-1 my-2 text-2xs text-nt3 font-mono">
            external image blocked · {resolved.blockedHost}
          </span>
        )
      }
      return (
        <img
          src={resolved.src}
          alt={alt || ''}
          referrerPolicy="no-referrer"
          width="1600"
          height="900"
          className={isChat
            ? 'rounded-lg border border-bdr my-2 max-h-60 object-contain shadow-ev1 w-auto h-auto'
            : 'rounded-lg border border-bdr my-3 max-h-72 object-contain shadow-ev1 w-auto h-auto'}
          loading="lazy"
          decoding="async"
        />
      )
    },
    ...(withHeadingIds
      ? {
          h3: ({ children }: { children?: React.ReactNode }) => (
            <h3 id={uniqueHeadingId(extractText(children))} className="text-16 font-bold text-nt mt-5 mb-2">{children}</h3>
          ),
          h4: ({ children }: { children?: React.ReactNode }) => (
            <h4 id={uniqueHeadingId(extractText(children))} className="text-15 font-bold text-nt mt-4 mb-2">{children}</h4>
          ),
          h5: ({ children }: { children?: React.ReactNode }) => (
            <h5 id={uniqueHeadingId(extractText(children))} className="text-14 font-bold text-nt mt-4 mb-2">{children}</h5>
          ),
          h6: ({ children }: { children?: React.ReactNode }) => (
            <h6 id={uniqueHeadingId(extractText(children))} className="text-13 font-bold text-nt mt-4 mb-2">{children}</h6>
          ),
        }
      : {}),
  }
}

export const docMarkdownComponents = createMarkdownComponents({ headingIds: true, reading: true })
export const revisionMarkdownComponents = createMarkdownComponents()
export const printMarkdownComponents = createMarkdownComponents()
export const chatMarkdownComponents = createMarkdownComponents({ chat: true })

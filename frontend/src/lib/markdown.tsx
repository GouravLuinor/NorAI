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
}

// Single source of truth for the shared ReactMarkdown `components` object.
export function createMarkdownComponents(options: MarkdownComponentsOptions = {}): Components {
  const isChat = options.chat === true
  const withHeadingIds = options.headingIds === true

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
      <p className={isChat ? 'mb-1.5 last:mb-0' : 'text-13 text-nt2 leading-relaxed mb-2 last:mb-0'}>
        {children}
      </p>
    ),
    strong: ({ children }) => <strong className="text-nt font-medium">{children}</strong>,
    ul: ({ children }) => (
      <ul className={isChat ? 'list-none pl-0 space-y-1 mt-1' : 'list-none pl-0 space-y-2'}>
        {children}
      </ul>
    ),
    li: ({ children }) => (
      <li className={isChat ? 'relative pl-4 text-xs text-nt2 leading-relaxed' : 'relative pl-5 text-13 text-nt2 leading-relaxed'}>
        <span className={`absolute left-0 top-2 rounded-full bg-ns3 border border-bdr2 ${isChat ? 'w-1 h-1' : 'w-1.5 h-1.5'}`} />
        {children}
      </li>
    ),
    code: ({ children, className }) => {
      if (!className) {
        return (
          <code className={isChat ? 'font-mono text-2xs bg-ns2 px-1 py-0.5 rounded text-nt border border-bdr' : 'font-mono text-2xs bg-ns2 px-1.5 py-0.5 rounded text-nt border border-bdr'}>
            {children}
          </code>
        )
      }
      return <code className={className}>{children}</code>
    },
    table: ({ children }) => <table className="w-full text-xs text-nt2">{children}</table>,
    thead: ({ children }) => (
      <thead className="text-2xs font-semibold text-nt uppercase tracking-wider border-b border-bdr2">
        {children}
      </thead>
    ),
    th: ({ children }) => <th className="p-2 text-left">{children}</th>,
    td: ({ children }) => (
      <td className="p-2 border-b border-bdr last:border-none">{children}</td>
    ),
    img: ({ src, alt }) => (
      <img
        src={cleanImageSrc(src || '')}
        alt={alt || ''}
        width="1600"
        height="900"
        className={isChat
          ? 'rounded-lg border border-bdr my-2 max-h-60 object-contain shadow-ev1 w-auto h-auto'
          : 'rounded-lg border border-bdr my-3 max-h-72 object-contain shadow-ev1 w-auto h-auto'}
        loading="lazy"
        decoding="async"
      />
    ),
    ...(withHeadingIds
      ? {
          h3: ({ children }: { children?: React.ReactNode }) => (
            <h3 id={uniqueHeadingId(extractText(children))} className="text-sm font-medium text-nt mt-5 mb-2">{children}</h3>
          ),
          h4: ({ children }: { children?: React.ReactNode }) => (
            <h4 id={uniqueHeadingId(extractText(children))} className="text-13 font-medium text-nt mt-4 mb-2">{children}</h4>
          ),
          h5: ({ children }: { children?: React.ReactNode }) => (
            <h5 id={uniqueHeadingId(extractText(children))} className="text-xs font-medium text-nt mt-4 mb-2">{children}</h5>
          ),
          h6: ({ children }: { children?: React.ReactNode }) => (
            <h6 id={uniqueHeadingId(extractText(children))} className="text-11 font-medium text-nt mt-4 mb-2">{children}</h6>
          ),
        }
      : {}),
  }
}

export const docMarkdownComponents = createMarkdownComponents({ headingIds: true })
export const revisionMarkdownComponents = createMarkdownComponents()
export const printMarkdownComponents = createMarkdownComponents()
export const chatMarkdownComponents = createMarkdownComponents({ chat: true })

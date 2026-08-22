import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeHighlight from 'rehype-highlight'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import {
  docMarkdownComponents,
  revisionMarkdownComponents,
  printMarkdownComponents,
  chatMarkdownComponents,
} from '../../lib/markdown'

// KaTeX CSS is imported here (not in index.css) so its fonts + styles ship only
// in the chunks that actually render markdown (workspace/print), never the
// marketing pages (P5.6).

export type MarkdownVariant = 'doc' | 'revision' | 'print' | 'chat'

const COMPONENTS: Record<MarkdownVariant, typeof docMarkdownComponents> = {
  doc: docMarkdownComponents,
  revision: revisionMarkdownComponents,
  print: printMarkdownComponents,
  chat: chatMarkdownComponents,
}

// P3.3: plugin arrays are hoisted to module scope. ReactMarkdown diffs its
// config per render; a fresh array literal invalidates the internal plugin
// memoization and forces a full mdast/hast re-parse (highlight + KaTeX) on
// every parent re-render even when `children` is unchanged.
const REMARK_PLUGINS = [remarkGfm, remarkMath]
const REHYPE_PLUGINS = [rehypeHighlight, rehypeKatex]

/** Single shared ReactMarkdown renderer for every markdown surface.
 *  Memoized: markdown surfaces are leaf nodes whose text rarely changes —
 *  parent re-renders skip the parse entirely when children/variant match. */
export const Markdown = memo(function Markdown({
  children,
  variant = 'doc',
}: {
  children: string
  variant?: MarkdownVariant
}) {
  return (
    <ReactMarkdown
      remarkPlugins={REMARK_PLUGINS}
      rehypePlugins={REHYPE_PLUGINS}
      components={COMPONENTS[variant]}
    >
      {children}
    </ReactMarkdown>
  )
})

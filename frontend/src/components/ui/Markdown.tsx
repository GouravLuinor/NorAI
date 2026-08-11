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

/** Single shared ReactMarkdown renderer for every markdown surface. */
export function Markdown({
  children,
  variant = 'doc',
}: {
  children: string
  variant?: MarkdownVariant
}) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeHighlight, rehypeKatex]}
      components={COMPONENTS[variant]}
    >
      {children}
    </ReactMarkdown>
  )
}
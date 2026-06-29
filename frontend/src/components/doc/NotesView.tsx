import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { chapter1NotesMd } from '../../mocks/notesData'

// Custom components to match the dark design
const components = {
  // Section headings — uppercase, purple accent, trailing rule
  h2: ({ children, ...props }: any) => (
    <h2
      className="text-[9.5px] font-semibold text-nt3 mt-8 mb-3 uppercase tracking-wider flex items-center gap-3 first:mt-0"
      {...props}
    >
      <span>{children}</span>
      <span className="flex-1 h-px bg-bdr" />
    </h2>
  ),

  // Tables — complexity comparison card style
  table: ({ children }: any) => (
    <div className="bg-ns border border-bdr2 rounded-lg p-5 mb-5 shadow-[0_1px_2px_rgba(0,0,0,0.28)]">
      <table className="w-full text-xs text-nt2">{children}</table>
    </div>
  ),
  thead: ({ children }: any) => (
    <thead className="text-[10px] font-semibold text-nt uppercase tracking-wider border-b border-bdr2">
      {children}
    </thead>
  ),
  th: ({ children }: any) => (
    <th className="p-2 text-left">{children}</th>
  ),
  td: ({ children }: any) => (
    <td className="p-2 border-b border-bdr last:border-none">{children}</td>
  ),

  // Code blocks — custom wrapper with language label and copy button
  pre: ({ children }: any) => {
    // Extract language from className of <code> if present
    const codeChild = Array.isArray(children) ? children[0] : children
    const lang = codeChild?.props?.className?.replace('language-', '') || ''

    return (
      <div className="bg-nb border border-bdr2 rounded-lg overflow-hidden mb-6 shadow-[0_1px_2px_rgba(0,0,0,0.28)]">
        {lang && (
          <div className="flex justify-between items-center bg-ns px-4 py-2 border-b border-bdr font-mono text-[10px] text-nt3">
            <span>{lang}</span>
            <button className="flex items-center gap-1 bg-transparent border-none text-nt3 hover:text-nt cursor-pointer font-inherit">
              Copy
            </button>
          </div>
        )}
        <pre className="p-4 m-0 overflow-x-auto font-mono text-[13px] text-nt2 leading-relaxed">
          {children}
        </pre>
      </div>
    )
  },
  code: ({ children, className }: any) => {
    // Inline code
    if (!className) {
      return (
        <code className="font-mono text-[10px] bg-ns2 px-1.5 py-0.5 rounded text-nt border border-bdr">
          {children}
        </code>
      )
    }
    // Block code — just pass through to <pre>
    return <code className={className}>{children}</code>
  },

  // Lists — clean dot style
  ul: ({ children }: any) => (
    <ul className="list-none pl-1.5 mb-5 space-y-2.5">{children}</ul>
  ),
  li: ({ children }: any) => (
    <li className="relative pl-5 text-[13px] text-nt2 leading-relaxed">
      <span className="absolute left-0 top-2 w-1.5 h-1.5 rounded-full bg-ns3 border border-bdr2" />
      {children}
    </li>
  ),

  // Paragraphs & emphasis
  p: ({ children }: any) => (
    <p className="text-[13px] text-nt2 leading-relaxed mb-4 max-w-[680px]">{children}</p>
  ),
  strong: ({ children }: any) => (
    <strong className="text-nt font-medium">{children}</strong>
  ),
}

export function NotesView() {
  return (
    <div className="flex-1 overflow-y-auto px-8 py-7 pb-15 scroll-smooth doc-content">
      <article className="max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={components}
        >
          {chapter1NotesMd}
        </ReactMarkdown>
      </article>
    </div>
  )
}
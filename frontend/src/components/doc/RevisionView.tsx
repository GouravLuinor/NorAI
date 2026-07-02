import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Bookmark, GitBranch, Clock, Lightbulb, AlertTriangle, Code, List, FileText, FlaskConical } from 'lucide-react'
import type { Components } from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
// ── Helpers ──────────────────────────────────────────────────────────────────

function headingToId(heading: string): string {
  return 'sec-' + heading
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

function splitByH2(md: string): { heading: string; body: string }[] {
  const sections: { heading: string; body: string }[] = []
  const parts = md.split(/^[ \t]*## /gm)
  if (parts[0]?.trim()) sections.push({ heading: '', body: parts[0].trim() })
  for (let i = 1; i < parts.length; i++) {
    const lines = parts[i].split('\n')
    const heading = lines[0]?.trim() || ''
    const body = lines.slice(1).join('\n').trim()
    sections.push({ heading, body })
  }
  return sections
}

type CardType = 'definition' | 'algorithm' | 'complexity' | 'example' | 'tips' | 'mistake' | 'summary' | 'list' | 'code' | 'formula' | 'prose'

const DEFINITION_KEYWORDS = ['definition', 'core concept', 'key concept', 'what is', 'overview', 'introduction']
const ALGORITHM_KEYWORDS = ['algorithm', 'steps', 'how to', 'procedure', 'method', 'forward pass', 'build', 'construction', 'query', 'update']
const COMPLEXITY_KEYWORDS = ['complexity', 'time', 'space', 'o(log n)', 'o(n)', 'efficiency', 'performance']
const EXAMPLE_KEYWORDS = ['example', 'worked', 'demonstration', 'illustration']
const TIPS_KEYWORDS = ['tip', 'hint', 'note', 'remember', 'pro tip']
const MISTAKE_KEYWORDS = ['mistake', 'common error', 'pitfall', 'watch out', 'caution', 'warning']
const SUMMARY_KEYWORDS = ['summary', 'key takeaway', 'conclusion', 'recap', 'important']
const FORMULA_KEYWORDS = ['formula', 'equation', 'expression', 'math']

function headingMatches(heading: string, keywords: string[]): boolean {
  const h = heading.toLowerCase()
  return keywords.some(kw => h.includes(kw))
}

function getCardType(heading: string, body: string): CardType {
  const h = heading.toLowerCase()

  if (body.includes('```')) return 'code'
  if (body.includes('|')) return 'complexity'

  if (headingMatches(h, DEFINITION_KEYWORDS)) return 'definition'
  if (headingMatches(h, ALGORITHM_KEYWORDS)) return 'algorithm'
  if (headingMatches(h, COMPLEXITY_KEYWORDS)) return 'complexity'
  if (headingMatches(h, EXAMPLE_KEYWORDS)) return 'example'
  if (headingMatches(h, TIPS_KEYWORDS)) return 'tips'
  if (headingMatches(h, MISTAKE_KEYWORDS)) return 'mistake'
  if (headingMatches(h, SUMMARY_KEYWORDS)) return 'summary'
  if (headingMatches(h, FORMULA_KEYWORDS)) return 'formula'

  const lines = body.split('\n').filter(l => l.trim())
  if (lines.filter(l => /^\s*[-*•]\s/.test(l)).length / lines.length > 0.5) return 'list'

  return 'prose'
}

// ── Card Wrappers ────────────────────────────────────────────────────────────

function DefinitionCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="bg-ns border border-bdr2 rounded-lg p-4 mb-4 shadow-sm border-l-2 border-l-np">
      <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-np uppercase tracking-wider mb-2">
        <Bookmark size={13} />
        {heading}
      </div>
      {children}
    </div>
  )
}

function AlgorithmCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="bg-ns border border-bdr2 rounded-lg p-4 mb-4 shadow-sm">
      <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nbl uppercase tracking-wider mb-2">
        <GitBranch size={13} />
        {heading}
      </div>
      {children}
    </div>
  )
}

function ComplexityCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="bg-ns border border-bdr2 rounded-lg p-5 mb-5 shadow-sm">
      <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-ng uppercase tracking-wider mb-2">
        <Clock size={13} />
        {heading}
      </div>
      {children}
    </div>
  )
}

function ExampleCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="bg-ns border border-bdr2 rounded-lg p-4 mb-4 shadow-sm">
      <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-na uppercase tracking-wider mb-2">
        <FlaskConical size={13} />
        {heading}
      </div>
      {children}
    </div>
  )
}

function TipsCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2.5 bg-nab border border-nabr rounded-lg p-3 mb-4">
      <Lightbulb size={14} className="text-na mt-0.5 shrink-0" />
      <div>
        <div className="text-[9.5px] font-semibold text-na uppercase tracking-wider mb-1">{heading}</div>
        <div className="text-xs text-nt2 leading-relaxed">{children}</div>
      </div>
    </div>
  )
}

function MistakeCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2.5 bg-nrb border border-nrbr rounded-lg p-3 mb-4">
      <AlertTriangle size={14} className="text-nr mt-0.5 shrink-0" />
      <div>
        <div className="text-[9.5px] font-semibold text-nr uppercase tracking-wider mb-1">{heading}</div>
        <div className="text-xs text-nt2 leading-relaxed">{children}</div>
      </div>
    </div>
  )
}

function SummaryCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2.5 bg-ngb border border-ngbr rounded-lg p-3 mb-4">
      <div className="w-2 h-2 rounded-full bg-ng mt-2 shrink-0" />
      <div>
        <div className="text-[9.5px] font-semibold text-ng uppercase tracking-wider mb-1">{heading}</div>
        <div className="text-xs text-nt2 leading-relaxed">{children}</div>
      </div>
    </div>
  )
}

function ListCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2">
        <List size={13} className="text-np" />
        {heading}
      </div>
      <ul className="list-none pl-1.5 space-y-2.5">{children}</ul>
    </div>
  )
}

function FormulaCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="bg-ns border border-bdr2 rounded-lg p-4 mb-4 shadow-sm border-l-2 border-l-np">
      <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-np uppercase tracking-wider mb-2">
        <FileText size={13} />
        {heading}
      </div>
      <div className="font-mono text-[13px] text-nt2">{children}</div>
    </div>
  )
}

function CodeCard({ heading, children, lang }: { heading: string; children: React.ReactNode; lang?: string }) {
  return (
    <div className="mb-6">
      {heading && (
        <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2">
          <Code size={13} className="text-nbl" />
          {heading}
        </div>
      )}
      <div className="bg-nb border border-bdr2 rounded-lg overflow-hidden shadow-sm">
        {lang && (
          <div className="flex justify-between items-center bg-ns px-4 py-2 border-b border-bdr font-mono text-[10px] text-nt3">
            <span>{lang}</span>
            <button className="flex items-center gap-1 bg-transparent border-none text-nt3 hover:text-nt cursor-pointer font-inherit">Copy</button>
          </div>
        )}
        <pre className="p-4 m-0 overflow-x-auto font-mono text-[13px] text-nt2 leading-relaxed">{children}</pre>
      </div>
    </div>
  )
}

function ProseCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="bg-ns border border-bdr2 rounded-lg p-5 mb-5 shadow-sm">
      <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2">
        <FileText size={13} className="text-nt3" />
        {heading}
      </div>
      {children}
    </div>
  )
}

// ── Custom renderers ─────────────────────────────────────────────────────────

const baseComponents: Components = {
  p: ({ children }) => <p className="text-[13px] text-nt2 leading-relaxed mb-2 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="text-nt font-medium">{children}</strong>,
  ul: ({ children }) => <ul className="list-none pl-0 space-y-2">{children}</ul>,
  li: ({ children }) => (
    <li className="relative pl-5 text-[13px] text-nt2 leading-relaxed">
      <span className="absolute left-0 top-2 w-1.5 h-1.5 rounded-full bg-ns3 border border-bdr2" />
      {children}
    </li>
  ),
  code: ({ children, className }) => {
    if (!className) {
      return <code className="font-mono text-[10px] bg-ns2 px-1.5 py-0.5 rounded text-nt border border-bdr">{children}</code>
    }
    return <code className={className}>{children}</code>
  },
  table: ({ children }) => <table className="w-full text-xs text-nt2">{children}</table>,
  thead: ({ children }) => <thead className="text-[10px] font-semibold text-nt uppercase tracking-wider border-b border-bdr2">{children}</thead>,
  th: ({ children }) => <th className="p-2 text-left">{children}</th>,
  td: ({ children }) => <td className="p-2 border-b border-bdr last:border-none">{children}</td>,
}

// ── Main Component ───────────────────────────────────────────────────────────

export function RevisionView({ chapterId }: { chapterId: number | null }) {
  const [sections, setSections] = useState<{ heading: string; body: string }[]>([])
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)

  const chapterIdStr = chapterId != null ? String(chapterId) : null

  useEffect(() => {
    if (!chapterIdStr) {
      setTitle('')
      setSections([{ heading: '', body: 'Select a chapter from the sidebar to see its revision notes.' }])
      setLoading(false)
      return
    }

    const controller = new AbortController()
    setLoading(true)

    fetch(`/summary?chapter_id=${chapterIdStr}`, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error('Not found')
        const rawText = await res.text()
        try {
          return rawText.startsWith('"') ? JSON.parse(rawText) : rawText
        } catch {
          return rawText
        }
      })
      .then((text) => {
        const lines = text.split('\n')
        let mdTitle = ''
        if (lines[0]?.startsWith('# ')) {
          mdTitle = lines[0].replace(/^# /, '').trim()
          text = lines.slice(1).join('\n').trim()
        }
        const secs = splitByH2(text)
        setTitle(mdTitle)
        setSections(secs)
        setLoading(false)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setTitle(`Chapter ${chapterIdStr}`)
        setSections([{ heading: '', body: 'Revision notes have not been generated for this chapter yet.' }])
        setLoading(false)
      })

    return () => controller.abort()
  }, [chapterIdStr])

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-nt3 text-sm">
        Loading revision notes…
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto doc-content px-8 py-7 pb-15 scroll-smooth">
      {title && (
        <h1 className="text-[21px] font-semibold text-nt tracking-tight mb-6 leading-tight">
          {title}
        </h1>
      )}

      {sections.map((section, idx) => {
        const { heading, body } = section
        if (!body) return null

        const innerContent = (
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeHighlight, rehypeKatex]}
            components={baseComponents}
          >
            {body}
          </ReactMarkdown>
        )

        const sectionId = heading ? headingToId(heading) : `sec-preamble-${idx}`

        if (!heading) {
          return (
            <div key={idx} id={sectionId} className="text-center text-nt3 text-[13px] py-12">
              {innerContent}
            </div>
          )
        }

        const cardType = getCardType(heading, body)

        switch (cardType) {
          case 'definition':
            return (
              <div key={idx} id={sectionId}>
                <DefinitionCard heading={heading}>{innerContent}</DefinitionCard>
              </div>
            )
          case 'algorithm':
            return (
              <div key={idx} id={sectionId}>
                <AlgorithmCard heading={heading}>{innerContent}</AlgorithmCard>
              </div>
            )
          case 'complexity':
            return (
              <div key={idx} id={sectionId}>
                <ComplexityCard heading={heading}>{innerContent}</ComplexityCard>
              </div>
            )
          case 'example':
            return (
              <div key={idx} id={sectionId}>
                <ExampleCard heading={heading}>{innerContent}</ExampleCard>
              </div>
            )
          case 'tips':
            return (
              <div key={idx} id={sectionId}>
                <TipsCard heading={heading}>{innerContent}</TipsCard>
              </div>
            )
          case 'mistake':
            return (
              <div key={idx} id={sectionId}>
                <MistakeCard heading={heading}>{innerContent}</MistakeCard>
              </div>
            )
          case 'summary':
            return (
              <div key={idx} id={sectionId}>
                <SummaryCard heading={heading}>{innerContent}</SummaryCard>
              </div>
            )
          case 'list':
            return (
              <div key={idx} id={sectionId}>
                <ListCard heading={heading}>{innerContent}</ListCard>
              </div>
            )
          case 'formula':
            return (
              <div key={idx} id={sectionId}>
                <FormulaCard heading={heading}>{innerContent}</FormulaCard>
              </div>
            )
          case 'code':
            const langMatch = body.match(/```(\w+)/)
            return (
              <div key={idx} id={sectionId}>
                <CodeCard heading={heading} lang={langMatch?.[1]}>{innerContent}</CodeCard>
              </div>
            )
          default:
            return (
              <div key={idx} id={sectionId}>
                <ProseCard heading={heading}>{innerContent}</ProseCard>
              </div>
            )
        }
      })}
    </div>
  )
}
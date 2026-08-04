import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Bookmark, GitBranch, Clock, Lightbulb, AlertTriangle, Code, List, FileText, FlaskConical } from 'lucide-react'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { useLectureStore } from '../../stores/useLectureStore'
import { revisionMarkdownComponents, headingToId } from '../../lib/markdown'
import { Card, CardHeader } from '../ui/Card'

// ── Helpers ──────────────────────────────────────────────────────────────────

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
      <Card accent="border-l-2 border-l-np" className="p-4 mb-4">
        <CardHeader tone="np" icon={<Bookmark size={13} strokeWidth={1.5} />}>
          {heading}
        </CardHeader>
        {children}
      </Card>
  )
}

function AlgorithmCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Card className="p-4 mb-4">
      <CardHeader tone="nbl" icon={<GitBranch size={13} strokeWidth={1.5} />}>
        {heading}
      </CardHeader>
      {children}
    </Card>
  )
}

function ComplexityCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Card className="p-5 mb-5">
      <CardHeader tone="ng" icon={<Clock size={13} strokeWidth={1.5} />}>
        {heading}
      </CardHeader>
      {children}
    </Card>
  )
}

function ExampleCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Card className="p-4 mb-4">
      <CardHeader tone="na" icon={<FlaskConical size={13} strokeWidth={1.5} />}>
        {heading}
      </CardHeader>
      {children}
    </Card>
  )
}

function TipsCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2.5 bg-nab border border-nabr rounded-lg p-3 mb-4">
      <Lightbulb size={14} strokeWidth={1.5} className="text-na mt-0.5 shrink-0" />
      <div>
        <div className="text-3xs font-semibold text-na uppercase tracking-wider mb-1">{heading}</div>
        <div className="text-xs text-nt2 leading-relaxed">{children}</div>
      </div>
    </div>
  )
}

function MistakeCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2.5 bg-nrb border border-nrbr rounded-lg p-3 mb-4">
      <AlertTriangle size={14} strokeWidth={1.5} className="text-nr mt-0.5 shrink-0" />
      <div>
        <div className="text-3xs font-semibold text-nr uppercase tracking-wider mb-1">{heading}</div>
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
        <div className="text-3xs font-semibold text-ng uppercase tracking-wider mb-1">{heading}</div>
        <div className="text-xs text-nt2 leading-relaxed">{children}</div>
      </div>
    </div>
  )
}

function ListCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <CardHeader icon={<List size={13} strokeWidth={1.5} className="text-np" />}>
        {heading}
      </CardHeader>
      <ul className="list-none pl-1.5 space-y-2.5">{children}</ul>
    </div>
  )
}

function FormulaCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Card accent="border-l-2 border-l-np" className="p-4 mb-4">
      <CardHeader tone="np" icon={<FileText size={13} strokeWidth={1.5} />}>
        {heading}
      </CardHeader>
      <div className="font-mono text-13 text-nt2">{children}</div>
    </Card>
  )
}

function CodeCard({ heading, children, lang }: { heading: string; children: React.ReactNode; lang?: string }) {
  return (
    <div className="mb-6">
      {heading && (
        <CardHeader icon={<Code size={13} strokeWidth={1.5} className="text-nbl" />}>
          {heading}
        </CardHeader>
      )}
      <Card surface="nb" className="overflow-hidden">
        {lang && (
          <div className="flex justify-between items-center bg-ns px-4 py-2 border-b border-bdr font-mono text-2xs text-nt3">
            <span>{lang}</span>
            <button className="flex items-center gap-1 bg-transparent border-none text-nt3 hover:text-nt cursor-pointer font-inherit">Copy</button>
          </div>
        )}
        <pre className="p-4 m-0 overflow-x-auto font-mono text-13 text-nt2 leading-relaxed">{children}</pre>
      </Card>
    </div>
  )
}

function ProseCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Card className="p-5 mb-5">
      <CardHeader icon={<FileText size={13} strokeWidth={1.5} className="text-nt3" />}>
        {heading}
      </CardHeader>
      {children}
    </Card>
  )
}

// ── Main Component ───────────────────────────────────────────────────────────

export function RevisionView({ chapterId }: { chapterId: number | null }) {
  const [sections, setSections] = useState<{ heading: string; body: string }[]>([])
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)

  const chapterIdStr = chapterId != null ? String(chapterId) : null
  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'  

  useEffect(() => {
    if (!chapterIdStr) {
      setTitle('')
      setSections([{ heading: '', body: 'Select a chapter from the sidebar to see its revision notes.' }])
      setLoading(false)
      return
    }

    const controller = new AbortController()
    setLoading(true)

    fetch(`/summary?chapter_id=${chapterIdStr}&lecture_id=${lectureId}`, { signal: controller.signal })
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
  }, [chapterIdStr, lectureId])

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
        <h1 className="font-serif text-[26px] font-medium text-nt tracking-tight mb-6 leading-snug">
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
            components={revisionMarkdownComponents}
          >
            {body}
          </ReactMarkdown>
        )

        const sectionId = heading ? headingToId(heading) : `sec-preamble-${idx}`

        if (!heading) {
          return (
            <div key={idx} id={sectionId} className="text-center text-nt3 text-13 py-12">
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
import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Bookmark, Clock, Lightbulb, Code, List, FileText } from 'lucide-react'
import type { Components } from 'react-markdown'
import { ChapterScreenshots } from './ChapterScreenshots'
import React from 'react'
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



function extractText(node: React.ReactNode): string {
  if (typeof node === 'string') return node
  if (typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(extractText).join('')
  if (React.isValidElement(node)) {
    const element = node as React.ReactElement<{ children?: React.ReactNode }>
    return extractText(element.props.children)
  }
  return ''
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

type CardType = 'definition' | 'table' | 'callout' | 'list' | 'code' | 'prose'

const DEFINITION_KEYWORDS = [
  'core concept', 'core idea', 'key concept',
  'detailed explanation', 'explanation',
  'interval decomposition', 'full binary tree', 'node structure',
  'tree construction', 'query operation', 'update operation',
  'recursive', 'introduction', 'motivation', 'overview',
  'definition', 'property', 'structure', 'implementation',
  'complexity', 'mechanism', 'algorithm',
]

const CALLOUT_KEYWORDS = [
  'important observation', 'key insight', 'observation',
  'common mistake', 'mistake', 'pitfall',
  'efficiency gap', 'dynamic limitation', 'limitation',
  'the balance', 'balance', 'trade-off', 'tradeoff',
  'caution', 'warning', 'note',
]

const LIST_KEYWORDS = [
  'application', 'use case', 'key takeaway', 'takeaway',
  'example', 'summary', 'checklist',
]

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function normalizeHeading(heading: string): string {
  return heading.toLowerCase().replace(/[*_`]/g, '').trim()
}

function headingMatches(heading: string, keywords: string[]): boolean {
  return keywords.some((kw) =>
    kw.includes(' ')
      ? heading.includes(kw)
      : new RegExp(`\\b${escapeRegExp(kw)}s?\\b`).test(heading)
  )
}

function hasFencedCode(body: string): boolean {
  return body.includes('```')
}

function looksLikeTable(body: string): boolean {
  return body.split('\n').some((line) => (line.match(/\|/g) ?? []).length >= 2)
}

function isBulletHeavy(body: string): boolean {
  const lines = body.split('\n').filter((l) => l.trim())
  if (lines.length === 0) return false
  const bulletCount = lines.filter((l) => /^\s*(?:[-*•]|\d+[.)])\s/.test(l)).length
  return bulletCount / lines.length > 0.5
}

function getCardType(heading: string, body: string): CardType {
  if (hasFencedCode(body)) return 'code'
  if (looksLikeTable(body)) return 'table'

  const h = normalizeHeading(heading)
  if (headingMatches(h, DEFINITION_KEYWORDS)) return 'definition'
  if (headingMatches(h, CALLOUT_KEYWORDS)) return 'callout'
  if (headingMatches(h, LIST_KEYWORDS)) return 'list'

  if (isBulletHeavy(body)) return 'list'
  return 'prose'
}

// ── Card Wrappers ────────────────────────────────────────────────────────────

function DefinitionCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="bg-ns border border-bdr2 rounded-lg p-4 mb-4 shadow-sm">
      <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2">
        <Bookmark size={13} className="text-np" />
        {heading}
      </div>
      {children}
    </div>
  )
}

function TableCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="bg-ns border border-bdr2 rounded-lg p-5 mb-5 shadow-sm">
      <div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2">
        <Clock size={13} className="text-ng" />
        {heading}
      </div>
      {children}
    </div>
  )
}

function CalloutCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2.5 bg-nblb border border-nblbr rounded-lg p-3 mb-4">
      <Lightbulb size={14} className="text-nbl mt-0.5 shrink-0" />
      <div>
        <div className="text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-1">{heading}</div>
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

function ProseSection({ heading, children }: { heading: string; children: React.ReactNode }) {
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
            <button className="flex items-center gap-1 bg-transparent border-none text-nt3 hover:text-nt cursor-pointer font-inherit">
              Copy
            </button>
          </div>
        )}
        <pre className="p-4 m-0 overflow-x-auto font-mono text-[13px] text-nt2 leading-relaxed">
          {children}
        </pre>
      </div>
    </div>
  )
}

// ── Custom renderers ─────────────────────────────────────────────────────────

const baseComponents: Components = {
  p: ({ children }) => (
    <p className="text-[13px] text-nt2 leading-relaxed mb-2 last:mb-0">{children}</p>
  ),
  strong: ({ children }) => <strong className="text-nt font-medium">{children}</strong>,
  ul: ({ children }) => (
    <ul className="list-none pl-0 space-y-2">{children}</ul>
  ),
  li: ({ children }) => (
    <li className="relative pl-5 text-[13px] text-nt2 leading-relaxed">
      <span className="absolute left-0 top-2 w-1.5 h-1.5 rounded-full bg-ns3 border border-bdr2" />
      {children}
    </li>
  ),
  code: ({ children, className }) => {
    if (!className) {
      return (
        <code className="font-mono text-[10px] bg-ns2 px-1.5 py-0.5 rounded text-nt border border-bdr">
          {children}
        </code>
      )
    }
    return <code className={className}>{children}</code>
  },
  table: ({ children }) => (
    <table className="w-full text-xs text-nt2">{children}</table>
  ),
  thead: ({ children }) => (
    <thead className="text-[10px] font-semibold text-nt uppercase tracking-wider border-b border-bdr2">
      {children}
    </thead>
  ),
  th: ({ children }) => <th className="p-2 text-left">{children}</th>,
  td: ({ children }) => (
    <td className="p-2 border-b border-bdr last:border-none">{children}</td>
  ),
  // Assign generated IDs to deep subheadings for linking
  h3: ({ children }) => <h3 id={headingToId(extractText(children))} className="text-[14px] font-medium text-nt mt-5 mb-2">{children}</h3>,
  h4: ({ children }) => <h4 id={headingToId(extractText(children))} className="text-[13px] font-medium text-nt mt-4 mb-2">{children}</h4>,
  h5: ({ children }) => <h5 id={headingToId(extractText(children))} className="text-[12px] font-medium text-nt mt-4 mb-2">{children}</h5>,
  h6: ({ children }) => <h6 id={headingToId(extractText(children))} className="text-[11px] font-medium text-nt mt-4 mb-2">{children}</h6>,
}

// ── Main Component ───────────────────────────────────────────────────────────

export function NotesView({ chapterId, screenshotsExpanded = false }: { chapterId: number | null; screenshotsExpanded?: boolean }) {
  const [sections, setSections] = useState<{ heading: string; body: string }[]>([])
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)

  const chapterIdStr = chapterId != null ? String(chapterId) : null

  useEffect(() => {
    if (!chapterIdStr) {
      setTitle('')
      setSections([{ heading: '', body: 'Select a chapter from the sidebar to see its study notes.' }])
      setLoading(false)
      return
    }

    const controller = new AbortController()
    setLoading(true)

    fetch(`/notes/${chapterIdStr}`, { signal: controller.signal })
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
        setSections([{ heading: '', body: 'Study notes have not been generated for this chapter yet.' }])
        setLoading(false)
      })

    return () => controller.abort()
  }, [chapterIdStr])

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-nt3 text-sm">
        Loading notes…
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
          case 'table':
            return (
              <div key={idx} id={sectionId}>
                <TableCard heading={heading}>{innerContent}</TableCard>
              </div>
            )
          case 'callout':
            return (
              <div key={idx} id={sectionId}>
                <CalloutCard heading={heading}>{innerContent}</CalloutCard>
              </div>
            )
          case 'list':
            return (
              <div key={idx} id={sectionId}>
                <ListCard heading={heading}>{innerContent}</ListCard>
              </div>
            )
          case 'code': {
            const langMatch = body.match(/```(\w+)/)
            return (
              <div key={idx} id={sectionId}>
                <CodeCard heading={heading} lang={langMatch?.[1]}>{innerContent}</CodeCard>
              </div>
            )
          }
          default:
            return (
              <div key={idx} id={sectionId}>
                <ProseSection heading={heading}>{innerContent}</ProseSection>
              </div>
            )
        }
      })}

      <ChapterScreenshots chapterId={chapterId} startExpanded={screenshotsExpanded} />
    </div>
  )
}
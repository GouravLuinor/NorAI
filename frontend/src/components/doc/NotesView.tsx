import { useState, useEffect } from 'react'
import { Bookmark, Clock, Lightbulb, Code, List, FileText, Play } from 'lucide-react'
import { ChapterScreenshots } from './ChapterScreenshots'
import React from 'react'
import { useLectureStore } from '../../stores/useLectureStore'
import { useVideoStore } from '../../stores/useVideoStore'
import { formatTimestamp } from '../../lib/video'
import { apiFetchRaw } from '../../lib/http'
import { headingToId } from '../../lib/markdown'
import { Markdown } from '../ui/Markdown'
import { Card, CardHeader } from '../ui/Card'
import { FOCUS_RING } from '../ui/shared'
import { PartialContentBadge } from '../ui/PartialContentBadge'
import { NotesSkeleton } from '../ui/SkeletonCard'
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
    <Card className="p-4 mb-4">
      <CardHeader icon={<Bookmark size={13} strokeWidth={1.5} className="text-np" />}>
        {heading}
      </CardHeader>
      {children}
    </Card>
  )
}

function TableCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Card className="p-5 mb-5">
      <CardHeader icon={<Clock size={13} strokeWidth={1.5} className="text-ng" />}>
        {heading}
      </CardHeader>
      {children}
    </Card>
  )
}

function CalloutCard({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="note-callout flex gap-2.5 p-3 mb-4">
      <Lightbulb size={14} strokeWidth={1.5} className="text-np mt-0.5 shrink-0" />
      <div>
        <div className="note-label mb-1">{heading}</div>
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
      <div className="pl-1.5 space-y-2.5">{children}</div>
    </div>
  )
}

function ProseSection({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Card className="p-5 mb-5">
      <CardHeader icon={<FileText size={13} strokeWidth={1.5} className="text-nt3" />}>
        {heading}
      </CardHeader>
      {children}
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
            <button className={`flex items-center gap-1 bg-transparent border-none text-nt3 hover:text-nt cursor-pointer font-inherit ${FOCUS_RING}`}>
              Copy
            </button>
          </div>
        )}
        <pre className="p-4 m-0 overflow-x-auto font-mono text-13 text-nt2 leading-relaxed">
          {children}
        </pre>
      </Card>
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────────────────

interface SectionItem {
  heading: string
  body: string
  cardType?: CardType
}

export function NotesView({ chapterId, screenshotsExpanded = false }: { chapterId: number | null; screenshotsExpanded?: boolean }) {
  const [sections, setSections] = useState<SectionItem[]>([])
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [partiallyGenerated, setPartiallyGenerated] = useState(false)

  const chapterIdStr = chapterId != null ? String(chapterId) : null
  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'

  // P6.3: chapter-level video seek target.
  const videoEmbeddable = useVideoStore(s => s.embeddable)
  const videoMap = useVideoStore(s => s.map)
  const seekToChapter = useVideoStore(s => s.seekToChapter)
  const chapterTime = chapterId != null
    ? videoMap?.chapters.find((c) => c.chapter_id === chapterId)
    : undefined
  const showSeekChip = videoEmbeddable && chapterTime?.start_sec != null

  useEffect(() => {
    if (!chapterIdStr) {
      setTitle('')
      setSections([{ heading: '', body: 'Select a chapter from the sidebar to see its study notes.' }])
      setLoading(false)
      setPartiallyGenerated(false)
      return
    }

    const controller = new AbortController()
    setLoading(true)
    setPartiallyGenerated(false)

    apiFetchRaw(`/notes/${chapterIdStr}?lecture_id=${lectureId}`, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error('Not found')
        const contentType = res.headers.get('content-type') || ''
        if (contentType.includes('application/json')) {
          return res.json()
        }
        const text = await res.text()
        try {
          return JSON.parse(text)
        } catch {
          return text
        }
      })
      .then((data) => {
        if (typeof data === 'object' && data !== null && 'sections' in data) {
          // 100% Deterministic Structured JSON Payload
          setTitle((data as { title?: string }).title || `Chapter ${chapterIdStr}`)
          const parsedSecs: SectionItem[] = ((data as { sections?: Array<Record<string, unknown>> }).sections || []).map((sec) => ({
            heading: (sec.title as string) || '',
            body: ((sec.content_markdown as string) || '').replace(/!\[.*?\]\(.*?\)/g, '').trim(),
            cardType: sec.section_type as CardType
          }))
          setSections(parsedSecs)
        } else {
          // Legacy Raw Markdown String Fallback (includes the graceful-degradation .md)
          let text = typeof data === 'string' ? data : String(data)
          setPartiallyGenerated(text.toLowerCase().includes('partially degraded'))
          const cleanedText = text
            .replace(/!\[.*?\]\(.*?\)/g, '')
            .replace(/\n{3,}/g, '\n\n')
            .trim()
          const lines = cleanedText.split('\n')
          let mdTitle = ''
          if (lines[0]?.startsWith('# ')) {
            mdTitle = lines[0].replace(/^# /, '').trim()
            text = lines.slice(1).join('\n').trim()
          }
          const secs = splitByH2(text)
          setTitle(mdTitle)
          setSections(secs)
        }
        setLoading(false)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setTitle(`Chapter ${chapterIdStr}`)
        setSections([{ heading: '', body: 'Study notes have not been generated for this chapter yet.' }])
        setLoading(false)
      })

    return () => controller.abort()
  }, [chapterIdStr, lectureId])

  if (loading) {
    return <NotesSkeleton />
  }

  return (
    <div className="flex-1 overflow-y-auto doc-content px-8 py-7 pb-15 scroll-smooth">
      {title && (
        <div className="flex items-center gap-3 mb-6">
          <h1 className="font-serif text-hero font-medium text-nt tracking-tight leading-snug">
            {title}
          </h1>
          {showSeekChip && chapterTime?.start_sec != null && (
            <button
              type="button"
              title={`Jump the video to ${formatTimestamp(chapterTime.start_sec)}`}
              onClick={() => seekToChapter(chapterId as number)}
              className={`flex items-center gap-1.5 px-2 py-1 rounded-sm bg-ns2 border border-bdr text-2xs text-nt3 hover:text-nt hover:border-nt4 transition cursor-pointer shrink-0 ${FOCUS_RING}`}
            >
              <Play size={10} strokeWidth={1.5} className="text-np" />
              Watch · {formatTimestamp(chapterTime.start_sec)}
            </button>
          )}
        </div>
      )}

      {partiallyGenerated && <PartialContentBadge className="mb-6" />}

      {sections.map((section, idx) => {
        const { heading, body, cardType: explicitType } = section
        if (!body) return null

        const innerContent = (
          <Markdown variant="doc">{body}</Markdown>
        )

        const sectionId = heading ? headingToId(heading) : `sec-preamble-${idx}`

        if (!heading) {
          return (
            <div key={idx} id={sectionId} className="text-center text-nt3 text-13 py-12">
              {innerContent}
            </div>
          )
        }

        const cardType = explicitType || getCardType(heading, body)

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
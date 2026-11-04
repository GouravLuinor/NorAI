import { useState, useEffect, useRef } from 'react'
import { Lightbulb, Play } from 'lucide-react'
import { ChapterScreenshots } from './ChapterScreenshots'
import React from 'react'
import { useLectureStore } from '../../stores/useLectureStore'
import { useVideoStore } from '../../stores/useVideoStore'
import { formatTimestamp } from '../../lib/video'

/** Fit a document location in the shelf mark: "p. 4" / "Slide 7" stay whole,
 *  a heading label is cut to a few characters (the full one is the h2). */
function shortLoc(loc: string): string {
  const slide = loc.match(/^Slide (\d+)$/)
  if (slide) return `S. ${slide[1]}`
  return loc.length <= 7 ? loc : `${loc.slice(0, 6).trimEnd()}…`
}
import { apiFetchRaw } from '../../lib/http'
import { headingToId } from '../../lib/markdown'
import { Markdown } from '../ui/Markdown'
import { Card } from '../ui/Card'
import { ShelfMark } from '../ui/ShelfMark'
import { FOCUS_RING } from '../ui/shared'
import { CopyButton } from '../ui/CopyButton'
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

// ── Section bodies ───────────────────────────────────────────────────────────
// Sections read as plain text under their heading. Only callouts and code get
// a container, because they are different objects, not more of the same.

function CalloutBody({ children }: { children: React.ReactNode }) {
  return (
    <div className="note-callout flex gap-3 p-4 mt-2">
      <Lightbulb size={16} strokeWidth={1.75} className="text-np mt-1 shrink-0" />
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  )
}

function CodeBody({ children, lang }: { children: React.ReactNode; lang?: string }) {
  const preRef = useRef<HTMLPreElement>(null)
  return (
    <Card surface="nb" className="overflow-hidden mt-2">
      {lang && (
        <div className="flex justify-between items-center bg-ns px-4 py-2 border-b border-bdr font-mono text-12 text-nt3">
          <span>{lang}</span>
          <CopyButton getValue={() => preRef.current?.textContent ?? ''} />
        </div>
      )}
      <pre ref={preRef} className="p-4 m-0 overflow-x-auto font-mono text-14 text-nt2 leading-relaxed">
        {children}
      </pre>
    </Card>
  )
}

// ── Main Component ───────────────────────────────────────────────────────────

interface SectionItem {
  heading: string
  body: string
  cardType?: CardType
  /** Where the section's material starts in the video (lean pipeline notes). */
  startSec?: number | null
  /** Documents: "p. 4", "Slide 7" or a heading (notes/chapter_N.json `loc`). */
  loc?: string | null
}

export function NotesView({ chapterId, screenshotsExpanded = true }: { chapterId: number | null; screenshotsExpanded?: boolean }) {
  const [sections, setSections] = useState<SectionItem[]>([])
  const [title, setTitle] = useState('')
  const [loading, setLoading] = useState(true)
  const [partiallyGenerated, setPartiallyGenerated] = useState(false)

  const chapterIdStr = chapterId != null ? String(chapterId) : null
  const lectureId = useLectureStore(s => s.activeLectureId) || 'default'

  // P6.3: chapter-level and chunk-level video seek targets.
  const videoEmbeddable = useVideoStore(s => s.embeddable)
  // Documents: sections carry a page/slide/heading label instead of a time.
  const isDocument = useVideoStore(s => s.sourceKind === 'document')
  const videoMap = useVideoStore(s => s.map)
  const seekToChapter = useVideoStore(s => s.seekToChapter)
  const sectionStart = useVideoStore(s => s.sectionStart)
  const requestSeek = useVideoStore(s => s.requestSeek)
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
            cardType: sec.section_type as CardType,
            startSec: typeof sec.start_sec === 'number' ? sec.start_sec : null,
            loc: typeof sec.loc === 'string' ? sec.loc : null,
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

  const sectionCount = sections.filter((sec) => sec.heading && sec.body).length
  let sectionNo = 0

  return (
    <div className="flex-1 overflow-y-auto doc-content px-5 sm:px-10 lg:px-14 py-8 pb-16 scroll-smooth">
      {title && (
        <header className="mb-8 max-w-[44rem]">
          <h1 className="font-serif text-28 sm:text-hero font-semibold text-nt tracking-tight leading-[1.15] text-balance">
            {title}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-13 text-nt3">
            <span className="font-mono">
              {chapterId != null && <>Chapter {chapterId}</>}
              {!isDocument && chapterTime?.start_sec != null && <> · {formatTimestamp(chapterTime.start_sec)}</>}
              {sectionCount > 0 && <> · {sectionCount} {sectionCount === 1 ? 'section' : 'sections'}</>}
            </span>
            {showSeekChip && chapterTime?.start_sec != null && (
              <button
                type="button"
                onClick={() => seekToChapter(chapterId as number)}
                className={`inline-flex items-center gap-1.5 px-2.5 h-7 rounded-md border border-bdr2 text-13 font-bold text-np hover:bg-npb transition cursor-pointer active:translate-y-[1px] ${FOCUS_RING}`}
              >
                <Play size={13} strokeWidth={1.75} />
                Watch from {formatTimestamp(chapterTime.start_sec)}
              </button>
            )}
          </div>
        </header>
      )}

      {partiallyGenerated && <PartialContentBadge className="mb-6" />}

      {sections.map((section, idx) => {
        const { heading, body, cardType: explicitType, startSec, loc } = section
        if (!body) return null

        const innerContent = (
          <Markdown variant="doc">{body}</Markdown>
        )

        const sectionId = heading ? headingToId(heading) : `sec-preamble-${idx}`

        if (!heading) {
          return (
            <div key={idx} id={sectionId} className="text-nt3 py-12 max-w-[44rem]">
              {innerContent}
            </div>
          )
        }

        sectionNo += 1
        const mark = chapterId != null ? `${chapterId}.${sectionNo}` : String(sectionNo)
        const sectionSec = !videoEmbeddable
          ? null
          : startSec ?? (chapterId != null ? sectionStart(chapterId, idx) : null)

        // The shelf mark carries the number, so "1. Title" drops its prefix.
        // All-caps headings (some generated notes) set smaller and tracked.
        const displayHeading = heading.replace(/^\s*\d+(?:\.\d+)*[.)]\s+/, '')
        const isCaps = /[A-Z]/.test(displayHeading) && displayHeading === displayHeading.toUpperCase()
        const cardType = explicitType || getCardType(heading, body)
        let content: React.ReactNode = innerContent
        if (cardType === 'callout') content = <CalloutBody>{innerContent}</CalloutBody>
        else if (cardType === 'code') content = <CodeBody lang={body.match(/```(\w+)/)?.[1]}>{innerContent}</CodeBody>

        return (
          <section
            key={idx}
            id={sectionId}
            className="grid grid-cols-[52px_1fr] sm:grid-cols-[72px_1fr] gap-x-3 sm:gap-x-5 mt-9 first-of-type:mt-0 scroll-mt-6"
          >
            <div className="pt-0.5">
              <ShelfMark
                top={mark}
                time={sectionSec != null ? formatTimestamp(sectionSec) : isDocument && loc ? shortLoc(loc) : undefined}
                className="w-full py-2"
                label={sectionSec != null ? `Play ${heading} from ${formatTimestamp(sectionSec)}` : undefined}
                title={sectionSec != null ? `Play the video from ${formatTimestamp(sectionSec)}` : undefined}
                onClick={sectionSec != null ? () => requestSeek(sectionSec) : undefined}
              />
            </div>
            <div className="min-w-0">
              <h2 className={`font-bold text-np leading-snug mb-2 max-w-[60ch] ${isCaps ? 'text-15 tracking-[0.03em]' : 'text-17'}`}>
                {displayHeading}
              </h2>
              {content}
            </div>
          </section>
        )
      })}

      <div className="mt-10">
        <ChapterScreenshots chapterId={chapterId} startExpanded={screenshotsExpanded} />
      </div>
    </div>
  )
}
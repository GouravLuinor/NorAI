import React, { useState, useEffect, Component, ErrorInfo, ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeHighlight from 'rehype-highlight'
import rehypeKatex from 'rehype-katex'
import { QuestionCard, AnswerKey } from '../components/doc/assessment-cards'
import { ChapterScreenshots } from '../components/doc/ChapterScreenshots'
import { fetchQuizQuestions, type Question } from '../stores/useQuizStore'
import type { Components } from 'react-markdown'
import { Bookmark, Clock, Lightbulb, Code, List, FileText } from 'lucide-react'

// ── Error Boundary ─────────────────────────────────────────────────────────
class PrintErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Print rendering error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="print-document bg-nb text-nt p-8">
          <div className="print-chapter border border-red-500/50 p-6 rounded-lg bg-red-900/10 text-red-400">
            <h1 className="text-xl font-bold mb-2">Rendering Error</h1>
            <p className="font-mono text-sm whitespace-pre-wrap">{this.state.error?.message}</p>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

// ── Card classifier ────────────────────────────────────────────────────────
const DEFINITION_KEYWORDS = ['core concept', 'core idea', 'key concept', 'detailed explanation', 'explanation', 'interval decomposition', 'full binary tree', 'node structure', 'tree construction', 'query operation', 'update operation', 'recursive', 'introduction', 'motivation', 'overview', 'definition', 'property', 'structure', 'implementation', 'complexity', 'mechanism', 'algorithm']
const CALLOUT_KEYWORDS = ['important observation', 'key insight', 'observation', 'common mistake', 'mistake', 'pitfall', 'efficiency gap', 'dynamic limitation', 'limitation', 'the balance', 'balance', 'trade-off', 'tradeoff', 'caution', 'warning', 'note']
const LIST_KEYWORDS = ['application', 'use case', 'key takeaway', 'takeaway', 'example', 'summary', 'checklist']

function getCardType(h: string, body: string): string {
  if (body.includes('```')) return 'code'
  if (body.split('\n').some(l => (l.match(/\|/g) ?? []).length >= 2)) return 'table'
  const hh = h.toLowerCase()
  if (DEFINITION_KEYWORDS.some(k => hh.includes(k))) return 'definition'
  if (CALLOUT_KEYWORDS.some(k => hh.includes(k))) return 'callout'
  if (LIST_KEYWORDS.some(k => hh.includes(k))) return 'list'
  const lines = body.split('\n').filter(l => l.trim())
  if (lines.length > 0 && lines.filter(l => /^\s*[-*•]\s/.test(l)).length / lines.length > 0.5) return 'list'
  return 'prose'
}

// ── Custom Markdown renderers ──────────────────────────────────────────────
const baseComponents: Components = {
  p: ({ children }) => <p className="text-[13px] text-nt2 leading-relaxed mb-2">{children}</p>,
  strong: ({ children }) => <strong className="text-nt font-medium">{children}</strong>,
  ul: ({ children }) => <ul className="list-none pl-0 space-y-2">{children}</ul>,
  li: ({ children }) => <li className="relative pl-5 text-[13px] text-nt2 leading-relaxed"><span className="absolute left-0 top-2 w-1.5 h-1.5 rounded-full bg-ns3 border border-bdr2" />{children}</li>,
  code: ({ children, className }: any) => !className ? <code className="font-mono text-[10px] bg-ns2 px-1.5 py-0.5 rounded text-nt border border-bdr">{children}</code> : <code className={className}>{children}</code>,
  table: ({ children }) => <table className="w-full text-xs text-nt2">{children}</table>,
  thead: ({ children }) => <thead className="text-[10px] font-semibold text-nt uppercase tracking-wider border-b border-bdr2">{children}</thead>,
  th: ({ children }) => <th className="p-2 text-left">{children}</th>,
  td: ({ children }) => <td className="p-2 border-b border-bdr last:border-none">{children}</td>,
}

// ── Card wrappers ──────────────────────────────────────────────────────────
const Wrapper = ({ type, heading, children }: { type: string; heading: string; children: React.ReactNode }) => {
  switch (type) {
    case 'definition': return <div className="bg-ns border border-bdr2 rounded-lg p-4 mb-4 shadow-sm"><div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2"><Bookmark size={13} className="text-np" />{heading}</div>{children}</div>
    case 'table': return <div className="bg-ns border border-bdr2 rounded-lg p-5 mb-5 shadow-sm"><div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2"><Clock size={13} className="text-ng" />{heading}</div>{children}</div>
    case 'callout': return <div className="flex gap-2.5 bg-nblb border border-nblbr rounded-lg p-3 mb-4"><Lightbulb size={14} className="text-nbl mt-0.5 shrink-0" /><div><div className="text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-1">{heading}</div><div className="text-xs text-nt2 leading-relaxed">{children}</div></div></div>
    case 'list': return <div className="mb-5"><div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2"><List size={13} className="text-np" />{heading}</div><ul className="list-none pl-1.5 space-y-2.5">{children}</ul></div>
    case 'code': return <div className="mb-6"><div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2"><Code size={13} className="text-nbl" />{heading}</div><div className="bg-nb border border-bdr2 rounded-lg overflow-hidden shadow-sm"><pre className="p-4 m-0 overflow-x-auto font-mono text-[13px] text-nt2 leading-relaxed">{children}</pre></div></div>
    default: return <div className="bg-ns border border-bdr2 rounded-lg p-5 mb-5 shadow-sm"><div className="flex items-center gap-1.5 text-[9.5px] font-semibold text-nt3 uppercase tracking-wider mb-2"><FileText size={13} className="text-nt3" />{heading}</div>{children}</div>
  }
}

// ── PrintPage logic ────────────────────────────────────────────────────────
function PrintPageContent() {
  const search = typeof window !== 'undefined' ? window.location.search : ''
  const params = new URLSearchParams(search)
  const rawType = params.get('type') || 'notes'

  // Normalize automated script variables to our internal layout states
  let type = 'notes'
  if (rawType.includes('assessment')) type = 'assessment'
  else if (rawType.includes('revision') || rawType.includes('summary')) type = 'revision'

  const [chapters, setChapters] = useState<string[]>([])
  const [assessmentChapters, setAssessmentChapters] = useState<{ ch: number; questions: Question[] }[]>([])
  const [loading, setLoading] = useState(true)
  const [globalError, setGlobalError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        if (type === 'assessment') {
          const promises = Array.from({ length: 6 }, async (_, i) => {
            const ch = i + 1
            const questions = await fetchQuizQuestions(ch).catch(() => [] as Question[])
            return { ch, questions }
          })
          const all = await Promise.all(promises)
          if (!cancelled) setAssessmentChapters(all)
        } else {
          const endpoint = type === 'revision' ? '/summary' : '/notes'
          const promises = Array.from({ length: 6 }, async (_, i) => {
            const ch = i + 1
            try {
              const url = type === 'revision' ? `${endpoint}?chapter_id=${ch}` : `${endpoint}/${ch}`
              const res = await fetch(url)
              if (!res.ok) throw new Error(`HTTP ${res.status}`)
              const raw = await res.text()
              return raw.startsWith('"') ? JSON.parse(raw) : raw
            } catch (err: any) {
              return `# Chapter ${ch}\n\n*Content not yet generated or failed to load. (${err.message})*`
            }
          })
          const texts = await Promise.all(promises)
          if (!cancelled) setChapters(texts)
        }
      } catch (err: any) {
        if (!cancelled) setGlobalError(err.message || 'An unexpected error occurred while fetching print data.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [type])

  if (loading) {
    return <div className="bg-nb text-nt p-8 font-mono text-sm">Generating PDF…</div>
  }

  if (globalError) {
    return (
      <div className="print-document bg-nb text-nt">
        <div className="print-chapter px-8 py-6">
          <div className="border border-red-500/50 p-6 rounded-lg bg-red-900/10 text-red-400">
            <h1 className="text-xl font-bold mb-2">Data Fetch Error</h1>
            <p className="font-mono text-sm">{globalError}</p>
          </div>
        </div>
      </div>
    )
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="print-document bg-nb text-nt">
      {type === 'assessment' && assessmentChapters.map(({ ch, questions }) => (
        <div key={ch} className="print-chapter px-8 py-6">
          <h1 className="text-[21px] font-semibold text-nt tracking-tight mb-6">Chapter {ch} — Assessment</h1>
          {questions.length === 0 ? (
            <div className="text-nt3 italic text-sm">No questions available for this chapter.</div>
          ) : (
            <>
              {questions.map((q, i) => (
                <div key={q.id ?? i} className="mb-4">
                  <QuestionCard question={q} index={i} />
                </div>
              ))}
              <AnswerKey questions={questions} isOpen={true} onToggle={() => {}} />
            </>
          )}
        </div>
      ))}

      {(type === 'notes' || type === 'revision') && chapters.map((md, idx) => {
        const ch = idx + 1
        const lines = md.split('\n')
        let title = `Chapter ${ch}`

        if (lines[0]?.startsWith('# ')) {
          title = lines[0].replace(/^# /, '').trim()
          md = lines.slice(1).join('\n').trim()
        }

        const parts = md.split(/^[ \t]*## /gm)
        const preamble = parts[0]?.trim()
        const sections = parts.slice(1).map(p => {
          const [h, ...b] = p.split('\n')
          return { heading: h?.trim() || '', body: b.join('\n').trim() }
        })

        return (
          <div key={ch} className="print-chapter px-8 py-7 pb-15">
            <h1 className="text-[21px] font-semibold text-nt tracking-tight mb-6">{title}</h1>

            {preamble && (
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeHighlight, rehypeKatex]}
                components={baseComponents}
              >
                {preamble}
              </ReactMarkdown>
            )}

            {sections.map((sec, i) => {
              if (!sec.body) return null
              const inner = (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeHighlight, rehypeKatex]}
                  components={baseComponents}
                >
                  {sec.body}
                </ReactMarkdown>
              )
              const cardType = getCardType(sec.heading, sec.body)
              return <Wrapper key={i} type={cardType} heading={sec.heading}>{inner}</Wrapper>
            })}

            {type === 'notes' && <ChapterScreenshots chapterId={ch} startExpanded={true} lazyLoad={false} />}
          </div>
        )
      })}
    </div>
  )
}

export function PrintPage() {
  return (
    <PrintErrorBoundary>
      <PrintPageContent />
    </PrintErrorBoundary>
  )
}
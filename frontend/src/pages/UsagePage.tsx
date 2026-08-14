import { useState, useEffect } from 'react'
import { ArrowLeft, BarChart3, Database, Cpu, Sparkles, DollarSign, AlertCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/useAuthStore'
import { apiGet } from '../lib/http'
import { Button } from '../components/ui/Button'

interface UsageTotals {
  api_calls: number
  input_tokens: number
  output_tokens: number
  cost_usd: number
  minutes: number
}

interface UsageStage {
  stage: string
  calls: number
  input_tokens: number
  output_tokens: number
  cost_usd: number
}

interface UsageDay {
  date: string
  calls: number
  cost_usd: number
  input_tokens: number
  output_tokens: number
}

interface UsageLecture {
  lecture_id: string
  calls: number
  cost_usd: number
  input_tokens: number
  output_tokens: number
}

interface UsageData {
  user_id?: string
  is_anonymous: boolean
  period: string
  is_estimated: boolean
  totals: UsageTotals
  by_stage: UsageStage[]
  by_day: UsageDay[]
  by_lecture: UsageLecture[]
}

const STAGE_LABEL: Record<string, string> = {
  transcription: 'Transcription',
  extract: 'Chunk extraction',
  outline: 'Lecture outline',
  visual: 'Visual extraction',
  screenshot_selection: 'Screenshot selection',
  notes: 'Study notes',
  embed: 'Embeddings',
  tutor: 'Tutor chat',
  pipeline: 'Pipeline',
}

function fmtCost(v: number) {
  if (!v) return '$0.00'
  if (v < 0.01) return `$${v.toFixed(4)}`
  if (v < 100) return `$${v.toFixed(2)}`
  return `$${v.toFixed(0)}`
}

function fmtTokens(v: number) {
  if (!v) return '0'
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`
  return String(v)
}

// Tiny dependency-free SVG bar chart for the per-day spend (no chart lib in the
// bundle, matching the project's zero-dep chart posture).
function SpendBarChart({ byDay, max }: { byDay: UsageDay[]; max: number }) {
  if (!byDay.length) {
    return (
      <div className="h-40 flex items-center justify-center text-11 text-nt4">
        No metered usage yet this period.
      </div>
    )
  }
  const cols = Math.max(byDay.length, 1)
  const barW = Math.max(6, Math.min(36, Math.floor(560 / cols)))
  return (
    <div className="flex items-end gap-1 h-40 overflow-x-auto pb-1" role="img" aria-label="Daily API cost bar chart">
      {byDay.map((d) => (
        <div key={d.date} className="flex flex-col items-center gap-1 shrink-0" title={`${d.date}: ${fmtCost(d.cost_usd)}`}>
          <div
            className="w-full rounded-t bg-np/80 hover:bg-np transition-colors"
            style={{ height: `${Math.max(2, (d.cost_usd / (max || 1)) * 96)}px`, width: barW }}
          />
          <span className="text-10 text-nt4 tabular-nums">{d.date.slice(8)}</span>
        </div>
      ))}
    </div>
  )
}

export function UsagePage() {
  const navigate = useNavigate()
  const { user, openAuthModal } = useAuthStore()
  const [data, setData] = useState<UsageData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const userId = user?.id

  useEffect(() => {
    let active = true
    if (!userId) {
      setData(null)
      return
    }
    apiGet<UsageData>('/usage')
      .then((d) => {
        if (active) setData(d)
      })
      .catch((e) => {
        if (active) setError(String(e instanceof Error ? e.message : e))
      })
    return () => {
      active = false
    }
  }, [userId])

  if (!user) {
    return (
      <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center justify-center px-6 py-16">
        <div className="max-w-md w-full text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-npb border border-npbr text-npt font-mono text-11 font-medium mb-6">
            <BarChart3 size={12} className="text-np" />
            <span>USAGE &amp; COST</span>
          </div>
          <h1 className="text-28 font-bold font-serif text-nt tracking-tight mb-3">Sign in to see your usage</h1>
          <p className="text-13 text-nt2 mb-6">Your Gemini API spend, per lecture and per stage, once you're signed in.</p>
          <div className="flex justify-center gap-3">
            <Button variant="primary" className="px-5 py-2 rounded-md text-12 gap-2" onClick={() => openAuthModal('login')}>
              Log in
            </Button>
            <Button variant="outline" className="px-5 py-2 rounded-md text-12 gap-2 bg-transparent border-bdr2 hover:border-nt4" onClick={() => openAuthModal('signup')}>
              Create account
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center justify-center px-6 py-16">
        <p className="text-13 text-nr mb-4">Couldn't load usage data ({error}).</p>
        <Button variant="outline" className="px-4 py-2 rounded-md text-12 bg-transparent border-bdr2" onClick={() => navigate('/workspace')}>
          <ArrowLeft size={14} /> Back to workspace
        </Button>
      </div>
    )
  }

  if (!data) {
    return (
      <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center justify-center px-6 py-16">
        <div className="text-13 text-nt3">Loading usage…</div>
      </div>
    )
  }

  const maxDay = Math.max(0.000001, ...data.by_day.map((d) => d.cost_usd))
  const totalTokens = (data.totals.input_tokens || 0) + (data.totals.output_tokens || 0)

  return (
    <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center py-12 px-6">
      <div className="w-full max-w-4xl flex flex-col gap-8 relative z-10">
        <button
          onClick={() => navigate('/workspace')}
          className="inline-flex items-center gap-1.5 text-12 text-nt3 hover:text-nt self-start cursor-pointer"
        >
          <ArrowLeft size={14} /> Back to workspace
        </button>

        <div className="text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-npb border border-npbr text-npt font-mono text-11 font-medium mb-4">
            <BarChart3 size={12} className="text-np" />
            <span>USAGE &amp; COST</span>
          </div>
          <h1 className="text-32 font-bold font-serif text-nt tracking-tight mb-2 text-balance">
            Gemini API spend
          </h1>
          <p className="text-14 text-nt2 max-w-xl mx-auto">
            Metered tokens and estimated cost for your lectures and tutor chats.
            {data.is_estimated && (
              <span className="text-nt3"> Embedding cost is estimated from character counts.</span>
            )}
          </p>
        </div>

        {/* Summary cards */}
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="rounded-lg bg-ns border border-bdr p-4">
            <div className="flex items-center gap-1.5 text-11 text-nt3 mb-1">
              <DollarSign size={12} className="text-np" /> Estimated cost
            </div>
            <div className="text-22 font-bold text-nt tabular-nums">{fmtCost(data.totals.cost_usd)}</div>
          </div>
          <div className="rounded-lg bg-ns border border-bdr p-4">
            <div className="flex items-center gap-1.5 text-11 text-nt3 mb-1">
              <Cpu size={12} className="text-np" /> API calls
            </div>
            <div className="text-22 font-bold text-nt tabular-nums">{data.totals.api_calls.toLocaleString()}</div>
          </div>
          <div className="rounded-lg bg-ns border border-bdr p-4">
            <div className="flex items-center gap-1.5 text-11 text-nt3 mb-1">
              <Database size={12} className="text-np" /> Tokens
            </div>
            <div className="text-22 font-bold text-nt tabular-nums">{fmtTokens(totalTokens)}</div>
          </div>
          <div className="rounded-lg bg-ns border border-bdr p-4">
            <div className="flex items-center gap-1.5 text-11 text-nt3 mb-1">
              <Sparkles size={12} className="text-np" /> Minutes used
            </div>
            <div className="text-22 font-bold text-nt tabular-nums">{data.totals.minutes}</div>
          </div>
        </section>

        {/* Daily cost chart */}
        <section className="rounded-lg bg-ns border border-bdr p-5">
          <h2 className="text-13 font-semibold text-nt mb-3">Cost by day</h2>
          <SpendBarChart byDay={data.by_day} max={maxDay} />
        </section>

        {/* By stage */}
        <section className="rounded-lg bg-ns border border-bdr p-5">
          <h2 className="text-13 font-semibold text-nt mb-3">Cost by stage</h2>
          {data.by_stage.length === 0 ? (
            <p className="text-11 text-nt4">No metered stage usage yet this period.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {data.by_stage.map((s) => {
                const pct = Math.min(100, (s.cost_usd / (data.totals.cost_usd || 1)) * 100)
                return (
                  <div key={s.stage} className="flex items-center gap-3">
                    <span className="w-40 text-11 text-nt2 truncate shrink-0">
                      {STAGE_LABEL[s.stage] ?? s.stage}
                    </span>
                    <div className="flex-1 bg-ns4 h-2.5 rounded-full overflow-hidden">
                      <div className="bg-np h-full rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="w-20 text-right text-11 text-nt tabular-nums shrink-0">
                      {fmtCost(s.cost_usd)}
                    </span>
                    <span className="w-16 text-right text-10 text-nt4 tabular-nums shrink-0">
                      {s.calls} calls
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </section>

        {/* By lecture */}
        <section className="rounded-lg bg-ns border border-bdr p-5">
          <h2 className="text-13 font-semibold text-nt mb-3">Cost by lecture</h2>
          {data.by_lecture.length === 0 ? (
            <p className="text-11 text-nt4">No metered lectures yet this period.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {data.by_lecture.map((l) => (
                <div key={l.lecture_id} className="flex items-center justify-between gap-3 text-11">
                  <span className="font-mono text-nt2 truncate">{l.lecture_id}</span>
                  <span className="text-nt3 tabular-nums">
                    {l.input_tokens + l.output_tokens} tokens · {l.calls} calls
                  </span>
                  <span className="text-nt font-medium tabular-nums">{fmtCost(l.cost_usd)}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <p className="text-center text-10 text-nt4 flex items-center justify-center gap-1">
          <AlertCircle size={11} /> Costs are metered estimates based on published Gemini pricing.
        </p>
      </div>
    </div>
  )
}

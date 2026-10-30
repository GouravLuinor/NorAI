import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Wordmark } from '../components/brand/Wordmark'
import { Button } from '../components/ui/Button'
import { ShelfMark } from '../components/ui/ShelfMark'
import { apiGet } from '../lib/http'
import type { ResolvedShare } from '../types'
import { ArrowRight, BookOpen, Brain, Check, Sparkles } from 'lucide-react'

function formatDuration(sec: number | null | undefined): string {
  if (!sec || sec <= 0) return ''
  const m = Math.floor(sec / 60)
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  const remM = m % 60
  return `${h}h ${remM > 0 ? `${remM}m` : ''}`
}

/**
 * Landing page for an unlisted share link. Resolves the slug against the
 * backend, renders a rich per-lecture preview, and provides one-click workspace entry.
 */
export function ShareRedirect() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [state, setState] = useState<'resolving' | 'ready' | 'error'>('resolving')
  const [shareInfo, setShareInfo] = useState<ResolvedShare | null>(null)

  useEffect(() => {
    let active = true
    if (!slug) {
      setState('error')
      return
    }
    apiGet<ResolvedShare>(`/share/${slug}`)
      .then((info) => {
        if (active && info?.lecture_id) {
          try {
            sessionStorage.setItem(`norai_shared_${info.lecture_id}`, 'true')
          } catch {
            // ignore storage restrictions
          }
          setShareInfo(info)
          setState('ready')
        } else if (active) {
          setState('error')
        }
      })
      .catch(() => {
        if (active) setState('error')
      })
    return () => {
      active = false
    }
  }, [slug])

  const openWorkspace = () => {
    if (shareInfo?.lecture_id) {
      try {
        sessionStorage.setItem(`norai_shared_${shareInfo.lecture_id}`, 'true')
      } catch {
        // ignore storage restrictions
      }
      navigate(`/workspace/${shareInfo.lecture_id}`)
    }
  }

  return (
    <div id="main" className="min-h-screen bg-nb flex flex-col items-center justify-center px-4 sm:px-6 py-12">
      <div className="max-w-lg w-full">
        <div className="mb-8 text-center sm:text-left">
          <Wordmark size="md" />
        </div>

        {state === 'resolving' ? (
          <div className="bg-ns border border-bdr rounded-lg p-8 text-center">
            <span className="inline-block h-6 w-6 rounded-full border-2 border-ns3 border-t-np animate-spin mb-4" />
            <h1 className="text-22 font-semibold font-serif text-nt leading-tight mb-2">
              Opening shared lecture…
            </h1>
            <p className="text-14 text-nt2">Fetching lecture notes and study materials.</p>
          </div>
        ) : state === 'ready' && shareInfo ? (
          <div className="bg-ns border border-bdr rounded-lg p-6 sm:p-8 shadow-ev2">
            <div className="flex items-center justify-between gap-3 mb-4">
              <ShelfMark top="SHARED" time={formatDuration(shareInfo.duration_sec) || 'LECTURE'} />
              <span className="text-12 font-mono text-nt3 uppercase tracking-wider bg-ns2 px-2.5 py-1 rounded">
                {shareInfo.chapters_count ? `${shareInfo.chapters_count} Chapters` : 'Complete Study Pack'}
              </span>
            </div>

            <h1 className="text-24 sm:text-26 font-bold font-serif text-nt leading-snug mb-3">
              {shareInfo.title}
            </h1>

            <p className="text-14 text-nt2 mb-6 leading-relaxed">
              A classmate or instructor shared this lecture study pack with you. All notes, revision sheets, and quizzes are ready.
            </p>

            <div className="border-t border-b border-bdr/60 py-4 mb-6 space-y-2.5 text-14 text-nt2">
              <div className="flex items-center gap-2.5 text-nt">
                <BookOpen size={16} className="text-np shrink-0" />
                <span>Chapter-wise study notes & formulas</span>
              </div>
              <div className="flex items-center gap-2.5 text-nt">
                <Check size={16} className="text-np shrink-0" />
                <span>Key takeaways revision sheet & practice quiz</span>
              </div>
              <div className="flex items-center gap-2.5 text-nt">
                <Brain size={16} className="text-np shrink-0" />
                <span>Spaced repetition flashcards (SM-2)</span>
              </div>
              {shareInfo.allow_tutor_chat && (
                <div className="flex items-center gap-2.5 text-np font-medium">
                  <Sparkles size={16} className="text-brass shrink-0" />
                  <span>AI Tutor Nora enabled: ask lecture-grounded questions</span>
                </div>
              )}
            </div>

            <div className="space-y-3">
              <Button
                onClick={openWorkspace}
                className="w-full h-12 rounded-md text-16 font-bold gap-2 justify-center"
              >
                Open Lecture in Workspace <ArrowRight size={17} />
              </Button>
              <button
                type="button"
                onClick={() => navigate('/')}
                className="w-full py-2 text-center text-14 text-nt3 hover:text-nt transition-colors cursor-pointer"
              >
                Learn more about NorAI
              </button>
            </div>
          </div>
        ) : (
          <div className="bg-ns border border-bdr rounded-lg p-8">
            <h1 className="text-24 font-semibold font-serif text-nt leading-tight mb-2">
              This share link doesn't work
            </h1>
            <p className="text-15 text-nt2 leading-relaxed mb-6">
              This link may have been revoked, expired, or mistyped. Ask the owner for a fresh link.
            </p>
            <Button className="px-5 h-11 rounded-md text-15 font-bold" onClick={() => navigate('/')}>
              Go to NorAI
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
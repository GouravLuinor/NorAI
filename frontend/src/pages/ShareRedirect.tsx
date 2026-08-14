import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Share2 } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { apiGet } from '../lib/http'
import type { ResolvedShare } from '../types'

/**
 * Landing page for an unlisted share link. Resolves the slug against the
 * backend, then redirects into the shared lecture's workspace. Anonymous-safe.
 */
export function ShareRedirect() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [state, setState] = useState<'resolving' | 'error'>('resolving')

  useEffect(() => {
    let active = true
    if (!slug) {
      setState('error')
      return
    }
    apiGet<ResolvedShare>(`/share/${slug}`)
      .then((info) => {
        if (active && info?.lecture_id) {
          navigate(`/workspace/${info.lecture_id}`, { replace: true })
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
  }, [slug, navigate])

  return (
    <div id="main" className="min-h-screen bg-nb bg-blueprint-grid noise flex flex-col items-center justify-center px-6 py-16">
      <div className="max-w-md w-full text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-npb border border-npbr text-npt font-mono text-11 font-medium mb-6">
          <Share2 size={12} className="text-np" />
          <span>SHARED LECTURE</span>
        </div>
        {state === 'resolving' ? (
          <>
            <h1 className="text-24 font-bold font-serif text-nt tracking-tight mb-3">Opening shared lecture…</h1>
            <p className="text-13 text-nt2">Resolving the share link.</p>
          </>
        ) : (
          <>
            <h1 className="text-24 font-bold font-serif text-nt tracking-tight mb-3">Share link not found</h1>
            <p className="text-13 text-nt2 mb-6">
              This link may have been revoked, expired, or mistyped. Ask the owner for a fresh link.
            </p>
            <Button variant="outline" className="px-4 py-2 rounded-md text-12 bg-transparent border-bdr2" onClick={() => navigate('/')}>
              Back to home
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
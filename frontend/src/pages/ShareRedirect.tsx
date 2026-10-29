import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Wordmark } from '../components/brand/Wordmark'
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
    <div id="main" className="min-h-screen bg-nb flex flex-col items-center justify-center px-6 py-16">
      <div className="max-w-md w-full">
        <div className="mb-10">
          <Wordmark size="md" />
        </div>
        {state === 'resolving' ? (
          <>
            <h1 className="text-28 font-semibold font-serif text-nt leading-tight mb-2">Opening a shared lecture…</h1>
            <p className="text-16 text-nt2" role="status">Someone shared their notes with you. One moment.</p>
          </>
        ) : (
          <>
            <h1 className="text-28 font-semibold font-serif text-nt leading-tight mb-2">This share link doesn't work</h1>
            <p className="text-16 text-nt2 leading-relaxed mb-6">
              This link may have been revoked, expired, or mistyped. Ask the owner for a fresh link.
            </p>
            <Button className="px-5 h-11 rounded-md text-15 font-bold" onClick={() => navigate('/')}>
              Go to NorAI
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
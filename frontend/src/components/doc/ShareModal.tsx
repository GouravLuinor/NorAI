import { useEffect, useState } from 'react'
import { X, Share2, Copy, Link2, ShieldCheck, RefreshCw } from 'lucide-react'
import { Dialog } from '../ui/Dialog'
import { IconButton } from '../ui/IconButton'
import { Button } from '../ui/Button'
import { FOCUS_RING } from '../ui/shared'
import { apiPost, apiPatch, apiDelete, apiGet } from '../../lib/http'
import { useToastStore } from '../../stores/useToastStore'
import type { ShareLinkInfo } from '../../types'

interface ShareModalProps {
  lectureId: string
  isOpen: boolean
  onClose: () => void
}

/**
 * P6.4 — create / manage the unlisted share link for a lecture.
 * Anyone with the link can read the lecture; tutor chat only when the owner
 * enables it. Revoking deletes the link (anonymous access dies immediately).
 */
export function ShareModal({ lectureId, isOpen, onClose }: ShareModalProps) {
  const addToast = useToastStore((s) => s.addToast)
  const [busy, setBusy] = useState(false)
  const [link, setLink] = useState<ShareLinkInfo | null>(null)

  useEffect(() => {
    if (!isOpen || !lectureId) return
    setBusy(true)
    setLink(null)
    apiGet<ShareLinkInfo>(`/lectures/${lectureId}/share`)
      .then((info) => setLink(info))
      .catch(() => setLink(null))
      .finally(() => setBusy(false))
  }, [isOpen, lectureId])

  const handleCreate = async () => {
    setBusy(true)
    try {
      const created = await apiPost<ShareLinkInfo>(`/lectures/${lectureId}/share`, {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allow_tutor_chat: true }),
      })
      setLink(created)
      addToast('Share link created', 'success')
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Could not create share link', 'error')
    } finally {
      setBusy(false)
    }
  }

  const handleToggleTutor = async (allow: boolean) => {
    setBusy(true)
    try {
      const updated = await apiPatch<ShareLinkInfo>(`/lectures/${lectureId}/share`, {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allow_tutor_chat: allow }),
      })
      setLink(updated)
      addToast(allow ? 'AI tutor chat enabled for shared viewers' : 'AI tutor chat disabled for shared viewers', 'success')
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Could not update share link', 'error')
    } finally {
      setBusy(false)
    }
  }

  const handleRevoke = async () => {
    if (!window.confirm('Revoke this share link? Anyone with it will lose access immediately.')) return
    setBusy(true)
    try {
      await apiDelete(`/lectures/${lectureId}/share`)
      setLink(null)
      addToast('Share link revoked', 'success')
    } catch (err) {
      addToast(err instanceof Error ? err.message : 'Could not revoke share link', 'error')
    } finally {
      setBusy(false)
    }
  }

  const handleCopy = async () => {
    if (!link?.url) return
    try {
      await navigator.clipboard.writeText(link.url)
      addToast('Link copied to clipboard', 'success')
    } catch {
      addToast('Could not copy — copy it manually from the field below.', 'error')
    }
  }

  if (!isOpen) return null

  return (
    <Dialog
      ariaLabel="Share this lecture"
      onClose={onClose}
      panelClassName="bg-ns border border-bdr2 rounded-xl p-6 w-full max-w-md shadow-ev3"
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-medium text-nt flex items-center gap-2">
          <Share2 size={14} strokeWidth={1.5} /> Share this lecture
        </h2>
        <IconButton label="Close share dialog" variant="bare" onClick={onClose}>
          <X size={14} strokeWidth={1.5} />
        </IconButton>
      </div>

      {!link ? (
        <div className="flex flex-col gap-4">
          <p className="text-2xs text-nt3">
            Create an unlisted link. Anyone with the link can view this lecture — nobody else will
            find it. No account needed on their side.
          </p>
          <Button variant="primary" onClick={handleCreate} disabled={busy} className="gap-1.5 px-4 py-2 rounded-md text-xs self-start">
            <Link2 size={13} /> {busy ? 'Creating…' : 'Create share link'}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <input
              readOnly
              aria-label="Share link"
              value={link.url}
              onFocus={(e) => e.currentTarget.select()}
              className="flex-1 rounded-md bg-ns2 border border-bdr2 px-3 py-2 text-2xs font-mono text-nt outline-none"
            />
            <Button variant="outline" onClick={handleCopy} className="gap-1 px-3 py-2 rounded-md text-2xs bg-transparent border-bdr2">
              <Copy size={12} /> Copy
            </Button>
          </div>

          <div className="flex items-center justify-between gap-3 rounded-md border border-bdr2 bg-ns2 px-3 py-2.5">
            <div className="flex items-center gap-2 text-2xs text-nt2">
              <ShieldCheck size={13} className="text-np" />
              <span id="share-tutor-chat-label">Allow AI tutor chat</span>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={link.allow_tutor_chat}
              aria-labelledby="share-tutor-chat-label"
              onClick={() => handleToggleTutor(!link.allow_tutor_chat)}
              disabled={busy}
              className={`relative h-5 w-9 rounded-full transition-colors ${FOCUS_RING} ${
                link.allow_tutor_chat ? 'bg-np' : 'bg-ns4'
              }`}
            >
              <span
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-nb border border-bdr2 transition-transform ${
                  link.allow_tutor_chat ? 'translate-x-[18px]' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>
          <p className="text-2xs text-nt4">
            When on, viewers can ask the AI tutor (costs are metered to this lecture's owner). When off,
            viewers can read everything but chat stays disabled.
          </p>

          <div className="flex items-center justify-between">
            <Button variant="outline" onClick={handleRevoke} disabled={busy} className="gap-1.5 px-3 py-1.5 rounded-md text-2xs text-nr bg-transparent border-nrbr">
              <RefreshCw size={12} /> Revoke
            </Button>
            <span className="text-2xs text-nt4">Revoking kills the link instantly.</span>
          </div>
        </div>
      )}
    </Dialog>
  )
}
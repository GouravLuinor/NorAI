import { useEffect, useRef, useState } from 'react'
import { Play, X } from 'lucide-react'
import { useVideoStore, type VideoPlayerHandle } from '../../stores/useVideoStore'
import { useLectureStore } from '../../stores/useLectureStore'
import { FOCUS_RING } from '../ui/shared'

/**
 * VideoPlayer — P6.3 click-to-video grounding.
 *
 * A floating "Watch video" button (bottom-right of the doc panel) that opens a
 * docked YouTube player on demand. The local copy of the video is transient
 * (deleted when the pipeline ends), so the player streams straight from
 * YouTube and only renders for completed, YouTube-sourced lectures. Every seek
 * request (chapter chips, tutor references) flows through useVideoStore, which
 * auto-opens the dock and buffers the target until the player is ready.
 */

function loadYouTubeIframeApi(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.YT && window.YT.Player) {
      resolve()
      return
    }
    const prev = window.onYouTubeIframeAPIReady
    window.onYouTubeIframeAPIReady = () => {
      prev?.()
      resolve()
    }
    const script = document.createElement('script')
    script.src = 'https://www.youtube.com/iframe_api'
    script.async = true
    script.onerror = () => reject(new Error('Failed to load the YouTube IFrame API'))
    document.head.appendChild(script)
  })
}

export function VideoPlayer() {
  const activeLectureId = useLectureStore((s) => s.activeLectureId)
  const lectureId = activeLectureId && activeLectureId !== 'default' ? activeLectureId : null

  const videoLoad = useVideoStore((s) => s.load)
  const reset = useVideoStore((s) => s.reset)
  const embeddable = useVideoStore((s) => s.embeddable)
  const open = useVideoStore((s) => s.open)
  const togglePlayer = useVideoStore((s) => s.togglePlayer)
  const videoId = useVideoStore((s) => s.videoId)
  const registerPlayer = useVideoStore((s) => s.registerPlayer)
  const clearPlayer = useVideoStore((s) => s.clearPlayer)

  const [error, setError] = useState(false)
  const [apiReady, setApiReady] = useState(false)
  const playerRef = useRef<VideoPlayerHandle | null>(null)
  const hostRef = useRef<HTMLDivElement>(null)

  // Load source info + seek map whenever the lecture changes.
  useEffect(() => {
    setError(false)
    setApiReady(false)
    if (lectureId) {
      void videoLoad(lectureId)
    } else {
      reset()
    }
  }, [lectureId, videoLoad, reset])

  // Lazy-load the IFrame API only when the player is opened.
  useEffect(() => {
    if (!open || !embeddable || apiReady) return
    let cancelled = false
    loadYouTubeIframeApi()
      .then(() => {
        if (!cancelled) setApiReady(true)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
    return () => {
      cancelled = true
    }
  }, [open, embeddable, apiReady])

  // Create/destroy the player around the host div.
  useEffect(() => {
    if (!open || !embeddable || !apiReady || !hostRef.current || !window.YT?.Player) return
    setError(false)
    const player = new window.YT.Player(hostRef.current, {
      videoId: videoId ?? '',
      playerVars: { playsinline: 1, rel: 0, modestbranding: 1 },
      events: {
        onReady: (e) => {
          playerRef.current = e.target
          registerPlayer(e.target)
        },
        onError: () => setError(true),
      },
    })
    return () => {
      playerRef.current = null
      clearPlayer()
      player.destroy()
    }
  }, [open, embeddable, apiReady, videoId, registerPlayer, clearPlayer])

  // Nothing to show until we know the source — the button appears only for
  // completed YouTube lectures (the local copy is transient during processing).
  if (!lectureId || !embeddable) return null

  return (
    <>
      {open && (
        <div className="absolute bottom-14 right-3 z-50 w-[min(560px,46vw)] max-w-full rounded-md border border-bdr2 bg-ns shadow-ev2 overflow-hidden">
          <div className="flex items-center gap-2 px-3 h-[30px] border-b border-bdr">
            <Play size={11} strokeWidth={1.5} className="text-np" />
            <span className="text-2xs font-medium text-nt2">Lecture video</span>
            <button
              type="button"
              onClick={togglePlayer}
              aria-label="Close video"
              className={`ml-auto p-1 text-nt4 hover:text-nt2 rounded-sm cursor-pointer ${FOCUS_RING}`}
            >
              <X size={12} strokeWidth={1.5} />
            </button>
          </div>
          <div className="aspect-video w-full bg-black">
            <div ref={hostRef} className="w-full h-full" />
          </div>
          {error && (
            <p className="px-3 py-2 text-2xs text-nr border-t border-bdr">
              Couldn't load the video. It may be private, unlisted, or removed on
              YouTube.
            </p>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={togglePlayer}
        aria-label={open ? 'Close video player' : 'Watch video'}
        aria-expanded={open}
        className={`absolute bottom-3 right-3 z-50 flex items-center gap-1.5 px-3 py-1.5 rounded-md text-11 font-medium shadow-ev2 animate-fade-in cursor-pointer transition bg-np text-ns hover:opacity-90 ${FOCUS_RING}`}
      >
        {open ? <X size={13} strokeWidth={1.5} /> : <Play size={13} strokeWidth={1.5} />}
        {open ? 'Close' : 'Watch video'}
      </button>
    </>
  )
}

/**
 * video.ts — P6.3 helpers for click-to-video grounding.
 *
 * Pure functions only (no React, no store), so they're unit-testable:
 *   - formatTimestamp: seconds → "m:ss" (or "h:mm:ss" over an hour)
 *   - extractYoutubeVideoId: pull the video id out of any common YouTube URL
 */

export function formatTimestamp(sec: number | null | undefined): string {
  if (sec == null || !Number.isFinite(sec) || sec < 0) return ''
  const total = Math.floor(sec)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

export function extractYoutubeVideoId(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    const parsed = new URL(url)
    if (/youtu\.be$/.test(parsed.hostname)) {
      const id = parsed.pathname.replace(/^\//, '')
      return id || null
    }
    if (parsed.hostname === 'youtube.com' || parsed.hostname === 'www.youtube.com' || parsed.hostname === 'm.youtube.com') {
      const v = parsed.searchParams.get('v')
      if (v) return v
      const pathMatch = parsed.pathname.match(/^\/(?:embed|shorts|live)\/([\w-]{11})$/)
      return pathMatch ? pathMatch[1] : null
    }
  } catch {
    // not a URL — fall through
  }
  // bare 11-char video id
  return /^[\w-]{11}$/.test(url.trim()) ? url.trim() : null
}

/**
 * Minimal ambient types for the YouTube IFrame Player API (P6.3).
 * The full @types/youtube is overkill; we only drive seekTo + playVideo.
 */
export {}

interface YTPlayer {
  seekTo(seconds: number, allowSeekAhead: boolean): void
  playVideo(): void
  pauseVideo(): void
  destroy(): void
}

interface YTPlayerOptions {
  videoId: string
  width?: string | number
  height?: string | number
  playerVars?: Record<string, string | number>
  events?: {
    onReady?: (event: { target: YTPlayer }) => void
    onError?: (event: { data: number }) => void
    onStateChange?: (event: { data: number }) => void
  }
}

interface YTNamespace {
  Player: new (elementId: string | HTMLElement, options: YTPlayerOptions) => YTPlayer
}

declare global {
  interface Window {
    YT?: YTNamespace
    onYouTubeIframeAPIReady?: (() => void) | null
  }
}

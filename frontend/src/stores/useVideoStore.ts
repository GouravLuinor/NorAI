import { create } from 'zustand'
import { apiFetch } from '../lib/http'
import { extractYoutubeVideoId } from '../lib/video'

/**
 * useVideoStore — P6.3 click-to-video grounding.
 *
 * Owns the per-lecture video source info + seek map (from /video-map) and a
 * reference to the mounted YouTube player, so ANY component (chapter chips,
 * tutor references, sidebar rows) can ask the player to jump to a timestamp
 * without prop drilling. A pending seek is buffered until the player is ready.
 */

export interface ChapterTime {
  chapter_id: number
  title: string
  chunk_ids: number[]
  start_sec: number | null
  end_sec: number | null
}

export interface ChunkTime {
  chunk_id: number
  start_sec: number
  end_sec: number | null
}

export interface VideoMap {
  chapters: ChapterTime[]
  chunks: ChunkTime[]
}

/** Minimal surface of the YouTube IFrame player the rest of the app may use. */
export interface VideoPlayerHandle {
  seekTo: (seconds: number, allowSeekAhead: boolean) => void
  playVideo: () => void
}

interface LectureSourceInfo {
  source_type?: string | null
  source_url?: string | null
  status?: string | null
}

interface VideoState {
  lectureId: string | null
  sourceType: string | null
  status: string | null
  videoId: string | null
  map: VideoMap | null
  /** True when a YouTube embed can actually play this lecture. */
  embeddable: boolean
  /** Whether the floating player dock is open. */
  open: boolean
  player: VideoPlayerHandle | null
  pendingSeek: number | null

  load: (lectureId: string) => Promise<void>
  reset: () => void
  togglePlayer: () => void
  setPlayerOpen: (open: boolean) => void
  registerPlayer: (player: VideoPlayerHandle) => void
  clearPlayer: () => void
  requestSeek: (seconds: number) => void
  seekToChapter: (chapterId: number) => void
  chapterStart: (chapterId: number | undefined) => number | null
}

export const useVideoStore = create<VideoState>((set, get) => ({
  lectureId: null,
  sourceType: null,
  status: null,
  videoId: null,
  map: null,
  embeddable: false,
  open: false,
  player: null,
  pendingSeek: null,

  load: async (lectureId) => {
    set({
      lectureId,
      sourceType: null,
      status: null,
      videoId: null,
      map: null,
      embeddable: false,
      open: false,
      pendingSeek: null,
    })
    const info = await apiFetch<LectureSourceInfo>(`/lectures/${lectureId}`)
    const map = await apiFetch<VideoMap>(`/video-map?lecture_id=${lectureId}`)
    const sourceType = info?.source_type ?? null
    const videoId = extractYoutubeVideoId(info?.source_url)
    set({
      sourceType,
      status: info?.status ?? null,
      videoId,
      map: map ?? null,
      embeddable: sourceType === 'youtube' && info?.status === 'completed' && videoId != null,
    })
  },

  reset: () =>
    set({
      lectureId: null,
      sourceType: null,
      status: null,
      videoId: null,
      map: null,
      embeddable: false,
      open: false,
      player: null,
      pendingSeek: null,
    }),

  togglePlayer: () => set((s) => ({ open: !s.open })),

  setPlayerOpen: (open) => set({ open }),

  registerPlayer: (player) => {
    set({ player })
    const pending = get().pendingSeek
    if (pending != null) {
      set({ pendingSeek: null })
      player.seekTo(pending, true)
      player.playVideo()
    }
  },

  clearPlayer: () => set({ player: null }),

  requestSeek: (seconds) => {
    if (!Number.isFinite(seconds) || seconds < 0) return
    set({ open: true })
    const player = get().player
    if (player) {
      player.seekTo(seconds, true)
      player.playVideo()
    } else {
      set({ pendingSeek: seconds })
    }
  },

  seekToChapter: (chapterId) => {
    const start = get().chapterStart(chapterId)
    if (start != null) get().requestSeek(start)
  },

  chapterStart: (chapterId) => {
    if (chapterId == null) return null
    const ch = get().map?.chapters.find((c) => c.chapter_id === chapterId)
    return ch?.start_sec ?? null
  },
}))

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
  seekToChunk: (chunkId: string | number, chapterId?: number) => void
  chapterStart: (chapterId: number | undefined) => number | null
  chunkStart: (chunkId?: string | number | null, chapterId?: number | null) => number | null
  chunkRange: (chunkId?: string | number | null, chapterId?: number | null) => { start_sec: number; end_sec: number | null } | null
  sectionStart: (chapterId: number | undefined, sectionIndex: number) => number | null
}

function resolveChunkId(chunkSpec: string | number, map: VideoMap | null): number | null {
  if (typeof chunkSpec === 'number' && Number.isFinite(chunkSpec)) {
    return chunkSpec
  }
  const str = String(chunkSpec).trim()
  if (/^\d+$/.test(str)) {
    return Number(str)
  }
  const directMatch = str.match(/^c(?:hunk_)?(\d+)$/i)
  if (directMatch) {
    return Number(directMatch[1])
  }
  const chromaMatch = str.match(/^ch(\d+)__.*?__(\d+)$/)
  if (chromaMatch && map) {
    const chId = Number(chromaMatch[1])
    const offset = Number(chromaMatch[2])
    const chapter = map.chapters.find((c) => c.chapter_id === chId)
    if (chapter?.chunk_ids && chapter.chunk_ids[offset] != null) {
      return chapter.chunk_ids[offset]
    }
  }
  return null
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

  seekToChunk: (chunkId, chapterId) => {
    const start = get().chunkStart(chunkId, chapterId)
    if (start != null) get().requestSeek(start)
  },

  chapterStart: (chapterId) => {
    if (chapterId == null) return null
    const ch = get().map?.chapters.find((c) => c.chapter_id === chapterId)
    return ch?.start_sec ?? null
  },

  chunkStart: (chunkId, chapterId) => {
    const map = get().map
    if (chunkId != null && map) {
      const resolvedId = resolveChunkId(chunkId, map)
      if (resolvedId != null) {
        const chunk = map.chunks.find((c) => c.chunk_id === resolvedId)
        if (chunk?.start_sec != null) return chunk.start_sec
      }
    }
    return get().chapterStart(chapterId ?? undefined)
  },

  chunkRange: (chunkId, chapterId) => {
    const map = get().map
    if (chunkId != null && map) {
      const resolvedId = resolveChunkId(chunkId, map)
      if (resolvedId != null) {
        const chunk = map.chunks.find((c) => c.chunk_id === resolvedId)
        if (chunk?.start_sec != null) {
          return { start_sec: chunk.start_sec, end_sec: chunk.end_sec }
        }
      }
    }
    const chapter = chapterId != null ? map?.chapters.find((c) => c.chapter_id === chapterId) : null
    if (chapter?.start_sec != null) {
      return { start_sec: chapter.start_sec, end_sec: chapter.end_sec }
    }
    return null
  },

  sectionStart: (chapterId, sectionIndex) => {
    if (chapterId == null) return null
    const map = get().map
    const chapter = map?.chapters.find((c) => c.chapter_id === chapterId)
    if (!chapter) return null

    if (chapter.chunk_ids && chapter.chunk_ids[sectionIndex] != null) {
      const chunkId = chapter.chunk_ids[sectionIndex]
      const chunk = map?.chunks.find((c) => c.chunk_id === chunkId)
      if (chunk?.start_sec != null) return chunk.start_sec
    }

    return chapter.start_sec ?? null
  },
}))

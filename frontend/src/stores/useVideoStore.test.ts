import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useVideoStore, type VideoMap, type VideoPlayerHandle } from './useVideoStore'

vi.mock('../lib/http', () => ({
  apiFetch: vi.fn(),
}))

import { apiFetch } from '../lib/http'

const apiFetchMock = vi.mocked(apiFetch)

const YT_LECTURE = { source_type: 'youtube', source_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', status: 'completed' }
const MAP: VideoMap = {
  chapters: [
    { chapter_id: 1, title: 'Intro', chunk_ids: [0, 1], start_sec: 0, end_sec: 150 },
    { chapter_id: 2, title: 'Deep Dive', chunk_ids: [2], start_sec: 150, end_sec: 240 },
  ],
  chunks: [
    { chunk_id: 0, start_sec: 0, end_sec: 75 },
    { chunk_id: 1, start_sec: 75, end_sec: 150 },
    { chunk_id: 2, start_sec: 150, end_sec: 240 },
  ],
}

function fakePlayer(): VideoPlayerHandle {
  return { seekTo: vi.fn(), playVideo: vi.fn() }
}

beforeEach(() => {
  apiFetchMock.mockReset()
  useVideoStore.getState().reset()
})

describe('useVideoStore', () => {
  it('marks a completed YouTube lecture as embeddable and extracts the video id', async () => {
    apiFetchMock.mockImplementation(async (path: string) => (path.startsWith('/lectures') ? YT_LECTURE : MAP))
    await useVideoStore.getState().load('lec-1')
    const s = useVideoStore.getState()
    expect(s.embeddable).toBe(true)
    expect(s.videoId).toBe('dQw4w9WgXcQ')
    expect(s.sourceType).toBe('youtube')
    expect(s.map).toEqual(MAP)
  })

  it('never marks non-YouTube sources as embeddable', async () => {
    apiFetchMock.mockImplementation(async (path: string) =>
      path.startsWith('/lectures') ? { source_type: 'upload', source_url: null, status: 'completed' } : MAP,
    )
    await useVideoStore.getState().load('lec-2')
    expect(useVideoStore.getState().embeddable).toBe(false)
  })

  it('requires status completed for embeddability', async () => {
    apiFetchMock.mockImplementation(async (path: string) =>
      path.startsWith('/lectures') ? { ...YT_LECTURE, status: 'processing' } : MAP,
    )
    await useVideoStore.getState().load('lec-3')
    expect(useVideoStore.getState().embeddable).toBe(false)
  })

  it('buffers a seek until a player registers, then flushes it', async () => {
    useVideoStore.getState().requestSeek(42)
    expect(useVideoStore.getState().pendingSeek).toBe(42)
    const player = fakePlayer()
    useVideoStore.getState().registerPlayer(player)
    expect(player.seekTo).toHaveBeenCalledWith(42, true)
    expect(player.playVideo).toHaveBeenCalled()
    expect(useVideoStore.getState().pendingSeek).toBeNull()
  })

  it('seeks directly when a player is already registered', () => {
    const player = fakePlayer()
    useVideoStore.getState().registerPlayer(player)
    useVideoStore.getState().requestSeek(90)
    expect(player.seekTo).toHaveBeenCalledWith(90, true)
    expect(useVideoStore.getState().pendingSeek).toBeNull()
  })

  it('ignores invalid seek targets', () => {
    const player = fakePlayer()
    useVideoStore.getState().registerPlayer(player)
    useVideoStore.getState().requestSeek(Number.NaN)
    useVideoStore.getState().requestSeek(-1)
    expect(player.seekTo).not.toHaveBeenCalled()
  })

  it('resolves chapter start times from the map', () => {
    useVideoStore.setState({ map: MAP })
    const s = useVideoStore.getState()
    expect(s.chapterStart(1)).toBe(0)
    expect(s.chapterStart(2)).toBe(150)
    expect(s.chapterStart(99)).toBeNull()
    expect(s.chapterStart(undefined)).toBeNull()
  })

  it('seekToChapter requests the chapter start', () => {
    const player = fakePlayer()
    useVideoStore.getState().registerPlayer(player)
    useVideoStore.setState({ map: MAP })
    useVideoStore.getState().seekToChapter(2)
    expect(player.seekTo).toHaveBeenCalledWith(150, true)
  })

  it('togglePlayer flips the open flag', () => {
    expect(useVideoStore.getState().open).toBe(false)
    useVideoStore.getState().togglePlayer()
    expect(useVideoStore.getState().open).toBe(true)
    useVideoStore.getState().togglePlayer()
    expect(useVideoStore.getState().open).toBe(false)
  })

  it('requestSeek opens the player even when no handle is registered yet', () => {
    useVideoStore.getState().requestSeek(60)
    const s = useVideoStore.getState()
    expect(s.open).toBe(true)
    expect(s.pendingSeek).toBe(60)
  })

  it('seekToChapter opens the player', () => {
    useVideoStore.setState({ map: MAP })
    useVideoStore.getState().seekToChapter(1)
    expect(useVideoStore.getState().open).toBe(true)
  })

  it('load and reset close the player', async () => {
    useVideoStore.setState({ open: true })
    useVideoStore.getState().reset()
    expect(useVideoStore.getState().open).toBe(false)

    useVideoStore.setState({ open: true })
    apiFetchMock.mockImplementation(async (path: string) => (path.startsWith('/lectures') ? YT_LECTURE : MAP))
    await useVideoStore.getState().load('lec-1')
    expect(useVideoStore.getState().open).toBe(false)
  })
})

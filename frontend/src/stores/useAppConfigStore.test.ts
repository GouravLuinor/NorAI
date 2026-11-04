import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// The store loads once per module (single-flight), so each case gets a fresh copy.
async function freshStore(body: unknown, ok = true) {
  vi.resetModules()
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status: ok ? 200 : 500,
      headers: { 'content-type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  const mod = await import('./useAppConfigStore')
  return { ...mod, fetchMock }
}

describe('useAppConfigStore', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('starts on the hosted fallback before loading', async () => {
    const { useAppConfigStore, FALLBACK_CONFIG } = await freshStore({ mode: 'local', sources: [] })
    const s = useAppConfigStore.getState()
    expect(s.loaded).toBe(false)
    expect(s.mode).toBe(FALLBACK_CONFIG.mode)
    expect(s.sources).toEqual(FALLBACK_CONFIG.sources)
  })

  it('loads local mode and keeps known sources in order', async () => {
    const { useAppConfigStore, isLocalMode } = await freshStore({
      mode: 'local',
      sources: ['upload', 'ftp', 'youtube'],
    })
    const cfg = await useAppConfigStore.getState().load()
    expect(cfg).toEqual({ mode: 'local', sources: ['youtube', 'upload'] })
    expect(useAppConfigStore.getState().loaded).toBe(true)
    expect(isLocalMode()).toBe(true)
  })

  it('treats an unknown mode as hosted', async () => {
    const { useAppConfigStore } = await freshStore({ mode: 'weird', sources: ['upload'] })
    expect(await useAppConfigStore.getState().load()).toEqual({ mode: 'hosted', sources: ['upload'] })
  })

  it('falls back to hosted defaults when the backend errors', async () => {
    const { useAppConfigStore, FALLBACK_CONFIG } = await freshStore({ detail: 'boom' }, false)
    expect(await useAppConfigStore.getState().load()).toEqual(FALLBACK_CONFIG)
  })

  it('asks the backend only once', async () => {
    const { useAppConfigStore, fetchMock } = await freshStore({ mode: 'hosted', sources: ['upload'] })
    await Promise.all([useAppConfigStore.getState().load(), useAppConfigStore.getState().load()])
    await useAppConfigStore.getState().load()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

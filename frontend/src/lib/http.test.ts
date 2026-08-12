import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch, apiFetchRaw, apiGet, apiPost } from './http'

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': ok ? 'application/json' : 'application/json' },
  })
}

describe('http client', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('apiGet issues GET and merges auth headers', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ hello: 'world' }))
    vi.stubGlobal('fetch', fetchMock)
    const data = await apiGet<{ hello: string }>('/test')
    expect(data).toEqual({ hello: 'world' })
    const [, init] = fetchMock.mock.calls[0]
    expect(init.method).toBe('GET')
    expect(init.headers).toBeDefined()
  })

  it('apiPost issues POST with a body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)
    await apiPost<{ ok: boolean }>('/test', { body: JSON.stringify({ a: 1 }) })
    expect(fetchMock.mock.calls[0][1].method).toBe('POST')
    expect(fetchMock.mock.calls[0][1].body).toBe('{"a":1}')
  })

  it('throws ApiError with the server detail on non-ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => jsonResponse({ detail: 'nope' }, false, 404)))
    await expect(apiGet('/x')).rejects.toBeInstanceOf(ApiError)
    await expect(apiGet('/x')).rejects.toMatchObject({ status: 404, message: 'nope' })
  })

  it('rejects non-JSON success responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('<html>', { status: 200, headers: { 'content-type': 'text/html' } })),
    )
    await expect(apiGet('/x')).rejects.toMatchObject({
      message: expect.stringContaining('Unexpected response type'),
    })
  })

  it('apiFetch returns null instead of throwing on failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'boom' }, false, 500)))
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(await apiFetch('/x')).toBeNull()
    expect(spy).toHaveBeenCalled()
  })

  it('apiFetchRaw returns the raw Response untouched', async () => {
    const res = new Response('plain text', { status: 200, headers: { 'content-type': 'text/plain' } })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(res))
    const out = await apiFetchRaw('/raw')
    expect(await out.text()).toBe('plain text')
  })

  it('passes an AbortSignal through to fetch', async () => {
    const controller = new AbortController()
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}))
    vi.stubGlobal('fetch', fetchMock)
    await apiGet('/x', { signal: controller.signal })
    expect(fetchMock.mock.calls[0][1].signal).toBe(controller.signal)
  })
})

import { authHeaders } from './authHeaders'
import type { paths } from '../types/api'

/**
 * Typed API client wrapper (P5.5).
 *
 * Every internal fetch goes through this module so that:
 *   - auth headers are merged automatically,
 *   - AbortSignal/AbortController passes through,
 *   - non-JSON / error responses are normalized into a typed ApiError.
 *
 * Response bodies are typed at the call site via the explicit generic `T`.
 * When `T` is omitted, the return type is derived from the openapi-typescript
 * `paths` schema (`ApiJson<P, M>`), so regeneration of `src/types/api.ts`
 * automatically tightens callers — today most 200 responses are `unknown`
 * because the backend does not yet declare `response_model` on every route.
 */

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** API base path (repo-root .env, e.g. `http://localhost:8000`) or '' for same-origin. */
export const API_BASE =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? ''

export type ApiPath = keyof paths & string

type ApiMethod = 'get' | 'post' | 'put' | 'delete' | 'patch'

export type ApiJson<P extends string, M extends ApiMethod> = P extends ApiPath
  ? M extends keyof paths[P]
    ? paths[P][M] extends {
        responses: { 200: { content: { 'application/json': infer Json } } }
      }
      ? Json
      : unknown
    : unknown
  : unknown

interface JsonLike {
  detail?: unknown
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as JsonLike
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return JSON.stringify(detail)
  } catch {
    // not JSON — fall through
  }
  return `Request failed: ${res.status}`
}

export interface ApiOptions extends RequestInit {
  signal?: AbortSignal
}

async function request<T>(path: string, init?: ApiOptions): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
  })
  const ct = res.headers.get('content-type') || ''
  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res))
  }
  if (!ct.includes('application/json')) {
    throw new ApiError(res.status, `Unexpected response type: ${ct || '(none)'}`)
  }
  return (await res.json()) as T
}

/**
 * Raw-fetch escape hatch for endpoints that return non-JSON (e.g. the
 * graceful-degradation `.md` notes fallback). Merges auth headers and passes
 * through the AbortSignal; the caller owns response handling.
 */
export async function apiFetchRaw(path: string, init?: ApiOptions): Promise<Response> {
  return fetch(path, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
  })
}

export function apiGet<T = never, P extends string = string>(path: P, init?: ApiOptions): Promise<[T] extends [never] ? ApiJson<P, 'get'> : T> {
  return request<[T] extends [never] ? ApiJson<P, 'get'> : T>(path, { ...init, method: 'GET' })
}

export function apiPost<T = never, P extends string = string>(path: P, init?: ApiOptions): Promise<[T] extends [never] ? ApiJson<P, 'post'> : T> {
  return request<[T] extends [never] ? ApiJson<P, 'post'> : T>(path, { ...init, method: 'POST' })
}

export function apiDelete<T = never, P extends string = string>(path: P, init?: ApiOptions): Promise<[T] extends [never] ? ApiJson<P, 'delete'> : T> {
  return request<[T] extends [never] ? ApiJson<P, 'delete'> : T>(path, { ...init, method: 'DELETE' })
}

export function apiPatch<T = never, P extends string = string>(path: P, init?: ApiOptions): Promise<[T] extends [never] ? ApiJson<P, 'patch'> : T> {
  return request<[T] extends [never] ? ApiJson<P, 'patch'> : T>(path, { ...init, method: 'PATCH' })
}

export function apiPut<T = never, P extends string = string>(path: P, init?: ApiOptions): Promise<[T] extends [never] ? ApiJson<P, 'put'> : T> {
  return request<[T] extends [never] ? ApiJson<P, 'put'> : T>(path, { ...init, method: 'PUT' })
}

/**
 * Error-tolerant variant for reads that fall back to a default on failure
 * (mirrors the old `apiFetch` contract of returning null instead of throwing).
 */
export async function apiFetch<T = never, P extends string = string>(path: P, init?: ApiOptions): Promise<([T] extends [never] ? ApiJson<P, 'get'> : T) | null> {
  try {
    return await apiGet<T, P>(path, init)
  } catch (err) {
    if (err instanceof Error && err.name !== 'AbortError') {
      console.error(`apiFetch ${path}:`, err)
    }
    return null
  }
}

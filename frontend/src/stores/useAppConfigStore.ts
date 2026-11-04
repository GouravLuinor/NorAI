import { create } from 'zustand'
import { apiFetch } from '../lib/http'

/**
 * How this install runs, from the backend's GET /system/config.
 *
 * - `hosted`: the public site. Supabase login, quotas.
 * - `local`: a single-user install on the user's own PC with their own Gemini
 *   key. No login (the backend treats every request as the local user), no
 *   marketing or pricing pages.
 *
 * `sources` is the intake allowlist (config.enabled_sources on the backend);
 * the upload page offers only these.
 */
export type RunMode = 'hosted' | 'local'
export type SourceType = 'youtube' | 'gdrive' | 'upload'

export interface AppConfig {
  mode: RunMode
  sources: SourceType[]
}

const KNOWN_SOURCES: readonly SourceType[] = ['youtube', 'gdrive', 'upload']

/** Used until the backend answers, and if it never does: the hosted defaults. */
export const FALLBACK_CONFIG: AppConfig = { mode: 'hosted', sources: ['gdrive', 'upload'] }

interface AppConfigState extends AppConfig {
  loaded: boolean
  load: () => Promise<AppConfig>
}

let _inflight: Promise<AppConfig> | null = null

function parse(raw: unknown): AppConfig {
  const r = (raw ?? {}) as { mode?: unknown; sources?: unknown }
  const mode: RunMode = r.mode === 'local' ? 'local' : 'hosted'
  const sources = Array.isArray(r.sources)
    ? KNOWN_SOURCES.filter((s) => (r.sources as unknown[]).includes(s))
    : FALLBACK_CONFIG.sources
  return { mode, sources }
}

export const useAppConfigStore = create<AppConfigState>((set) => ({
  ...FALLBACK_CONFIG,
  loaded: false,
  // Single-flight: initAuth and the upload page may both ask on first paint.
  load: () => {
    if (!_inflight) {
      _inflight = apiFetch<unknown>('/system/config')
        .then(parse)
        .catch(() => FALLBACK_CONFIG)
        .then((cfg) => {
          set({ ...cfg, loaded: true })
          return cfg
        })
    }
    return _inflight
  },
}))

export const isLocalMode = () => useAppConfigStore.getState().mode === 'local'

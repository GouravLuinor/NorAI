import { create } from 'zustand'
import { useLectureStore } from './useLectureStore'

const KEY = 'norai-tutor-settings'

function save(persona: string) {
  try {
    const lectureId = useLectureStore.getState().activeLectureId || 'default'
    localStorage.setItem(`${KEY}-${lectureId}`, JSON.stringify({ persona }))
  } catch {
    // ignore — persistence is best-effort
  }
}

function load(): string {
  const lectureId = useLectureStore.getState().activeLectureId || 'default'
  try {
    const raw = localStorage.getItem(`${KEY}-${lectureId}`)
    if (raw) {
      const parsed = JSON.parse(raw) as { persona?: string }
      if (typeof parsed.persona === 'string') return parsed.persona
    }
  } catch {
    // fall through to default
  }
  return ''
}

interface TutorSettingsState {
  persona: string
  setPersona: (persona: string) => void
}

export const useTutorSettingsStore = create<TutorSettingsState>((set) => ({
  persona: load(),
  setPersona: (persona) => {
    set({ persona })
    save(persona)
  },
}))

// Reload per-lecture settings when the active lecture changes.
useLectureStore.subscribe((s, prev) => {
  if (s.activeLectureId !== prev.activeLectureId) {
    useTutorSettingsStore.setState({ persona: load() })
  }
})
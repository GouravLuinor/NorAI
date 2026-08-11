import { create } from 'zustand'
import { apiGet } from '../lib/http'

interface LectureState {
  activeLectureId: string | null
  lectures: { lecture_id: string; title: string }[]
  setActiveLecture: (id: string) => void
  loadLectures: () => Promise<void>
}

export const useLectureStore = create<LectureState>((set) => ({
  activeLectureId: null,
  lectures: [],
  setActiveLecture: (id) => set({ activeLectureId: id }),
  loadLectures: async () => {
    try {
      const data = await apiGet<{ lecture_id: string; title: string }[]>('/lectures')
      set({ lectures: data ?? [] })
    } catch {
      set({ lectures: [] })
    }
  },
}))
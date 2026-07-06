import { create } from 'zustand'

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
    const res = await fetch('/lectures')
    const data = await res.json()
    set({ lectures: data })
  },
}))
import { create } from 'zustand'

interface ChapterState {
  activeChapterId: number
  activeDocTab: 'notes' | 'revision' | 'assessment'
  sidebarCollapsed: boolean
  setChapter: (id: number) => void
  setDocTab: (tab: 'notes' | 'revision' | 'assessment') => void
  toggleSidebar: () => void
}

export const useChapterStore = create<ChapterState>((set) => ({
  activeChapterId: 1,
  activeDocTab: 'revision',
  sidebarCollapsed: false,
  setChapter: (id) => set({ activeChapterId: id }),
  setDocTab: (tab) => set({ activeDocTab: tab }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}))
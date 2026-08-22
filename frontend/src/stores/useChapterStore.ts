import { create } from 'zustand'
import { apiGet } from '../lib/http'

interface Chapter {
  id: number
  title: string
}

interface ChapterState {
  activeChapterId: number
  activeDocTab: 'notes' | 'revision' | 'assessment' | 'guide' | 'concepts'
  sidebarCollapsed: boolean
  chapters: Chapter[]
  chaptersLoading: boolean
  setChapter: (id: number) => void
  setDocTab: (tab: 'notes' | 'revision' | 'assessment' | 'guide' | 'concepts') => void
  toggleSidebar: () => void
  loadChapters: (lectureId: string) => Promise<void>
}

let _loadChapterGeneration = 0

export const useChapterStore = create<ChapterState>((set) => ({
  activeChapterId: 1,
  activeDocTab: 'revision',
  sidebarCollapsed: false,
  chapters: [],
  chaptersLoading: false,

  setChapter: (id) => set({ activeChapterId: id }),
  setDocTab: (tab) => set({ activeDocTab: tab }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  loadChapters: async (lectureId: string) => {
    const gen = ++_loadChapterGeneration
    set({ chaptersLoading: true })
    try {
      const outline = await apiGet<{ chapters?: { chapter_id?: number; id?: number; title?: string }[] }>(
        `/outline?lecture_id=${lectureId}&_t=${Date.now()}`,
      )
      if (gen !== _loadChapterGeneration) return

      const chs = outline?.chapters || []

      if (chs.length === 0) {
        set({ chapters: [], activeChapterId: 1, chaptersLoading: false })
        return
      }

      const chapters: Chapter[] = chs.map((ch) => ({
        id: ch.chapter_id || ch.id || 1,
        title: ch.title || `Chapter ${ch.chapter_id || ch.id}`,
      }))

      set({
        chapters,
        activeChapterId: chapters[0]?.id || 1,
        chaptersLoading: false,
      })
    } catch {
      if (gen !== _loadChapterGeneration) return
      console.warn('Failed to load chapters — /outline endpoint may not be available')
      set({ chapters: [], activeChapterId: 1, chaptersLoading: false })
    }
  },
}))
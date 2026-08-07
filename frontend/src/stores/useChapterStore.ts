import { create } from 'zustand'

interface Chapter {
  id: number
  title: string
}

interface ChapterState {
  activeChapterId: number
  activeDocTab: 'notes' | 'revision' | 'assessment' | 'guide' | 'concepts'
  sidebarCollapsed: boolean
  chapters: Chapter[]
  setChapter: (id: number) => void
  setDocTab: (tab: 'notes' | 'revision' | 'assessment' | 'guide' | 'concepts') => void
  toggleSidebar: () => void
  loadChapters: (lectureId: string) => Promise<void>
}

export const useChapterStore = create<ChapterState>((set) => ({
  activeChapterId: 1,
  activeDocTab: 'revision',
  sidebarCollapsed: false,
  chapters: [],

  setChapter: (id) => set({ activeChapterId: id }),
  setDocTab: (tab) => set({ activeDocTab: tab }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

loadChapters: async (lectureId: string) => {
    try {
      const res = await fetch(`/outline?lecture_id=${lectureId}&_t=${Date.now()}`)
      if (!res.ok) throw new Error('Outline not found')
      const outline = await res.json()
      const chs = outline.chapters || []
      
      if (chs.length === 0) {
        set({ chapters: [], activeChapterId: 1 })
        return
      }

      const chapters: Chapter[] = chs.map((ch: { chapter_id?: number; id?: number; title?: string }) => ({
        id: ch.chapter_id || ch.id || 1,
        title: ch.title || `Chapter ${ch.chapter_id || ch.id}`,
      }))

      set({
        chapters,
        activeChapterId: chapters[0]?.id || 1,
      })
    } catch {
      console.warn('Failed to load chapters — /outline endpoint may not be available')
      set({ chapters: [], activeChapterId: 1 })
    }
  },
}))
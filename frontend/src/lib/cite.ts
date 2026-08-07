import { useChapterStore } from '../stores/useChapterStore'
import { headingToId } from './markdown'

/**
 * Scroll a "where is this in the notes?" citation into view.
 *
 * Mirrors ChatArea's reference-click behaviour: resolves the leaf heading of
 * a heading_path (e.g. "Chapter 1 > Core Architecture") to a DOM section id,
 * switches the doc pane to the right chapter + notes tab, then polls for
 * the element (it mounts after the tab swap) before smooth-scrolling.
 */
export function scrollToHeading(headingPath: string, chapterId?: number | null) {
  const leafHeading = headingPath.split('>').pop()?.trim() || ''
  if (!leafHeading) return

  const sectionId = headingToId(leafHeading)
  const store = useChapterStore.getState()
  const currentChapterId = store.activeChapterId

  if (chapterId && chapterId !== currentChapterId) {
    store.setChapter(chapterId)
  }
  store.setDocTab('notes')

  let attempts = 0
  const interval = setInterval(() => {
    const el = document.getElementById(sectionId)
    if (el) {
      clearInterval(interval)
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.remove('scroll-highlight')
      void el.offsetWidth
      el.classList.add('scroll-highlight')
      el.addEventListener('animationend', function h() {
        el.classList.remove('scroll-highlight')
        el.removeEventListener('animationend', h)
      })
    } else if (attempts >= 20) {
      clearInterval(interval)
    }
    attempts++
  }, 100)
}

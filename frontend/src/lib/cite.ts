import { useChapterStore } from '../stores/useChapterStore'
import { headingToId } from './markdown'

function findSectionCard(targetId: string, headingText: string): HTMLElement | null {
  // 1. Direct ID lookup
  if (targetId) {
    const direct = document.getElementById(targetId)
    if (direct) return direct
  }

  // 2. Query all section card containers within the active document area
  const docContainer = document.querySelector('.doc-content') || document
  const cards = Array.from(docContainer.querySelectorAll<HTMLElement>('[id^="sec-"]'))
  if (cards.length === 0) return null

  // 3. Normalized slug matching
  const targetSlug = headingToId(headingText).replace(/^sec-/, '').toLowerCase()
  if (!targetSlug) return cards[0] || null

  // Exact slug contains or card id contains
  for (const card of cards) {
    const cardSlug = card.id.replace(/^sec-/, '').toLowerCase()
    if (cardSlug === targetSlug || cardSlug.includes(targetSlug) || targetSlug.includes(cardSlug)) {
      return card
    }
  }

  // 4. Token overlap matching (handling truncated headings or number prefixes)
  const targetTokens = targetSlug.split('-').filter((t) => t.length > 2 && !/^\d+$/.test(t))
  let bestCard: HTMLElement | null = null
  let maxScore = 0

  for (const card of cards) {
    const cardText = (card.querySelector('h1, h2, h3, h4, [class*="font-"]') || card).textContent || ''
    const cardSlug = headingToId(cardText).replace(/^sec-/, '').toLowerCase()
    const matches = targetTokens.filter((tok) => cardSlug.includes(tok)).length
    if (matches > maxScore) {
      maxScore = matches
      bestCard = card
    }
  }

  return maxScore > 0 ? bestCard : (cards[0] || null)
}

/**
 * Scroll a "where is this in the notes?" citation into view.
 *
 * 1. Resolves target chapter and switches chapter + docTab to 'notes'.
 * 2. Smart DOM polling: searches by exact sectionId, card IDs,
 *    and keyword/subheading match across all rendered section cards.
 * 3. Smooth-scrolls the matching card into view and triggers the pulsing highlight animation.
 */
export function scrollToHeading(headingPath: string, chapterId?: number | null, explicitSectionId?: string) {
  const leafHeading = headingPath ? headingPath.split('>').pop()?.trim() || '' : ''
  const targetId = explicitSectionId || (leafHeading ? headingToId(leafHeading) : '')

  const store = useChapterStore.getState()
  const currentChapterId = store.activeChapterId

  if (chapterId != null && chapterId > 0 && chapterId !== currentChapterId) {
    store.setChapter(chapterId)
  }
  store.setDocTab('notes')

  let attempts = 0
  const maxAttempts = 35 // Poll up to 3.5s to allow notes to fetch and render
  const interval = setInterval(() => {
    const el = findSectionCard(targetId, leafHeading || headingPath)
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
    } else if (attempts >= maxAttempts) {
      clearInterval(interval)
      console.warn('Reference click — section card not found in DOM:', { targetId, leafHeading, headingPath })
    }
    attempts++
  }, 100)
}

import { useChapterStore } from '../stores/useChapterStore'
import { headingToId } from './markdown'

let activeInterval: ReturnType<typeof setInterval> | null = null

function findSectionCard(targetId: string, headingText: string): HTMLElement | null {
  // 1. Direct ID lookup
  if (targetId) {
    const direct = document.getElementById(targetId)
    if (direct) return direct
  }

  // 2. Query ALL section card containers across every doc-content area.
  //    Desktop mounts the doc pane; on mobile only the active tab is mounted,
  //    so scan every scroller rather than the first `.doc-content` in DOM order
  //    (which may be the chat's own message scroller).
  const containers = Array.from(document.querySelectorAll<HTMLElement>('.doc-content'))
  let cards: HTMLElement[] = []
  for (const container of containers) {
    cards = cards.concat(Array.from(container.querySelectorAll<HTMLElement>('[id^="sec-"]')))
  }
  if (cards.length === 0) return null

  // 3. Normalized slug matching
  const targetSlug = headingToId(headingText).replace(/^sec-/, '').toLowerCase()
  if (!targetSlug) return cards[0] || null

  // Exact slug equality first, then contains (exact is never ambiguous).
  for (const card of cards) {
    const cardSlug = card.id.replace(/^sec-/, '').toLowerCase()
    if (cardSlug === targetSlug) {
      return card
    }
  }
  for (const card of cards) {
    const cardSlug = card.id.replace(/^sec-/, '').toLowerCase()
    if (cardSlug.includes(targetSlug) || targetSlug.includes(cardSlug)) {
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

  const validChapters = useChapterStore.getState().chapters

  // Validate target chapter ID exists in this lecture
  let validTargetChapterId = chapterId
  if (validTargetChapterId != null && validChapters.length > 0 && !validChapters.some((c) => c.id === validTargetChapterId)) {
    // If bogus or unmatched chapter ID, attempt to recover by chapter title in headingPath
    const found = validChapters.find((c) => c.title && headingPath.toLowerCase().includes(c.title.toLowerCase()))
    validTargetChapterId = found ? found.id : null
  }

  openChapterNotes(validTargetChapterId)
  pollAndHighlight(() => findSectionCard(targetId, leafHeading || headingPath), () => {
    console.warn('Reference click — section card not found in DOM:', { targetId, leafHeading, headingPath })
  })
}

/** Switch to a chapter's notes tab (and the doc pane on mobile). */
function openChapterNotes(chapterId: number | null | undefined) {
  const store = useChapterStore.getState()
  if (chapterId != null && chapterId > 0 && chapterId !== store.activeChapterId) {
    store.setChapter(chapterId)
  }
  store.setDocTab('notes')
  // On mobile only one panel is mounted; if the chat pane is active the doc
  // pane isn't in the DOM yet. Ask the Workspace to switch to the doc tab so
  // the section cards can mount (Workspace.tsx listens for this event).
  window.dispatchEvent(new CustomEvent('norai:show-doc'))
}

/** Poll (up to 10 s, while notes fetch and render) for a section card, then
 *  scroll it into view with the pulse highlight. */
function pollAndHighlight(find: () => HTMLElement | null, onMiss: () => void) {
  // Clear any previous poll (e.g. a prior citation click still running) so we
  // never accumulate intervals or scroll to a stale target after navigation.
  if (activeInterval) clearInterval(activeInterval)
  let attempts = 0
  const maxAttempts = 100
  const interval = setInterval(() => {
    const el = find()
    if (el) {
      clearInterval(interval)
      if (activeInterval === interval) activeInterval = null
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
      if (activeInterval === interval) activeInterval = null
      onMiss()
    }
    attempts++
  }, 100)
  activeInterval = interval
}

/**
 * Documents: a passage citation carries the passage's (synthetic) start time,
 * not a note heading. Open its chapter and scroll to the section that covers
 * it: the last section starting at or before `sec`.
 */
export function scrollToSectionAt(chapterId: number | null | undefined, sec: number) {
  openChapterNotes(chapterId)
  pollAndHighlight(() => {
    const cards = Array.from(document.querySelectorAll<HTMLElement>('.doc-content section[data-start-sec]'))
    if (cards.length === 0) return null
    let best: HTMLElement | null = null
    for (const card of cards) {
      if (Number(card.dataset.startSec) <= sec + 0.5) best = card
    }
    return best ?? cards[0]
  }, () => console.warn('Reference click — no section covers', { chapterId, sec }))
}

import type { Reference, RetrievedChunk, RetrievedImage, VerifiedCitation } from '../types'
import { headingToId } from './markdown'
import { useChapterStore } from '../stores/useChapterStore'

function chapterFromChunkId(chunkId?: string): number | undefined {
  if (!chunkId) return undefined
  // Only match explicit ch<N>__ pattern (e.g. ch1__heading), NEVER chunk_<hex_hash>
  const m = chunkId.match(/^ch(\d+)__/i)
  const n = m ? Number(m[1]) : NaN
  return Number.isInteger(n) && n > 0 ? n : undefined
}

export function resolveChapterId(
  explicitChapterId?: number | null,
  chunkId?: string | null,
  headingPath?: string | null,
  sectionName?: string | null,
  chunks: RetrievedChunk[] = [],
): number | undefined {
  if (explicitChapterId != null && explicitChapterId > 0) {
    return explicitChapterId
  }

  // 1. Check chunks lookup by chunkId
  if (chunkId) {
    const chunk = chunks.find((c) => c.chunk_id === chunkId)
    if (chunk?.chapter_id != null && chunk.chapter_id > 0) {
      return chunk.chapter_id
    }
  }

  // 2. Check explicit ch<N>__ prefix
  const fromPrefix = chapterFromChunkId(chunkId ?? undefined)
  if (fromPrefix != null) return fromPrefix

  // 3. Match against retrieved chunks by heading path / section
  const queryText = headingPath || sectionName || ''
  if (queryText) {
    const chunk = chunks.find(
      (c) =>
        c.heading_path === queryText ||
        c.heading === queryText ||
        (c.heading && queryText.includes(c.heading)) ||
        (c.heading_path && queryText.includes(c.heading_path)),
    )
    if (chunk?.chapter_id != null && chunk.chapter_id > 0) {
      return chunk.chapter_id
    }

    // 4. Match against store chapter titles
    const storeChapters = useChapterStore.getState().chapters
    for (const ch of storeChapters) {
      if (ch.title && queryText.toLowerCase().includes(ch.title.toLowerCase())) {
        return ch.id
      }
    }
  }

  return undefined
}

export function buildReferences(
  chunks: RetrievedChunk[] = [],
  images: RetrievedImage[] = [],
  _rawText: string = '',
  verifiedCitations: VerifiedCitation[] = [],
): Reference[] {
  const refs: Reference[] = []

  // Only citations the backend verified against this turn's retrieved
  // passages become references (P3.3). There is deliberately no fallback to
  // "confident" retrieved chunks or to the model's own Sources text: off-topic
  // questions still retrieve passages that look confident (cosine 0.22–0.31,
  // measured), so a fallback would attach lecture references to an answer
  // that says the lecture doesn't cover the question.
  for (const v of verifiedCitations) {
    if (!v.verified) continue
    const headingParts = (v.heading_path || v.section || '').split('>')
    const leafHeading = headingParts[headingParts.length - 1].trim()

    const chapterId = resolveChapterId(
      v.chapter_id,
      v.chunk_id,
      v.heading_path,
      v.section,
      chunks,
    )

    refs.push({
      id: v.chunk_id || v.section,
      title: v.section || v.heading_path || 'Notes Reference',
      section: chapterId != null ? `Ch ${chapterId}` : 'Notes Reference',
      sectionId: headingToId(leafHeading),
      chapterId: chapterId ?? undefined,
      chunkId: v.chunk_id ?? undefined,
      startSec: v.start ?? undefined,
      endSec: v.end ?? undefined,
      type: 'note',
    })
  }

  // Screenshots: the backend only returns ones whose caption matches the question.
  for (const img of images) {
    refs.push({
      id: img.path,
      title: img.section,
      section: img.chapter_id != null ? `Ch ${img.chapter_id}` : 'Screenshot',
      sectionId: '',
      chapterId: img.chapter_id ?? undefined,
      type: 'screenshot',
    })
  }

  return refs
}

/**
 * Strip the auto-appended Sources appendix from assistant messages
 * (sources are surfaced via ReferencesPanel).
 *
 * Only an appendix-shaped header triggers a cut — a bare "Sources" word in
 * prose (e.g. "The sources of variance are many.") must never truncate the
 * answer. When multiple appendix markers exist, the LAST one wins.
 */
const SOURCES_HEADER_RE = /(\*\*Sources\*\*|\n[ \t]*Sources\s*[:•]|\n[ \t]*Sources\s*\n)/i

export const stripSources = (text: string): string => {
  const match = text.match(SOURCES_HEADER_RE)
  if (!match || match.index == null) return text.trim()
  return text.slice(0, match.index).trim()
}


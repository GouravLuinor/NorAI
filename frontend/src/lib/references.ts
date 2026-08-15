import type { Reference, RetrievedChunk, RetrievedImage, VerifiedCitation } from '../types'
import { headingToId } from './markdown'
import { useChapterStore } from '../stores/useChapterStore'

/**
 * Confidence threshold for surfacing a retrieved chunk as a reference.
 * Mirrors `tutor/retrieval_config.py` CONFIDENCE_THRESHOLD (cosine distance).
 * Chunks above this are weak matches and must never render as references (P3.8).
 */
export const CONFIDENCE_THRESHOLD = 0.35

/** A chunk is reference-worthy only when the backend marked it relevant or its
 * distance is confidently within threshold. Missing both → excluded. */
function isConfident(chunk: RetrievedChunk): boolean {
  if (chunk.relevant === true) return true
  if (chunk.relevant === false) return false
  return (chunk.distance ?? 1) <= CONFIDENCE_THRESHOLD
}

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
  rawText: string = '',
  verifiedCitations: VerifiedCitation[] = [],
): Reference[] {
  const refs: Reference[] = []

  // 1. P3.3 — verified citations are authoritative: the answer cited the exact
  //    section name AND it matched a retrieved chunk. Never show a fabricated
  //    or unverified citation as a reference.
  const verified = verifiedCitations.filter((v) => v.verified)
  if (verified.length > 0) {
    for (const v of verified) {
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
        type: 'note',
      })
    }
  } else {
    // 2. Fallback — confidence-gated retrieved chunks (P3.8): weak matches are
    //    dropped so off-topic questions surface zero references.
    for (const c of chunks) {
      if (!isConfident(c)) continue
      const headingParts = (c.heading_path || c.heading || '').split('>')
      const leafHeading = headingParts[headingParts.length - 1].trim()
      const chapterId = resolveChapterId(
        c.chapter_id,
        c.chunk_id,
        c.heading_path,
        c.heading,
        chunks,
      )
      refs.push({
        id: c.chunk_id || c.heading_path,
        title: c.heading_path || c.heading || 'Notes Reference',
        section: chapterId != null ? `Ch ${chapterId}` : 'Notes Reference',
        sectionId: headingToId(leafHeading),
        chapterId: chapterId ?? undefined,
        chunkId: c.chunk_id ?? undefined,
        type: 'note',
      })
    }
  }

  // 3. Screenshots (unchanged — shown when retrieved)
  for (const img of images) {
    refs.push({
      id: img.path,
      title: img.section,
      section: img.path,
      sectionId: '',
      type: 'screenshot',
    })
  }

  // 4. rawText "Sources" fallback ONLY when retrieval returned nothing at all.
  //    If chunks/images existed but all were weak, we must NOT resurrect them
  //    from the model's own text (P3.8).
  if (refs.length === 0 && chunks.length === 0 && images.length === 0 && rawText) {
    const match = rawText.match(/(?:Sources|Sources\s*[:•])[\s\S]*$/i)
    if (match) {
      const sourceLine = match[0]
      const items = sourceLine.split(/[•\n]/).map((s) => s.trim()).filter((s) => s && !s.toLowerCase().startsWith('sources'))
      for (const item of items) {
        if (item.includes('outputs/') || item.includes('frame_') || item.includes('.jpg') || item.includes('.png')) {
          const pathMatch = item.match(/(outputs\/[^\s)]+)|(frame_\d+\.(?:jpg|png))/i)
          const imgPath = pathMatch ? pathMatch[0] : item
          refs.push({
            id: imgPath,
            title: item.split('(')[0].trim() || 'Keyframe Screenshot',
            section: imgPath,
            sectionId: '',
            type: 'screenshot',
          })
        } else {
          const headingParts = item.split('>')
          const leafHeading = headingParts[headingParts.length - 1].trim()
          refs.push({
            id: item,
            title: item,
            section: 'Notes Reference',
            sectionId: headingToId(leafHeading),
            type: 'note',
          })
        }
      }
    }
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


import type { Reference, RetrievedChunk, RetrievedImage } from '../types'
import { headingToId } from './markdown'

export function buildReferences(
  chunks: RetrievedChunk[] = [],
  images: RetrievedImage[] = [],
): Reference[] {
  return [
    ...chunks.map((c) => {
      const headingParts = (c.heading_path || '').split('>')
      const leafHeading = headingParts[headingParts.length - 1].trim()
      return {
        id: c.heading_path,
        title: c.heading_path,
        section: `Ch ${c.chapter_id}`,
        sectionId: headingToId(leafHeading),
        chapterId: c.chapter_id,
        type: 'note' as const,
      }
    }),
    ...images.map((img) => ({
      id: img.path,
      title: img.section,
      section: img.path,
      sectionId: '',
      type: 'screenshot' as const,
    })),
  ]
}

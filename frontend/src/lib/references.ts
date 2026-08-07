import type { Reference, RetrievedChunk, RetrievedImage } from '../types'
import { headingToId } from './markdown'

export function buildReferences(
  chunks: RetrievedChunk[] = [],
  images: RetrievedImage[] = [],
  rawText: string = '',
): Reference[] {
  const refs: Reference[] = [
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

  if (refs.length === 0 && rawText) {
    const match = rawText.match(/(?:Sources|Sources\s*[\:\•])[\s\S]*$/i)
    if (match) {
      const sourceLine = match[0]
      const items = sourceLine.split(/[•\n]/).map((s) => s.trim()).filter((s) => s && !s.toLowerCase().startsWith('sources'))
      for (const item of items) {
        if (item.includes('outputs/') || item.includes('frame_') || item.includes('.jpg') || item.includes('.png')) {
          const pathMatch = item.match(/(outputs\/[^\s\)]+)|(frame_\d+\.(?:jpg|png))/i)
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

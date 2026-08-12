import { describe, expect, it } from 'vitest'
import { buildReferences } from './references'
import type { RetrievedChunk, RetrievedImage, VerifiedCitation } from '../types'

function chunk(over: Partial<RetrievedChunk> = {}): RetrievedChunk {
  return {
    heading_path: 'Top > Leaf',
    chapter_id: 1,
    chunk_id: 'ch1__abc',
    distance: 0.1,
    ...over,
  }
}

describe('buildReferences', () => {
  it('drops weak chunks above the confidence threshold', () => {
    expect(buildReferences([chunk({ distance: 0.9 })], [], '')).toHaveLength(0)
  })

  it('keeps chunks within the confidence threshold', () => {
    const refs = buildReferences([chunk({ distance: 0.2 })], [], '')
    expect(refs).toHaveLength(1)
    expect(refs[0]).toMatchObject({ title: 'Top > Leaf', sectionId: 'sec-leaf', chapterId: 1, type: 'note' })
  })

  it('respects an explicit relevant=false override', () => {
    expect(buildReferences([chunk({ distance: 0.1, relevant: false })], [], '')).toHaveLength(0)
  })

  it('treats relevant=true as confident regardless of distance', () => {
    expect(buildReferences([chunk({ distance: 0.9, relevant: true })], [], '')).toHaveLength(1)
  })

  it('prefers verified citations over the chunk fallback', () => {
    const cites: VerifiedCitation[] = [
      { section: 'Right Answer', heading_path: 'Ch1 > Right Answer', chunk_id: 'ch1__x', verified: true },
    ]
    const refs = buildReferences([chunk({ distance: 0.9 })], [], '', cites)
    expect(refs).toHaveLength(1)
    expect(refs[0]).toMatchObject({ title: 'Right Answer', section: 'Ch 1' })
  })

  it('drops unverified citations and falls back to chunks', () => {
    const cites: VerifiedCitation[] = [
      { section: 'Fabricated', heading_path: 'Nope', chunk_id: 'ch1__y', verified: false },
    ]
    const refs = buildReferences([chunk({ distance: 0.1 })], [], '', cites)
    expect(refs).toHaveLength(1)
    expect(refs[0].title).toBe('Top > Leaf')
  })

  it('does not resurrect rawText Sources when weak chunks existed', () => {
    const refs = buildReferences(
      [chunk({ distance: 0.9 })],
      [],
      'Text. Sources:\n• outputs/x/frame_1.jpg\n• Chapter 1 > Notes',
    )
    expect(refs).toHaveLength(0)
  })

  it('falls back to rawText Sources only when nothing was retrieved', () => {
    const refs = buildReferences(
      [],
      [],
      'Text. Sources:\n• outputs/x/frame_1.jpg\n• Chapter 1 > Notes',
    )
    expect(refs.length).toBeGreaterThanOrEqual(2)
    expect(refs.some((r) => r.type === 'screenshot')).toBe(true)
    expect(refs.some((r) => r.type === 'note')).toBe(true)
  })

  it('appends retrieved screenshots alongside note refs', () => {
    const images: RetrievedImage[] = [{ path: 'outputs/foo/bar.jpg', section: 'Fig 1' }]
    const refs = buildReferences([chunk({ distance: 0.1 })], images, '')
    expect(refs).toHaveLength(2)
    expect(refs[1]).toMatchObject({ type: 'screenshot', id: 'outputs/foo/bar.jpg' })
  })
})

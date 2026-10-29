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
  it('shows no note references when nothing was cited', () => {
    expect(buildReferences([chunk({ distance: 0.1, relevant: true })], [], '')).toHaveLength(0)
  })

  it('turns verified citations into references', () => {
    const cites: VerifiedCitation[] = [
      { section: 'Right Answer', heading_path: 'Ch1 > Right Answer', chunk_id: 'ch1__x', verified: true },
    ]
    const refs = buildReferences([chunk({ distance: 0.9 })], [], '', cites)
    expect(refs).toHaveLength(1)
    expect(refs[0]).toMatchObject({ title: 'Right Answer', section: 'Ch 1' })
  })

  it('drops unverified citations without falling back to chunks', () => {
    const cites: VerifiedCitation[] = [
      { section: 'Fabricated', heading_path: 'Nope', chunk_id: 'ch1__y', verified: false },
    ]
    expect(buildReferences([chunk({ distance: 0.1 })], [], '', cites)).toHaveLength(0)
  })

  it('never resurrects the model\'s own Sources text', () => {
    const refs = buildReferences(
      [],
      [],
      'Text. Sources:\n• outputs/x/frame_1.jpg\n• Chapter 1 > Notes',
    )
    expect(refs).toHaveLength(0)
  })

  it('carries the lecture time of a verified transcript citation', () => {
    const cites: VerifiedCitation[] = [
      { section: '3:42 — rings unrolled', heading_path: 'Transcript 3:42–4:10', chunk_id: 'tx_222_a', chapter_id: 2, verified: true, start: 222, end: 250 },
    ]
    const refs = buildReferences([], [], '', cites)
    expect(refs[0]).toMatchObject({ startSec: 222, endSec: 250, chapterId: 2, title: '3:42 — rings unrolled', transcript: true })
  })

  it('keeps a lean notes citation a note ref while carrying its section start', () => {
    const cites: VerifiedCitation[] = [
      { section: 'The LIS Problem', heading_path: 'DP > The LIS Problem', chunk_id: 'note_ab', chapter_id: 1, kind: 'notes', verified: true, start: 64 },
    ]
    const refs = buildReferences([], [], '', cites)
    expect(refs[0]).toMatchObject({ startSec: 64, transcript: false, type: 'note' })
  })

  it('appends retrieved screenshots alongside note refs', () => {
    const cites: VerifiedCitation[] = [
      { section: 'Leaf', heading_path: 'Top > Leaf', chunk_id: 'ch1__abc', verified: true },
    ]
    const images: RetrievedImage[] = [
      { path: 'outputs/foo/bar.jpg', section: 'Fig 1', chapter_id: 2 },
      { path: 'outputs/foo/baz.jpg', section: 'Fig 2' },
    ]
    const refs = buildReferences([chunk()], images, '', cites)
    expect(refs).toHaveLength(3)
    // The label column shows the chapter, never the file path.
    expect(refs[1]).toMatchObject({ type: 'screenshot', id: 'outputs/foo/bar.jpg', section: 'Ch 2', chapterId: 2 })
    expect(refs[2]).toMatchObject({ type: 'screenshot', section: 'Screenshot' })
  })
})

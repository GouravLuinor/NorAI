import { describe, expect, it } from 'vitest'
import { chipText, detectFile, detectLink, disabledReason } from './intake'

describe('detectFile', () => {
  it('maps documents and videos to the upload source', () => {
    expect(detectFile('Lecture 3.PDF')).toMatchObject({ kind: 'pdf', sourceType: 'upload', isDocument: true })
    expect(detectFile('notes.docx')).toMatchObject({ kind: 'docx', isDocument: true })
    expect(detectFile('deck.pptx')).toMatchObject({ kind: 'pptx' })
    expect(detectFile('readme.md')).toMatchObject({ kind: 'text' })
    expect(detectFile('talk.MOV')).toMatchObject({ kind: 'video', isDocument: false })
  })

  it('rejects legacy Office and unknown files with a reason', () => {
    expect(detectFile('old.doc')).toHaveProperty('error')
    expect((detectFile('old.ppt') as { error: string }).error).toMatch(/pptx/)
    expect(detectFile('archive.zip')).toHaveProperty('error')
  })
})

describe('detectLink', () => {
  it('routes links by host', () => {
    expect(detectLink('https://youtu.be/abc')?.sourceType).toBe('youtube')
    expect(detectLink('https://www.youtube.com/watch?v=x')?.sourceType).toBe('youtube')
    expect(detectLink('https://docs.google.com/document/d/1x/edit')).toMatchObject({ kind: 'gdoc', sourceType: 'gdrive', isDocument: true })
    expect(detectLink('https://docs.google.com/presentation/d/1x/edit')).toMatchObject({ kind: 'gslides' })
    expect(detectLink('https://drive.google.com/file/d/1x/view')).toMatchObject({ kind: 'gdrive', isDocument: false })
    expect(detectLink('https://example.com/article')).toMatchObject({ kind: 'web', sourceType: 'link' })
    expect(detectLink('https://cdn.example.com/a.mp4')).toMatchObject({ sourceType: 'link', isDocument: false })
    expect(detectLink('https://example.com/paper.pdf')?.label).toBe('PDF link')
  })

  it('ignores text that is not a full http(s) URL', () => {
    expect(detectLink('youtube.com/watch')).toBeNull()
    expect(detectLink('ftp://x.com/a')).toBeNull()
    expect(detectLink('')).toBeNull()
  })

  it('explains a source switched off on this install', () => {
    const yt = detectLink('https://youtu.be/abc')!
    expect(disabledReason(yt, ['gdrive', 'upload', 'link'])).toMatch(/upload the file/i)
    expect(disabledReason(yt, ['youtube'])).toBeNull()
  })
})

describe('chipText', () => {
  it('shows pages/slides and quota minutes', () => {
    const pdf = detectFile('a.pdf') as ReturnType<typeof detectLink> & object
    expect(chipText(pdf, { pages: 23, minutes_needed: 12, doc_type: 'pdf' })).toBe('PDF · 23 pages · uses 12 min')
    const deck = detectFile('a.pptx') as ReturnType<typeof detectLink> & object
    expect(chipText(deck, { pages: 9, doc_type: 'pptx' })).toBe('PowerPoint · 9 slides')
    const web = detectLink('https://example.com/a')!
    expect(chipText(web, { words: 3757, minutes_needed: 26 })).toBe('Web page or file link · 3,757 words · uses 26 min')
  })
})

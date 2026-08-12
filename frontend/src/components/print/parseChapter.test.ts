import { describe, expect, it } from 'vitest'
import { parseChapterContent } from './parseChapter'

describe('parseChapterContent', () => {
  it('parses a structured sections payload object', () => {
    const out = parseChapterContent(
      {
        title: 'Ethernet Basics',
        sections: [
          { title: 'Intro', content_markdown: 'Some **markdown** body', section_type: 'overview' },
        ],
      },
      1,
    )
    expect(out.title).toBe('Ethernet Basics')
    expect(out.preamble).toBe('')
    expect(out.sections).toEqual([
      { heading: 'Intro', body: 'Some **markdown** body', cardType: 'overview' },
    ])
  })

  it('parses a JSON-encoded sections payload string', () => {
    const payload = JSON.stringify({
      title: 'JSON Title',
      sections: [{ title: 'S1', content_markdown: 'body text' }],
    })
    const out = parseChapterContent(payload, 2)
    expect(out.title).toBe('JSON Title')
    expect(out.sections[0]).toEqual({ heading: 'S1', body: 'body text', cardType: undefined })
  })

  it('unwraps guide { markdown } chapters', () => {
    const out = parseChapterContent({ markdown: '# Guide Title\n\n## Part\n\ncontent' }, 3)
    expect(out.title).toBe('Guide Title')
    expect(out.sections).toEqual([{ heading: 'Part', body: 'content', cardType: undefined }])
  })

  it('parses plain markdown with # title and ## sections', () => {
    const out = parseChapterContent(
      '# Chapter One\n\nintro text\n\n## Section A\n\naaa\n\n## Section B\n\nbbb',
      4,
    )
    expect(out.title).toBe('Chapter One')
    expect(out.preamble).toBe('intro text')
    expect(out.sections.map((s) => s.heading)).toEqual(['Section A', 'Section B'])
  })

  it('falls back to Chapter N when markdown has no title', () => {
    const out = parseChapterContent('just a paragraph', 5)
    expect(out.title).toBe('Chapter 5')
  })

  it('strips image markdown from structured-payload section bodies', () => {
    const out = parseChapterContent(
      { sections: [{ title: 'S', content_markdown: '![alt](http://x/img.png) text' }] },
      1,
    )
    expect(out.sections[0].body).toBe('text')
  })

  it('preserves image markdown in plain-markdown sections (print CSS hides them)', () => {
    const out = parseChapterContent('## S\n\n![alt](http://x/img.png) text', 1)
    expect(out.sections[0].body).toContain('![alt]')
  })

  it('handles a null payload defensively', () => {
    const out = parseChapterContent(null, 1)
    expect(out.title).toBe('Chapter 1')
    expect(out.sections).toEqual([])
  })
})

// Normalizes a raw chapter payload (structured JSON, JSON-encoded string, or
// plain markdown) into { title, preamble, sections } for the print renderer.
export interface PrintSection {
  heading: string
  body: string
  cardType?: string
}

export interface ParsedChapter {
  title: string
  preamble: string
  sections: PrintSection[]
}

function sectionFrom(sec: any): PrintSection {
  return {
    heading: sec.title || '',
    body: (sec.content_markdown || '').replace(/!\[.*?\]\(.*?\)/g, '').trim(),
    cardType: sec.section_type,
  }
}

export function parseChapterContent(item: any, ch: number): ParsedChapter {
  if (typeof item === 'object' && item !== null && 'sections' in item) {
    return {
      title: item.title || `Chapter ${ch}`,
      preamble: '',
      sections: (item.sections || []).map(sectionFrom),
    }
  }

  let md = typeof item === 'string' ? item : String(item)
  let parsedObj: any = null
  try {
    parsedObj = JSON.parse(md)
  } catch {
    parsedObj = null
  }

  if (typeof parsedObj === 'object' && parsedObj !== null && 'sections' in parsedObj) {
    return {
      title: parsedObj.title || `Chapter ${ch}`,
      preamble: '',
      sections: (parsedObj.sections || []).map(sectionFrom),
    }
  }

  const cleanedText = md.replace(/!\[.*?\]\(.*?\)/g, '').replace(/\n{3,}/g, '\n\n').trim()
  const lines = cleanedText.split('\n')
  let title = `Chapter ${ch}`
  if (lines[0]?.startsWith('# ')) {
    title = lines[0].replace(/^# /, '').trim()
    md = lines.slice(1).join('\n').trim()
  }
  const parts = md.split(/^[ \t]*## /gm)
  return {
    title,
    preamble: parts[0]?.trim() || '',
    sections: parts.slice(1).map(p => {
      const [h, ...b] = p.split('\n')
      return { heading: h?.trim() || '', body: b.join('\n').trim() }
    }),
  }
}

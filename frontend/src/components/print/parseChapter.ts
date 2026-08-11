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

interface SectionRecord {
  title?: string
  content_markdown?: string
  section_type?: string
}

interface SectionsPayload {
  title?: string
  sections?: SectionRecord[]
}

function sectionFrom(sec: SectionRecord): PrintSection {
  return {
    heading: sec.title || '',
    body: (sec.content_markdown || '').replace(/!\[.*?\]\(.*?\)/g, '').trim(),
    cardType: sec.section_type,
  }
}

function parseSectionsPayload(payload: SectionsPayload, ch: number): ParsedChapter {
  return {
    title: payload.title || `Chapter ${ch}`,
    preamble: '',
    sections: (payload.sections || []).map(sectionFrom),
  }
}

function isSectionsPayload(value: unknown): value is SectionsPayload {
  return (
    typeof value === 'object' &&
    value !== null &&
    'sections' in value &&
    Array.isArray((value as SectionsPayload).sections)
  )
}

export function parseChapterContent(item: unknown, ch: number): ParsedChapter {
  if (typeof item === 'object' && item !== null) {
    // Guide chapters carry { markdown } — unwrap to plain markdown first.
    const raw = (item as { markdown?: unknown }).markdown
    if (typeof raw === 'string') return parseChapterContent(raw, ch)
    if (isSectionsPayload(item)) return parseSectionsPayload(item as SectionsPayload, ch)
  }

  const md = typeof item === 'string' ? item : String(item)
  let parsedObj: unknown = null
  try {
    parsedObj = JSON.parse(md)
  } catch {
    parsedObj = null
  }

  if (isSectionsPayload(parsedObj)) return parseSectionsPayload(parsedObj as SectionsPayload, ch)

  const cleanedText = md.replace(/!\[.*?\]\(.*?\)/g, '').replace(/\n{3,}/g, '\n\n').trim()
  const lines = cleanedText.split('\n')
  let title = `Chapter ${ch}`
  let body = md
  if (lines[0]?.startsWith('# ')) {
    title = lines[0].replace(/^# /, '').trim()
    body = lines.slice(1).join('\n').trim()
  }
  const parts = body.split(/^[ \t]*## /gm)
  return {
    title,
    preamble: parts[0]?.trim() || '',
    sections: parts.slice(1).map(p => {
      const [h, ...b] = p.split('\n')
      return { heading: h?.trim() || '', body: b.join('\n').trim() }
    }),
  }
}

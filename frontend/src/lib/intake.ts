import type { SourceType } from '../stores/useAppConfigStore'

/**
 * Intake detection for the one-box "Add a lecture" input: what a dropped file
 * or a pasted link is, and which API source_type carries it. The backend
 * re-checks everything (magic bytes, SSRF guard); this only drives the chip
 * and picks the source_type.
 */

export type IntakeKind =
  | 'video'
  | 'pdf'
  | 'docx'
  | 'pptx'
  | 'text'
  | 'youtube'
  | 'gdrive'
  | 'gdoc'
  | 'gslides'
  | 'web'

export interface Detected {
  kind: IntakeKind
  sourceType: SourceType
  label: string
  /** Video sources measure length from the media; documents count words. */
  isDocument: boolean
}

export const VIDEO_EXTENSIONS = ['.mp4', '.mov', '.mkv', '.avi', '.webm']
export const DOC_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.txt', '.md']
export const ACCEPT_ATTR = ['video/*', ...VIDEO_EXTENSIONS, ...DOC_EXTENSIONS].join(',')

const LABELS: Record<IntakeKind, string> = {
  video: 'Video file',
  pdf: 'PDF',
  docx: 'Word document',
  pptx: 'PowerPoint',
  text: 'Text file',
  youtube: 'YouTube video',
  gdrive: 'Google Drive file',
  gdoc: 'Google Doc',
  gslides: 'Google Slides',
  web: 'Web page or file link',
}

function make(kind: IntakeKind, sourceType: SourceType): Detected {
  const isDocument = !['video', 'youtube', 'gdrive'].includes(kind)
  return { kind, sourceType, label: LABELS[kind], isDocument }
}

function extOf(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

/** A chosen/dropped file, or null with a reason when it can't be accepted. */
export function detectFile(name: string, mime = ''): Detected | { error: string } {
  const ext = extOf(name)
  if (ext === '.pdf') return make('pdf', 'upload')
  if (ext === '.docx') return make('docx', 'upload')
  if (ext === '.pptx') return make('pptx', 'upload')
  if (ext === '.txt' || ext === '.md') return make('text', 'upload')
  if (VIDEO_EXTENSIONS.includes(ext)) return make('video', 'upload')
  if (ext === '.doc' || ext === '.ppt') {
    return { error: 'Old Office formats (.doc / .ppt) aren\'t supported. Save it as .docx or .pptx first.' }
  }
  if (mime.startsWith('video/')) {
    return { error: 'Rename the video to .mp4, .mov, .mkv, .avi or .webm and try again.' }
  }
  return { error: 'Upload a video (MP4, MOV, MKV, AVI, WebM) or a document (PDF, DOCX, PPTX, TXT, MD).' }
}

function hostOf(raw: string): { host: string; path: string } | null {
  try {
    const u = new URL(raw.trim())
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return null
    return { host: u.hostname.toLowerCase(), path: u.pathname }
  } catch {
    return null
  }
}

/** A pasted link. Returns null while the text isn't a full http(s) URL yet. */
export function detectLink(raw: string): Detected | null {
  const parsed = hostOf(raw)
  if (!parsed) return null
  const { host, path } = parsed
  if (host === 'youtu.be' || host === 'youtube.com' || host.endsWith('.youtube.com')) {
    return make('youtube', 'youtube')
  }
  if (host === 'docs.google.com') {
    if (path.startsWith('/document/d/')) return make('gdoc', 'gdrive')
    if (path.startsWith('/presentation/d/')) return make('gslides', 'gdrive')
    return make('gdrive', 'gdrive')
  }
  if (host === 'drive.google.com') return make('gdrive', 'gdrive')
  const ext = extOf(path)
  if (VIDEO_EXTENSIONS.includes(ext)) return { ...make('web', 'link'), label: 'Video file link', isDocument: false }
  if (ext === '.pdf') return { ...make('pdf', 'link'), label: 'PDF link' }
  return make('web', 'link')
}

/** Why a detected source can't be used on this install, or null when it can. */
export function disabledReason(d: Detected, enabled: readonly SourceType[]): string | null {
  if (enabled.includes(d.sourceType)) return null
  switch (d.sourceType) {
    case 'youtube':
      return "YouTube links aren't available here. Download the video and upload the file instead."
    case 'gdrive':
      return "Google Drive links aren't available here. Upload the file instead."
    case 'link':
      return "Web links aren't available here. Upload the file instead."
    default:
      return "File uploads aren't available here."
  }
}

/** The chip text: "PDF · 23 pages · uses 12 min". */
export function chipText(
  d: Detected,
  est?: { pages?: number | null; words?: number | null; minutes_needed?: number | null; doc_type?: string | null },
): string {
  const parts = [d.label]
  if (est?.pages) parts.push(`${est.pages} ${est.doc_type === 'pptx' ? 'slides' : 'pages'}`)
  else if (est?.words) parts.push(`${est.words.toLocaleString()} words`)
  if (est?.minutes_needed) parts.push(`uses ${est.minutes_needed} min`)
  return parts.join(' · ')
}

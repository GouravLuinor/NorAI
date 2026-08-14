export interface Reference {
  id: string
  title: string
  section: string
  sectionId: string
  type: 'note' | 'screenshot'
  thumbnail?: string
  chapterId?: number
  chunkId?: string | number
  startSec?: number | null
  endSec?: number | null
}

export interface RetrievedChunk {
  heading_path: string
  chapter_id: number
  heading?: string
  distance?: number
  relevant?: boolean
  context?: string
  chunk_id?: string
}

export interface RetrievedImage {
  path: string
  section: string
  distance?: number
}

export interface VerifiedCitation {
  section: string
  verified: boolean
  chunk_id?: string | null
  heading_path?: string | null
  heading?: string | null
  chapter_id?: number | null
}

export interface ChatResponse {
  answer: string
  assistant_message_id?: string
  retrieved_chunks: RetrievedChunk[]
  retrieved_images: RetrievedImage[]
  verified_citations?: VerifiedCitation[]
}

export interface ProcessEvent {
  stage?: string
  message?: string
  progress?: number
}

/** P6.4 — a user-owned course collection of lectures. */
export interface CourseSummary {
  course_id: string
  name: string
  description?: string | null
  lecture_count: number
  created_at?: string | null
}

export interface CourseLectureEntry {
  lecture_id: string
  title: string
  status: string
  source_type?: string | null
  duration_seconds?: number
  chapter_count?: number
  created_at?: string | null
}

export interface CourseDetail extends CourseSummary {
  lectures: CourseLectureEntry[]
}

/** P6.4 — unlisted share link for a lecture (owner-created). */
export interface ShareLinkInfo {
  slug: string
  url: string
  allow_tutor_chat: boolean
}

export interface ResolvedShare {
  lecture_id: string
  title: string
  status: string
  source_type?: string | null
  allow_tutor_chat: boolean
}

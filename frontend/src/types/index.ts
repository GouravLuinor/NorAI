export interface Reference {
  id: string
  title: string
  section: string
  sectionId: string
  type: 'note' | 'screenshot'
  thumbnail?: string
  chapterId?: number
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

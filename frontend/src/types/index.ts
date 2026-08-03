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
}

export interface RetrievedImage {
  path: string
  section: string
}

export interface ChatResponse {
  answer: string
  assistant_message_id?: string
  retrieved_chunks: RetrievedChunk[]
  retrieved_images: RetrievedImage[]
}

export interface ProcessEvent {
  stage?: string
  message?: string
  progress?: number
}

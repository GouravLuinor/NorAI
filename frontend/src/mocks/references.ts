export interface Reference {
  id: string
  title: string
  section: string
  sectionId: string       // the DOM id to scroll to
  type: 'note' | 'screenshot'
  thumbnail?: string
}

export const mockReferences: Reference[] = [
  { id: '1', title: 'Structure and Properties', section: 'Core Concepts', sectionId: 'sec-core-concept', type: 'note' },
  { id: '2', title: 'Efficiency gap', section: 'Key Concepts', sectionId: 'sec-efficiency-gap', type: 'note' },
  { id: '3', title: 'Layer composition diagram', section: '00:14', sectionId: 'sec-core-concept', type: 'screenshot', thumbnail: 'thumb1' },
]
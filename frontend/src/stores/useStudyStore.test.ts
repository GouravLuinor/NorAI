import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useStudyStore } from './useStudyStore'
import { apiGet } from '../lib/http'

vi.mock('../lib/http', () => ({
  apiGet: vi.fn(),
}))

const mockApiGet = vi.mocked(apiGet)

describe('useStudyStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useStudyStore.setState({ overview: null, loading: false, error: false })
  })

  it('loads study overview successfully', async () => {
    const mockData = {
      recent_lecture: {
        lecture_id: 'lec-1',
        title: 'Algorithms and Computation',
        chapter_count: 9,
        duration_seconds: 2734,
        is_demo: false,
        source_type: 'youtube',
      },
      flashcards_due: {
        total_due: 5,
        decks: [{ lecture_id: 'lec-1', lecture_title: 'Algorithms', chapter_id: 1, due_count: 5, total_cards: 10 }],
      },
      quiz_retakes: [
        {
          attempt_id: 'att-1',
          lecture_id: 'lec-1',
          lecture_title: 'Algorithms',
          chapter_id: 1,
          difficulty: 'Medium',
          score: 3,
          total: 5,
          missed_count: 2,
          finished_at: '2026-10-30T00:00:00Z',
        },
      ],
      stats: {
        total_user_lectures: 1,
        total_quizzes_finished: 1,
        total_cards_rated: 10,
      },
    }

    mockApiGet.mockResolvedValueOnce(mockData)

    await useStudyStore.getState().loadOverview()

    const state = useStudyStore.getState()
    expect(state.loading).toBe(false)
    expect(state.error).toBe(false)
    expect(state.overview?.recent_lecture?.title).toBe('Algorithms and Computation')
    expect(state.overview?.flashcards_due.total_due).toBe(5)
    expect(state.overview?.quiz_retakes.length).toBe(1)
  })

  it('handles load failure gracefully', async () => {
    mockApiGet.mockRejectedValueOnce(new Error('Network error'))

    await useStudyStore.getState().loadOverview()

    const state = useStudyStore.getState()
    expect(state.loading).toBe(false)
    expect(state.error).toBe(true)
    expect(state.overview).toBeNull()
  })
})

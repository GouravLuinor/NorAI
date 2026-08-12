import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchQuizQuestions } from './useQuizStore'

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })
}

describe('fetchQuizQuestions', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('normalizes question_id onto id and forwards params', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        questions: [
          { question_id: 5, question: 'A' },
          { id: 7, question: 'B' },
        ],
        incomplete: false,
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const out = await fetchQuizQuestions(1, 'lec', 'Easy')
    expect(out.map((q) => q.id)).toEqual([5, 7])
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/quiz/questions?')
    expect(url).toContain('chapter_id=1')
    expect(url).toContain('lecture_id=lec')
    expect(url).toContain('difficulty=Easy')
  })

  it('handles a bare array payload', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([{ question_id: 3, question: 'C' }])))
    const out = await fetchQuizQuestions()
    expect(out.map((q) => q.id)).toEqual([3])
  })

  it('uses q.id when question_id is absent', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([{ id: 11, question: 'D' }])))
    const out = await fetchQuizQuestions()
    expect(out.map((q) => q.id)).toEqual([11])
  })
})

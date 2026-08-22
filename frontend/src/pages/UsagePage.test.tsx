import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { UsagePage } from './UsagePage'

const apiGetMock = vi.fn()
const navigateMock = vi.fn()
const openAuthModalMock = vi.fn()

vi.mock('../lib/http', () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
}))

const authStateMock = vi.fn()
vi.mock('../stores/useAuthStore', () => ({
  useAuthStore: () => authStateMock(),
}))

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}))

const SAMPLE = {
  is_anonymous: false,
  period: 'month',
  is_estimated: true,
  totals: { api_calls: 42, input_tokens: 9000, output_tokens: 6000, cost_usd: 0.0056, minutes: 9 },
  by_stage: [
    { stage: 'extract', calls: 20, input_tokens: 8000, output_tokens: 5000, cost_usd: 0.0098 },
    { stage: 'embed', calls: 2, input_tokens: 400, output_tokens: 0, cost_usd: 0.00008 },
  ],
  by_day: [
    { date: '2026-08-12', calls: 30, cost_usd: 0.0102, input_tokens: 7000, output_tokens: 5000 },
    { date: '2026-08-13', calls: 12, cost_usd: 0.0021, input_tokens: 2000, output_tokens: 1000 },
  ],
  by_lecture: [{ lecture_id: 'lec_1', calls: 30, cost_usd: 0.011, input_tokens: 8000, output_tokens: 5000 }],
}

describe('UsagePage', () => {
  beforeEach(() => {
    apiGetMock.mockReset()
    navigateMock.mockReset()
    openAuthModalMock.mockReset()
    authStateMock.mockReset()
  })

  it('prompts anonymous users to log in', () => {
    authStateMock.mockReturnValue({ user: null, openAuthModal: openAuthModalMock })
    render(<UsagePage />)
    expect(screen.getByText('Sign in to see your usage')).toBeInTheDocument()
    expect(apiGetMock).not.toHaveBeenCalled()
  })

  it('renders summary cards, chart and stage breakdown', async () => {
    authStateMock.mockReturnValue({ user: { id: 'u1', email: 'a@b.com' }, openAuthModal: openAuthModalMock })
    apiGetMock.mockResolvedValue(SAMPLE)
    render(<UsagePage />)

    expect(await screen.findByText('Gemini API spend')).toBeInTheDocument()
    expect(screen.getByText('$0.0056')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('9')).toBeInTheDocument()
    expect(screen.getByText('Cost by day')).toBeInTheDocument()
    expect(screen.getByText('Chunk extraction')).toBeInTheDocument()
    expect(screen.getByText('Embeddings')).toBeInTheDocument()
    expect(screen.getByText('lec_1')).toBeInTheDocument()
  })

  it('handles fetch failure with an error state', async () => {
    authStateMock.mockReturnValue({ user: { id: 'u1', email: 'a@b.com' }, openAuthModal: openAuthModalMock })
    apiGetMock.mockRejectedValue(new Error('boom'))
    render(<UsagePage />)
    // P4.3: raw backend messages map to friendly copy (never dumps 'boom').
    expect(await screen.findByText('Something went wrong. Please try again.')).toBeInTheDocument()
  })
})

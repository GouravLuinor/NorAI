import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { VideoPlayer } from './VideoPlayer'
import { useVideoStore } from '../../stores/useVideoStore'
import { useLectureStore } from '../../stores/useLectureStore'
import { apiFetch } from '../../lib/http'

vi.mock('../../lib/http', () => ({
  apiFetch: vi.fn(),
}))

const apiFetchMock = vi.mocked(apiFetch)

function stubSource(info: Record<string, unknown>) {
  apiFetchMock.mockImplementation(async (path: string) =>
    path.startsWith('/lectures') ? info : { chapters: [], chunks: [] },
  )
}

beforeEach(() => {
  apiFetchMock.mockReset()
  useLectureStore.setState({ activeLectureId: 'lec-1' })
  useVideoStore.getState().reset()
})

describe('VideoPlayer', () => {
  it('renders nothing when no lecture is active', () => {
    useLectureStore.setState({ activeLectureId: null })
    const { container } = render(<VideoPlayer />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for an incomplete source', async () => {
    stubSource({ source_type: 'youtube', source_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', status: 'processing' })
    const { container } = render(<VideoPlayer />)
    await waitFor(() => expect(useVideoStore.getState().status).toBe('processing'))
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for non-YouTube sources', async () => {
    stubSource({ source_type: 'upload', source_url: null, status: 'completed' })
    const { container } = render(<VideoPlayer />)
    await waitFor(() => expect(useVideoStore.getState().status).toBe('completed'))
    expect(container).toBeEmptyDOMElement()
  })

  it('shows a floating button for completed YouTube sources and toggles the dock', async () => {
    stubSource({ source_type: 'youtube', source_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', status: 'completed' })
    const user = userEvent.setup()
    render(<VideoPlayer />)
    await waitFor(() => expect(screen.getByRole('button', { name: /watch video/i })).toBeInTheDocument())

    const button = screen.getByRole('button', { name: /watch video/i })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Lecture video')).not.toBeInTheDocument()

    await user.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Lecture video')).toBeInTheDocument()
    expect(screen.getByLabelText('Close video')).toBeInTheDocument()

    await user.click(screen.getByLabelText('Close video'))
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Lecture video')).not.toBeInTheDocument()
  })

  it('reopens the dock when a seek is requested', async () => {
    stubSource({ source_type: 'youtube', source_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', status: 'completed' })
    render(<VideoPlayer />)
    await waitFor(() => expect(screen.getByRole('button', { name: /watch video/i })).toBeInTheDocument())
    expect(useVideoStore.getState().open).toBe(false)

    useVideoStore.getState().requestSeek(120)
    expect(useVideoStore.getState().open).toBe(true)
    await waitFor(() => expect(screen.getByText('Lecture video')).toBeInTheDocument())
  })
})

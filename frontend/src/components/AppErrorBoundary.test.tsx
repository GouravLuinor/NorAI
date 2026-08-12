import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AppErrorBoundary } from './AppErrorBoundary'

function Bomb(): never {
  throw new Error('boom')
}

describe('AppErrorBoundary', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders children when nothing throws', () => {
    render(
      <AppErrorBoundary>
        <div>healthy</div>
      </AppErrorBoundary>,
    )
    expect(screen.getByText('healthy')).toBeInTheDocument()
  })

  it('shows the recovery panel on a child render error', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <AppErrorBoundary>
        <Bomb />
      </AppErrorBoundary>,
    )
    expect(screen.getByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument()
    expect(screen.getByText('boom')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  })
})

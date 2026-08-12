import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Markdown } from './Markdown'

describe('Markdown', () => {
  it('renders headings and inline formatting', () => {
    render(<Markdown>{'# Title\n\nSome **bold** text'}</Markdown>)
    expect(screen.getByRole('heading', { name: 'Title' })).toBeInTheDocument()
    expect(screen.getByText('bold').tagName).toBe('STRONG')
  })

  it('renders GFM tables', () => {
    render(<Markdown>{'| A | B |\n|---|---|\n| 1 | 2 |'}</Markdown>)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('renders inline math via KaTeX', () => {
    const { container } = render(<Markdown>{'$E = mc^2$'}</Markdown>)
    expect(container.textContent).toContain('E = mc')
  })
})

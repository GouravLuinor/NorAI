import { describe, expect, it } from 'vitest'
import { escapeCurrency } from './escapeCurrency'

describe('escapeCurrency', () => {
  it('escapes dollar amounts that would pair up as math', () => {
    expect(escapeCurrency('for $3, you value it more than the $3 you gave up')).toBe(
      'for \\$3, you value it more than the \\$3 you gave up',
    )
    expect(escapeCurrency('costs $5 to $10 each')).toBe('costs \\$5 to \\$10 each')
  })

  it('keeps real inline and display math', () => {
    expect(escapeCurrency('so $x^2 + 1$ holds')).toBe('so $x^2 + 1$ holds')
    expect(escapeCurrency('area is $\\pi r^2$ and $2x$')).toBe('area is $\\pi r^2$ and $2x$')
    expect(escapeCurrency('$$\n\\frac{a}{b}\n$$')).toBe('$$\n\\frac{a}{b}\n$$')
  })

  it('keeps math next to a price in the same line', () => {
    expect(escapeCurrency('price $4 and $y$ here')).toBe('price \\$4 and $y$ here')
  })

  it('leaves code and already-escaped dollars alone', () => {
    expect(escapeCurrency('use `$5 and $6` literally')).toBe('use `$5 and $6` literally')
    expect(escapeCurrency('```\n$5 and $6\n```')).toBe('```\n$5 and $6\n```')
    expect(escapeCurrency('already \\$3 and \\$4')).toBe('already \\$3 and \\$4')
  })

  it('escapes a lone dollar sign', () => {
    expect(escapeCurrency('only $ here')).toBe('only \\$ here')
  })
})

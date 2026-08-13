import { describe, expect, it } from 'vitest'
import { formatTimestamp, extractYoutubeVideoId } from './video'

describe('formatTimestamp', () => {
  it('formats seconds as m:ss', () => {
    expect(formatTimestamp(0)).toBe('0:00')
    expect(formatTimestamp(75)).toBe('1:15')
    expect(formatTimestamp(3599)).toBe('59:59')
  })

  it('formats hours as h:mm:ss', () => {
    expect(formatTimestamp(3600)).toBe('1:00:00')
    expect(formatTimestamp(7325)).toBe('2:02:05')
  })

  it('floors fractional seconds', () => {
    expect(formatTimestamp(61.9)).toBe('1:01')
  })

  it('returns empty for null / NaN / negative', () => {
    expect(formatTimestamp(null)).toBe('')
    expect(formatTimestamp(undefined)).toBe('')
    expect(formatTimestamp(Number.NaN)).toBe('')
    expect(formatTimestamp(-5)).toBe('')
  })
})

describe('extractYoutubeVideoId', () => {
  const ID = 'dQw4w9WgXcQ'

  it('parses watch URLs', () => {
    expect(extractYoutubeVideoId(`https://www.youtube.com/watch?v=${ID}`)).toBe(ID)
  })

  it('parses youtu.be short links', () => {
    expect(extractYoutubeVideoId(`https://youtu.be/${ID}`)).toBe(ID)
  })

  it('parses embed / shorts / live paths', () => {
    expect(extractYoutubeVideoId(`https://www.youtube.com/embed/${ID}`)).toBe(ID)
    expect(extractYoutubeVideoId(`https://www.youtube.com/shorts/${ID}`)).toBe(ID)
    expect(extractYoutubeVideoId(`https://www.youtube.com/live/${ID}`)).toBe(ID)
  })

  it('returns null for non-YouTube URLs and garbage', () => {
    expect(extractYoutubeVideoId('https://example.com/watch?v=abc')).toBeNull()
    expect(extractYoutubeVideoId('not-a-url')).toBeNull()
    expect(extractYoutubeVideoId(null)).toBeNull()
    expect(extractYoutubeVideoId('')).toBeNull()
  })
})

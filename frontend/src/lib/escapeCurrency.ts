/**
 * Lecture text mixes dollar amounts ("$3 you gave up") with LaTeX ($x^2$), and
 * remark-math treats any pair of `$` as math, so "$3 ... $3" turned into one
 * run-together italic formula. This applies Pandoc's rule before parsing: an
 * opening `$` must be followed by a non-space, and a closing `$` must follow a
 * non-space and must NOT be followed by a digit. A `$` that never finds a
 * closer is a currency sign and gets escaped. Code (fenced and inline) and
 * `$$` display math are left alone.
 */
export function escapeCurrency(md: string): string {
  if (!md.includes('$')) return md
  let inFence = false
  let inDisplay = false
  return md
    .split('\n')
    .map((line) => {
      if (/^\s*(```|~~~)/.test(line)) {
        inFence = !inFence
        return line
      }
      if (inFence) return line
      if (/^\s*\$\$/.test(line)) {
        // A line that opens and closes display math on its own ($$ ... $$) leaves state alone.
        const count = (line.match(/\$\$/g) ?? []).length
        if (count % 2 === 1) inDisplay = !inDisplay
        return line
      }
      if (inDisplay) return line
      // Inline code spans sit at odd indexes when split on backticks.
      return line
        .split('`')
        .map((seg, i) => (i % 2 === 1 ? seg : escapeSegment(seg)))
        .join('`')
    })
    .join('\n')
}

function escapeSegment(s: string): string {
  if (!s.includes('$')) return s
  const out: string[] = []
  let i = 0
  while (i < s.length) {
    const ch = s[i]
    if (ch === '\\') {
      out.push(ch, s[i + 1] ?? '')
      i += 2
      continue
    }
    if (ch !== '$') {
      out.push(ch)
      i++
      continue
    }
    // `$$` inline display math: copy through its closer untouched.
    if (s[i + 1] === '$') {
      const end = s.indexOf('$$', i + 2)
      const stop = end === -1 ? s.length : end + 2
      out.push(s.slice(i, stop))
      i = stop
      continue
    }
    const closer = opensMath(s, i) ? findCloser(s, i + 1) : -1
    if (closer === -1) {
      out.push('\\$')
      i++
    } else {
      out.push(s.slice(i, closer + 1))
      i = closer + 1
    }
  }
  return out.join('')
}

const isSpace = (c: string | undefined) => c === undefined || /\s/.test(c)

function opensMath(s: string, i: number): boolean {
  return !isSpace(s[i + 1])
}

function findCloser(s: string, from: number): number {
  for (let j = from; j < s.length; j++) {
    if (s[j] === '\\') {
      j++
      continue
    }
    if (s[j] !== '$') continue
    const next = s[j + 1]
    if (!isSpace(s[j - 1]) && !(next !== undefined && next >= '0' && next <= '9')) return j
    // Another `$` that could open math before any closer: the first was a price.
    if (isSpace(s[j - 1]) && !isSpace(next)) return -1
  }
  return -1
}
